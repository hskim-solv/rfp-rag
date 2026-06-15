# ADR-0006: Codex agent surface redesign

- 상태: 채택
- 날짜: 2026-06-13
- 결정자: Codex 제안 후 사용자 요청

## 배경

`RFP`에는 Claude Code용 `.claude/skills/eval-lane`, `.claude/agents/*`, `.claude/settings.json` hook이 있고, Codex에서는 `AGENTS.md -> CLAUDE.md` symlink로 지침은 이미 공유된다. 남은 문제는 Claude `tools`/hook 의미를 Codex에 그대로 복사하면 권한(permission)과 lifecycle 동작이 달라질 수 있다는 점이다.

## 선택 기준

- 높음: real lane 비용 실행과 `.env` 직접 편집을 막는 guardrail.
- 높음: `eval-lane`, `eval-gate-analyst`, `langgraph-reviewer`가 Codex에서 명확히 trigger되는가.
- 중: Claude-only metadata를 Codex 권한으로 오해하지 않게 분리하는가.
- 중: 기존 symlink와 repo workflow를 깨지 않는가.
- 낮음: 자동 변환량을 최대화하는가.

## 후보 비교

| 기준 | A. full migrator 실행 | B. skill/agent만 변환 | C. skill/agent + 최소 Codex hook |
|------|------------------------|-----------------------|----------------------------------|
| 비용/secret guardrail | `.claude/settings.json` hook이 변환되지만 의미 재검토 필요 | real lane guard는 skill에 남지만 `.env` hook 없음 | real lane은 skill, `.env`는 custom PreToolUse hook으로 분리 |
| Claude-only metadata 처리 | `tools`가 manual-review prompt로 남음 | 수동 정리 가능 | 수동 정리 가능 |
| hook 의미 차이 | PostToolUse/ruff까지 섞여 review 필요 | hook 없음 | `.env` 보호만 좁게 채택, ruff autofix는 보류 |
| symlink 유지 | 유지 가능 | 유지 | 유지 |
| 재검토 비용 | 높음 | 낮음 | 중간 |

## 결정

C를 채택한다. `eval-lane`은 Codex skill로, `eval-gate-analyst`와 `langgraph-reviewer`는 read-only Codex agent로 옮긴다. `.env` 직접 편집 차단은 project `.codex/hooks.json`의 최소 PreToolUse hook으로 재설계한다. Ruff 자동수정 PostToolUse hook은 Codex/Claude lifecycle 의미 차이가 있어 채택하지 않는다.

## 탈락 사유

- A. full migrator 실행: hook 의미 차이와 manual-review 항목이 많아 현재 repo에는 과하다.
- B. skill/agent만 변환: `.env` 직접 편집 차단이라는 기존 guardrail이 빠진다.

## 재검토 조건

- Codex hook payload나 matcher semantics가 변경될 때.
- `.env`가 아닌 별도 secret manager를 도입할 때.
- real lane 실행 정책이 automation으로 바뀔 때.

## 출처

- `.claude/settings.json`
- `.claude/skills/eval-lane/SKILL.md`
- `.claude/agents/eval-gate-analyst.md`
- `.claude/agents/langgraph-reviewer.md`
- `migrate-to-codex --dry-run` 결과
- Codex manual, fetched 2026-06-13
