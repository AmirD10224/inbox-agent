import Image from "next/image";
import Link from "next/link";
import { StatusDot } from "@/components/ui/card";

export function Footer() {
  return (
    <footer className="border-t border-[var(--color-line)] bg-[var(--color-panel)] mt-12">
      <div className="max-w-[1280px] mx-auto px-5 grid grid-cols-1 md:grid-cols-[1.4fr_1fr_1fr_1fr] gap-10 py-10">
        <div>
          <Link href="/" className="flex items-center gap-2.5">
            <Image src="/logo.svg" alt="inbox-agent" width={28} height={9} className="h-[9px] w-auto" />
            <span className="text-[14px] font-semibold tracking-tight uppercase">
              Inbox Agent
            </span>
          </Link>
          <p className="mt-4 max-w-xs text-[12.5px] leading-[1.55] text-[var(--color-fg-mute)]">
            Small AI support agent. Three Sonnet calls, FAQ retrieval,
            eval gate in CI.
          </p>
        </div>

        <FooterCol title="Product">
          <FooterLink href="/dashboard">Dashboard</FooterLink>
          <FooterLink href="https://github.com/AmirD10224/inbox-agent" external>
            Source
          </FooterLink>
          <FooterLink
            href="https://github.com/AmirD10224/inbox-agent/blob/main/ARCHITECTURE.md"
            external
          >
            Architecture
          </FooterLink>
        </FooterCol>

        <FooterCol title="Stack">
          <FooterItem>Claude Sonnet 4.6</FooterItem>
          <FooterItem>Voyage-3</FooterItem>
          <FooterItem>pgvector</FooterItem>
          <FooterItem>Langfuse</FooterItem>
        </FooterCol>

        <FooterCol title="Maintainer">
          <FooterItem>Amir Dhibi</FooterItem>
        </FooterCol>
      </div>

      <div className="border-t border-[var(--color-line)]">
        <div className="max-w-[1280px] mx-auto px-5 h-10 flex items-center gap-4 text-[11px] font-mono text-[var(--color-fg-mute)]">
          <span className="flex items-center gap-1.5">
            <StatusDot tone="acid" pulse />
            <span className="text-[var(--color-acid)]">Connected</span>
            <span className="text-[var(--color-fg-mute)]">· /v1/agent</span>
          </span>
          <span className="h-4 w-px bg-[var(--color-line-2)]" />
          <span>v0.1.0 · MIT · 2026</span>
          <span className="ml-auto hidden md:inline tabular">
            mypy --strict · ruff · 75% coverage gate · eval-gated CI
          </span>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10.5px] font-mono uppercase tracking-[0.16em] text-[var(--color-fg-mute)] mb-3">
        {title}
      </p>
      <ul className="space-y-2">{children}</ul>
    </div>
  );
}

function FooterItem({ children }: { children: React.ReactNode }) {
  return <li className="text-[12.5px] text-[var(--color-fg-dim)]">{children}</li>;
}

function FooterLink({
  href,
  children,
  external = false,
}: {
  href: string;
  children: React.ReactNode;
  external?: boolean;
}) {
  return (
    <li>
      <a
        href={href}
        {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
        className="text-[12.5px] text-[var(--color-fg-dim)] hover:text-[var(--color-fg)] transition-colors"
      >
        {children}
      </a>
    </li>
  );
}
