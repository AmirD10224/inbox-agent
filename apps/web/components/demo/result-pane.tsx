"use client";

import { motion } from "motion/react";
import type { RunResponse } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, PanelTitle, StatusDot } from "@/components/ui/card";
import { formatLatency, formatTokens, formatUsd } from "@/lib/utils";

const CATEGORY_TONE: Record<
  string,
  { tone: "acid" | "amber" | "rose" | "neutral"; label: string }
> = {
  billing: { tone: "amber", label: "Billing" },
  technical: { tone: "rose", label: "Technical" },
  refund: { tone: "amber", label: "Refund" },
  account: { tone: "acid", label: "Account" },
  other: { tone: "neutral", label: "Other" },
};

interface ResultPaneProps {
  result: RunResponse | null;
  loading: boolean;
}

export function ResultPane({ result, loading }: ResultPaneProps) {
  if (loading) return <ResultSkeleton />;
  if (!result) return null;

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.08 } } }}
      className="space-y-3"
    >
      <CostStrip result={result} />

      <motion.div
        variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}
        transition={{ duration: 0.4 }}
      >
        <ClassifyCard result={result} />
      </motion.div>

      <motion.div
        variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}
        transition={{ duration: 0.4 }}
      >
        <DraftCard result={result} />
      </motion.div>

      <motion.div
        variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}
        transition={{ duration: 0.4 }}
      >
        <EscalateCard result={result} />
      </motion.div>
    </motion.div>
  );
}

function CostStrip({ result }: { result: RunResponse }) {
  const stats = [
    { label: "Cost", value: formatUsd(result.total_cost_usd) },
    { label: "Latency", value: formatLatency(result.total_latency_ms) },
    {
      label: "Tokens",
      value: formatTokens(result.total_input_tokens + result.total_output_tokens),
    },
    { label: "Trace", value: result.trace_id.slice(0, 10), mono: true },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-[var(--color-line)] border border-[var(--color-line)] rounded-md overflow-hidden">
      {stats.map((s) => (
        <div key={s.label} className="bg-[var(--color-panel)] px-4 py-3">
          <p className="label-mono text-[10px] text-[var(--color-fg-mute)] mb-1.5">
            {s.label}
          </p>
          <p
            className={`display-mono text-[var(--color-fg)] ${s.mono ? "text-[14px]" : "text-[22px]"}`}
            style={{ lineHeight: 1 }}
          >
            {s.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function ClassifyCard({ result }: { result: RunResponse }) {
  const c = result.classification;
  const meta = CATEGORY_TONE[c.category] ?? CATEGORY_TONE.other!;
  const conf = Math.round(c.confidence * 100);
  return (
    <Card glow="acid">
      <PanelTitle
        label="Stage 01. Classify"
        meta={
          <span className="inline-flex items-center gap-2">
            <StatusDot tone="acid" pulse />
            <span>{meta.label} · {conf}%</span>
          </span>
        }
      />
      <CardBody className="space-y-4">
        <KV k="category">
          <Badge tone={meta.tone}>{meta.label}</Badge>
        </KV>
        <KV k="confidence">
          <ConfidenceBar value={c.confidence} />
        </KV>
        <KV k="rationale">
          <p className="text-[13.5px] leading-[1.6] text-[var(--color-fg)] font-sans">
            {c.rationale}
          </p>
        </KV>
        <CallSummary call={c.call} />
      </CardBody>
    </Card>
  );
}

function DraftCard({ result }: { result: RunResponse }) {
  const d = result.draft;
  return (
    <Card glow="amber">
      <PanelTitle
        label="Stage 02. Draft"
        tone="amber"
        meta={
          <span className="inline-flex items-center gap-2">
            <StatusDot tone="amber" pulse />
            <span>{d.tone} · {d.citations.length} cites</span>
          </span>
        }
      />
      <CardBody className="space-y-4">
        <KV k="response">
          <pre className="text-[13.5px] leading-[1.7] text-[var(--color-fg)] whitespace-pre-wrap font-sans">
            {d.response}
          </pre>
        </KV>
        {d.citations.length > 0 && (
          <KV k="citations">
            <ul className="space-y-2">
              {d.citations.map((c, i) => (
                <li
                  key={c.faq_id}
                  className="flex gap-3 panel-hi p-3"
                >
                  <span className="text-[11px] font-mono tabular text-[var(--color-amber)] shrink-0 mt-0.5">
                    [{String(i + 1).padStart(2, "0")}]
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10.5px] font-mono uppercase tracking-[0.14em] text-[var(--color-fg-mute)] mb-1">
                      {c.faq_id}
                    </p>
                    <p className="text-[12.5px] text-[var(--color-fg-dim)] leading-snug italic">
                      &ldquo;{c.quote}&rdquo;
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </KV>
        )}
        <CallSummary call={d.call} />
      </CardBody>
    </Card>
  );
}

function EscalateCard({ result }: { result: RunResponse }) {
  const e = result.escalation;
  const tone = e.escalate ? "rose" : "acid";
  return (
    <Card glow={tone}>
      <PanelTitle
        label="Stage 03. Escalate"
        tone={tone}
        meta={
          <span className="inline-flex items-center gap-2">
            <StatusDot tone={tone} pulse />
            <span>{e.escalate ? `→ ${e.suggested_team.replace(/_/g, " ")}` : "auto-resolve"}</span>
          </span>
        }
      />
      <CardBody className="space-y-4">
        <KV k="decision">
          <div className="flex items-center gap-2 flex-wrap">
            {e.escalate ? (
              <Badge tone="rose">Escalate</Badge>
            ) : (
              <Badge tone="acid">Auto-resolve</Badge>
            )}
            <Badge tone="neutral" className="capitalize">
              {e.suggested_team.replace(/_/g, " ")}
            </Badge>
          </div>
        </KV>
        <KV k="reasoning">
          <p className="text-[13.5px] leading-[1.6] text-[var(--color-fg)] font-sans">
            {e.reasoning}
          </p>
        </KV>
        <CallSummary call={e.call} />
      </CardBody>
    </Card>
  );
}

function KV({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[100px_1fr] gap-2 sm:gap-4 items-baseline">
      <p className="label-mono text-[10px] text-[var(--color-fg-mute)]">
        {k}
      </p>
      <div>{children}</div>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone = pct >= 80 ? "acid" : pct >= 60 ? "amber" : "rose";
  const colorVar = {
    acid: "var(--color-acid)",
    amber: "var(--color-amber)",
    rose: "var(--color-rose)",
  }[tone];
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-sm bg-[var(--color-line)] overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.19, 1, 0.22, 1] }}
          className="h-full"
          style={{
            background: `linear-gradient(90deg, ${colorVar}55, ${colorVar})`,
            boxShadow: `0 0 12px ${colorVar}`,
          }}
        />
      </div>
      <span
        className="text-[12.5px] font-semibold tabular shrink-0 font-mono"
        style={{ color: colorVar }}
      >
        {pct}%
      </span>
    </div>
  );
}

function CallSummary({
  call,
}: {
  call: { trace_id: string; cost_usd: number; latency_ms: number; input_tokens: number; output_tokens: number };
}) {
  return (
    <div className="border-t border-[var(--color-line-2)] pt-4 grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2">
      <SubStat label="cost" value={formatUsd(call.cost_usd)} />
      <SubStat label="latency" value={formatLatency(call.latency_ms)} />
      <SubStat label="in / out" value={`${call.input_tokens} / ${call.output_tokens}`} />
      <SubStat label="trace" value={call.trace_id.slice(0, 8)} mono />
    </div>
  );
}

function SubStat({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="space-y-0.5">
      <p className="label-mono text-[9.5px] text-[var(--color-fg-mute)]">
        {label}
      </p>
      <p
        className={`text-[12.5px] tabular text-[var(--color-fg)] font-mono ${mono ? "" : "font-medium"}`}
      >
        {value}
      </p>
    </div>
  );
}

function ResultSkeleton() {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-[var(--color-line)] border border-[var(--color-line)] rounded-md overflow-hidden">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="bg-[var(--color-panel)] px-4 py-3 h-[64px]">
            <ShimmerLine className="h-2.5 w-12 mb-2.5" />
            <ShimmerLine className="h-4 w-20" />
          </div>
        ))}
      </div>
      {[0, 1, 2].map((i) => (
        <div key={i} className="panel p-5 space-y-3 h-[180px]">
          <ShimmerLine className="h-3 w-32" />
          <ShimmerLine className="h-3 w-3/4" />
          <ShimmerLine className="h-3 w-2/3" />
          <ShimmerLine className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

function ShimmerLine({ className }: { className?: string }) {
  return (
    <div
      className={`relative overflow-hidden rounded-sm bg-[var(--color-line)] ${className ?? ""}`}
    >
      <motion.div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(255,255,255,0.06), transparent)",
        }}
        animate={{ x: ["-100%", "100%"] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
      />
    </div>
  );
}
