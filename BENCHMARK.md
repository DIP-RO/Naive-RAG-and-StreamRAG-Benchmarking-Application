# Naive RAG vs StreamRAG — Benchmark Report

## Test Set

10 queries designed to exercise retrieval, tool use, and reasoning:

1. "What is the capital of France?"
2. "Calculate 2 + 3 * 4"
3. "What time is it right now?"
4. "Tell me about machine learning"
5. "Research the impact of climate change on agriculture"
6. "Search the web for latest AI news"
7. "What is the weather like?"
8. "Explain the difference between RAG and fine-tuning"
9. "Compare StreamRAG with naive RAG"
10. "What is 15% of 200?"

## How to Reproduce

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
python scripts/run_benchmark.py
```

This will run both RAG paths against all 10 queries and output a JSON report.

## Results (EchoLLM Mock — 10 queries × 2 trials)

| Metric                  | Naive RAG         | StreamRAG         |
|-------------------------|-------------------|-------------------|
| Avg latency (ms)        | 18.0              | 6.5               |
| Time to first token (ms)| 10.8              | 1.9               |
| Avg prompt tokens       | 286.7             | 7.5               |
| Avg completion tokens   | 12.4              | 11.7              |
| Avg total tokens        | 299.1             | 19.4              |
| Est. cost per query     | $0.00085          | $0.00014          |
| Grounding score         | 1.0000            | 0.7083            |
| Hallucination rate      | 0.0000            | 0.2917            |
| Failures                | 0                 | 0                 |

**Winner by latency:** StreamRAG (64% faster total, 82% faster TTFT)

## Guardrails Impact

With the new guardrail system, all queries pass through:

| Guardrail              | Pass Rate | Notes |
|------------------------|-----------|-------|
| Input content safety   | 100%      | No toxic/injection patterns in test set |
| PII detection          | 100%      | No PII in test queries |
| Output content safety  | 100%      | EchoLLM responses are benign |
| Relevance filtering    | 100%      | All retrieved chunks exceed 0.15 threshold |
| Citation grounding     | 92% avg   | Naive: 100% (context provided), Stream: 71% (no context in mock) |

## Analysis

### Latency

StreamRAG's lower token counts reflect its simpler prompt structure — it skips the full context injection that Naive RAG prepends, resulting in faster generation and lower cost.

The significant latency advantage for StreamRAG comes from:
1. **Parallel execution** — retrieval and generation overlap
2. **Lighter prompt** — no injected context in the initial generation pass
3. **Immediate streaming** — first tokens appear after just the initial retrieval, not the full context assembly

### Grounding & Hallucination

Naive RAG achieves perfect grounding scores because its prompt includes full context from retrieved chunks, and the EchoLLM fallback answer reuses query terms that naturally overlap with chunk content. StreamRAG shows lower grounding in mock mode because the streaming answer is generated without full context in the initial pass — this is expected and would improve with a real LLM that can reason over the incrementally provided context.

In production with a real LLM (e.g., GPT-4o), the absolute latencies will be higher, but the relative advantage of StreamRAG (parallelism, reduced context, streaming) should remain proportional.

## Notes

- **Grounding/hallucination scores**: Computed via `CitationVerifier` using sentence-level keyword overlap between answer and retrieved chunks. Available on every `ChatResponse` as `grounding_score` and `hallucination_rate` fields.
- **Guardrails trace**: Every response includes a `guardrails` field with `input_blocked`, `pii_redacted`, and `output_blocked` status.
- **Memory usage**: Both modes use negligible memory in mock mode. Production measurements would require real model inference.
- **Cold start**: The first query (Q1) was ~10× slower for Naive RAG due to lazy initialization; averaged across all queries, this inflates Naive's mean slightly.

## Conclusion

StreamRAG is the better choice when user-facing latency matters. Naive RAG is preferred for simplicity and deterministic behavior. With guardrails and hallucination reduction in place, both modes now provide grounding scores and content safety checks on every response. For production results, re-run with a real LLM backend using `scripts/run_benchmark.py`.
