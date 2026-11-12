"use client";

/**
 * ProofReturn global ledger state — deliberately tiny and honest:
 * this is a front-end simulation, so state lives in memory only.
 */

import { create } from "zustand";
import { PRODUCT } from "@/lib/data";

export type StampToast = {
  id: number;
  kind: "ink" | "green" | "red";
  title: string;
  line?: string;
};

export type SealedOrder = {
  ref: string;
  tx: string;
  sealedAt: string;
  total: number;
};

type LedgerState = {
  /** units of the single demo product in the ledger (0..3) */
  qty: number;
  /** set once the Condition Passport verification sequence completes */
  passportVerified: boolean;
  toasts: StampToast[];
  lastOrder: SealedOrder | null;

  stamp: (qty: number) => void;
  setQty: (qty: number) => void;
  removeFromLedger: () => void;
  setPassportVerified: () => void;
  pushToast: (t: Omit<StampToast, "id">) => void;
  dismissToast: (id: number) => void;
  sealOrder: (order: SealedOrder) => void;
};

let toastId = 0;

export const useLedger = create<LedgerState>((set, get) => ({
  qty: 0,
  passportVerified: false,
  toasts: [],
  lastOrder: null,

  stamp: (qty) => {
    set({ qty: Math.min(3, Math.max(0, get().qty + qty)) });
    get().pushToast({
      kind: "green",
      title: "Stamped to ledger",
      line: `${PRODUCT.name} × ${get().qty} · ${PRODUCT.sku}`,
    });
  },

  setQty: (qty) => set({ qty: Math.min(3, Math.max(0, qty)) }),

  removeFromLedger: () => {
    set({ qty: 0 });
    get().pushToast({ kind: "red", title: "Struck from ledger", line: "The object was removed." });
  },

  setPassportVerified: () => {
    if (get().passportVerified) return;
    set({ passportVerified: true });
    get().pushToast({
      kind: "green",
      title: "Passport seal verified — demo",
      line: "Fast-Lane eligibility updated in the Counting House.",
    });
  },

  pushToast: (t) => {
    const id = ++toastId;
    set({ toasts: [...get().toasts, { ...t, id }] });
    window.setTimeout(() => get().dismissToast(id), 3200);
  },

  dismissToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),

  sealOrder: (order) => {
    set({ lastOrder: order, qty: 0 });
  },
}));
