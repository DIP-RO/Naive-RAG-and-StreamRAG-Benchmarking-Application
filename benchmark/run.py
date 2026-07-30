"""
Automated benchmark: runs both RAG paths against the test dataset and prints results.

Usage:
    # Start backend first:
    cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

    # In another terminal:
    python benchmark/run.py

Requires the backend server to be running at http://localhost:8000.
"""

import json
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000/api"
TEST_SET_PATH = Path(__file__).parent / "test_set.json"
REPORT_PATH = Path("benchmark_report.json")


def load_test_set() -> list[dict]:
    with open(TEST_SET_PATH) as f:
        return json.load(f)


def parse_sse_response(text: str) -> tuple[str, float]:
    answer = ""
    latency_ms = 0.0
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        data_str = line.removeprefix("data: ")
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "delta":
            answer += event.get("payload", {}).get("text", "")
        elif event.get("type") == "completed":
            payload = event.get("payload", {})
            answer = payload.get("answer", answer)
            latency_ms = payload.get("latency_ms", 0.0)
    return answer, latency_ms


def run_benchmark() -> dict:
    test_set = load_test_set()
    queries = [item["query"] for item in test_set]
    client = httpx.Client(base_url=BASE_URL, timeout=60.0)
    results = {"naive": {}, "stream": {}}

    for item in test_set:
        qid = item["id"]
        query = item["query"]
        for mode in ("naive", "stream"):
            endpoint = "/chat/stream" if mode == "stream" else "/chat"
            resp = client.post(
                endpoint,
                json={"message": query, "mode": mode},
                timeout=120.0,
            )
            if resp.status_code != 200:
                results[mode][qid] = {"error": resp.text, "query": query}
                continue
            if mode == "stream":
                answer, latency_ms = parse_sse_response(resp.text)
                results[mode][qid] = {
                    "query": query,
                    "expected": item["expected_answer"],
                    "answer": answer,
                    "latency_ms": latency_ms,
                    "usage": {},
                    "tool_calls": [],
                }
            else:
                data = resp.json()
                results[mode][qid] = {
                    "query": query,
                    "expected": item["expected_answer"],
                    "answer": data["answer"],
                    "latency_ms": data["latency_ms"],
                    "usage": data["usage"],
                    "tool_calls": data.get("tool_calls", []),
                }

    summary = {}
    for mode in ("naive", "stream"):
        latencies = [v["latency_ms"] for v in results[mode].values() if "latency_ms" in v]
        errors = sum(1 for v in results[mode].values() if "error" in v)
        summary[mode] = {
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "errors": errors,
            "total": len(test_set),
        }

    return {"test_set_size": len(test_set), "results": results, "summary": summary}


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Running benchmark against {BASE_URL}")
    print(f"Test set: {len(test_set)} queries ({TEST_SET_PATH})\n")
    for item in test_set:
        print(f"  [{item['id']}] ({item['category']}) {item['query']}")

    report = run_benchmark()

    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    for mode, s in report["summary"].items():
        print(f"\n{mode.upper()} RAG:")
        print(f"  Avg latency:  {s['avg_latency_ms']:.1f}ms")
        print(f"  Min latency:  {s['min_latency_ms']:.1f}ms")
        print(f"  Max latency:  {s['max_latency_ms']:.1f}ms")
        print(f"  Errors:       {s['errors']}/{s['total']}")

    winner = "stream" if report["summary"]["stream"]["avg_latency_ms"] < report["summary"]["naive"]["avg_latency_ms"] else "naive"
    print(f"\nWinner by latency: {winner.upper()} RAG")

    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nFull report: {REPORT_PATH}")
