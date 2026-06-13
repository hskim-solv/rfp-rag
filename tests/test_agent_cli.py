from __future__ import annotations

import json
from pathlib import Path

from rfp_rag.agent.run_agent import main


def _build_offline_index(tmp_path: Path, parse_manifest_path: Path) -> Path:
    """build_index CLI를 그대로 재사용해 실제 corpus로 오프라인 인덱스를 만든다."""
    from rfp_rag.build_index import main as build_main

    out = tmp_path / "index"
    rc = build_main(
        [
            "--data",
            "data/data_list.csv",
            "--files",
            "data/files",
            "--out",
            str(out),
            "--chunk-size",
            "500",
            "--chunk-overlap",
            "80",
            "--embedding-provider",
            "offline",
            "--parse-manifest",
            str(parse_manifest_path),
        ]
    )
    assert rc == 0
    return out


def test_cli_answers_question_offline(
    tmp_path: Path, capsys, parsed_manifest_factory
) -> None:
    index = _build_offline_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )
    capsys.readouterr()  # build_index CLI 출력 버림
    rc = main(
        [
            "--index",
            str(index),
            "--data",
            "data/data_list.csv",
            "--files",
            "data/files",
            "--question",
            "한영대학교 특성화 맞춤형 교육환경 구축 - 트랙운영 학사정보시스템 고도화 사업의 발주 기관은 어디야?",
            "--thread-id",
            "cli-t1",
            "--min-score",
            "0.23",
            "--artifacts",
            str(tmp_path / "agent_artifacts"),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "answered"
    assert "한영대학" in payload["answer"]["answer"]
    # audit log가 지정 위치에 생성된다
    assert (tmp_path / "agent_artifacts" / "audit.jsonl").exists()


def test_cli_resume_without_pending_interrupt_errors(
    tmp_path: Path, capsys, parsed_manifest_factory
) -> None:
    index = _build_offline_index(
        tmp_path, parsed_manifest_factory(Path("data/data_list.csv"))
    )
    rc = main(
        [
            "--index",
            str(index),
            "--data",
            "data/data_list.csv",
            "--files",
            "data/files",
            "--thread-id",
            "cli-none",
            "--artifacts",
            str(tmp_path / "agent_artifacts"),
            "--approve",
        ]
    )
    assert rc == 2
    assert "재개할 승인 대기 상태가 없습니다" in capsys.readouterr().err
