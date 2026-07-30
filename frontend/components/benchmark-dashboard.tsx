"use client";

import { useState } from 'react';
import { Play, ArrowRight, Zap, Workflow, BarChart3, Split, CheckCircle, XCircle, Clock, DollarSign, Target, Activity } from 'lucide-react';
import { runBenchmark, sendChat, type ChatResponse, type BenchmarkResponse } from '@/lib/api';

function MetricBadge({ label, value, icon, good }: { label: string; value: string; icon: React.ReactNode; good?: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
      <span className={good !== undefined ? (good ? 'text-emerald-400' : 'text-red-400') : 'text-orange-300'}>{icon}</span>
      <div>
        <div className="text-[10px] uppercase tracking-wider text-white/50">{label}</div>
        <div className="text-sm font-semibold text-white">{value}</div>
      </div>
    </div>
  );
}

export function BenchmarkDashboard() {
  const [prompt, setPrompt] = useState('What is retrieval-augmented generation and how does StreamRAG differ from Naive RAG?');
  const [naiveAnswer, setNaiveAnswer] = useState('');
  const [streamAnswer, setStreamAnswer] = useState('');
  const [naiveLatency, setNaiveLatency] = useState<number | null>(null);
  const [streamLatency, setStreamLatency] = useState<number | null>(null);
  const [benchmark, setBenchmark] = useState<string>('');
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function onRun() {
    setLoading(true);
    try {
      const [naiveRes, streamRes] = await Promise.all([
        sendChat(prompt, 'naive'),
        sendChat(prompt, 'stream'),
      ]);
      const bench = (await runBenchmark(prompt, 3)) as BenchmarkResponse;
      setNaiveAnswer(naiveRes.answer);
      setStreamAnswer(streamRes.answer);
      setNaiveLatency(naiveRes.latency_ms);
      setStreamLatency(streamRes.latency_ms);
      setBenchmark(JSON.stringify(bench, null, 2));
      setBenchmarkData(bench);
    } finally {
      setLoading(false);
    }
  }

  const naiveRecord = benchmarkData?.records.find(r => r.mode === 'naive');
  const streamRecord = benchmarkData?.records.find(r => r.mode === 'stream');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="rounded-2xl bg-gradient-to-br from-orange-500/20 to-orange-600/10 p-3">
          <Workflow className="h-8 w-8 text-orange-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-paper">RAG Comparison Bench</h1>
          <p className="text-sm text-white/60">Naive RAG vs StreamRAG — side by side</p>
        </div>
      </div>

      {/* Input */}
      <section className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-glow backdrop-blur">
        <label className="block text-sm font-medium text-white/75">Enter your query</label>
        <textarea
          className="mt-2 min-h-28 w-full rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm text-white outline-none transition placeholder:text-white/35 focus:border-orange-400/60"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onRun}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-full bg-orange-400 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-orange-300 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Play className="h-4 w-4" />
            {loading ? 'Comparing...' : 'Compare both paths'}
          </button>
        </div>
      </section>

      {/* Side-by-side RAG responses */}
      <section className="grid gap-6 lg:grid-cols-2">
        {/* Naive RAG */}
        <div className="rounded-3xl border border-white/10 bg-slate-950/70 p-6 transition hover:border-blue-500/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.25em] text-blue-400">
              <Split className="h-4 w-4" /> Naive RAG
            </div>
            {naiveLatency !== null && (
              <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs text-blue-300">
                {naiveLatency.toFixed(0)}ms
              </span>
            )}
          </div>
          <div className="mt-4 min-h-32 rounded-2xl bg-black/20 p-4">
            <p className="whitespace-pre-wrap text-sm leading-7 text-white/80">
              {naiveAnswer || <span className="text-white/30 italic">Naive RAG response will appear here...</span>}
            </p>
          </div>
        </div>

        {/* StreamRAG */}
        <div className="rounded-3xl border border-orange-500/20 bg-slate-950/70 p-6 transition hover:border-orange-400/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.25em] text-orange-400">
              <Zap className="h-4 w-4" /> StreamRAG
            </div>
            {streamLatency !== null && (
              <span className="rounded-full bg-orange-500/10 px-3 py-1 text-xs text-orange-300">
                {streamLatency.toFixed(0)}ms
              </span>
            )}
          </div>
          <div className="mt-4 min-h-32 rounded-2xl bg-black/20 p-4">
            <p className="whitespace-pre-wrap text-sm leading-7 text-white/80">
              {streamAnswer || <span className="text-white/30 italic">StreamRAG response will appear here...</span>}
            </p>
          </div>
        </div>
      </section>

      {/* Metrics comparison */}
      {(naiveRecord || streamRecord) && (
        <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur">
          <h2 className="text-lg font-semibold text-paper">Benchmark Metrics</h2>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <MetricBadge
              label="Naive Latency"
              value={naiveRecord ? `${naiveRecord.latency_ms.toFixed(0)}ms` : '-'}
              icon={<Clock className="h-4 w-4" />}
            />
            <MetricBadge
              label="Stream Latency"
              value={streamRecord ? `${streamRecord.latency_ms.toFixed(0)}ms` : '-'}
              icon={<Clock className="h-4 w-4" />}
              good={streamRecord && naiveRecord ? streamRecord.latency_ms < naiveRecord.latency_ms : undefined}
            />
            <MetricBadge
              label="Naive TTFT"
              value={naiveRecord ? `${naiveRecord.time_to_first_token_ms?.toFixed(0) || '-'}ms` : '-'}
              icon={<Activity className="h-4 w-4" />}
            />
            <MetricBadge
              label="Stream TTFT"
              value={streamRecord ? `${streamRecord.time_to_first_token_ms?.toFixed(0) || '-'}ms` : '-'}
              icon={<Activity className="h-4 w-4" />}
              good={true}
            />
            <MetricBadge
              label="Naive Cost"
              value={naiveRecord ? `$${naiveRecord.estimated_cost_usd.toFixed(6)}` : '-'}
              icon={<DollarSign className="h-4 w-4" />}
            />
            <MetricBadge
              label="Stream Cost"
              value={streamRecord ? `$${streamRecord.estimated_cost_usd.toFixed(6)}` : '-'}
              icon={<DollarSign className="h-4 w-4" />}
            />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <MetricBadge
              label="Naive Tokens"
              value={naiveRecord ? `${naiveRecord.total_tokens}` : '-'}
              icon={<BarChart3 className="h-4 w-4" />}
            />
            <MetricBadge
              label="Stream Tokens"
              value={streamRecord ? `${streamRecord.total_tokens}` : '-'}
              icon={<BarChart3 className="h-4 w-4" />}
            />
            <MetricBadge
              label="Naive Grounding"
              value={naiveRecord ? `${(naiveRecord.grounding_score * 100).toFixed(0)}%` : '-'}
              icon={<Target className="h-4 w-4" />}
            />
            <MetricBadge
              label="Stream Grounding"
              value={streamRecord ? `${(streamRecord.grounding_score * 100).toFixed(0)}%` : '-'}
              icon={<Target className="h-4 w-4" />}
              good={streamRecord && naiveRecord ? streamRecord.grounding_score >= naiveRecord.grounding_score : undefined}
            />
            <MetricBadge
              label="Naive Failures"
              value={naiveRecord ? `${naiveRecord.failures}` : '-'}
              icon={naiveRecord?.failures ? <XCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
              good={naiveRecord ? naiveRecord.failures === 0 : undefined}
            />
            <MetricBadge
              label="Stream Failures"
              value={streamRecord ? `${streamRecord.failures}` : '-'}
              icon={streamRecord?.failures ? <XCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
              good={streamRecord ? streamRecord.failures === 0 : undefined}
            />
          </div>
          {benchmarkData?.winner && (
            <div className="mt-4 rounded-2xl bg-gradient-to-r from-orange-500/10 to-orange-600/5 p-4 text-center">
              <span className="text-sm text-white/60">Winner by latency: </span>
              <span className="text-lg font-bold text-orange-400">{benchmarkData.winner.toUpperCase()} RAG</span>
            </div>
          )}
        </section>
      )}

      {/* Raw JSON */}
      <section className="rounded-3xl border border-white/10 bg-slate-950/70 p-6">
        <details>
          <summary className="cursor-pointer text-sm font-medium text-white/60 hover:text-white/80">Benchmark JSON output</summary>
          <pre className="mt-4 overflow-auto rounded-2xl bg-black/30 p-4 text-xs leading-6 text-emerald-300">
            {benchmark || 'Run the comparison to see benchmark data.'}
          </pre>
        </details>
      </section>
    </div>
  );
}
