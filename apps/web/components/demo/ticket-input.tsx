"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { cn } from "@/lib/cn";
import { Card, PanelTitle } from "@/components/ui/card";

interface TicketInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  placeholder?: string;
}

export function TicketInput({
  value,
  onChange,
  onSubmit,
  loading,
  placeholder = "Paste a customer ticket…",
}: TicketInputProps) {
  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && value.trim() && !loading) {
      e.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="space-y-3">
      <Card glow="acid">
        <PanelTitle
          label="Ticket input"
          meta={`${value.length.toString().padStart(4, "0")} chars`}
        />
        <div className="flex">
          <span className="font-mono text-[14px] text-[var(--color-acid)] py-3.5 pl-4 select-none leading-[1.65] glow-acid">
            ▸
          </span>
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKey}
            disabled={loading}
            placeholder={placeholder}
            rows={5}
            className={cn(
              "w-full resize-none bg-transparent px-3 py-3.5 outline-none",
              "font-mono text-[13.5px] leading-[1.65] text-[var(--color-fg)]",
              "placeholder:text-[var(--color-fg-faint)] disabled:opacity-50",
            )}
          />
        </div>
      </Card>

      <div className="flex items-center justify-between gap-3">
        <p className="text-[11.5px] text-[var(--color-fg-mute)] flex items-center gap-1.5 font-mono">
          <kbd className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded border border-[var(--color-line-2)] text-[10.5px] tabular">
            ⌘
          </kbd>
          <kbd className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded border border-[var(--color-line-2)] text-[10.5px] tabular">
            ↵
          </kbd>
          <span className="ml-2 uppercase tracking-tight">
            to execute · 3 LLM calls · ≈ $0.008
          </span>
        </p>
        <button
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          className="btn-primary group disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              >
                <Loader2 className="size-3.5" />
              </motion.span>
              <span className="uppercase tracking-[0.12em]">Running</span>
            </>
          ) : (
            <>
              <span className="uppercase tracking-[0.12em]">Execute</span>
              <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
