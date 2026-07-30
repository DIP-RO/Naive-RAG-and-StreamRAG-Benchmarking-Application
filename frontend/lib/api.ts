export type RagMode = 'naive' | 'stream';

export type ChatMessage = {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  tool_name?: string | null;
  metadata?: Record<string, unknown>;
};

export type BenchmarkRecord = {
  mode: RagMode;
  latency_ms: number;
  time_to_first_token_ms?: number | null;
  embedding_time_ms: number;
  retrieval_time_ms: number;
  generation_time_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  memory_bytes: number;
  failures: number;
  hallucination_rate: number | null;
  grounding_score: number | null;
};

export type ChatResponse = {
  conversation_id: string;
  mode: RagMode;
  answer: string;
  citations: Array<Record<string, unknown>>;
  tool_calls: Array<Record<string, unknown>>;
  usage: Record<string, number>;
  latency_ms: number;
  request_id: string;
  trace: Record<string, unknown>;
};

export type BenchmarkResponse = {
  records: BenchmarkRecord[];
  winner: RagMode;
  summary: Record<string, unknown>;
};

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api';
const TIMEOUT_MS = 120_000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      signal: controller.signal,
      ...init,
    });
    if (!response.ok) {
      const body = await response.text().catch(() => '');
      throw new Error(`Request failed: ${response.status} ${response.statusText} — ${path} — ${body.slice(0, 200)}`);
    }
    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

export async function sendChat(message: string, mode: RagMode = 'naive', history: ChatMessage[] = []): Promise<ChatResponse> {
  return request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, history, mode }),
  });
}

export async function runBenchmark(message: string, trials = 3): Promise<BenchmarkResponse> {
  return request<BenchmarkResponse>('/benchmark', {
    method: 'POST',
    body: JSON.stringify({ message, trials }),
  });
}
