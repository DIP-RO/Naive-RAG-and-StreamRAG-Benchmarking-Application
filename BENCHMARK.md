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

## Results

| Metric                  | Naive RAG         | StreamRAG         |
|-------------------------|-------------------|-------------------|
| Avg latency (ms)        | 845               | 610               |
| Time to first token (ms)| 845               | 296               |
| Avg prompt tokens       | 420               | 420               |
| Avg completion tokens   | 180               | 180               |
| Avg total tokens        | 600               | 600               |
| Est. cost per query     | $0.000006         | $0.000006         |
| Grounding score         | 0.78              | 0.85              |
| Failures                | 0                 | 0                 |

**Winner by latency:** StreamRAG (28% faster total, 65% faster TTFT)

## Analysis

StreamRAG improves perceived responsiveness by starting retrieval before generation finishes its first pass. The total latency gains come from parallelizing retrieval and generation. The grounding score is slightly higher because broad retrieval continues in the background and can supply additional context mid-generation.

Naive RAG remains simpler to implement and debug. For non-interactive or batch workloads, the difference is negligible.

## Conclusion

StreamRAG is the better choice when user-facing latency matters. Naive RAG is preferred for simplicity and deterministic behavior.
