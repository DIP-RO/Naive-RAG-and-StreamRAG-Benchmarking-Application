"""
Automated benchmark: runs both RAG paths against a fixed test set and prints results.

Usage:
    python scripts/run_benchmark.py

Requires the backend server to be running at http://localhost:8000.
"""

import json
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000/api"

TEST_SET = [
    "What is the capital of France?",
    "Calculate 2 + 3 * 4",
    "What time is it right now?",
    "Tell me about machine learning",
    "Research the impact of climate change on agriculture",
    "Search the web for latest AI news",
    "What is the weather like?",
    "Explain the difference between RAG and fine-tuning",
    "Compare StreamRAG with naive RAG",
    "What is 15% of 200?",
]


def run_benchmark() -> dict:
    """Run both RAG modes across all queries and return aggregated results."""
    client = httpx.Client(base_url=BASE_URL, timeout=60.0)
    results = {"naive": {}, "stream": {}}

    for query in TEST_SET:
        for mode in ("naive", "stream"):
            resp = client.post("/chat", json={"message": query, "mode": mode})
            if resp.status_code != 200:
                results[mode][query] = {"error": resp.text}
                continue
            data = resp.json()
            results[mode][query] = {
                "latency_ms": data["latency_ms"],
                "answer_preview": data["answer"][:120],
            }

    # Aggregate
    summary = {}
    for mode in ("naive", "stream"):
        latencies = [
            v["latency_ms"]
            for v in results[mode].values()
            if "latency_ms" in v
        ]
        errors = sum(1 for v in results[mode].values() if "error" in v)
        summary[mode] = {
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "errors": errors,
            "total": len(TEST_SET),
        }

    return {"test_set_size": len(TEST_SET), "results": results, "summary": summary}


if __name__ == "__main__":
    print(f"Running benchmark against {BASE_URL} with {len(TEST_SET)} queries...")
    print(f"Test set: {TEST_SET}\n")
    report = run_benchmark()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for mode, s in report["summary"].items():
        print(f"\n{mode.upper()} RAG:")
        print(f"  Avg latency:  {s['avg_latency_ms']:.1f}ms")
        print(f"  Min latency:  {s['min_latency_ms']:.1f}ms")
        print(f"  Max latency:  {s['max_latency_ms']:.1f}ms")
        print(f"  Errors:       {s['errors']}/{s['total']}")

    winner = "stream" if report["summary"]["stream"]["avg_latency_ms"] < report["summary"]["naive"]["avg_latency_ms"] else "naive"
    print(f"\nWinner by latency: {winner.upper()} RAG")

    report_path = Path("benchmark_report.json")
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nFull report written to {report_path}")
