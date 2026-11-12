"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/**
 * Scroll orchestration — every plate rises into register, and every
 * engraved rule draws itself left to right as it enters the press.
 */
export function ScrollInk({ children }: { children: React.ReactNode }) {
  const scope = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scope.current;
    if (!el) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    gsap.registerPlugin(ScrollTrigger);
    const ctx = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>("[data-reveal]", el).forEach((node) => {
        gsap.fromTo(
          node,
          { y: 26, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.85,
            ease: "power3.out",
            delay: Number(node.dataset.delay ?? 0),
            scrollTrigger: { trigger: node, start: "top 88%", once: true },
          },
        );
      });
      gsap.utils.toArray<HTMLElement>(".rule-draw", el).forEach((node) => {
        gsap.fromTo(
          node,
          { scaleX: 0 },
          {
            scaleX: 1,
            duration: 1.1,
            ease: "power2.inOut",
            scrollTrigger: { trigger: node, start: "top 92%", once: true },
          },
        );
      });
      gsap.utils.toArray<HTMLElement>("[data-parallax]", el).forEach((node) => {
        const strength = Number(node.dataset.parallax ?? 40);
        gsap.to(node, {
          y: -strength,
          ease: "none",
          scrollTrigger: {
            trigger: node,
            start: "top bottom",
            end: "bottom top",
            scrub: 0.6,
          },
        });
      });
    }, el);

    return () => ctx.revert();
  }, []);

  return (
    <div ref={scope} className="contents">
      {children}
    </div>
  );
}
