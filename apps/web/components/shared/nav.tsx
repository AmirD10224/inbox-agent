"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Github } from "lucide-react";
import { StatusDot } from "@/components/ui/card";

export function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--color-line)] bg-[var(--color-bg)]/85 backdrop-blur-md">
      <div className="max-w-[1280px] mx-auto px-5 h-11 flex items-center gap-5 text-[11.5px]">
        <Link href="/" className="flex items-center gap-2.5">
          <Image src="/logo.svg" alt="inbox-agent" width={28} height={9} priority className="h-[9px] w-auto" />
          <span className="font-semibold tracking-tight uppercase text-[var(--color-fg)]">
            Inbox Agent
          </span>
          <span className="text-[var(--color-fg-faint)]">/</span>
          <span className="text-[var(--color-fg-mute)] uppercase tracking-tight">
            Operator
          </span>
        </Link>

        <span className="h-4 w-px bg-[var(--color-line-2)]" />

        <span className="flex items-center gap-1.5">
          <StatusDot tone="acid" pulse />
          <span className="text-[var(--color-acid)] glow-acid font-medium">ONLINE</span>
        </span>

        <span className="h-4 w-px bg-[var(--color-line-2)]" />
        <span className="text-[var(--color-fg-mute)] uppercase tracking-tight hidden md:inline tabular">
          v0.1.0 · 73 / 73 tests · 92.95% cov
        </span>

        <span className="ml-auto flex items-center gap-3">
          <span className="text-[var(--color-fg-mute)] uppercase tracking-tight hidden sm:inline">
            UTC
          </span>
          <span className="text-[var(--color-acid)] glow-acid font-medium tabular">
            <Clock />
          </span>
          <span className="h-4 w-px bg-[var(--color-line-2)]" />
          <NavLink href="/dashboard" label="Dashboard" />
          <a
            href="https://github.com/AmirD10224/inbox-agent"
            target="_blank"
            rel="noreferrer"
            aria-label="GitHub"
            className="inline-flex h-7 w-7 items-center justify-center rounded text-[var(--color-fg-mute)] hover:text-[var(--color-fg)] hover:bg-[var(--color-panel-2)] transition-colors"
          >
            <Github className="size-3.5" />
          </a>
          <Link
            href={"/#try" as never}
            className="inline-flex items-center px-3 h-7 text-[11px] font-mono font-semibold uppercase tracking-[0.12em] bg-[var(--color-acid)] text-[var(--color-bg)] hover:bg-[var(--color-acid-glow)] transition-colors rounded-sm"
          >
            Try it
          </Link>
        </span>
      </div>
    </header>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href as never}
      className="hidden sm:inline-flex items-center px-2 h-7 text-[11px] text-[var(--color-fg-dim)] hover:text-[var(--color-fg)] uppercase tracking-[0.12em] font-mono rounded-sm hover:bg-[var(--color-panel-2)] transition-colors"
    >
      {label}
    </Link>
  );
}

function Clock() {
  const [now, setNow] = useState<string>("");
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setNow(
        [
          d.getUTCHours().toString().padStart(2, "0"),
          d.getUTCMinutes().toString().padStart(2, "0"),
          d.getUTCSeconds().toString().padStart(2, "0"),
        ].join(":") + "Z",
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="tabular">{now || "00:00:00Z"}</span>;
}
