"use client";

import { motion } from "motion/react";
import { Check } from "lucide-react";
import { samples, type Sample } from "@/lib/samples";
import { cn } from "@/lib/cn";

interface SamplePickerProps {
  active: number | null;
  onSelect: (idx: number, sample: Sample) => void;
}

export function SamplePicker({ active, onSelect }: SamplePickerProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-px bg-[var(--color-line)] border border-[var(--color-line)] rounded-md overflow-hidden">
      {samples.map((s, idx) => {
        const isActive = active === idx;
        const tag = (s.label.split(". ")[0] || s.label).toLowerCase();
        const title = s.label.split(". ")[1] || s.label;
        return (
          <motion.button
            key={s.label}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.04 * idx, duration: 0.3 }}
            onClick={() => onSelect(idx, s)}
            className={cn(
              "group relative text-left p-4 transition-colors duration-150 cursor-pointer",
              "bg-[var(--color-panel)]",
              isActive
                ? "bg-[var(--color-panel-hi)]"
                : "hover:bg-[var(--color-panel-2)]",
            )}
            style={
              isActive
                ? {
                    boxShadow: `inset 0 0 0 1px var(--color-acid), 0 0 24px -8px var(--color-acid)`,
                  }
                : undefined
            }
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase tracking-[0.14em] text-[var(--color-acid)]">
                CASE.{String(idx + 1).padStart(2, "0")}
              </span>
              <span className="text-[10px] font-mono uppercase tracking-tight text-[var(--color-fg-mute)]">
                {tag}
              </span>
            </div>
            <p className="text-[12.5px] font-medium text-[var(--color-fg)] leading-snug font-sans">
              {title}
            </p>
            {isActive && (
              <span
                className="absolute top-2.5 right-2.5 text-[var(--color-acid)]"
                aria-hidden
              >
                <Check className="size-3" strokeWidth={3} />
              </span>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}
