"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { RotateCcw, ShieldCheck, Box, Package, UserCheck, LayoutDashboard } from "lucide-react";
import { useDemoContext } from "@/lib/demo-context";
import { cn } from "@/lib/utils";

const PERSONAS = [
  {
    num: "01",
    label: "Storefront",
    subtitle: "The Note",
    href: "/",
    icon: Box,
    accent: "#d63a00", // signature orange
  },
  {
    num: "02",
    label: "Packing Station",
    subtitle: "The Mint",
    href: "/packing",
    icon: Package,
    accent: "#0d9488", // teal
  },
  {
    num: "03",
    label: "Shopper Return",
    subtitle: "The Claim",
    href: "/shopper",
    icon: UserCheck,
    accent: "#4f46e5", // indigo
  },
  {
    num: "04",
    label: "Merchant Console",
    subtitle: "The Ledger",
    href: "/merchant",
    icon: LayoutDashboard,
    accent: "#0c7a44", // green
  },
];

export function DemoNavbar() {
  const pathname = usePathname();
  const { state, resetDemo } = useDemoContext();
  const [backendLive, setBackendLive] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    const checkBackend = async () => {
      try {
        const res = await fetch("/api/backend/ready", {
          method: "GET",
          headers: { Accept: "application/json" },
          signal: AbortSignal.timeout(2500),
        });
        if (active) setBackendLive(res.ok);
      } catch {
        // Fallback direct check
        try {
          const direct = await fetch("http://localhost:8000/v1/ready", {
            method: "GET",
            headers: { Accept: "application/json" },
            signal: AbortSignal.timeout(2000),
          });
          if (active) setBackendLive(direct.ok);
        } catch {
          if (active) setBackendLive(false);
        }
      }
    };
    checkBackend();
    const interval = setInterval(checkBackend, 8000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const getOrderStatusBadge = () => {
    switch (state.order.status) {
      case "CHECKOUT_PENDING":
        return { text: "PENDING", color: "text-warn border-warn/40 bg-warn/10" };
      case "FULFILLED":
        return { text: "ORDER ACTIVE", color: "text-ok border-ok/40 bg-ok/10" };
      case "RETURN_REQUESTED":
        return { text: "RETURN FILED", color: "text-indigo border-indigo/40 bg-indigo/10" };
      case "REFUNDED_R0":
        return { text: "R0 REFUNDED", color: "text-sig border-sig/40 bg-sig/10" };
      case "CLOSED":
        return { text: "DOCK VERIFIED", color: "text-teal border-teal/40 bg-teal/10" };
      default:
        return { text: "ACTIVE", color: "text-faint border-line bg-panel-2" };
    }
  };

  const badge = getOrderStatusBadge();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-line bg-paper/90 backdrop-blur-md">
      {/* Top micro-strip for security network branding */}
      <div className="flex h-11 items-center justify-between border-b border-line/60 px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="group flex items-center gap-2">
            <span className="relative flex h-5 w-5 items-center justify-center rounded border border-sig/60 bg-paper">
              <span className="h-1.5 w-1.5 rounded-sm bg-sig transition-transform duration-200 group-hover:scale-125" />
            </span>
            <span className="font-display text-xs font-bold tracking-tight text-ink uppercase">
              ProofReturn
            </span>
          </Link>
          {backendLive ? (
            <span className="hidden items-center gap-1.5 rounded-full border border-ok/40 bg-ok/10 px-2.5 py-0.5 font-tech text-[9px] font-semibold tracking-wider text-ok md:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-ok animate-pulse" />
              BACKEND LIVE (:8000)
            </span>
          ) : (
            <span className="hidden items-center gap-1.5 rounded-full border border-line bg-panel-2 px-2.5 py-0.5 font-tech text-[9px] font-medium tracking-wider text-dim md:flex" title="Run 'uv run uvicorn backend.api.app:app --port 8000' to connect live API">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              DEMO SIMULATION (STANDALONE)
            </span>
          )}
        </div>

        {/* Live Active Order Status Pill & Reset */}
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-2 rounded-full border border-line bg-panel px-2.5 py-1 font-tech text-[10px]">
            <span className="text-faint hidden sm:inline">DEMO CONTEXT:</span>
            <span className="font-semibold text-ink">{state.order.id}</span>
            <span className="text-dim">(${(state.order.priceMinor / 100).toFixed(2)})</span>
            <span
              className={cn(
                "rounded border px-1.5 py-0.2 font-semibold uppercase text-[8px] tracking-widest",
                badge.color
              )}
            >
              {badge.text}
            </span>
          </div>

          <button
            onClick={() => {
              if (confirm("Reset demo data to initial state?")) {
                resetDemo();
              }
            }}
            title="Reset Demo Scenario"
            className="flex items-center gap-1 rounded-full border border-line bg-panel hover:bg-panel-2 hover:border-sig/40 px-2 py-1 font-tech text-[10px] text-dim hover:text-ink transition-colors cursor-pointer"
          >
            <RotateCcw className="h-2.5 w-2.5" />
            <span className="hidden sm:inline">Reset</span>
          </button>
        </div>
      </div>

      {/* Main Persona Switcher Bar */}
      <nav aria-label="Demo Persona Switcher" className="px-4 sm:px-6">
        <div className="mx-auto flex h-12 max-w-[1500px] items-center justify-start sm:justify-center overflow-x-auto gap-1 sm:gap-2 no-scrollbar">
          {PERSONAS.map((p) => {
            const isActive =
              p.href === "/"
                ? pathname === "/"
                : pathname?.startsWith(p.href);

            const Icon = p.icon;

            return (
              <Link
                key={p.num}
                href={p.href}
                className={cn(
                  "group relative flex items-center gap-2 rounded-lg px-3 py-1.5 text-left transition-all duration-200 whitespace-nowrap",
                  isActive
                    ? "bg-panel shadow-xs border border-line"
                    : "hover:bg-panel/60 text-dim hover:text-ink"
                )}
              >
                <div
                  className={cn(
                    "grid h-6 w-6 place-items-center rounded border transition-colors",
                    isActive
                      ? "border-current bg-panel-2 text-ink"
                      : "border-line bg-paper text-faint group-hover:text-dim"
                  )}
                  style={{ color: isActive ? p.accent : undefined }}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>

                <div className="flex flex-col">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="font-tech text-[9px] font-semibold tracking-wider"
                      style={{ color: isActive ? p.accent : undefined }}
                    >
                      {p.num}
                    </span>
                    <span
                      className={cn(
                        "font-display text-[12px] font-medium tracking-tight",
                        isActive ? "text-ink font-semibold" : "text-dim group-hover:text-ink"
                      )}
                    >
                      {p.label}
                    </span>
                  </div>
                  <span className="font-tech text-[8px] uppercase tracking-widest text-faint -mt-0.5">
                    {p.subtitle}
                  </span>
                </div>

                {isActive && (
                  <span
                    className="absolute bottom-0 inset-x-3 h-[2px] rounded-full"
                    style={{ backgroundColor: p.accent }}
                  />
                )}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
