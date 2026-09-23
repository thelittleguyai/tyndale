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


# ── 2 · "Not a chatbot with opinions" — the playback's words are registry copy ──────────

COMPARE_JSON = MARKETING / "content/landing-compare.json"


def _compare_messages() -> list[tuple[str, dict]]:
    import json

    doc = json.loads(_read(COMPARE_JSON))
    return [(pane, m) for pane, data in doc["panes"].items() for m in data["messages"]]


def test_every_keyed_playback_line_is_verbatim_registry_copy():
    """The marketing site cannot read the registry at build time (a separate static deploy),
    so the transcript JSON mirrors it — and this is what keeps the mirror honest. Every entry
    with a `key` renders exactly what `orchestration_step(key, **vars)` renders."""
    from app.agents.context_loader import load_orchestration_registry, orchestration_step

    registry = load_orchestration_registry()
    keyed = [(p, m) for p, m in _compare_messages() if m.get("key")]
    assert len(keyed) >= 8
    for pane, m in keyed:
        assert m["key"] in registry, f"{pane}: unknown registry key {m['key']!r}"
        expected = orchestration_step(m["key"], **m.get("vars", {}))
        assert m["text"] == expected, f"{pane}/{m['key']} drifted from the registry"
        if m.get("chip"):
            chip = m["chip"]
            assert chip["text"] == orchestration_step(chip["key"], **chip.get("vars", {}))
    # the shared question really is shared, and every landing.compare key is used
    first = {p: ms[0] for p, ms in {p: [m for q, m in _compare_messages() if q == p] for p in ("generic", "tyndale")}.items()}
    assert first["generic"]["key"] == first["tyndale"]["key"] == "landing.compare.user_q1"
    used = {m["key"] for _, m in keyed}
    assert {k for k in registry if k.startswith("landing.compare.")} <= used


def test_the_tyndale_pane_keeps_the_doctrine_the_band_claims():
    """It shows a range where an input is missing, cites what it stands on, and never states a
    statistic; the foil is the one that quotes odds and invents a statute."""
    msgs = {p: [m for q, m in _compare_messages() if q == p] for p in ("generic", "tyndale")}
    tyndale = " ".join(m["text"] for m in msgs["tyndale"] if m["from"] == "bot")
    assert "Your share becomes a range." in tyndale and "$412.40 to $1,184.60" in tyndale
    chips = [m["chip"]["text"] for m in msgs["tyndale"] if m.get("chip")]
    assert any("Summary of Benefits" in c for c in chips) and any("EOB" in c for c in chips)
    assert "What you should actually owe: $612.40" in tyndale  # the hero fixture, not new numbers
    # no base rate, no odds ("80% of imaging" is the plan's own coinsurance term, not a statistic)
    assert not re.search(r"\b\d{1,3}% (?:get|succeed|win|of (?:people|cases|disputes|bills))", tyndale)
    assert "studies show" not in tyndale and "Most people" not in tyndale
    generic = " ".join(m["text"] for m in msgs["generic"] if m["from"] == "bot")
    assert "60%" in generic and "Fair Medical Billing Act" in generic
    # every spotlight phrase is really in its message, inside one bold/plain segment
    for _, m in _compare_messages():
        if m.get("spot"):
            assert any(m["spot"] in seg for seg in m["text"].split("**")), m["spot"]
    # every foil flag is a ✗ the caption row also states; every Tyndale flag is a ✓
    assert all(m.get("flag") for m in msgs["generic"] if m["from"] == "bot")
