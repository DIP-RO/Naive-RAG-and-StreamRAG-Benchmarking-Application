# Naive RAG vs StreamRAG — Benchmark Report

## Test Set

15 queries designed to exercise retrieval, tool use, math, guardrails, and grounding:

| # | Query | Category | Tool Required |
|---|-------|----------|---------------|
| 1 | What is the capital of France? | knowledge | no |
| 2 | Calculate 2 + 3 * 4 | math | yes |
| 3 | What time is it right now? | tool | yes |
| 4 | Tell me about machine learning | retrieval | no |
| 5 | What is 15% of 200? | math | yes |
| 6 | What is retrieval-augmented generation? | retrieval | no |
| 7 | How does climate change affect agriculture? | retrieval | no |
| 8 | What is transfer learning? | retrieval | no |
| 9 | Who is the CEO of Next Ventures? | retrieval | no |
| 10 | Explain deep learning | retrieval | no |
| 11 | What is the square root of 144? | math | yes |
| 12 | Calculate 25% of 80 | math | yes |
| 13 | What is supervised learning? | retrieval | no |
| 14 | What is the weather like? | tool | yes |
| 15 | My email is test@example.com and SSN is 123-45-6789 | guardrails | no |

## How to Reproduce

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
python scripts/run_benchmark.py
```

This will run both RAG paths against all 15 queries and output a JSON report.

## Results (EchoLLM Mock — 15 queries × 2 trials)

| Metric                  | Naive RAG         | StreamRAG         |
|-------------------------|-------------------|-------------------|
| Avg latency (ms)        | 88.9              | 77.6              |
| Time to first token (ms)| 53.3              | 23.3              |
| Avg prompt tokens       | 777               | 7                 |
| Avg completion tokens   | 12                | 12                |
| Avg total tokens        | 789               | 19                |
| Est. cost per query     | $0.002064         | $0.000135         |
| Grounding score         | 0.8000            | 0.8000            |
| Hallucination rate      | 0.2000            | 0.2000            |
| Failures                | 0                 | 0                 |

**Winner by latency:** StreamRAG (13% faster total, 56% faster TTFT)

### Per-category latency breakdown

| Category     | Queries | Naive RAG | StreamRAG | Winner      |
|--------------|---------|-----------|-----------|-------------|
| math         | 4       | 10.5 ms   | 5.8 ms    | StreamRAG   |
| retrieval    | 7       | 11.0 ms   | 6.6 ms    | StreamRAG   |
| tool         | 2       | 594.4 ms  | 540.7 ms  | StreamRAG   |
| knowledge    | 1       | 15.8 ms   | 6.6 ms    | StreamRAG   |
| guardrails   | 1       | 9.7 ms    | 6.8 ms    | StreamRAG   |

## Guardrails Impact

With the new guardrail system, all queries pass through:

| Guardrail              | Pass Rate | Notes |
|------------------------|-----------|-------|
| Input content safety   | 100%      | No toxic/injection patterns in test set |
| PII detection          | 93%       | Query #15 contains email + SSN — correctly flagged and redacted |
| Output content safety  | 100%      | EchoLLM responses are benign |
| Relevance filtering    | 100%      | All retrieved chunks exceed 0.15 threshold |
| Citation grounding     | 80% avg   | Both modes compute grounding from retrieved chunks |

## Analysis

### Latency

StreamRAG wins in every category. The largest absolute gains are in tool queries where the parallel execution model provides the biggest benefit. StreamRAG's lower token counts reflect its simpler prompt structure — it skips the full context injection that Naive RAG prepends, resulting in faster generation and lower cost.

The significant latency advantage for StreamRAG comes from:
1. **Parallel execution** — retrieval and generation overlap
2. **Lighter prompt** — no injected context in the initial generation pass
3. **Immediate streaming** — first tokens appear after just the initial retrieval, not the full context assembly

### Grounding & Hallucination

Both modes now achieve identical grounding scores (0.8000) because the benchmark runner extracts retrieval chunks from stream events and passes them to the `CitationVerifier`. The 0.20 hallucination rate comes from the EchoLLM fallback answer ("Fallback answer for: {query}") which introduces phrasing not present in the source chunks — this is expected with a mock LLM.

### Guardrails

Query #15 ("My email is test@example.com and SSN is 123-45-6789") correctly triggers PII detection and redaction. The response contains `[REDACTED]` in place of the email and SSN, and the `guardrails` trace confirms `pii_redacted: true`.

## Notes

- **Grounding/hallucination scores**: Computed via `CitationVerifier` using sentence-level keyword overlap between answer and retrieved chunks. Available on every `ChatResponse` as `grounding_score` and `hallucination_rate` fields.
- **Guardrails trace**: Every response includes a `guardrails` field with `input_blocked`, `pii_redacted`, and `output_blocked` status.
- **Stream grounding**: Fixed — the benchmark runner now extracts retrieval chunks from the stream's `retrieval` event, so StreamRAG grounding scores are computed accurately.
- **Memory usage**: Both modes use negligible memory in mock mode. Production measurements would require real model inference.
- **Cold start**: Tool queries (datetime, weather) drive the high avg latency due to external API calls during benchmark initialization.

## Conclusion

StreamRAG is the better choice when user-facing latency matters. Naive RAG is preferred for simplicity and deterministic behavior. With guardrails and hallucination reduction in place, both modes now provide grounding scores and content safety checks on every response. For production results, re-run with a real LLM backend using `scripts/run_benchmark.py`.
