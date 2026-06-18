# ADR-0016: MCP-Style RFP RAG Ops Tool Server

- 상태: 채택
- 날짜: 2026-06-17
- 결정자: Codex 제안 후 사용자 승인

## 배경

The final portfolio target asks for auditable document retrieval and
ops/MCP-style tools, but the core service/eval workflow should not be blocked by
new daemon storage, auth, or cloud/API surfaces. The repo already exposes local
gate and ops evidence through Python functions and FastAPI endpoints. The next
safe step is a narrow tool protocol that can be called by agents or wrapped by a
real MCP/FastMCP server later.

## 선택 기준

- 높음: no-cost, credential-free operation over local artifacts.
- 높음: explicit tool allowlist and max tool-call budget.
- 높음: no raw RFP/body text persistence beyond already-local artifacts.
- 높음: tool arguments must not allow arbitrary local path reads; artifact paths
  stay under approved repository artifact locations.
- 중: MCP-compatible mental model (`tools/list`, `tools/call`) without requiring
  a background daemon.
- 중: easy migration path to FastMCP after core service/guardrails are stable.
- 낮음: full MCP transport/auth compliance in this slice.

## 후보 비교

검증 일자: 2026-06-17. 검증 근거: current repository architecture and local
dependencies. No new package documentation was required because this decision
intentionally avoids a new dependency.

| 기준 | 후보 A: internal JSONL MCP-style tool server | 후보 B: FastMCP dependency now | 후보 C: FastAPI endpoints only |
|------|--------|--------|--------|
| credential-free local operation | yes | yes, but adds dependency/runtime surface | yes |
| allowlist/tool budget guardrail | implemented in-process | possible, but needs wrapper policy | endpoint auth/policy would be separate |
| dependency/storage scope | none | new package and future server/runtime decisions | none |
| MCP-style portfolio signal | `tools/list` / `tools/call` shape | strongest MCP signal | weak, API-only |
| migration path | wrap same tool functions with FastMCP later | already on FastMCP | needs separate adapter later |
| risk | low | medium: dependency/protocol/storage/auth scope expansion | low but misses ops-tool requirement |

## 결정

후보 A를 채택한다. `rfp_rag.ops_tool_server` exposes local tools with
`tools/list` and `tools/call` JSON messages, enforces an explicit allowlist and
max tool-call budget, and delegates to existing gate/ops artifact readers.

## 탈락 사유

- 후보 B: FastMCP is still valuable later, but adopting it now expands dependency,
  daemon, auth, and storage questions before the core ops contract is stable.
- 후보 C: FastAPI endpoints remain useful for service consumers, but they do not
  demonstrate typed agent tool operation or tool-call budget policy.

## 재검토 조건

- Add a real MCP/FastMCP wrapper when an external agent client must connect over
  a standard MCP transport.
- Reopen if auth, multi-user retention, or background execution is added.
- Reopen if ops tools begin mutating artifacts or running cost-bearing providers.

## 출처

- 현재 저장소 파일: `rfp_rag.gate_status`, `rfp_rag.ops_metrics`,
  `rfp_rag.service.app`, `docs/portfolio/2026-rfp-rag-final-goal.md`
