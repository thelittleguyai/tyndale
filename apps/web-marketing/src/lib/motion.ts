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

/** `true` from the first moment `ref` crosses `threshold` of the viewport. With `once` (the
 *  default) the observer disconnects after that: a set-piece plays when the visitor reaches
 *  it and does not restart every time they scroll past. */
export function useInView(
  ref: RefObject<Element | null>,
  { threshold = 0.25, once = true }: { threshold?: number; once?: boolean } = {},
): boolean {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === 'undefined') {
      setInView(true); // no observer (very old browsers): show the piece rather than hide it
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries.some((e) => e.isIntersecting);
        if (hit) {
          setInView(true);
          if (once) io.disconnect();
        } else if (!once) {
          setInView(false);
        }
      },
      { threshold },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref, threshold, once]);
  return inView;
}
