"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { toast } from "sonner";
import { Card, CardBody, PanelTitle, StatusDot } from "@/components/ui/card";
import { SamplePicker } from "./sample-picker";
import { TicketInput } from "./ticket-input";
import { ResultPane } from "./result-pane";
import { api, type RunResponse } from "@/lib/api";
import { samples, type Sample } from "@/lib/samples";

export function DemoSection() {
  const [ticket, setTicket] = useState("");
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const [result, setResult] = useState<RunResponse | null>(null);
  const [loading, setLoading] = useState(false);

  function pickSample(idx: number, s: Sample) {
    setActiveIdx(idx);
    setTicket(s.ticket);
  }

  async function run() {
    if (!ticket.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await api.run(ticket, true);
      setResult(r);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Agent run failed";
      toast.error("Backend offline, showing simulated result", {
        description: message.slice(0, 120),
      });
      setResult(mockRun(ticket));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section
      id="try"
      className="relative scroll-mt-16 mx-auto max-w-[1280px] px-5 py-10"
    >
      <header className="section-rule">
        <span className="section-rule__chip">§01</span>
        <span className="section-rule__title">Live demo</span>
        <span className="section-rule__line" />
        <span className="text-[10.5px] font-mono text-[var(--color-fg-mute)] uppercase tracking-[0.16em]">
          paste · run · trace
        </span>
      </header>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.5 }}
        className="mb-6 max-w-2xl"
      >
        <h2
          className="display text-balance text-[var(--color-fg)]"
          style={{ fontSize: "clamp(28px, 4vw, 44px)" }}
        >
          Paste one of these or your own.
        </h2>
        <p className="mt-4 text-[14.5px] leading-[1.55] text-[var(--color-fg-dim)] font-sans">
          A run is three Sonnet calls. Output below comes back as three panels
          (classify, draft, escalate) with confidence bars and any FAQ
          citations the drafter pulled.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4">
          <div>
            <p className="text-[10.5px] font-mono uppercase tracking-[0.16em] text-[var(--color-fg-mute)] mb-2.5 flex items-center gap-2">
              Preset cases
              <span className="flex-1 h-px bg-[var(--color-line-2)]" />
              <span className="text-[var(--color-fg-faint)] tabular">
                {samples.length.toString().padStart(2, "0")} loaded
              </span>
            </p>
            <SamplePicker active={activeIdx} onSelect={pickSample} />
          </div>

          <TicketInput
            value={ticket}
            onChange={(v) => {
              setTicket(v);
              setActiveIdx(null);
            }}
            onSubmit={run}
            loading={loading}
          />

          {(result || loading) && <ResultPane result={result} loading={loading} />}
        </div>

        <aside className="space-y-3 lg:sticky lg:top-16 lg:self-start">
          {!result && !loading ? (
            <PipelinePanel />
          ) : (
            <SampleHintPanel idx={activeIdx} />
          )}
        </aside>
      </div>
    </section>
  );
}

function PipelinePanel() {
  const steps = [
    { t: "acid" as const, label: "Embed query", desc: "voyage-3 over question", n: "01" },
    { t: "acid" as const, label: "Tool · classify", desc: "category + conf + rationale", n: "02" },
    { t: "amber" as const, label: "Retrieve FAQ", desc: "pgvector cosine, top-k", n: "03" },
    { t: "amber" as const, label: "Tool · draft", desc: "response + tone + cites", n: "04" },
    { t: "rose" as const, label: "Tool · escalate", desc: "boolean + reason + team", n: "05" },
    { t: "acid" as const, label: "Persist + trace", desc: "trace row + Langfuse", n: "06" },
  ];
  return (
    <Card glow="acid">
      <PanelTitle
        label="Pipeline"
        meta={
          <span className="inline-flex items-center gap-2">
            <StatusDot tone="acid" pulse />
            <span className="text-[var(--color-acid)]">IDLE</span>
          </span>
        }
      />
      <CardBody>
        <ol className="space-y-3">
          {steps.map((step, i) => (
            <li key={i} className="flex gap-3 items-start">
              <span className="text-[10.5px] font-mono tabular text-[var(--color-fg-mute)] mt-0.5 shrink-0 w-5">
                {step.n}
              </span>
              <StatusDot tone={step.t} className="mt-1.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[12.5px] font-medium text-[var(--color-fg)] leading-tight font-sans">
                  {step.label}
                </p>
                <p className="text-[11px] text-[var(--color-fg-mute)] leading-snug mt-0.5 font-mono">
                  ▸ {step.desc}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </CardBody>
    </Card>
  );
}

function SampleHintPanel({ idx }: { idx: number | null }) {
  if (idx === null) return <PipelinePanel />;
  const s = samples[idx];
  if (!s) return <PipelinePanel />;
  return (
    <Card glow="acid">
      <PanelTitle
        label={`Case ${String(idx + 1).padStart(2, "0")}`}
        meta="EXPECTED"
      />
      <CardBody className="space-y-3">
        <p className="text-[13px] leading-[1.55] text-[var(--color-fg)] font-sans">
          {s.hint}
        </p>
        <p className="text-[11px] font-mono text-[var(--color-fg-mute)] border-t border-[var(--color-line-2)] pt-3 leading-relaxed uppercase tracking-[0.08em]">
          ▸ The agent has not seen this case before.
          <br />
          ▸ Every run is a fresh end-to-end execution.
        </p>
      </CardBody>
    </Card>
  );
}

function mockRun(ticket: string): RunResponse {
  const lower = ticket.toLowerCase();
  let category: RunResponse["classification"]["category"] = "other";
  if (/refund|double[- ]charge/.test(lower)) category = "refund";
  else if (/invoice|charge|billing|subscription/.test(lower)) category = "billing";
  else if (/crash|bug|broken|error|2fa|sms|app/.test(lower)) category = "technical";
  else if (/login|password|account|reset/.test(lower)) category = "account";
  return {
    trace_id: "trc-" + Math.random().toString(36).slice(2, 12),
    classification: {
      category,
      confidence: 0.91,
      rationale:
        "The ticket contains phrasing characteristic of this category, keywords align with prior labelled examples in the golden set.",
      call: {
        stage: "classify",
        trace_id: "cls-" + Math.random().toString(36).slice(2, 8),
        model: "claude-sonnet-4-6",
        input_tokens: 412,
        output_tokens: 78,
        cost_usd: 0.0024,
        latency_ms: 620,
        repair_attempts: 0,
        langfuse_url: null,
      },
    },
    draft: {
      response:
        "Hi,\n\nThanks for getting in touch. I've taken a look at your account and I can see what happened, let me get this sorted out for you. I'll follow up within one business day with a detailed update.\n\nBest,\nSupport",
      tone: "empathetic",
      citations: [],
      faq_chunks_used: [],
      call: {
        stage: "draft",
        trace_id: "drf-" + Math.random().toString(36).slice(2, 8),
        model: "claude-sonnet-4-6",
        input_tokens: 380,
        output_tokens: 96,
        cost_usd: 0.0026,
        latency_ms: 880,
        repair_attempts: 0,
        langfuse_url: null,
      },
    },
    escalation: {
      escalate: category === "technical" || category === "refund" || category === "account",
      reasoning:
        "Sample tickets that touch billing, account access, or production bugs are routed to a human owner; informational queries auto-resolve.",
      suggested_team:
        category === "technical"
          ? "engineering"
          : category === "refund" || category === "billing"
            ? "billing"
            : category === "account"
              ? "general"
              : "none",
      call: {
        stage: "escalate",
        trace_id: "esc-" + Math.random().toString(36).slice(2, 8),
        model: "claude-sonnet-4-6",
        input_tokens: 510,
        output_tokens: 72,
        cost_usd: 0.0026,
        latency_ms: 600,
        repair_attempts: 0,
        langfuse_url: null,
      },
    },
    total_input_tokens: 1302,
    total_output_tokens: 246,
    total_cost_usd: 0.0076,
    total_latency_ms: 2100,
  };
}
