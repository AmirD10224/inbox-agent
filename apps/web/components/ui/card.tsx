"use client";

import { type HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  glow?: "acid" | "amber" | "rose" | null;
  hover?: boolean;
}

export function Card({
  className,
  glow = null,
  hover = false,
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        "panel",
        glow === "acid" && "panel-glow-acid",
        glow === "amber" && "panel-glow-amber",
        glow === "rose" && "panel-glow-rose",
        hover && "transition-colors hover:bg-[var(--color-panel-2)]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

interface PanelTitleProps extends HTMLAttributes<HTMLDivElement> {
  label: string;
  meta?: React.ReactNode;
  tone?: "acid" | "amber" | "rose" | "mute";
}

export function PanelTitle({
  label,
  meta,
  tone = "acid",
  className,
  ...props
}: PanelTitleProps) {
  const headerCls = {
    acid: "panel-header",
    amber: "panel-header panel-header-amber",
    rose: "panel-header panel-header-rose",
    mute: "panel-header panel-header-mute",
  }[tone];
  return (
    <div className={cn(headerCls, "justify-between", className)} {...props}>
      <span className="font-medium text-[var(--color-fg-dim)]">{label}</span>
      {meta && (
        <span className="tabular text-[var(--color-fg-mute)] normal-case font-mono">
          {meta}
        </span>
      )}
    </div>
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}

export function StatusDot({
  tone = "acid",
  pulse: shouldPulse = false,
  className,
}: {
  tone?: "acid" | "amber" | "rose" | "neutral";
  pulse?: boolean;
  className?: string;
}) {
  const colorVar = {
    acid: "var(--color-acid)",
    amber: "var(--color-amber)",
    rose: "var(--color-rose)",
    neutral: "var(--color-fg-mute)",
  }[tone];
  return (
    <span
      className={cn("relative inline-block h-1.5 w-1.5 rounded-full", className)}
      style={{
        background: colorVar,
        boxShadow: tone === "neutral" ? "none" : `0 0 8px ${colorVar}`,
      }}
      aria-hidden
    >
      {shouldPulse && (
        <span
          className="absolute inset-0 rounded-full pulse"
          style={{ background: colorVar }}
        />
      )}
    </span>
  );
}
