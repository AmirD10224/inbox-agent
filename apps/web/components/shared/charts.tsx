"use client";

import { useMemo } from "react";

/* Sparkline with gradient fill, glow, smooth curve, last-value dot */
export function Sparkline({
  data,
  color = "var(--color-acid)",
  height = 80,
}: {
  data: number[];
  color?: string;
  height?: number;
}) {
  const id = useMemo(() => `sl-${Math.random().toString(36).slice(2, 9)}`, []);
  if (data.length === 0) return null;
  const w = 240;
  const h = height;
  const padX = 2;
  const padY = 6;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = (w - padX * 2) / (data.length - 1 || 1);
  const pts = data.map((v, i) => ({
    x: padX + i * step,
    y: padY + (h - padY * 2) * (1 - (v - min) / range),
  }));
  const d = pts.reduce((acc, p, i) => {
    if (i === 0) return `M ${p.x.toFixed(2)} ${p.y.toFixed(2)}`;
    const prev = pts[i - 1]!;
    const cp1x = prev.x + (p.x - prev.x) * 0.5;
    const cp2x = prev.x + (p.x - prev.x) * 0.5;
    return `${acc} C ${cp1x.toFixed(2)} ${prev.y.toFixed(2)}, ${cp2x.toFixed(2)} ${p.y.toFixed(2)}, ${p.x.toFixed(2)} ${p.y.toFixed(2)}`;
  }, "");
  const fillPath = `${d} L ${pts[pts.length - 1]!.x} ${h} L ${pts[0]!.x} ${h} Z`;
  const last = pts[pts.length - 1]!;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="w-full block">
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.32" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fillPath} fill={`url(#${id}-fill)`} />
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        style={{ filter: `drop-shadow(0 0 4px ${color})` }}
      />
      <circle
        cx={last.x}
        cy={last.y}
        r={2.5}
        fill={color}
        style={{ filter: `drop-shadow(0 0 6px ${color})` }}
      />
    </svg>
  );
}

/* Bar chart, horizontal rows */
export function BarChart({
  data,
  labels,
  color = "var(--color-acid)",
  unit = "ms",
}: {
  data: number[];
  labels?: string[];
  color?: string;
  unit?: string;
}) {
  const max = Math.max(...data) || 1;
  return (
    <div className="space-y-2.5">
      {data.map((v, i) => {
        const pct = (v / max) * 100;
        return (
          <div key={i} className="flex items-center gap-3">
            {labels && (
              <span className="text-[10.5px] text-[var(--color-fg-mute)] uppercase tracking-tight w-16 shrink-0 font-mono">
                {labels[i]}
              </span>
            )}
            <div className="flex-1 h-2.5 bg-[var(--color-line)] rounded-sm relative overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 rounded-sm"
                style={{
                  width: `${pct}%`,
                  background: `linear-gradient(90deg, ${color}55, ${color})`,
                  boxShadow: `0 0 6px ${color}`,
                }}
              />
            </div>
            <span className="text-[11px] tabular text-[var(--color-fg-dim)] w-14 text-right shrink-0 font-mono">
              {v.toFixed(0)}
              {unit}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* Stage Flow, animated tickets flowing through 3 stages (classify → draft → escalate) */
export function StageFlow({
  active,
}: {
  active?: "classify" | "draft" | "escalate" | null;
}) {
  const W = 600;
  const H = 100;
  const STAGE_X = [80, 300, 520];
  const Y = H / 2;
  const STAGES = [
    { x: STAGE_X[0]!, label: "CLASSIFY", color: "var(--color-acid)", n: "01" },
    { x: STAGE_X[1]!, label: "DRAFT", color: "var(--color-amber)", n: "02" },
    { x: STAGE_X[2]!, label: "ESCALATE", color: "var(--color-rose)", n: "03" },
  ];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full block">
      <defs>
        <linearGradient id="flow-line" x1="0" x2="1">
          <stop offset="0%" stopColor="var(--color-acid)" stopOpacity="0.5" />
          <stop offset="50%" stopColor="var(--color-amber)" stopOpacity="0.5" />
          <stop offset="100%" stopColor="var(--color-rose)" stopOpacity="0.5" />
        </linearGradient>
      </defs>
      <line
        x1={STAGE_X[0]}
        y1={Y}
        x2={STAGE_X[2]}
        y2={Y}
        stroke="url(#flow-line)"
        strokeWidth={1.5}
        strokeDasharray="3 4"
      />
      {STAGES.map((s, i) => {
        const isActive =
          (active === "classify" && i === 0) ||
          (active === "draft" && i === 1) ||
          (active === "escalate" && i === 2);
        return (
          <g key={i}>
            <circle
              cx={s.x}
              cy={Y}
              r={isActive ? 18 : 14}
              fill="var(--color-bg)"
              stroke={s.color}
              strokeWidth={1.5}
              style={{ filter: `drop-shadow(0 0 8px ${s.color})` }}
            />
            <circle cx={s.x} cy={Y} r={4} fill={s.color} />
            <text
              x={s.x}
              y={Y - 26}
              textAnchor="middle"
              fill={s.color}
              fontSize="9"
              fontFamily="var(--font-mono)"
              letterSpacing="0.16em"
              style={{ filter: `drop-shadow(0 0 4px ${s.color})` }}
            >
              {s.label}
            </text>
            <text
              x={s.x}
              y={Y + 30}
              textAnchor="middle"
              fill="var(--color-fg-mute)"
              fontSize="9"
              fontFamily="var(--font-mono)"
            >
              {s.n}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
