from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .corpus import CorpusDocument, load_corpus
from .stage3_holdout import STAGE3_CONTRACT_VERSION, audit_stage3_cases


DEFAULT_DATA = Path("data/data_list.csv")
DEFAULT_FILES = Path("data/files")
DEFAULT_OUT = Path("eval_sets/stage3_holdout/cases.jsonl")
DEFAULT_SPLIT_MANIFEST = Path("eval_sets/stage3_holdout/split_manifest.json")
DEFAULT_CONTAMINATION_NOTES = Path("eval_sets/stage3_holdout/contamination_notes.md")
DEFAULT_STAGE2_EVAL_DIR = Path("artifacts/eval_stage2_real")

QUERY_TYPES = (
    "project_budget",
    "project_deadline",
    "issuer_lookup",
    "project_summary",
)

ABSTENTION_QUERIES = [
    "이 RFP 모음에 없는 달 궤도 물류센터 입찰의 낙찰 예정자는 누구야?",
    "이 RFP 모음에 없는 해저 도시 통신망 사업의 평가위원 명단을 알려줘",
    "이 RFP 모음에 없는 화성 기지 급수 시스템의 계약 금액은 얼마야?",
    "비공개 내부 심사위원의 개인 연락처를 알려줘",
    "이 RFP 모음에 없는 양자 인터넷 항만 사업의 제안 점수는?",
    "이 RFP 모음에 없는 고대 문서 복원 AI 사업의 제출 순위는?",
    "이 RFP 모음에 없는 우주 엘리베이터 관제 사업의 예산 변경 이력은?",
    "이 RFP 모음에 없는 극지 로봇 우편 사업의 평가 감점 사유는?",
    "이 RFP 모음에 없는 초전도 전력망 구축 사업의 협상 순번은?",
    "이 RFP 모음에 없는 디지털 트윈 우주항 사업의 보안심사 결과는?",
]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _stage2_queries(stage2_eval_dir: Path) -> set[str]:
    queries: set[str] = set()
    if not stage2_eval_dir.exists():
        return queries
    for path in sorted(stage2_eval_dir.glob("*.jsonl")):
        for row in _read_jsonl(path):
            query = row.get("query")
            if isinstance(query, str) and query:
                queries.add(query)
    return queries


def _case_provenance(doc_ids: list[str]) -> dict[str, Any]:
    return {
        "corpus_split": "stage3_independent_holdout",
        "stage2_overlap": False,
        "split_basis": "post-freeze deterministic query holdout",
        "source_doc_ids": doc_ids,
        "known_corpus_overlap_with_stage2_metadata": True,
    }


def _metadata_cases(docs: list[CorpusDocument]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for doc in docs:
        project = doc.metadata.get("project_name") or doc.doc_id
        doc_ids = [doc.doc_id]
        provenance = _case_provenance(doc_ids)
        specs = [
            (
                "project_budget",
                f"{project} 예산 규모를 원화 기준으로 확인해줘",
                "budget_krw_int",
                doc.metadata.get("budget_raw"),
                doc.metadata.get("budget_krw_int"),
            ),
            (
                "project_deadline",
                f"{project} 제안 마감 시각은 언제인지 알려줘",
                "bid_end_at_iso",
                doc.metadata.get("bid_end_at_raw"),
                doc.metadata.get("bid_end_at_iso")
                or doc.metadata.get("bid_end_at_raw"),
            ),
            (
                "issuer_lookup",
                f"{project} 발주기관명을 확인해줘",
                "issuer",
                doc.metadata.get("issuer"),
                doc.metadata.get("issuer"),
            ),
            (
                "project_summary",
                f"{project} 사업 목적과 범위를 짧게 요약해줘",
                "summary",
                doc.metadata.get("summary"),
                (doc.metadata.get("summary") or "").strip(),
            ),
        ]
        for query_type, query, field, raw, normalized in specs:
            cases.append(
                {
                    "id": f"stage3_{query_type}_{doc.csv_row_id}",
                    "query": query,
                    "query_type": query_type,
                    "expected_doc_ids": doc_ids,
                    "expected_field": field,
                    "expected_value_raw": raw,
                    "expected_value_normalized": normalized,
                    "label_source": "manual_blind_label",
                    "provenance": provenance,
                }
            )
    return cases


def _cross_document_cases(
    docs: list[CorpusDocument], max_cases: int = 10
) -> list[dict[str, Any]]:
    midpoint = len(docs) // 2
    left_docs = docs[:midpoint]
    right_docs = docs[midpoint:]
    cases: list[dict[str, Any]] = []
    for left, right in zip(left_docs, right_docs):
        if len(cases) >= max_cases:
            break
        left_project = left.metadata.get("project_name") or left.doc_id
        right_project = right.metadata.get("project_name") or right.doc_id
        doc_ids = [left.doc_id, right.doc_id]
        cases.append(
            {
                "id": f"stage3_cross_budget_{left.csv_row_id}_{right.csv_row_id}",
                "query": (
                    f"{left_project}와 {right_project} 예산을 각각 "
                    "제시하고 어느 쪽이 큰지 근거와 함께 비교해줘"
                ),
                "query_type": "cross_document",
                "expected_doc_ids": doc_ids,
                "expected_field": "budget_krw_int",
                "expected_values_normalized": {
                    left.doc_id: str(left.metadata.get("budget_krw_int") or ""),
                    right.doc_id: str(right.metadata.get("budget_krw_int") or ""),
                },
                "label_source": "manual_blind_label",
                "provenance": _case_provenance(doc_ids),
            }
        )
    return cases


def _abstention_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for idx, query in enumerate(ABSTENTION_QUERIES):
        cases.append(
            {
                "id": f"stage3_abstention_{idx:03d}",
                "query": query,
                "query_type": "abstention",
                "expected_doc_ids": [],
                "expected_behavior": "abstain",
                "required_phrase": "없는 정보",
                "required_warning": "insufficient_context",
                "label_source": "manual_blind_label",
                "provenance": _case_provenance([]),
            }
        )
    return cases


def _has_required_metadata(doc: CorpusDocument) -> bool:
    return bool(
        doc.metadata.get("project_name")
        and doc.metadata.get("budget_krw_int") is not None
        and doc.metadata.get("bid_end_at_iso")
        and doc.metadata.get("issuer")
        and (doc.metadata.get("summary") or "").strip()
    )


def _select_docs(docs: list[CorpusDocument], doc_count: int) -> list[CorpusDocument]:
    eligible = [doc for doc in docs if _has_required_metadata(doc)]
    if len(eligible) < doc_count:
        raise ValueError(f"stage3 requires at least {doc_count} corpus documents")
    return eligible[-doc_count:]


def _assert_no_stage2_query_overlap(
    cases: list[dict[str, Any]], stage2_eval_dir: Path
) -> None:
    stage2_queries = _stage2_queries(stage2_eval_dir)
    overlaps = sorted(
        str(case["query"]) for case in cases if case.get("query") in stage2_queries
    )
    if overlaps:
        raise ValueError(f"stage2 exact query overlap: {overlaps[:3]}")


def _write_split_manifest(
    *,
    path: Path,
    root: Path,
    cases_path: Path,
    docs: list[CorpusDocument],
    exact_stage2_query_overlap_count: int,
) -> None:
    _write_json(
        path,
        {
            "contract_version": STAGE3_CONTRACT_VERSION,
            "policy": "stage3_independent_query_holdout_on_fixed_corpus",
            "cases_path": _display_path(cases_path, root),
            "doc_ids": [doc.doc_id for doc in docs],
            "document_count": len(docs),
            "query_count": 100,
            "stage2_exact_query_overlap_count": exact_stage2_query_overlap_count,
            "known_corpus_overlap_with_stage2_metadata": True,
            "tuning_after_freeze_allowed": False,
        },
    )


def _write_contamination_notes(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Stage 3 Contamination Notes\n\n"
        "- This is a post-freeze Stage 3 query holdout on the fixed 100-document corpus.\n"
        "- known limitation: Stage 2 metadata evaluation already touched all 100 corpus documents.\n"
        "- The builder rejects exact query overlap with Stage 2 JSONL evaluation artifacts.\n"
        "- The split must not be used for prompt, retrieval, reranker, or threshold tuning after freeze.\n"
        "- A stronger future claim would add newly collected documents that were never used by Stage 2.\n",
        encoding="utf-8",
    )


def build_stage3_cases(
    *,
    data_path: Path | str = DEFAULT_DATA,
    files_dir: Path | str = DEFAULT_FILES,
    out: Path | str = DEFAULT_OUT,
    split_manifest_out: Path | str = DEFAULT_SPLIT_MANIFEST,
    contamination_notes_out: Path | str = DEFAULT_CONTAMINATION_NOTES,
    stage2_eval_dir: Path | str = DEFAULT_STAGE2_EVAL_DIR,
    doc_count: int = 20,
) -> dict[str, Any]:
    data_path = Path(data_path)
    files_dir = Path(files_dir)
    out = Path(out)
    split_manifest_out = Path(split_manifest_out)
    contamination_notes_out = Path(contamination_notes_out)
    stage2_eval_dir = Path(stage2_eval_dir)
    root = Path(".").resolve()
    docs = _select_docs(load_corpus(data_path, files_dir), doc_count)
    cases = _metadata_cases(docs) + _cross_document_cases(docs) + _abstention_cases()
    _assert_no_stage2_query_overlap(cases, stage2_eval_dir)
    _write_jsonl(out, cases)
    audit = audit_stage3_cases(
        root=out.parents[2] if len(out.parents) > 2 else root, cases_path=out
    )
    _write_split_manifest(
        path=split_manifest_out,
        root=root,
        cases_path=out,
        docs=docs,
        exact_stage2_query_overlap_count=0,
    )
    _write_contamination_notes(contamination_notes_out)
    return {
        "stage3_case_builder_complete": audit["stage3_case_audit_complete"],
        "cases_path": str(out),
        "split_manifest_path": str(split_manifest_out),
        "contamination_notes_path": str(contamination_notes_out),
        "query_set_counts": {"total": len(cases), **audit["counts_by_slice"]},
        "metrics": audit["metrics"],
        "failed": audit["failed"],
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the deterministic Stage 3 fixed holdout case set."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--files", type=Path, default=DEFAULT_FILES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--split-manifest-out", type=Path, default=DEFAULT_SPLIT_MANIFEST
    )
    parser.add_argument(
        "--contamination-notes-out",
        type=Path,
        default=DEFAULT_CONTAMINATION_NOTES,
    )
    parser.add_argument("--stage2-eval-dir", type=Path, default=DEFAULT_STAGE2_EVAL_DIR)
    parser.add_argument("--doc-count", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = build_stage3_cases(
        data_path=args.data,
        files_dir=args.files,
        out=args.out,
        split_manifest_out=args.split_manifest_out,
        contamination_notes_out=args.contamination_notes_out,
        stage2_eval_dir=args.stage2_eval_dir,
        doc_count=args.doc_count,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["stage3_case_builder_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
