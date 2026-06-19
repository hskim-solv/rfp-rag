# Stage 3 Contamination Notes

- This is a post-freeze Stage 3 query holdout on the fixed 100-document corpus.
- known limitation: Stage 2 metadata evaluation already touched all 100 corpus documents.
- The builder rejects exact query overlap with Stage 2 JSONL evaluation artifacts.
- The split must not be used for prompt, retrieval, reranker, or threshold tuning after freeze.
- A stronger future claim would add newly collected documents that were never used by Stage 2.
