"""Generate dated substantiation files per public claim (Internal Analytics P0, §7).

Evaluates each claim's evidence gate against analytics_daily and writes a JSON + Markdown record
(claim, number, definition, denominator, n, gate status, generated_at) to docs/substantiation/.
A claim that fails its gate is written as NOT PUBLISHABLE with the shortfall — the export never
hides an under-powered number. No public surface is touched; the files ARE the deliverable, and
publication is a later, separately-gated step.

Usage:
  uv run python scripts/generate_substantiation.py
  uv run python scripts/generate_substantiation.py --out /tmp/substantiation
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/ on the path

_DEFAULT_OUT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "substantiation"


async def _main() -> None:
    from app.analytics.substantiation import CLAIMS, evaluate_claim, to_markdown
    from app.db.base import AsyncSessionLocal

    ap = argparse.ArgumentParser(description="Generate claim-substantiation files")
    ap.add_argument("--out", type=pathlib.Path, default=_DEFAULT_OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as s:
        published, blocked = 0, 0
        for claim in CLAIMS.values():
            rec = await evaluate_claim(s, claim)
            stamp = rec["as_of"]
            (args.out / f"{claim.key}_{stamp}.json").write_text(json.dumps(rec, indent=2))
            (args.out / f"{claim.key}_{stamp}.md").write_text(to_markdown(rec))
            if rec["gate_status"] == "PUBLISHABLE":
                published += 1
            else:
                blocked += 1
            print(f"{claim.key}: {rec['gate_status']} (n={int(rec['n'])}/{claim.min_n})")
        print(f"\n{published} publishable, {blocked} not-yet-publishable → {args.out}")


if __name__ == "__main__":
    asyncio.run(_main())
