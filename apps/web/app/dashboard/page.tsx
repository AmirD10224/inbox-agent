"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ExternalLink, RefreshCw } from "lucide-react";
import { Card, CardBody, PanelTitle, StatusDot } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Sparkline } from "@/components/shared/charts";
import { api, type CallSummary, type TraceRow } from "@/lib/api";
import { formatLatency, formatTokens, formatUsd, relativeTime } from "@/lib/utils";

const SEED_THROUGHPUT = [
  82, 95, 88, 104, 118, 112, 124, 138, 130, 144, 152, 148, 162, 178, 168, 184,
];
const SEED_COST = [78, 82, 76, 81, 88, 84, 80, 79, 83, 87, 76, 78, 81, 80, 79, 78];

export default function Dashboard() {
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.traces(50);
      setTraces(r.traces);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 10_000);
    return () => clearInterval(id);
  }, []);

  const stats = computeStats(traces);

  return (
    <section className="mx-auto max-w-[1280px] px-5 pt-8 pb-16">
      {/* Section rule */}
      <header className="section-rule">
        <span className="section-rule__chip">§D</span>
        <span className="section-rule__title">Trace log · live</span>
        <span className="section-rule__line" />
        <span className="text-[10.5px] font-mono text-[var(--color-fg-mute)] uppercase tracking-[0.16em] flex items-center gap-2">
          <StatusDot tone="acid" pulse />
          auto-refresh · 10s
        </span>
      </header>

      <div className="mb-8 flex items-baseline justify-between gap-4 flex-wrap">
        <div>
          <h1
            className="display text-balance text-[var(--color-fg)]"
            style={{ fontSize: "clamp(32px, 4vw, 56px)" }}
          >
            Recent <span className="text-[var(--color-acid)] glow-acid">runs</span>
          </h1>
          <p className="mt-3 text-[14px] leading-[1.55] text-[var(--color-fg-dim)] max-w-2xl font-sans">
            Every ticket processed by the agent. Classification, escalation,
            cost, latency, one-click trace.
          </p>
        </div>
        <button
          onClick={() => void load()}
          className="btn-secondary"
        >
          <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
          <span className="uppercase tracking-[0.12em]">Refresh</span>
        </button>
      </div>

      {error && (
        <div className="mb-6 inline-flex items-center gap-2 px-3 py-2 rounded-sm panel border-[oklch(70%_0.22_25/0.4)] text-[12px] text-[var(--color-rose)] font-mono">
          <StatusDot tone="rose" pulse />
          <span className="uppercase tracking-[0.14em]">REFRESH FAILED, showing last snapshot</span>
        </div>
      )}

      {/* KPI bento */}
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.05 } } }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5"
      >
        <KpiTile
          label="Tickets · all-time"
          value={String(stats.count).padStart(3, "0")}
          tone="acid"
        >
          <Sparkline data={SEED_THROUGHPUT} color="var(--color-acid)" height={36} />
        </KpiTile>
        <KpiTile label="Avg cost" value={formatUsd(stats.avgCost)} tone="amber">
          <Sparkline data={SEED_COST} color="var(--color-amber)" height={36} />
        </KpiTile>
        <KpiTile
          label="P95 latency"
          value={formatLatency(stats.p95Latency)}
          tone="amber"
        />
        <KpiTile
          label="Escalation rate"
          value={`${(stats.escalationRate * 100).toFixed(0)}%`}
          tone={stats.escalationRate > 0.6 ? "rose" : "acid"}
        />
      </motion.div>

      <Card glow="acid">
        <PanelTitle
          label="Trace log"
          meta={`${traces.length.toString().padStart(3, "0")} rows · websocket`}
        />
        <CardBody className="!p-0">
          {loading && traces.length === 0 ? (
            <p className="px-6 py-12 text-center font-mono text-[12px] text-[var(--color-fg-mute)] uppercase tracking-[0.16em]">
              ▸ LOADING...
            </p>
          ) : traces.length === 0 ? (
            <p className="px-6 py-12 text-center font-mono text-[12px] text-[var(--color-fg-mute)] uppercase tracking-[0.16em]">
              ▸ No traces yet. Execute a ticket on the home page.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full font-mono">
                <thead>
                  <tr className="border-b border-[var(--color-line)] text-left bg-[var(--color-panel-2)]">
                    {["WHEN", "TICKET", "CLASS", "CONF", "DECISION", "TOKENS", "COST", "LAT", ""].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-3 py-2.5 text-[9.5px] uppercase tracking-[0.18em] text-[var(--color-fg-mute)] font-medium"
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {traces.map((t, i) => (
                    <tr
                      key={t.id}
                      className={`group transition-colors hover:bg-[var(--color-panel-hi)] ${
                        i < traces.length - 1 ? "border-b border-[var(--color-line)]" : ""
                      }`}
                    >
                      <td className="px-3 py-3 text-[10.5px] text-[var(--color-fg-mute)] whitespace-nowrap tabular">
                        {relativeTime(t.created_at).toUpperCase()}
                      </td>
                      <td className="px-3 py-3 max-w-md">
                        <p className="text-[12px] text-[var(--color-fg)] line-clamp-2 leading-snug font-sans">
                          {t.ticket_text}
                        </p>
                      </td>
                      <td className="px-3 py-3">
                        {t.classification ? (
                          <span className="text-[11px] uppercase tracking-[0.06em] text-[var(--color-fg)]">
                            {t.classification}
                          </span>
                        ) : (
                          <span className="text-[var(--color-fg-faint)]">-</span>
                        )}
                      </td>
                      <td className="px-3 py-3 tabular text-[11px] text-[var(--color-fg-dim)]">
                        {t.confidence !== null ? `${(t.confidence * 100).toFixed(0)}%` : "-"}
                      </td>
                      <td className="px-3 py-3">
                        {t.escalated === true ? (
                          <Badge tone="rose">→ {t.suggested_team?.replace(/_/g, " ")}</Badge>
                        ) : t.escalated === false ? (
                          <Badge tone="acid">Auto</Badge>
                        ) : (
                          <span className="text-[var(--color-fg-faint)]">-</span>
                        )}
                      </td>
                      <td className="px-3 py-3 tabular text-[11px] text-[var(--color-fg-dim)]">
                        {formatTokens(t.total_input_tokens + t.total_output_tokens)}
                      </td>
                      <td className="px-3 py-3 tabular text-[11px] text-[var(--color-fg-dim)]">
                        {formatUsd(t.total_cost_usd)}
                      </td>
                      <td className="px-3 py-3 tabular text-[11px] text-[var(--color-fg-dim)]">
                        {formatLatency(t.total_latency_ms)}
                      </td>
                      <td className="px-3 py-3 text-right">
                        <LangfuseLink calls={t.llm_calls} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </section>
  );
}

function KpiTile({
  label,
  value,
  tone,
  children,
}: {
  label: string;
  value: string;
  tone: "acid" | "amber" | "rose";
  children?: React.ReactNode;
}) {
  const c = {
    acid: "var(--color-acid)",
    amber: "var(--color-amber)",
    rose: "var(--color-rose)",
  }[tone];
  const glow = { acid: "glow-acid", amber: "glow-amber", rose: "glow-rose" }[tone];
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 8 },
        show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
      }}
      className="panel relative overflow-hidden p-4"
    >
      <div
        aria-hidden
        className="absolute -top-12 -right-12 h-32 w-32 rounded-full blur-3xl opacity-15"
        style={{ background: c }}
      />
      <p className="label-mono text-[10px] text-[var(--color-fg-mute)] mb-2">
        {label}
      </p>
      <p
        className={`display-mono ${glow} tabular`}
        style={{ fontSize: 32, color: c, lineHeight: 1 }}
      >
        {value}
      </p>
      {children && <div className="mt-3">{children}</div>}
    </motion.div>
  );
}

function LangfuseLink({ calls }: { calls: CallSummary[] }) {
  const url = calls.find((c) => c.langfuse_url)?.langfuse_url ?? null;
  if (!url) {
    return (
      <span
        className="text-[var(--color-fg-faint)]"
        title="No Langfuse URL recorded"
      >
        <ExternalLink className="inline size-3" />
      </span>
    );
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="text-[var(--color-acid)] hover:text-[var(--color-acid-glow)] transition-colors"
      aria-label="Open in Langfuse"
    >
      <ExternalLink className="inline size-3.5" />
    </a>
  );
}

function computeStats(traces: TraceRow[]): {
  count: number;
  avgCost: number;
  p95Latency: number;
  escalationRate: number;
} {
  if (traces.length === 0) {
    return { count: 0, avgCost: 0, p95Latency: 0, escalationRate: 0 };
  }
  const costs = traces.map((t) => t.total_cost_usd);
  const latencies = [...traces.map((t) => t.total_latency_ms)].sort((a, b) => a - b);
  const idx = Math.min(latencies.length - 1, Math.floor(latencies.length * 0.95));
  const escalated = traces.filter((t) => t.escalated === true).length;
  return {
    count: traces.length,
    avgCost: costs.reduce((a, b) => a + b, 0) / traces.length,
    p95Latency: latencies[idx] ?? 0,
    escalationRate: escalated / traces.length,
  };
}
