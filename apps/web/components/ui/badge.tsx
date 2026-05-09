"use client";

import { forwardRef, type HTMLAttributes } from "react";
import { tv, type VariantProps } from "tailwind-variants";

const badge = tv({
  base: [
    "inline-flex items-center gap-1.5",
    "h-5 px-2 rounded-sm",
    "text-[10.5px] font-mono font-medium",
    "uppercase tracking-[0.12em]",
    "border",
    "transition-colors duration-150",
  ],
  variants: {
    tone: {
      neutral:
        "bg-[var(--color-panel-2)] text-[var(--color-fg-dim)] border-[var(--color-line-2)]",
      acid:
        "bg-[var(--color-acid-soft)] text-[var(--color-acid)] border-[oklch(80%_0.22_165/0.4)]",
      amber:
        "bg-[var(--color-amber-soft)] text-[var(--color-amber)] border-[oklch(80%_0.18_75/0.4)]",
      rose:
        "bg-[var(--color-rose-soft)] text-[var(--color-rose)] border-[oklch(70%_0.22_25/0.4)]",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badge> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, tone, ...props }, ref) => (
    <span ref={ref} className={badge({ tone, className })} {...props} />
  ),
);
Badge.displayName = "Badge";
