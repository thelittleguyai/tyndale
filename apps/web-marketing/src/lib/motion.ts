'use client';

/**
 * The landing's two motion primitives (Landing Motion Parity, Phase A — 2026-09-23).
 *
 * Every animated set-piece on the page starts when it is actually on screen and stands still
 * for anyone who asked for reduced motion. Both hooks are dependency-free: one
 * IntersectionObserver and one media query, nothing else.
 */
import { useEffect, useState, type RefObject } from 'react';

const REDUCED = '(prefers-reduced-motion: reduce)';

/** `true` once the OS asks for reduced motion; tracks the setting live. SSR renders `false`
 *  and the first client render corrects it before any timer starts. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(REDUCED);
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

/** The IntersectionObserver rule, computed directly: the share of the element's own area that
 *  is inside the viewport is at least ``threshold`` (any visible pixel when it is 0). */
export function inViewport(el: Element, threshold: number): boolean {
  const r = el.getBoundingClientRect();
  const vh = window.innerHeight || document.documentElement.clientHeight;
  const vw = window.innerWidth || document.documentElement.clientWidth;
  const visibleH = Math.min(r.bottom, vh) - Math.max(r.top, 0);
  const visibleW = Math.min(r.right, vw) - Math.max(r.left, 0);
  if (r.width <= 0 || r.height <= 0 || visibleH <= 0 || visibleW <= 0) return false;
  return (visibleH * visibleW) / (r.width * r.height) >= threshold;
}

/** `true` from the first moment `ref` crosses `threshold` of the viewport. With `once` (the
 *  default) it stays true: a set-piece plays when the visitor reaches it and does not restart
 *  every time they scroll past.
 *
 *  IntersectionObserver alone was not enough (e2e re-test 2026-09-23 item 7): it reports on
 *  TRANSITIONS computed during rendering, so a band already in view at load, or scrolled to by
 *  script, waited for a first callback that a document which is not rendering (a background
 *  tab, an automation pane) never delivers. The observer still drives the normal case; the
 *  same rule is also checked directly — at mount, on scroll / resize / tab-visible, and on a
 *  slow timer until the first hit (timers run where rendering does not). */
export function useInView(
  ref: RefObject<Element | null>,
  { threshold = 0.25, once = true }: { threshold?: number; once?: boolean } = {},
): boolean {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let seen = false;
    let io: IntersectionObserver | null = null;
    let timer: number | undefined;

    const stopPolling = () => {
      if (timer !== undefined) window.clearInterval(timer);
      timer = undefined;
    };
    const cleanup = () => {
      io?.disconnect();
      window.removeEventListener('scroll', check);
      window.removeEventListener('resize', check);
      document.removeEventListener('visibilitychange', check);
      stopPolling();
    };
    const report = (hit: boolean) => {
      if (hit) {
        setInView(true);
        if (!seen) {
          seen = true;
          if (once) cleanup();
          else stopPolling();
        }
      } else if (!once) {
        setInView(false);
      }
    };
    function check() {
      if (seen && once) return;
      if (el) report(inViewport(el, threshold));
    }

    if (typeof IntersectionObserver === 'undefined') {
      setInView(true); // no observer (very old browsers): show the piece rather than hide it
      return;
    }
    io = new IntersectionObserver(
      (entries) => report(entries.some((e) => e.isIntersecting)),
      { threshold },
    );
    io.observe(el);
    window.addEventListener('scroll', check, { passive: true });
    window.addEventListener('resize', check);
    document.addEventListener('visibilitychange', check);
    timer = window.setInterval(check, 1000);
    check(); // already in view at mount — don't wait for the observer's first callback
    return cleanup;
  }, [ref, threshold, once]);
  return inView;
}
