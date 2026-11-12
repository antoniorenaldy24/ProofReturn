import type { Metadata, Viewport } from "next";
// Self-hosted variable fonts (no build-time fetch to Google's servers).
// The @font-face rules live in node_modules and register:
//   'Instrument Sans Variable' (wght 400–700)
//   'JetBrains Mono Variable'  (wght 100–800)
// The --font-instrument / --font-jbmono CSS variables they feed are
// declared in globals.css :root.
import "@fontsource-variable/instrument-sans/wght.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "./globals.css";
import { DemoProvider } from "@/lib/demo-context";
import { DemoNavbar } from "@/components/demo-navbar";

export const metadata: Metadata = {
  title: "ProofReturn — Unified Demonstration Suite",
  description:
    "An end-to-end interactive demonstration of the ProofReturn protocol: Storefront with CIRC, Packing Station passport minting, Shopper Portal 30s forensic challenge, and Merchant Risk Console.",
  keywords: [
    "ProofReturn",
    "demo storefront",
    "refund curve",
    "CIRC",
    "condition passport",
    "open-box",
    "transparency",
  ],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#FAFAF7",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased bg-paper text-ink">
        <DemoProvider>
          <DemoNavbar />
          {children}
        </DemoProvider>
      </body>
    </html>
  );
}
