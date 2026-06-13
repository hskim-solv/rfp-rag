# 2026 Agent Engineer Service Positioning

## Positioning

Target role:

- Agentic AI Engineer
- MCP / AI Backend Engineer
- Agentic Evals Engineer
- AI Platform / AgentOps Engineer

The RFP project should not be framed as only a retrieval demo. The stronger
agent-engineering framing is:

> A source-aware RFP analysis agent with typed tools, durable workflow state,
> trace-based evaluation, human approval, and production service boundaries.

This keeps the RAG foundation central while adding service and agent signals that
current hiring markets recognize.

## Market Signal

Recent AI agent and MCP hiring material repeatedly asks for:

- production agent systems, not prompt-only demos
- LangGraph or equivalent stateful orchestration
- tool use, MCP, function calling, and typed schemas
- context/memory/state management beyond framework defaults
- trace-based debugging and deterministic replay
- evals for tool trajectories, not just final answers
- HITL approval for risky or business-critical actions
- observability, logging, latency, cost, and failure classification
- backend/service engineering: FastAPI, TypeScript, PostgreSQL, Redis, queues,
  cloud deployment, CI/CD, auth, and rate limits

Useful source references:

- GlobalLogic AI Platform Engineer, Agent Systems: production agent systems,
  LangGraph, MCP, context management, tool interfaces, traces, evals, and
  failure analysis.
  https://www.globallogic.com/careers/ai-platform-engineer-agent-systems-irc296274-2/
- NeuronHire Agentic Evals Engineer: trajectory evaluation, deterministic
  replay, trace debugging, structured output validation, scenario tests, and
  document workflows.
  https://www.neuronhire.com/for-developers/jobs/336e3e51-d72e-80a1-94e0-f89353156a68
- O'Reilly AI Agents Stack 2026: agents need state, tools, memory, guardrails,
  evals, and deployment layers distinct from chatbot/RAG stacks.
  https://www.oreilly.com/radar/the-ai-agents-stack-2026-edition/
- AgenticCareers MCP Engineer guide: MCP engineers design safe typed tool
  surfaces, auth, observability, failure handling, and integration tests.
  https://agenticcareers.co/blog/what-is-mcp-engineer
- OpenAI Agents SDK: modern agent primitives include agents, tools, handoffs,
  guardrails, HITL, sessions, tracing, MCP, and sandbox agents.
  https://github.com/openai/openai-agents-python
- LangChain agent frameworks guide: LangGraph/LangSmith emphasize stateful
  orchestration, observability, tracing, evaluation, and MCP integration.
  https://www.langchain.com/resources/ai-agent-frameworks

## What To Add To This Project

### 1. Agentic RAG Workflow

Build a LangGraph workflow around the existing RFP RAG system:

- classify query type
- choose retrieval strategy
- call typed RFP tools
- retrieve candidates
- rerank
- generate grounded answer
- verify citations
- retry/rewrite when evidence is weak
- abstain when retrieval remains insufficient

Portfolio signal:

> Built a stateful LangGraph RFP analysis workflow that routes query types,
> selects retrieval strategies, calls typed tools, verifies citations, and
> retries or abstains based on evidence quality.

### 2. MCP / FastMCP Tool Layer

Expose the RFP system as a safe internal tool surface:

- `search_rfp`
- `summarize_rfp`
- `compare_rfps`
- `parse_source`
- `evaluate_retrieval`
- `read_metrics`
- `generate_review_report`

Tool design requirements:

- typed input/output schemas
- strict validation
- explicit error envelopes
- read-only defaults
- cost/rate guardrails
- tool-level auth or scoped permission flags
- trace IDs for every tool call

Portfolio signal:

> Designed an MCP/FastMCP tool layer for an RFP RAG system with typed schemas,
> scoped permissions, validation, error envelopes, trace IDs, and retrieval
> evaluation tools.

### 3. Agent Evaluation Harness

Evaluate agent behavior as a trajectory, not only as a final answer:

- expected tool sequence
- expected metadata filter usage
- expected retry/rewrite behavior
- expected abstention path
- expected HITL pause
- final answer quality

Example checks:

- condition-search queries should call metadata filtering before generation
- comparison queries should retrieve both target documents
- unsupported questions should abstain without report generation
- report-save requests should pause for human approval

Portfolio signal:

> Built an agentic evaluation harness that scores tool-call trajectories,
> state transitions, citation verification, abstention behavior, and final
> answer quality for document-centric workflows.

### 4. Observability / AgentOps

Add trace logging for each run:

- user query
- classified query type
- selected retrieval strategy
- tool calls
- retrieved chunk IDs
- reranker scores
- generated citations
- validation failures
- retry reasons
- token usage
- latency by step
- cost estimate

Use one of:

- LangSmith
- Langfuse
- OpenTelemetry-compatible structured logs

Portfolio signal:

> Instrumented RFP agent runs with trace-level observability, including tool
> calls, retrieval scores, state transitions, latency, token usage, cost, and
> failure classification.

### 5. Human-In-The-Loop Approval

Business-critical actions should use propose-and-approve flow:

- saving a report
- recommending a bid opportunity
- producing customer-facing summaries
- exporting a comparison table

Portfolio signal:

> Added human approval gates for high-impact RFP agent actions, preserving an
> audit trail of proposed outputs, approval decisions, and resumed workflow
> state.

### 6. Service Boundary

Package the project as a small service:

- FastAPI backend
- Streamlit or Next.js UI
- PostgreSQL for documents, runs, metrics, and reports
- Redis/RQ/Celery for long parser/eval jobs
- optional Temporal or Modal later for durable workflows
- auth/rate limit for tool endpoints
- CI command for credential-free tests

Portfolio signal:

> Turned a local RAG prototype into a service boundary with FastAPI, persistent
> run records, async job execution, eval artifacts, trace logs, and operator
> endpoints.

## Recommended Roadmap

The order should stay retrieval-first, then agent/service:

1. parser/render bakeoff
2. source-first indexing without CSV body fallback
3. section-aware chunking
4. hybrid retrieval + reranking ablation
5. agentic RAG workflow
6. MCP/FastMCP tool layer
7. agent eval + trace observability
8. HITL report approval
9. FastAPI/Streamlit or FastAPI/Next.js service shell

Do not lead with multi-agent autonomy. In this project, the stronger story is a
reliable workflow agent for RFP review:

- controlled tools
- explicit state
- measurable retrieval quality
- evidence-grounded answers
- traceable failures
- human approval for business actions

## Final Agent Engineer Sentence

> Extended a source-aware RFP RAG system into a production-style agent workflow
> with LangGraph orchestration, MCP/FastMCP tools, trajectory evaluation,
> citation verification, trace observability, latency/cost tracking, and
> human-in-the-loop approval for report generation.
