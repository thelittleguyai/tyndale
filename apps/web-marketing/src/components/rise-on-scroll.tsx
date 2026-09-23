'use client';

/**
 * Rise-on-scroll entrances (Landing Motion Parity, Phase A — 2026-09-23). Any element with a
 * `data-rise` attribute rises 12 px and fades in (`tyn-rise`, globals.css) the first time it
 * enters the viewport; siblings that arrive together are staggered 75 ms apart. One observer
 * for the whole page, mounted once from the landing — the bands themselves stay server
 * components and only carry the attribute.
 *
 * Safety first, then motion:
 *  - Nothing is hidden until THIS code runs and confirms it can reveal things again. The CSS
 *    hides `[data-rise]` only under `@media (scripting: enabled)`, and this component bails
 *    (leaving everything visible, static) when that media query is unsupported, when the
 *    visitor asked for reduced motion, or when IntersectionObserver is missing. There is no
 *    build in which content can be left at opacity 0.
 *  - Opacity/transform only — never layout. Never applied to an element with `backdrop-filter`
 *    (there are none on the page by rule; the guard test keeps it so).
 */
import { useEffect } from 'react';

const STAGGER_MS = 75;

export function RiseOnScroll() {
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    if (!window.matchMedia('(scripting: enabled)').matches) return; // old engines: static
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const targets = Array.from(document.querySelectorAll<HTMLElement>('[data-rise]'));
    if (targets.length === 0) return;

    const io = new IntersectionObserver(
      (entries) => {
        /* Group this batch by parent, in DOM order, so siblings stagger and a lone
           late-comer starts at once. */
        const byParent = new Map<Element | null, HTMLElement[]>();
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const el = e.target as HTMLElement;
          const list = byParent.get(el.parentElement) ?? [];
          list.push(el);
          byParent.set(el.parentElement, list);
        }
        for (const list of byParent.values()) {
          list.sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
          list.forEach((el, i) => {
            el.style.animationDelay = `${i * STAGGER_MS}ms`;
            el.setAttribute('data-rise', 'in');
            io.unobserve(el);
          });
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' },
    );
    targets.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return null;
}
