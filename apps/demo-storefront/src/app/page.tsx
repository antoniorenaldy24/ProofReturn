import { Nav } from "@/components/chrome/nav";
import { Cursor } from "@/components/chrome/cursor";
import { Toasts } from "@/components/chrome/toasts";
import { Ticker } from "@/components/chrome/ticker";
import { JourneyStrip, JourneyRail } from "@/components/chrome/journey";
import { Footer } from "@/components/footer";
import { HeroStage } from "@/components/hero/hero-stage";
import { CircConsole } from "@/components/circ/circ-console";
import { PassportRig } from "@/components/passport/passport-rig";
import { CheckoutBay } from "@/components/checkout/checkout-bay";
import { TICKER_A, TICKER_B } from "@/lib/data";

/**
 * ProofReturn — Demo Storefront · LIVING LAB
 * Single route, purely client-side simulation. All fixtures live in lib/data.ts.
 * The four sections carry a color each: orange → indigo → teal → green.
 */
export default function Page() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="flex-1">
        <HeroStage />
        <JourneyStrip />
        <Ticker items={TICKER_A} />
        <CircConsole />
        <Ticker items={TICKER_B} />
        <PassportRig />
        <CheckoutBay />
      </main>
      <Footer />
      <JourneyRail />
      <Cursor />
      <Toasts />
    </div>
  );
}
