import Link from 'next/link';
import { ArrowRight, Workflow, BarChart3, BookOpen } from 'lucide-react';

export default function Page() {
  return (
    <main className="min-h-screen bg-hero-grid">
      <div className="mx-auto max-w-5xl px-6 py-20 md:px-10 md:py-28">
        <div className="text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-br from-orange-500/20 to-orange-600/10">
            <Workflow className="h-8 w-8 text-orange-400" aria-hidden="true" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-paper md:text-5xl">
            Naive RAG vs{' '}
            <span className="bg-gradient-to-r from-orange-300 to-orange-500 bg-clip-text text-transparent">
              StreamRAG
            </span>
          </h1>
          <p className="mt-4 text-lg text-white/60">
            Production-grade AI agent benchmark comparing sequential and streaming RAG architectures.
          </p>
        </div>

        <div className="mt-16 grid gap-6 md:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 text-center backdrop-blur">
            <BookOpen className="mx-auto h-8 w-8 text-blue-400" aria-hidden="true" />
            <h2 className="mt-4 text-lg font-semibold text-paper">Side-by-Side Comparison</h2>
            <p className="mt-2 text-sm text-white/60">
              See both RAG responses simultaneously with latency, token, and cost metrics.
            </p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 text-center backdrop-blur">
            <BarChart3 className="mx-auto h-8 w-8 text-emerald-400" aria-hidden="true" />
            <h2 className="mt-4 text-lg font-semibold text-paper">Automated Benchmark</h2>
            <p className="mt-2 text-sm text-white/60">
              22-query test dataset with latency, cost, and accuracy measurements.
            </p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 text-center backdrop-blur">
            <Workflow className="mx-auto h-8 w-8 text-purple-400" aria-hidden="true" />
            <h2 className="mt-4 text-lg font-semibold text-paper">Full-Stack Architecture</h2>
            <p className="mt-2 text-sm text-white/60">
              FastAPI + Next.js + Qdrant + LangChain agent with tool calling and memory.
            </p>
          </div>
        </div>

        <div className="mt-12 text-center">
          <Link
            href="/benchmark"
            className="inline-flex items-center gap-2 rounded-full bg-orange-400 px-8 py-4 text-base font-semibold text-slate-950 transition hover:bg-orange-300"
          >
            Open Benchmark Dashboard
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </main>
  );
}
