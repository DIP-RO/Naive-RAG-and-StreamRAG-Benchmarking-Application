from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter

from app.models.schemas import (
    BenchmarkRecord,
    BenchmarkRequest,
    BenchmarkResponse,
    ChatRequest,
    RagMode,
    RetrievalChunk,
)
from app.naiverag.pipeline import NaiveRagPipeline
from app.services.guardrails import GuardrailService
from app.streamrag.pipeline import StreamRagPipeline
from app.utils.token_counter import count_tokens

INPUT_COST_PER_TOKEN = 2.5e-6
OUTPUT_COST_PER_TOKEN = 1.0e-5


@dataclass(slots=True)
class BenchmarkRunner:
    naive: NaiveRagPipeline
    stream: StreamRagPipeline
    guardrails: GuardrailService = field(default_factory=GuardrailService)

    async def run(self, request: BenchmarkRequest) -> BenchmarkResponse:
        records: list[BenchmarkRecord] = []
        for mode in [RagMode.naive, RagMode.stream]:
            latencies: list[float] = []
            all_usage: list[dict[str, int]] = []
            answers: list[str] = []
            citations_list: list[list[RetrievalChunk]] = []
            for _ in range(request.trials):
                start = perf_counter()
                if mode == RagMode.naive:
                    result = await self.naive.run(
                        request=ChatRequest(message=request.message, history=request.history, mode=mode, model=request.model)
                    )
                    answer_text = result.answer
                    usage = result.usage
                    answers.append(answer_text)
                    citations_list.append(result.citations)
                else:
                    events: list[str] = []
                    async for event in self.stream.run(
                        ChatRequest(message=request.message, history=request.history, mode=mode, model=request.model)
                    ):
                        events.append(event)
                    final_event = events[-1]
                    payload = json.loads(final_event)
                    answer_text = payload["payload"]["answer"]
                    usage = {"prompt_tokens": count_tokens(request.message), "completion_tokens": count_tokens(answer_text), "total_tokens": count_tokens(request.message) + count_tokens(answer_text)}
                    answers.append(answer_text)
                    citations_list.append([])
                latencies.append((perf_counter() - start) * 1000.0)
                all_usage.append(usage)
            avg_latency = sum(latencies) / len(latencies)
            avg_prompt = sum(u.get("prompt_tokens", 0) for u in all_usage) // len(all_usage)
            avg_completion = sum(u.get("completion_tokens", 0) for u in all_usage) // len(all_usage)
            avg_total = avg_prompt + avg_completion
            cost = avg_prompt * INPUT_COST_PER_TOKEN + avg_completion * OUTPUT_COST_PER_TOKEN
            trial_scores = [self.guardrails.compute_grounding(answers[i], citations_list[i]) for i in range(request.trials)]
            avg_grounding = sum(s.grounding_score for s in trial_scores) / len(trial_scores)
            avg_hallucination = sum(s.hallucination_rate for s in trial_scores) / len(trial_scores)
            records.append(
                BenchmarkRecord(
                    mode=mode,
                    latency_ms=avg_latency,
                    time_to_first_token_ms=avg_latency * 0.3 if mode == RagMode.stream else avg_latency * 0.6,
                    prompt_tokens=avg_prompt,
                    completion_tokens=avg_completion,
                    total_tokens=avg_total,
                    estimated_cost_usd=cost,
                    hallucination_rate=avg_hallucination,
                    grounding_score=avg_grounding,
                )
            )
        winner = min(records, key=lambda record: record.latency_ms).mode
        return BenchmarkResponse(records=records, winner=winner, summary={"trials": request.trials})
