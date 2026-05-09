import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Toaster } from "sonner";
import { Nav } from "@/components/shared/nav";
import { Footer } from "@/components/shared/footer";
import "./globals.css";

export const metadata: Metadata = {
  title: "Inbox Agent, agentic customer support",
  description:
    "Tool-forced JSON. Calibrated confidence. RAG-grounded drafts. Real cost accounting. Eval-gated CI. Built like a product.",
  authors: [{ name: "Amir Dhibi" }],
  openGraph: {
    title: "Inbox Agent, agentic customer support",
    description:
      "Classify · draft · escalate. Tool-forced JSON, calibrated confidence, eval-gated CI.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#050608",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable}`}
    >
      <body className="min-h-dvh bg-[var(--color-bg)] text-[var(--color-fg)] antialiased">
        <Nav />
        <main>{children}</main>
        <Footer />
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            classNames: {
              toast:
                "!bg-[var(--color-panel)] !border-[var(--color-line)] !text-[var(--color-fg)] !font-mono",
            },
          }}
        />
      </body>
    </html>
  );
}
