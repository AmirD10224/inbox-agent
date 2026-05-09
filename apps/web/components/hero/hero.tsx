"use client";

import { motion } from "motion/react";
import { ArrowDown } from "lucide-react";
import Link from "next/link";
import { Card, PanelTitle, StatusDot } from "@/components/ui/card";
import { Sparkline, StageFlow } from "@/components/shared/charts";

const SEED_THROUGHPUT = [
  82, 95, 88, 104, 118, 112, 124, 138, 130, 144, 152, 148, 162, 178, 168, 184,
];
const SEED_COST = [78, 82, 76, 81, 88, 84, 80, 79, 83, 87, 76, 78, 81, 80, 79, 78];

export function Hero() {
  return (
    <section className="relative pt-10 pb-8">
      <div className="max-w-[1280px] mx-auto px-5">
        {/* Section rule */}
        <div className="section-rule">
          <span className="section-rule__chip">§00</span>
          <span className="section-rule__title">Mission</span>
          <span className="section-rule__line" />
          <span className="text-[10.5px] font-mono text-[var(--color-fg-mute)] uppercase tracking-[0.16em]">
            agentic customer support · v0.1.0
          </span>
        </div>

        {/* Headline */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="grid grid-cols-1 lg:grid-cols-12 gap-5 mb-6"
        >
          <div className="lg:col-span-8">
            <h1
              className="display text-balance text-[var(--color-fg)]"
              style={{ fontSize: "clamp(36px, 6vw, 72px)" }}
            >
              An <span className="text-[var(--color-acid)] glow-acid">AI support agent</span>
              <br />
              with the wiring you'd expect.
            </h1>

            <p className="mt-7 max-w-2xl text-[15.5px] leading-[1.55] text-[var(--color-fg-dim)] font-sans">
              You feed it a ticket. It picks a category, drafts a reply, and
              decides whether a human should pick it up. Three Sonnet calls.
              Tool-use JSON so the schema can't drift. Per-call dollar cost.
              An eval set runs on every PR and blocks the merge if quality
              drops.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a href="#try" className="btn-primary group">
                Run the demo
                <ArrowDown className="size-3.5 transition-transform group-hover:translate-y-0.5" />
              </a>
              <Link href="/dashboard" className="btn-secondary">
                View dashboard
              </Link>
              <a
                href="https://github.com/AmirD10224/inbox-agent"
                target="_blank"
                rel="noreferrer"
                className="text-[12.5px] text-[var(--color-fg-mute)] hover:text-[var(--color-fg)] uppercase tracking-[0.14em] font-mono transition-colors"
              >
                Source ↗
              </a>
            </div>
          </div>

          {/* Right: live stage flow */}
          <Card glow="acid" className="lg:col-span-4">
            <PanelTitle
              label="Pipeline · stages"
              meta={
                <span className="inline-flex items-center gap-1.5">
                  <StatusDot tone="acid" pulse />
                  <span className="text-[var(--color-acid)]">IDLE</span>
                </span>
              }
            />
            <div className="p-4">
              <StageFlow active={null} />
            </div>
          </Card>
        </motion.div>

        {/* KPI strip */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3"
        >
          <KpiTile label="Cost / ticket" value="$0.008" sub="3 sonnet calls" tone="acid">
            <Sparkline data={SEED_COST} color="var(--color-acid)" height={40} />
          </KpiTile>
          <KpiTile label="P50 latency" value="2.10s" sub="end-to-end" tone="amber">
            <Sparkline data={SEED_THROUGHPUT} color="var(--color-amber)" height={40} />
          </KpiTile>
          <KpiTile label="Tests passing" value="73 / 73" sub="pytest · CI on every PR" tone="acid" />
          <KpiTile label="Branch coverage" value="92.95%" sub="gate at 75%" tone="acid" />
        </motion.div>
      </div>
    </section>
  );
}

function KpiTile({
  label,
  value,
  sub,
  tone,
  children,
}: {
  label: string;
  value: string;
  sub: string;
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
    <div className="panel relative overflow-hidden p-4">
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
        style={{ fontSize: 28, color: c, lineHeight: 1 }}
      >
        {value}
      </p>
      <p className="text-[10.5px] text-[var(--color-fg-mute)] mt-2 font-mono uppercase tracking-tight">
        {sub}
      </p>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
