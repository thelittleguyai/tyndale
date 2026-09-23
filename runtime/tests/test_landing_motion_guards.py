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


# ── 3 · the hero loop is never blank; the three-act demo runs on the hero's numbers ─────

DEMO_JSON = MARKETING / "content/landing-demo.json"
HERO_MOCK = MARKETING / "components/audit-mock.tsx"
AUDIT_DEMO = MARKETING / "components/audit-demo.tsx"
HERO_FIXTURE = ("$2,347.18", "$1,184.60", "$612.40")


def test_the_hero_loop_starts_populated_and_crossfades_instead_of_wiping():
    src = _read(HERO_MOCK)
    # the three rows are unconditional markup — no `play ?` gate, no delay-hidden rows
    for figure in HERO_FIXTURE:
        assert figure in src
    assert "tyn-mock-doc" not in src and "tyn-mock-cross" in src
    assert "play ?" not in src and "{play ?" not in src
    # the loop resets at the crossfade's midpoint, never a hard cut to an empty card
    assert "CROSS_MS / 2" in src
    css = _read(GLOBALS_CSS)
    cross = re.search(r"@keyframes tyn-mock-cross\s*\{(.*?)\n\}", css, re.S).group(1)
    assert "opacity: 1" in cross and "opacity: 0" in cross and "width" not in cross


def test_the_demo_uses_the_hero_fixture_and_registry_copy_only():
    import json

    from app.agents.context_loader import orchestration_step

    doc = json.loads(_read(DEMO_JSON))
    text = json.dumps(doc)
    for figure in HERO_FIXTURE:
        assert figure in text, f"demo fixture lost the hero figure {figure}"
    assert "$572.20" in text  # the gap, 1,184.60 − 612.40
    # no dollar figure the hero does not carry (the deductible terms are the compare story's)
    allowed = set(HERO_FIXTURE) | {"$572.20", "$2,000", "$2,000.00", "$1,750.00", "$1,034.75", "$5,000"}
    assert set(re.findall(r"\$[\d,]+(?:\.\d{2})?", text)) <= allowed
    for item in doc["sorted"]:
        if item.get("chip"):
            assert item["chip"]["text"] == orchestration_step(item["chip"]["key"], **item["chip"]["vars"])
        if item.get("body_key"):
            assert item["body"] == orchestration_step(item["body_key"], **item["body_vars"])
    assert [p["id"] for p in doc["phases"]] == ["add", "audit", "sort"]
    src = _read(AUDIT_DEMO)
    assert "tyn-funnel" in src and "tyn-intake" in src and "tyn-rise" in src
    assert "IntersectionObserver" in _read(MARKETING / "lib/motion.ts") and "useInView(" in src
    page = _read(LANDING)
    assert page.index("<AuditDemo />") < page.index("{STEPS.map(")  # the demo shows, the cards explain


# ── 4 · rise-on-scroll ──────────────────────────────────────────────────────────────────

RISE = MARKETING / "components/rise-on-scroll.tsx"


def test_rise_on_scroll_hides_nothing_it_cannot_reveal():
    """The attribute is inert without the observer: hidden only under `(scripting: enabled)`
    AND no reduced-motion preference, and the observer bails on exactly the same conditions,
    so a no-JS visitor, an old engine, or a reduced-motion visitor sees everything, static."""
    css = _read(GLOBALS_CSS)
    block = re.search(
        r"@media \(scripting: enabled\) and \(prefers-reduced-motion: no-preference\)\s*\{(.*?)\n\}", css, re.S
    )
    assert block, "the [data-rise] rules must sit under the scripting+motion media query"
    assert re.search(r"\[data-rise\]\s*\{\s*opacity: 0;\s*\}", block.group(1))
    assert "[data-rise='in']" in block.group(1) and "tyn-rise" in block.group(1)
    assert "[data-rise]" not in css.replace(block.group(0), "")  # never hidden outside the gate
    src = _read(RISE)
    assert "matchMedia('(scripting: enabled)')" in src and "prefers-reduced-motion: reduce" in src
    assert "IntersectionObserver" in src and "setAttribute('data-rise', 'in')" in src
    page = _read(LANDING)
    assert "<RiseOnScroll />" in page
    assert page.count("data-rise") >= 20, "band headings and card grids carry data-rise"
    # the hero (above the fold) does not rise — nothing hidden on first paint
    hero_end = page.index("<main>")
    assert "data-rise" not in page[:hero_end]


# ── 5 · the fence: exactly these keyframes, and no glass riding in with the motion ──────

# What a landing build may define. `tyn-mock-*` is the hero loop; `spin` is Tailwind's
# `animate-spin` on the signed-in page's loader; `tyn-typing` is the one name the 2026-09-23
# prompt did not list — the chat-compare typing dots (the prototype used Tailwind's
# `animate-bounce`, which would have put an un-namespaced `bounce` in the build instead).
ALLOWED_KEYFRAMES = {"tyn-rise", "tyn-kenburns", "tyn-funnel", "tyn-intake", "tyn-typing", "spin"}
ALLOWED_PREFIXES = ("tyn-mock-",)
# Tailwind's animation utilities → the keyframe each one emits into the build.
_TAILWIND_ANIMATE = {"animate-spin": "spin", "animate-ping": "ping", "animate-pulse": "pulse", "animate-bounce": "bounce"}
# The round-2 glass language (delta inventory N7) — HELD. None of it may appear in the source.
_GLASS = ("backdrop-filter", "backdropFilter", "backdrop-blur", "AmbientAuras", "GlassCard", "glass-tile", "glass-dark", "aura")


def _strip_comments(src: str) -> str:
    """Code only: block comments (/* */, the JSX {/* */} kind included) and // lines go."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"^\s*//.*$", "", src, flags=re.M)


def _defined_keyframes() -> set[str]:
    names: set[str] = set()
    for css in _src_files(".css"):
        names |= set(re.findall(r"@keyframes\s+([\w-]+)", _read(css)))
    for tsx in _src_files(".tsx", ".ts"):
        src = _read(tsx)
        names |= set(re.findall(r"@keyframes\s+([\w-]+)", src))  # a component-body <style> would land here
        names |= {kf for util, kf in _TAILWIND_ANIMATE.items() if re.search(rf"(?<![\w-]){util}(?![\w-])", src)}
    return names


def _allowed(name: str) -> bool:
    return name in ALLOWED_KEYFRAMES or name.startswith(ALLOWED_PREFIXES)


def test_a_landing_build_defines_exactly_the_allowed_keyframe_set():
    defined = _defined_keyframes()
    stray = sorted(n for n in defined if not _allowed(n))
    assert stray == [], f"keyframes outside the allowed set: {stray}"
    # every named keyframe is really defined — the set is exact in both directions
    missing = sorted(n for n in ALLOWED_KEYFRAMES if n not in defined)
    assert missing == [], f"allowed keyframes no build defines any more: {missing}"
    assert any(n.startswith("tyn-mock-") for n in defined)
    # every `tyn-*` name an animation shorthand or a className references is defined
    referenced: set[str] = set()
    for f in _src_files(".css", ".tsx", ".ts"):
        src = _read(f)
        referenced |= set(re.findall(r"animation:\s*(tyn-[\w-]+)", src))
        referenced |= set(re.findall(r"['\"`](tyn-[\w-]+)", src))
    undefined = sorted(r for r in referenced if r not in defined and not r.endswith("-"))  # 'tyn-mock-' is prose
    assert undefined == [], f"animations referencing undefined keyframes: {undefined}"


def test_every_keyframe_is_namespaced_and_lives_in_globals_css():
    for tsx in _src_files(".tsx", ".ts"):
        src = _read(tsx)
        assert "<style" not in src, f"{tsx.name}: component-body <style> — keyframes belong in globals.css"
        assert "@keyframes" not in src, f"{tsx.name}: keyframes belong in globals.css"
    for css in _src_files(".css"):
        for name in re.findall(r"@keyframes\s+([\w-]+)", _read(css)):
            assert name.startswith("tyn-"), f"{css.name}: keyframe {name!r} is not namespaced tyn-*"


def test_no_glass_rides_in_with_the_motion():
    """N7 (glass / auras / floating glass cards) is HELD for Brock's round-2.5 decision. A
    motion port is exactly how it would slip in — so the source is scanned, not trusted."""
    offenders = []
    for f in _src_files(".css", ".tsx", ".ts"):
        for i, line in enumerate(_strip_comments(_read(f)).splitlines(), 1):
            for token in _GLASS:
                if token in line:
                    offenders.append(f"{f.relative_to(REPO)}:{i}: {token}")
    assert offenders == [], "glass language in the marketing source:\n  " + "\n  ".join(offenders)
    # no translucent-surface utility either (bg-white/40-style glass tints on cards)
    for tsx in _src_files(".tsx"):
        assert not re.search(r"backdrop-blur|backdrop-saturate", _read(tsx))


def test_every_tyn_animation_class_has_a_reduced_motion_rule():
    css = _read(GLOBALS_CSS)
    classes = set(re.findall(r"^\.(tyn-[\w-]+)\s*\{", css, re.M))
    reduced_blocks = re.findall(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", css, re.S)
    reduced = "\n".join(reduced_blocks)
    for cls in classes:
        assert f".{cls}" in reduced, f".{cls} has no prefers-reduced-motion rule"
        rule = re.search(rf"\.{re.escape(cls)}[^{{]*\{{(.*?)\}}", reduced, re.S)
        assert rule and "animation: none" in rule.group(1), cls
    # the hero mock and the demo apply their keyframes only when motion is not reduced
    for comp in (HERO_MOCK, AUDIT_DEMO, MARKETING / "components/chat-compare.tsx"):
        assert "useReducedMotion" in _read(comp), comp.name


def test_the_built_css_when_present_matches_the_source_model():
    """`next build` output, when a build exists locally or in CI: the real keyframe set and the
    real absence of glass. Tailwind's content scanner turns even a COMMENT saying
    "backdrop-filter" into an emitted utility, which is why the source comments avoid the
    token and the config trims it from the default transition list."""
    import pytest

    built = sorted((REPO / "apps/web-marketing/.next/static/css").glob("*.css"))
    if not built:
        pytest.skip("no marketing build present (apps/web-marketing/.next) — source model only")
    css = "\n".join(_read(p) for p in built)
    defined = set(re.findall(r"@keyframes\s+([\w-]+)", css))
    stray = sorted(n for n in defined if not _allowed(n))
    assert stray == [], f"built CSS defines keyframes outside the allowed set: {stray}"
    assert ALLOWED_KEYFRAMES <= defined
    # (Tailwind's preflight resets `--tw-backdrop-*` variables on every element — that is not a
    # blur; the PROPERTY and the UTILITY are what glass would need)
    assert "backdrop-filter" not in css
    assert not re.search(r"\.backdrop-(?:blur|saturate)", css)
    assert not re.search(r"\.glass[\s{-]", css) and not re.search(r"\.aura[\s{-]", css)



# ── re-test 2026-09-23 item 7: playback starts in view at load and after a scripted scroll ──


def test_in_view_is_checked_directly_not_only_on_observer_transitions():
    """IntersectionObserver reports transitions computed while RENDERING — a band already in
    view at load, or scrolled to by script, waited for a first callback a non-rendering document
    (a background tab, an automation pane) never delivers. Proven headless 2026-09-23: the
    deployed page stayed 'waiting' after scrollIntoView in a hidden tab; this one plays."""
    src = _read(MARKETING / "lib/motion.ts")
    body = src[src.index("export function useInView"):]
    assert "check(); // already in view at mount" in body
    assert body.index("io.observe(el)") < body.index("check(); // already in view at mount")
    for event in ("'scroll'", "'resize'", "'visibilitychange'"):
        assert f"addEventListener({event}" in body and f"removeEventListener({event}" in body
    assert "setInterval(check, 1000)" in body and "stopPolling()" in body  # polls only until seen
    assert "export function inViewport" in src and "/ (r.width * r.height) >= threshold" in src
