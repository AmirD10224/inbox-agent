"use client";

import { motion } from "motion/react";

const FEATURES: { n: string; title: string; body: string; tag: string }[] = [
  {
    n: "01",
    tag: "tool-use",
    title: "Tool-forced JSON",
    body:
      "Every LLM call goes through Anthropic's tool-use API and is validated by Pydantic. No JSON parse failures. One place owns the schema.",
  },
  {
    n: "02",
    tag: "calibration",
    title: "Calibrated confidence",
    body:
      "The classifier's confidence is forced to be justified. Eval harness measures calibration vs ground truth on every PR.",
  },
  {
    n: "03",
    tag: "rag",
    title: "FAQ retrieval, not invention",
    body:
      "Drafter retrieves top-k chunks via pgvector cosine over Voyage-3 embeddings, then cites them inline. No FAQ → no citations.",
  },
  {
    n: "04",
    tag: "cost",
    title: "Real cost accounting",
    body:
      "Tokens come from `usage.input_tokens` / `usage.output_tokens`, not estimated. Per-call costs roll up into a total per ticket.",
  },
  {
    n: "05",
    tag: "ci",
    title: "Eval gate in CI",
    body:
      "50-row golden set runs on every PR. >5% regression on any metric blocks merge. Sticky PR comment posts the diff.",
  },
  {
    n: "06",
    tag: "production",
    title: "Production engineering",
    body:
      "mypy --strict, ruff. 75% coverage gate. Langfuse tracing. Alembic migrations. Modal deploy. `make ci` runs clean on a fresh clone.",
  },
];

export function FeaturesSection() {
  return (
    <section className="relative mx-auto max-w-[1280px] px-5 py-12">
      <header className="section-rule">
        <span className="section-rule__chip">§02</span>
        <span className="section-rule__title">How it's wired</span>
        <span className="section-rule__line" />
        <span className="text-[10.5px] font-mono text-[var(--color-fg-mute)] uppercase tracking-[0.16em]">
          six pieces
        </span>
      </header>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.5 }}
        className="mb-10 max-w-3xl"
      >
        <h2
          className="display text-balance text-[var(--color-fg)]"
          style={{ fontSize: "clamp(28px, 4vw, 48px)" }}
        >
          Six pieces of plumbing that keep this thing honest in CI.
        </h2>
      </motion.div>

      <div className="border border-[var(--color-line)] rounded-md overflow-hidden bg-[var(--color-panel)]">
        {FEATURES.map((f, i) => (
          <motion.article
            key={f.n}
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.4, delay: i * 0.04 }}
            className={`group grid grid-cols-[60px_220px_1fr] sm:grid-cols-[80px_280px_1fr] gap-4 sm:gap-8 px-6 py-7 ${i < FEATURES.length - 1 ? "border-b border-[var(--color-line)]" : ""} hover:bg-[var(--color-panel-hi)] transition-colors`}
          >
            <span className="text-[11px] font-mono uppercase tracking-[0.16em] text-[var(--color-acid)] tabular pt-0.5">
              ▸ {f.n}
            </span>
            <div>
              <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-[var(--color-fg-mute)] mb-1.5">
                {f.tag}
              </p>
              <h3 className="text-[15px] sm:text-[17px] font-semibold tracking-tight text-[var(--color-fg)] leading-tight font-sans">
                {f.title}
              </h3>
            </div>
            <p className="text-[13px] leading-[1.6] text-[var(--color-fg-dim)] font-sans">
              {f.body}
            </p>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
