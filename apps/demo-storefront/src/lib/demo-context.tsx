"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export interface DemoOrder {
  id: string;
  sku: string;
  name: string;
  priceMinor: number;
  status: "CHECKOUT_PENDING" | "FULFILLED" | "RETURN_REQUESTED" | "REFUNDED_R0" | "CLOSED";
  timestamp: string;
}

export interface DemoPassport {
  id: string;
  serialNumber: string;
  serialHash: string;
  weightGrams: number;
  originNonce: string;
  tier: "FULL" | "LITE" | "NONE";
  mintedAt: string;
  sealIntact: boolean;
  functionalSelfTestPassed: boolean;
}

export interface DemoReturnClaim {
  returnId: string;
  declaredGrade: "A" | "B" | "C" | "D" | "DEF";
  accessories: { case: boolean; cable: boolean; adapter: boolean };
  lane: "FAST" | "STANDARD" | "ESCALATED";
  timing: "R0" | "R1" | "ESC";
  r0TrancheMinor: number;
  holdbackMinor: number;
  refundStatus: "NONE" | "DECLARED" | "EVIDENCE_SUBMITTED" | "R0_SETTLED" | "CANCELLED";
  forensicCaptured: boolean;
  forensicHash: string;
  submittedAt?: string;
  plainLanguageExplanation: string;
}

export interface DemoDockCheckIn {
  actualWeightGrams: number;
  observedGrade: "A" | "B" | "C" | "D" | "DEF";
  sealIntact: boolean;
  status: "PENDING" | "PASSED" | "DISCREPANCY_FLAGGED";
  verifiedAt?: string;
}

export interface DemoPolicy {
  id: string;
  misdeclarationFeeMinor: number;
  gradeDiscounts: Record<string, number>;
}

export interface DemoState {
  order: DemoOrder;
  passport: DemoPassport;
  returnClaim: DemoReturnClaim;
  dockCheckin: DemoDockCheckIn;
  policy: DemoPolicy;
  kpis: {
    totalVolume: number;
    capitalReleasedMinor: number;
    holdbackRetainedMinor: number;
    fraudPreventedMinor: number;
  };
}

const DEFAULT_DEMO_STATE: DemoState = {
  order: {
    id: "ord_demo_1",
    sku: "PR-HP-XM5",
    name: "Sony WH-1000XM5 Wireless Headphones",
    priceMinor: 38000,
    status: "FULFILLED",
    timestamp: "2026-11-10T14:22:00Z",
  },
  passport: {
    id: "pass_demo_1",
    serialNumber: "SN-DEMO-XM5-001",
    serialHash: "3ea4d6ef259b7fb85f40f0980cf7bc51b0e50e93de7eb0fc4dc0cf3fbf285f20",
    weightGrams: 250.0,
    originNonce: "NONCE-ORIGIN-77",
    tier: "FULL",
    mintedAt: "2026-11-10T14:25:30Z",
    sealIntact: true,
    functionalSelfTestPassed: true,
  },
  returnClaim: {
    returnId: "ret_demo_1",
    declaredGrade: "B",
    accessories: { case: true, cable: true, adapter: true },
    lane: "FAST",
    timing: "R0",
    r0TrancheMinor: 36500, // $380 - $15 holdback
    holdbackMinor: 1500,  // $15 fee
    refundStatus: "NONE",
    forensicCaptured: false,
    forensicHash: "",
    plainLanguageExplanation: "Fast-Lane R0: Condition B verified with intact tamper seal. Instant release $365.00 with $15.00 misdeclaration holdback.",
  },
  dockCheckin: {
    actualWeightGrams: 249.8,
    observedGrade: "B",
    sealIntact: true,
    status: "PENDING",
  },
  policy: {
    id: "pol_electronics_us_v1",
    misdeclarationFeeMinor: 1500,
    gradeDiscounts: { A: 1.0, B: 0.95, C: 0.8, D: 0.5, DEF: 0.0 },
  },
  kpis: {
    totalVolume: 1420,
    capitalReleasedMinor: 31245000,
    holdbackRetainedMinor: 6420000,
    fraudPreventedMinor: 4890000,
  },
};

const STORAGE_KEY = "proofreturn_demo_suite_state_v1";

interface DemoContextValue {
  state: DemoState;
  resetDemo: () => void;
  setOrderPaid: (orderId: string) => void;
  mintPassport: (draft: Partial<DemoPassport>) => void;
  declareReturn: (grade: "A" | "B" | "C" | "D" | "DEF", accessories: { case: boolean; cable: boolean; adapter: boolean }) => void;
  submitEvidence: (hash: string) => void;
  settleR0Refund: () => void;
  cancelReturn: () => void;
  processDockCheckIn: (passed: boolean, actualWeight: number, grade: "A" | "B" | "C" | "D" | "DEF") => void;
}

const DemoContext = createContext<DemoContextValue | undefined>(undefined);

export function DemoProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<DemoState>(DEFAULT_DEMO_STATE);
  const [isLoaded, setIsLoaded] = useState(false);

  // Rehydrate state from localStorage ONLY on client mount (prevents SSR hydration error)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        setState(JSON.parse(saved));
      }
    } catch (e) {
      console.error("Failed to restore demo state from storage", e);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  // Persist state updates to localStorage only after initial client mount
  useEffect(() => {
    if (isLoaded && typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch (e) {
        console.error("Failed to save demo state to storage", e);
      }
    }
  }, [state, isLoaded]);

  const resetDemo = () => {
    setState(DEFAULT_DEMO_STATE);
    if (typeof window !== "undefined") {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (e) {
        console.error("Failed to clear demo storage", e);
      }
    }
  };

  const setOrderPaid = (orderId: string) => {
    setState((prev) => ({
      ...prev,
      order: {
        ...prev.order,
        id: orderId || prev.order.id,
        status: "FULFILLED",
      },
    }));
  };

  const mintPassport = (draft: Partial<DemoPassport>) => {
    const newPassport: DemoPassport = {
      ...state.passport,
      ...draft,
      id: draft.id || `pass_${Date.now()}`,
      mintedAt: new Date().toISOString(),
    };
    setState((prev) => ({
      ...prev,
      passport: newPassport,
    }));
  };

  const declareReturn = (
    grade: "A" | "B" | "C" | "D" | "DEF",
    accessories: { case: boolean; cable: boolean; adapter: boolean }
  ) => {
    setState((prev) => ({
      ...prev,
      order: { ...prev.order, status: "RETURN_REQUESTED" },
      returnClaim: {
        ...prev.returnClaim,
        declaredGrade: grade,
        accessories,
        refundStatus: "DECLARED",
      },
    }));
  };

  const submitEvidence = (hash: string) => {
    setState((prev) => ({
      ...prev,
      returnClaim: {
        ...prev.returnClaim,
        forensicCaptured: true,
        forensicHash: hash,
        refundStatus: "EVIDENCE_SUBMITTED",
      },
    }));
  };

  const settleR0Refund = () => {
    setState((prev) => ({
      ...prev,
      order: { ...prev.order, status: "REFUNDED_R0" },
      returnClaim: {
        ...prev.returnClaim,
        refundStatus: "R0_SETTLED",
      },
      kpis: {
        ...prev.kpis,
        capitalReleasedMinor: prev.kpis.capitalReleasedMinor + prev.returnClaim.r0TrancheMinor,
        holdbackRetainedMinor: prev.kpis.holdbackRetainedMinor + prev.returnClaim.holdbackMinor,
      },
    }));
  };

  const cancelReturn = () => {
    setState((prev) => ({
      ...prev,
      order: { ...prev.order, status: "FULFILLED" },
      returnClaim: {
        ...prev.returnClaim,
        refundStatus: "CANCELLED",
      },
    }));
  };

  const processDockCheckIn = (
    passed: boolean,
    actualWeight: number,
    grade: "A" | "B" | "C" | "D" | "DEF"
  ) => {
    setState((prev) => ({
      ...prev,
      dockCheckin: {
        actualWeightGrams: actualWeight,
        observedGrade: grade,
        sealIntact: passed,
        status: passed ? "PASSED" : "DISCREPANCY_FLAGGED",
        verifiedAt: new Date().toISOString(),
      },
      order: {
        ...prev.order,
        status: "CLOSED",
      },
    }));
  };

  return (
    <DemoContext.Provider
      value={{
        state,
        resetDemo,
        setOrderPaid,
        mintPassport,
        declareReturn,
        submitEvidence,
        settleR0Refund,
        cancelReturn,
        processDockCheckIn,
      }}
    >
      {children}
    </DemoContext.Provider>
  );
}

export function useDemoContext() {
  const ctx = useContext(DemoContext);
  if (!ctx) {
    throw new Error("useDemoContext must be used within a DemoProvider");
  }
  return ctx;
}
