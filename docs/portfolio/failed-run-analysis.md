# Failed Run and Edge-case Analysis

This document is a redacted reviewer artifact. It records failure modes and
edge cases without raw prompts, raw RFP text, secrets, or provider payloads.

## rewrite_recovery

- Classification: retrieval_low_score_recovery
- Observed in current artifacts: true
- Lesson: Noisy user phrasing must trigger bounded rewrite instead of silent failure.
- Evidence policy: cite scenario ids, outcomes, metrics, and hashes only.

## abstain

- Classification: out_of_domain_abstention
- Observed in current artifacts: true
- Lesson: Unsupported questions should fail closed with abstention.
- Evidence policy: cite scenario ids, outcomes, metrics, and hashes only.

## hitl_reject

- Classification: human_rejected_side_effect
- Observed in current artifacts: true
- Lesson: Report-writing side effects must stop when approval is rejected.
- Evidence policy: cite scenario ids, outcomes, metrics, and hashes only.

## thread_reuse

- Classification: checkpoint_thread_isolation
- Observed in current artifacts: true
- Lesson: A reused thread must not leak stale question state into the next run.
- Evidence policy: cite scenario ids, outcomes, metrics, and hashes only.

## malicious_tool_output

- Classification: tool_output_injection
- Observed in current artifacts: true
- Lesson: Tool outputs and retrieved evidence must never override system policy.
- Evidence policy: cite scenario ids, outcomes, metrics, and hashes only.
