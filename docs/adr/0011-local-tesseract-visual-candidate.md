# ADR-0011: 첫 visual OCR candidate로 Tesseract CLI 채택

- 상태: 채택
- 날짜: 2026-06-16
- 결정자: Codex 추천 -> 사용자 "그래 가자" 승인

## 배경

ADR-0009로 deterministic no-model visual baseline을 만들었다. 채택 당시 60-record
baseline은 `precision=0.15`, `recall=0.81818182`, `f1=0.25352113`이었다. 다음 단계는
실제 OCR/VLM candidate extractor를 추가해 reviewer gold set과 같은 evaluator로
비교하는 것이다.

이번 결정은 full VLM 채택이 아니다. 목적은 비용 없는 local OCR/layout candidate를
먼저 붙여, queue prior만 쓰는 baseline보다 unsupported visual claim을 줄일 수 있는지
검증하는 것이다.

## 선택 기준

| 기준 | 가중치 | 근거 |
|------|--------|------|
| credential-free 실행 | 높음 | offline/visual 실험은 API key와 비용 없이 재현 가능해야 함 |
| 한국어 지원 | 높음 | RFP 원문과 visual page text가 한국어 중심 |
| 기존 PDF render artifact 재사용 | 높음 | `artifacts/parsed_docs/pdf/*.pdf`와 `pdftoppm` 흐름을 유지 |
| dependency blast radius | 높음 | OCR 후보 하나 때문에 heavy ML stack을 바로 core dependency로 넣지 않음 |
| evaluator 연결성 | 높음 | `run_visual_gold_eval`의 `(record_id, fact_type, field)` 계약을 그대로 사용 |
| 이후 확장성 | 중 | PaddleOCR/EasyOCR/Docling/VLM과 같은 candidate lane으로 비교 가능해야 함 |

## 후보 비교

검증일: 2026-06-16. 공식 문서/저장소와 로컬 실행성 기준이다.

| 기준 | Tesseract CLI | PaddleOCR | EasyOCR | Docling |
|------|------|------|------|------|
| credential-free | 가능. 로컬 CLI | 가능. 로컬 모델 다운로드 필요 | 가능. 로컬 모델 다운로드 필요 | 가능. 로컬 실행 지원 |
| 한국어 지원 | `kor`, `kor_vert` traineddata 지원 | PP-OCRv5 multilingual recognition이 Korean 포함 | supported languages에 Korean `ko` 포함 | OCR/PDF understanding 지원. 한국어 품질은 별도 검증 필요 |
| dependency blast radius | 낮음. 이미 로컬 CLI와 language pack 설치됨 | 높음. Paddle/PaddleOCR stack 도입 | 중~높음. PyTorch/EasyOCR stack 도입 | 높음. document conversion stack 도입 |
| 기존 render artifact 재사용 | 좋음. `pdftoppm` PPM stream -> `tesseract stdin` | 가능하나 image pipeline/model config 필요 | 가능하나 image pipeline/model download 필요 | 자체 conversion pipeline이 강해 기존 lane과 중복 가능 |
| evaluator 연결성 | 좋음. OCR text keyword rule로 candidate facts 생성 | 좋음 | 좋음 | 중간. 구조 rich output을 fact schema에 매핑해야 함 |
| 첫 실험 적합성 | 가장 작음 | 두 번째 후보로 적합 | 빠른 비교 후보로 가능 | 별도 document parsing bakeoff에 가까움 |

## 결정

**Tesseract CLI를 첫 visual OCR candidate로 채택한다.**

구현은 새 Python OCR dependency를 추가하지 않는다. `pdftoppm`으로 target page를 PPM으로
렌더링하고, 로컬 Tesseract에는 파일 경로가 아니라 `stdin`으로 PPM bytes를 전달한다.
로컬 검증에서 `/opt/homebrew/bin/tesseract 5.5.2`는 PNG/PPM 경로 입력에서 Leptonica
파일 열기 오류가 났지만, `tesseract stdin stdout -l kor+eng --psm 11`은 같은 PPM bytes를
정상 OCR했다.

구현은 같은 PDF page에 여러 visual record가 있는 경우 page-level OCR cache를 사용한다.
초기 채택 당시 gold 비교 대상은 60 records였고 unique rendered page는 30개였다.

Candidate fact policy:

- `system_architecture_diagram` + architecture keywords -> `visual_type_present`,
  field `system_architecture`
- `gantt_schedule` + schedule keywords -> `visual_type_present`, field `schedule`
- `organization_chart` + organization keywords -> `business_field_affected`,
  field `requirements`
- `requirements_table` + requirements keywords -> `business_field_affected`,
  field `requirements`
- OCR text가 비거나 visual type별 keyword가 없으면 candidate를 내지 않는다.

이 후보는 recall 최대화를 목표로 하지 않는다. 목적은 no-model baseline 대비
`negative_violation_count`와 `unknown_candidate_count`를 줄이는 precision 중심 비교군이다.

초기 실행 결과 (`--dpi 120 --timeout-seconds 15`):

| metric | local record baseline | Tesseract OCR candidate |
|---|---:|---:|
| candidate_fact_count | `60` | `43` |
| true_positive_count | `9` | `10` |
| false_positive_count | `51` | `33` |
| false_negative_count | `2` | `1` |
| negative_violation_count | `32` | `16` |
| unknown_candidate_count | `19` | `17` |
| precision | `0.15` | `0.23255814` |
| recall | `0.81818182` | `0.90909091` |
| f1 | `0.25352113` | `0.37037037` |

Tesseract 후보는 baseline보다 모든 핵심 eval 지표를 개선했다. 다만 precision은 아직
낮다. 특히 system architecture keyword가 너무 넓어 rejected page에서도 candidate를
내는 경우가 남아 있다.

Precision hardening 이후 실행 결과 (`--dpi 120 --timeout-seconds 15`):

| metric | local record baseline | Tesseract OCR candidate |
|---|---:|---:|
| candidate_fact_count | `60` | `13` |
| true_positive_count | `9` | `10` |
| false_positive_count | `51` | `3` |
| false_negative_count | `2` | `1` |
| negative_violation_count | `32` | `2` |
| unknown_candidate_count | `19` | `1` |
| precision | `0.15` | `0.76923077` |
| recall | `0.81818182` | `0.90909091` |
| f1 | `0.25352113` | `0.83333333` |

Hardening 규칙은 extractor `visual_tesseract_ocr_candidate_v2`로 기록한다. schedule
3-keyword 이상, organization chart의 `조직`/`수행체계` 필수, system architecture의
high-signal keyword 또는 단독 `연계`, requirements table candidate 보류로 구성된다. 이
결과는 같은 작은 reviewer gold set에 맞춘 후보 lane 성능이므로, production visual
extraction 품질로 직접 일반화하지 않는다.

확장 gold 후속 실행 결과: 같은 날 `needs_page_review` 50 records를 page-review해 gold
set을 110 records로 확장하고, baseline과 Tesseract 모두
`--review-status reviewed_needs_extraction --review-status needs_page_review` 범위로
재평가했다.

| metric | local record baseline | Tesseract OCR candidate |
|---|---:|---:|
| candidate_fact_count | `110` | `20` |
| true_positive_count | `19` | `14` |
| false_positive_count | `91` | `6` |
| false_negative_count | `6` | `11` |
| negative_violation_count | `52` | `3` |
| unknown_candidate_count | `39` | `3` |
| precision | `0.17272727` | `0.7` |
| recall | `0.76` | `0.56` |
| f1 | `0.28148148` | `0.62222222` |

해석: 확장 gold에서도 Tesseract는 local baseline 대비 precision, F1, negative violation을
명확히 개선한다. 다만 recall은 `0.76`에서 `0.56`으로 낮아졌다. 따라서 현재
Tesseract lane은 production visual extractor가 아니라 precision-hardened local OCR
candidate이며, 다음 후보는 recall recovery를 명시 목표로 삼아야 한다.

## 탈락 사유

- PaddleOCR: 한국어/다국어 인식 근거는 좋지만 첫 candidate로는 dependency와 model
  download 범위가 크다. Tesseract 결과가 낮거나 실패 유형이 명확해진 뒤 두 번째 후보로
  비교한다.
- EasyOCR: Korean 지원과 간단한 API가 장점이지만 PyTorch stack을 도입한다. 지금은 CLI
  기반 Tesseract로 더 작은 실험이 가능하다.
- Docling: PDF understanding, OCR, VLM 지원이 넓지만 기존 source parser lane과 역할이
  겹친다. visual fact candidate 하나를 만드는 첫 실험으로는 과하다.

## 재검토 조건

- Tesseract candidate가 local baseline 대비 F1 또는 negative violation을 개선하지 못할 때
- Tesseract OCR text가 대부분 비어 있어 candidate coverage가 의미 없을 때
- PaddleOCR/EasyOCR가 같은 gold evaluator에서 명확히 더 높은 precision/recall을 보일 때
- Docling이 기존 parser/render bakeoff를 대체할 수준의 구조화 성능을 보일 때
- hosted VLM 비용 lane을 사용자가 명시 승인할 때

## 출처

- https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html
- https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md
- https://www.jaided.ai/easyocr/
- https://docling-project.github.io/docling/
- https://github.com/docling-project/docling
- `artifacts/visual_tesseract_candidate_expanded/summary.json`
- `artifacts/visual_tesseract_candidate_expanded_eval/summary.json`
- `artifacts/visual_local_baseline_expanded_eval/summary.json`
