from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDNAMES = [
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


def write_synthetic_corpus(
    *, root: Path = Path("."), doc_count: int = 100
) -> dict[str, Any]:
    root = root.resolve()
    data_dir = root / "data"
    files_dir = data_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "data_list.csv"

    hwp_count = 0
    pdf_count = 0
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for idx in range(doc_count):
            suffix = "pdf" if idx >= max(doc_count - 4, 0) else "hwp"
            if suffix == "pdf":
                pdf_count += 1
            else:
                hwp_count += 1
            filename = f"ci_fixture_{idx:03d}.{suffix}"
            project = (
                "한영대학교 특성화 맞춤형 교육환경 구축 - 트랙운영 학사정보시스템 고도화"
                if idx == 0
                else f"CI 합성 RFP 사업 {idx:03d}"
            )
            issuer = "한영대학" if idx == 0 else f"CI 발주기관 {idx:03d}"
            text = (
                f"{project} 제안요청서 본문. 발주기관은 {issuer}. "
                "평가 기준은 기술능력평가와 가격평가로 구성한다."
            )
            writer.writerow(
                {
                    "공고 번호": f"2026{idx:06d}",
                    "공고 차수": "0",
                    "사업명": project,
                    "사업 금액": str(100_000_000 + idx),
                    "발주 기관": issuer,
                    "공개 일자": "2026-06-17 09:00:00",
                    "입찰 참여 시작일": "2026-06-18 09:00:00",
                    "입찰 참여 마감일": "2026-06-30 17:00:00",
                    "사업 요약": f"{project} 요약",
                    "파일형식": suffix,
                    "파일명": filename,
                    "텍스트": text,
                }
            )
            (files_dir / filename).write_text(text, encoding="utf-8")

    return {
        "synthetic_corpus_complete": True,
        "doc_count": doc_count,
        "hwp_count": hwp_count,
        "pdf_count": pdf_count,
        "data_path": str(csv_path.relative_to(root)),
        "files_path": str(files_dir.relative_to(root)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create the credential-free synthetic corpus used by CI and fresh-clone smoke."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--doc-count", type=int, default=100)
    args = parser.parse_args(argv)

    summary = write_synthetic_corpus(root=args.root, doc_count=args.doc_count)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["synthetic_corpus_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
