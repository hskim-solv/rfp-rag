# Dependency Security Register

## Remediated

- `langchain` GHSA-gr75-jv2w-4656: vulnerable package is absent from `uv.lock`
  or patched to the safe floor.
- `diskcache` GHSA-w8v5-vhqr-4h9v: absent from `uv.lock`.
- `ragas` GHSA-95ww-475f-pr4f: removed from the runtime dependency graph by
  ADR-0021. The repo-local LLM judge keeps the eval-lane contract without
  carrying the unpatched package.

accepted_by: not_required
accepted_scope: no_unresolved_dependency_alert
