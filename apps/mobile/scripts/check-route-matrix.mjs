#!/usr/bin/env node
/**
 * Route matrix check (2026-08-26 viewport-sweep bug): every route in the Expo static
 * export must be reachable BOTH with and without a trailing slash — hard refreshes,
 * shared links, and email links arrive in either form. The /chat hang was nginx's
 * automatic directory redirect emitting an absolute plain-http Location behind the
 * TLS-terminating ingress; this check fails on any non-2xx terminal status, any
 * redirect chain longer than one hop, and any absolute-URL Location header (a
 * relative Location can never downgrade the scheme).
 *
 * Usage: node scripts/check-route-matrix.mjs <baseUrl> [distDir=dist]
 */
import { readdirSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const base = (process.argv[2] || '').replace(/\/$/, '');
const dist = process.argv[3] || 'dist';
if (!base) {
  console.error('usage: node scripts/check-route-matrix.mjs <baseUrl> [distDir]');
  process.exit(2);
}

/** Enumerate routes from the export: every prerendered .html plus every directory that
 *  carries an index.html (a slash-less request to those is the bug's shape). Dynamic
 *  segments ([param].html) are exercised with a literal probe value via SPA fallback. */
function routes(dir, prefix = '') {
  const out = [];
  for (const name of readdirSync(dir)) {
    if (name.startsWith('_') || name.startsWith('+') || name === 'assets') continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (existsSync(join(full, 'index.html'))) out.push(`${prefix}/${name}`);
      out.push(...routes(full, `${prefix}/${name}`));
    } else if (name.endsWith('.html') && name !== 'index.html') {
      const stem = name.slice(0, -5);
      out.push(
        stem.startsWith('[') ? `${prefix}/probe-${stem.slice(1, -1)}` : `${prefix}/${stem}`,
      );
    }
  }
  return out;
}

async function probe(path) {
  const res = await fetch(base + path, { redirect: 'manual', signal: AbortSignal.timeout(8000) });
  if (res.status >= 200 && res.status < 300) return { ok: true, note: String(res.status) };
  if (res.status >= 300 && res.status < 400) {
    const loc = res.headers.get('location') || '';
    if (/^[a-z]+:\/\//i.test(loc)) {
      return { ok: false, note: `${res.status} -> ABSOLUTE Location "${loc}" (scheme-downgrade risk)` };
    }
    const res2 = await fetch(base + loc, { redirect: 'manual', signal: AbortSignal.timeout(8000) });
    return res2.status >= 200 && res2.status < 300
      ? { ok: true, note: `${res.status} -> ${loc} -> ${res2.status}` }
      : { ok: false, note: `${res.status} -> ${loc} -> ${res2.status}` };
  }
  return { ok: false, note: String(res.status) };
}

const all = ['/', ...new Set(routes(dist))];
let failures = 0;
for (const route of all) {
  const forms = route === '/' ? ['/'] : [route, route + '/'];
  for (const form of forms) {
    try {
      const { ok, note } = await probe(form);
      if (!ok) failures++;
      console.log(`${ok ? 'ok  ' : 'FAIL'} ${form}  (${note})`);
    } catch (e) {
      failures++;
      console.log(`FAIL ${form}  (${String(e).slice(0, 60)})`);
    }
  }
}
console.log(failures === 0 ? `\nroute matrix green — ${all.length} routes, both slash forms` : `\n${failures} FAILURES`);
process.exit(failures === 0 ? 0 : 1);
