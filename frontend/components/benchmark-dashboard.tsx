"use client";

import { useState } from 'react';
import { Play, ArrowRight, Zap, Workflow, BarChart3 } from 'lucide-react';
import { runBenchmark, sendChat, type ChatResponse, type BenchmarkResponse } from '@/lib/api';

export function BenchmarkDashboard() {
  const [prompt, setPrompt] = useState('Compare StreamRAG and naive RAG for enterprise document Q&A.');
  const [answer, setAnswer] = useState('');
  const [benchmark, setBenchmark] = useState<string>('');
  const [loading, setLoading] = useState(false);

  async function onRun() {
    setLoading(true);
    try {
      const chat = (await sendChat(prompt, [])) as ChatResponse;
      const bench = (await runBenchmark(prompt, 3)) as BenchmarkResponse;
      setAnswer(chat.answer);
      setBenchmark(JSON.stringify(bench, null, 2));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <section className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-glow backdrop-blur">
        <div className="flex items-center gap-3 text-sm uppercase tracking-[0.3em] text-orange-300">
          <Workflow className="h-4 w-4" />
          Full-stack AI agent
        </div>
        <h1 className="mt-4 max-w-2xl text-4xl font-semibold leading-tight text-paper md:text-6xl">
          Naive RAG vs StreamRAG, benchmarked in one production app.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-white/72 md:text-base">
          This interface is designed to make engineering tradeoffs visible: retrieval latency, time to first token,
          grounding quality, and observability signals all sit in the same flow.
        </p>

        <div className="mt-8 space-y-4">
          <label className="block text-sm font-medium text-white/75">Assessment prompt</label>
          <textarea
            className="min-h-32 w-full rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm text-white outline-none transition placeholder:text-white/35 focus:border-orange-400/60"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
          />
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onRun}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-full bg-orange-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-orange-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Play className="h-4 w-4" />
              {loading ? 'Running benchmark...' : 'Run comparison'}
            </button>
            <a
              href="#results"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-medium text-white/80 transition hover:border-white/30 hover:bg-white/5"
            >
              See output <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>
      </section>

      <aside className="grid gap-4">
        <MetricCard icon={<Zap className="h-5 w-5" />} title="StreamRAG" value="Retrieval starts immediately" description="Evidence arrives while generation is already underway." />
        <MetricCard icon={<BarChart3 className="h-5 w-5" />} title="Benchmarking" value="TTFT + latency + cost" description="Designed for interview-grade comparison, not feature count." />
        <MetricCard icon={<Workflow className="h-5 w-5" />} title="Production concerns" value="Retries, tracing, budgets" description="Structured logging, request IDs, and token controls are first-class." />
      </aside>

      <section id="results" className="lg:col-span-2 grid gap-6 lg:grid-cols-2">
        <div className="rounded-3xl border border-white/10 bg-slate-950/70 p-6">
          <h2 className="text-xl font-semibold text-paper">Assistant answer</h2>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-white/80">
            {answer || 'Run the benchmark to produce a grounded response here.'}
          </p>
        </div>
        <div className="rounded-3xl border border-white/10 bg-slate-950/70 p-6">
          <h2 className="text-xl font-semibold text-paper">Benchmark output</h2>
          <pre className="mt-4 overflow-auto rounded-2xl bg-black/30 p-4 text-xs leading-6 text-emerald-300">
            {benchmark || 'Benchmark JSON will appear here.'}
          </pre>
        </div>
      </section>
    </div>
  );
}

function MetricCard({ icon, title, value, description }: { icon: React.ReactNode; title: string; value: string; description: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
      <div className="flex items-center gap-3 text-orange-300">
        {icon}
        <span className="text-sm uppercase tracking-[0.25em]">{title}</span>
      </div>
      <div className="mt-4 text-2xl font-semibold text-paper">{value}</div>
      <p className="mt-2 text-sm leading-6 text-white/68">{description}</p>
    </div>
  );
}
