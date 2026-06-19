from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from rfp_rag.stage3_case_builder import build_stage3_cases
from rfp_rag.stage3_holdout import audit_stage3_cases


def _write_csv(path: Path, rows: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "공고 번호",
        "공고 차수",
        "사업명",
        "사업 금액",
        "발주 기관",
        "공개 일자",
        "입찰 참여 시작일",
        "입찰 참여 마감일",
        "사업 요약",
        "파일형식",
        "파일명",
        "텍스트",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for idx in range(rows):
            writer.writerow(
                {
                    "공고 번호": f"notice-{idx:03d}",
                    "공고 차수": "0",
                    "사업명": f"Stage3 테스트 사업 {idx:03d}",
                    "사업 금액": str(100_000_000 + idx),
                    "발주 기관": f"테스트기관 {idx:03d}",
                    "공개 일자": "2026-01-01 00:00:00",
                    "입찰 참여 시작일": "2026-01-02 00:00:00",
                    "입찰 참여 마감일": "2026-01-10 10:00:00",
                    "사업 요약": f"Stage3 테스트 사업 {idx:03d} 요약",
                    "파일형식": "hwp",
                    "파일명": f"stage3-{idx:03d}.hwp",
                    "텍스트": "",
                }
            )


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_build_stage3_cases_writes_fixed_holdout_candidate(tmp_path: Path) -> None:
    data_path = tmp_path / "data/data_list.csv"
    cases_path = tmp_path / "eval_sets/stage3_holdout/cases.jsonl"
    manifest_path = tmp_path / "eval_sets/stage3_holdout/split_manifest.json"
    contamination_path = tmp_path / "eval_sets/stage3_holdout/contamination_notes.md"
    _write_csv(data_path)

    summary = build_stage3_cases(
        data_path=data_path,
        files_dir=tmp_path / "data/files",
        out=cases_path,
        split_manifest_out=manifest_path,
        contamination_notes_out=contamination_path,
        stage2_eval_dir=tmp_path / "artifacts/eval_stage2_real",
    )

    rows = _read_jsonl(cases_path)
    audit = audit_stage3_cases(root=tmp_path, cases_path=cases_path)
    assert summary["stage3_case_builder_complete"] is True
    assert len(rows) == 100
    assert audit["stage3_case_audit_complete"] is True
    assert audit["metrics"] == {"document_count": 20, "query_count": 100}
    assert audit["counts_by_slice"]["abstention"] == 10
    assert all(row["provenance"]["stage2_overlap"] is False for row in rows)
    assert all(row["label_source"] == "manual_blind_label" for row in rows)
    assert manifest_path.is_file()
    assert "known limitation" in contamination_path.read_text(encoding="utf-8")


def test_build_stage3_cases_rejects_exact_stage2_query_overlap(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "data/data_list.csv"
    stage2_dir = tmp_path / "artifacts/eval_stage2_real"
    stage2_dir.mkdir(parents=True)
    _write_csv(data_path)
    (stage2_dir / "golden_metadata.jsonl").write_text(
        json.dumps(
            {
                "query": (
                    "Stage 3 검증: Stage3 테스트 사업 000 예산 규모를 "
                    "원화 기준으로 확인해줘"
                )
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="stage2 exact query overlap"):
        build_stage3_cases(
            data_path=data_path,
            files_dir=tmp_path / "data/files",
            out=tmp_path / "eval_sets/stage3_holdout/cases.jsonl",
            stage2_eval_dir=stage2_dir,
        )
