// Typed API client. Server-side fetches use NEXT_PUBLIC_API_BASE_URL so the
// frontend can be served on Vercel while the API lives on Modal.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Category = "billing" | "technical" | "account" | "refund" | "other";
export type Tone = "empathetic" | "neutral" | "apologetic" | "informative";
export type Team =
  | "billing"
  | "engineering"
  | "trust_safety"
  | "general"
  | "none";

export interface CallSummary {
  stage: "classify" | "draft" | "escalate";
  trace_id: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  repair_attempts: number;
  langfuse_url: string | null;
}

export interface ClassifyResponse {
  category: Category;
  confidence: number;
  rationale: string;
  call: CallSummary;
}

export interface DraftCitation {
  faq_id: string;
  quote: string;
}

export interface DraftResponse {
  response: string;
  citations: DraftCitation[];
  tone: Tone;
  faq_chunks_used: string[];
  call: CallSummary;
}

export interface EscalateResponse {
  escalate: boolean;
  reasoning: string;
  suggested_team: Team;
  call: CallSummary;
}

export interface RunResponse {
  trace_id: string;
  classification: ClassifyResponse;
  draft: DraftResponse;
  escalation: EscalateResponse;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  total_latency_ms: number;
}

export interface TraceRow {
  id: string;
  operation: string;
  ticket_text: string;
  classification: Category | null;
  confidence: number | null;
  escalated: boolean | null;
  suggested_team: Team | null;
  drafted_response: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  total_latency_ms: number;
  llm_calls: CallSummary[];
  langfuse_trace_id: string | null;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} failed (${res.status}): ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  run: (ticket: string, useFaq = true) =>
    request<RunResponse>("/run", {
      method: "POST",
      body: JSON.stringify({ ticket, use_faq: useFaq, faq_top_k: 3 }),
    }),
  traces: (limit = 50) =>
    request<{ traces: TraceRow[]; count: number }>(`/traces?limit=${limit}`),
  ingestFaq: (url: string) =>
    request<{
      document_id: string;
      source_url: string;
      title: string | null;
      chunks_inserted: number;
    }>("/ingest-faq", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  health: () =>
    request<{
      status: "ok";
      version: string;
      db: "ok" | "error";
      langfuse_enabled: boolean;
    }>("/health"),
};
