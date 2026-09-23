"""Landing motion guards (Landing Motion Parity, Phase A — 2026-09-23).

The 08-28 review counted content bands and called the landing "~85% shipped"; measured on
2026-09-23 it carried one animated set-piece and none of the prototype's ambient motion. This
module pins what Phase A added — and, more importantly, what must NOT ride in with it: the
round-2 glass language (N7) is HELD, so a landing build defines exactly the allowed keyframe
set and contains no `backdrop-filter`, no auras, no glass surfaces.

The marketing app has no test runner of its own; like the palette guards next door
(test_design_token_guards.py) these read the SOURCE the build is made from.
"""

from __future__ import annotations

import pathlib
import re


REPO = pathlib.Path(__file__).resolve().parents[2]
MARKETING = REPO / "apps/web-marketing/src"
GLOBALS_CSS = MARKETING / "app/globals.css"
LANDING = MARKETING / "app/page.tsx"


def _src_files(*suffixes: str) -> list[pathlib.Path]:
    return sorted(p for p in MARKETING.rglob("*") if p.suffix in suffixes and p.is_file())


def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


# ── 1 · Hero photo — ken-burns drift ────────────────────────────────────────────────────


def test_the_hero_photo_carries_the_kenburns_drift_as_a_transform_only():
    css = _read(GLOBALS_CSS)
    assert "@keyframes tyn-kenburns" in css
    block = re.search(r"@keyframes tyn-kenburns\s*\{(.*?)\n\}", css, re.S).group(1)
    assert "scale(1.05)" in block and "scale(1.14)" in block and "-1.5%" in block
    # transform only — never a property that moves layout
    assert not re.search(r"\b(width|height|margin|padding|top|left|inset)\s*:", block)
    page = _read(LANDING)
    hero_img = re.search(r'<Image\s+src="/hero-calm\.jpg"(.*?)/>', page, re.S).group(1)
    assert "tyn-kenburns" in hero_img and "fill" in hero_img
    # the band clips the drift so the scaled photo can never widen the page
    assert re.search(r'className="relative isolate overflow-hidden[^"]*">\s*\{/\* Atmospheric', page)


def test_reduced_motion_holds_the_kenburns_frame_at_the_end_scale():
    css = _read(GLOBALS_CSS)
    reduced = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", css, re.S)
    assert reduced, "no reduced-motion block"
    rule = re.search(r"\.tyn-kenburns\s*\{(.*?)\}", reduced.group(1), re.S)
    assert rule and "animation: none" in rule.group(1) and "scale(1.14)" in rule.group(1)
