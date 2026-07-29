import { BenchmarkDashboard } from '@/components/benchmark-dashboard';

export default function Page() {
  return (
    <main className="min-h-screen bg-hero-grid">
      <div className="mx-auto max-w-7xl px-6 py-10 md:px-10 md:py-16">
        <BenchmarkDashboard />
      </div>
    </main>
  );
}
