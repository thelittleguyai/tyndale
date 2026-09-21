"""Design-token guards — one source of truth, mirrors in sync, contrast at AA.

Lives in the runtime suite deliberately: it's the only test runner that always runs in CI
regardless of which workspace changed, and these are repo-wide invariants rather than app
behaviour. Pure file inspection — no runtime imports.

Three properties:
  1. NO RAW HEX outside packages/shared/src/design-tokens.ts (plus the two sanctioned mirrors).
     A hex in a component is how the app and the landing page drifted apart in the first place.
  2. The Tailwind configs + global.css MIRRORS agree with the shared file. They exist because
     Tailwind can't import TS at config-eval time; they must never diverge.
  3. Every foreground/background pair the palette defines clears WCAG AA (4.5:1), in BOTH modes.
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SHARED = REPO / "packages/shared/src/design-tokens.ts"
MIRRORS = (
    REPO / "apps/mobile/global.css",
    REPO / "apps/mobile/tailwind.config.js",
    REPO / "apps/admin/tailwind.config.ts",
    REPO / "apps/web-marketing/tailwind.config.ts",
)
_HEX = re.compile(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?\b")

# THIRD-PARTY BRAND MARKS — exempt by necessity, not convenience. Google's sign-in mark must
# render in Google's exact colours per their brand guidelines; tokenising it would be wrong,
# not just unnecessary. Keep this list to marks we don't own.
_BRAND_MARK_EXEMPT = {"apps/web-marketing/src/components/google-icon.tsx"}


def _app_sources() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for app in ("apps/mobile", "apps/admin", "apps/web-marketing", "packages/shared"):
        for ext in ("*.ts", "*.tsx"):
            out += [
                p
                for p in (REPO / app).rglob(ext)
                if "node_modules" not in p.parts
                and ".next" not in p.parts
                and p != SHARED
                and p not in MIRRORS
            ]
    return out


# --- 1. single source of truth ----------------------------------------------
def test_no_raw_hex_outside_the_shared_token_file():
    offenders: list[str] = []
    for path in _app_sources():
        if str(path.relative_to(REPO)) in _BRAND_MARK_EXEMPT:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _HEX.search(line) and "logoSvg" not in line:
                offenders.append(f"{path.relative_to(REPO)}:{i}: {line.strip()[:90]}")
    assert not offenders, (
        "raw colour literals outside packages/shared/src/design-tokens.ts — import a token "
        "or use useThemeColors() instead:\n  " + "\n  ".join(offenders)
    )


def test_mobile_theme_defines_no_values_of_its_own():
    """apps/mobile/theme/tokens.ts must be a pure re-export — the drift vector that existed
    before this consolidation."""
    text = (REPO / "apps/mobile/theme/tokens.ts").read_text(encoding="utf-8")
    assert not _HEX.search(text), "apps/mobile/theme/tokens.ts must not define colour values"
    assert "@tyndale/shared" in text


# --- 2. mirrors agree with the source ---------------------------------------
def _shared_values() -> dict[str, str]:
    """Parse ONLY the `brand` block — the rest of the file legitimately reuses those names
    (e.g. dark-mode `money`), so a whole-file scan would read the wrong value."""
    text = SHARED.read_text(encoding="utf-8")
    block = text[text.index("export const brand = {") : text.index("} as const;", text.index("export const brand = {"))]
    return {k: v.upper() for k, v in re.findall(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'", block)}


@pytest.mark.parametrize(
    ("slot", "expected"),
    [("teal", "#3E5C57"), ("navy", "#1D2A38"), ("money", "#2E7D5B"),
     ("citation", "#2C6E8F"), ("cream", "#FAF7F0")],
)
def test_brand_palette_is_brocks_checklist_a(slot, expected):
    """Checklist §A is the acceptance authority — these five are not ours to drift."""
    assert _shared_values().get(slot) == expected


def test_mirrors_carry_the_brand_values():
    """Each mirror must contain the brand hexes it is responsible for (case-insensitive)."""
    css = (REPO / "apps/mobile/global.css").read_text(encoding="utf-8").lower()
    light = css[css.index(":root {") : css.index(".dark:root")]
    assert "--c-accent: #3e5c57" in light, "global.css light accent must be brand teal"
    assert "--c-bg-page: #faf7f0" in light, "global.css light page must be brand cream"
    assert "--c-money: #2e7d5b" in light
    assert "--c-citation: #2c6e8f" in light

    for cfg in (REPO / "apps/admin/tailwind.config.ts", REPO / "apps/web-marketing/tailwind.config.ts"):
        s = cfg.read_text(encoding="utf-8").upper()
        assert "#3E5C57" in s and "#2E7D5B" in s and "#FAF7F0" in s and "#2C6E8F" in s, cfg.name


def test_dark_block_is_not_the_light_block():
    """Guards the exact bug this session hit while editing the mirror: the dark values
    overwriting :root, leaving light mode rendering dark-mode colours."""
    css = (REPO / "apps/mobile/global.css").read_text(encoding="utf-8").lower()
    light = css[css.index(":root {") : css.index(".dark:root")]
    darkb = css[css.index(".dark:root") :]
    assert "--c-accent: #3e5c57" in light and "--c-accent: #5dcaa5" in darkb
    assert "--c-bg-page: #faf7f0" in light and "--c-bg-page: #0c1210" in darkb


# --- 3. contrast (checklist A9) ---------------------------------------------
def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    parts = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (label, foreground, background) — every pair the product actually renders as text.
LIGHT_PAGE, LIGHT_SURFACE = "#FAF7F0", "#FFFFFF"
DARK_PAGE, DARK_SURFACE = "#0C1210", "#141D19"
AA_PAIRS = [
    ("light text.primary/page", "#1A2B27", LIGHT_PAGE),
    ("light text.secondary/page", "#5F5E5A", LIGHT_PAGE),
    ("light text.faint/page", "#726F69", LIGHT_PAGE),
    ("light text.faint/surface", "#726F69", LIGHT_SURFACE),
    ("light accent/page", "#3E5C57", LIGHT_PAGE),
    ("light money/page", "#2E7D5B", LIGHT_PAGE),
    ("light money/surface", "#2E7D5B", LIGHT_SURFACE),
    ("light citation/page", "#2C6E8F", LIGHT_PAGE),
    ("light warning/page", "#9A5F12", LIGHT_PAGE),
    ("light danger/page", "#C1443B", LIGHT_PAGE),
    ("white on accent", "#FFFFFF", "#3E5C57"),
    ("white on money", "#FFFFFF", "#2E7D5B"),
    ("white on citation", "#FFFFFF", "#2C6E8F"),
    ("white on navy", "#FFFFFF", "#1D2A38"),
    ("dark text.primary/page", "#F2F5F3", DARK_PAGE),
    ("dark text.secondary/page", "#8FA39B", DARK_PAGE),
    ("dark text.faint/page", "#748981", DARK_PAGE),
    ("dark text.faint/surface", "#748981", DARK_SURFACE),
    ("dark accent/page", "#5DCAA5", DARK_PAGE),
    ("dark money/page", "#4FBF8B", DARK_PAGE),
    ("dark money/surface", "#4FBF8B", DARK_SURFACE),
    ("dark citation/page", "#7FB6D3", DARK_PAGE),
    ("dark citation/surface", "#7FB6D3", DARK_SURFACE),
    ("dark warning/page", "#FAC775", DARK_PAGE),
    ("dark danger/page", "#E5776C", DARK_PAGE),
    # The admin console (navy) + its soft state pills — deep review 2026-09-18: rose text on
    # rose-soft rendered 3.51:1. The derived checks below find NEW pairs; these pin the values.
    ("rose-deep on rose-soft (disapproved / low / canary pills)", "#9A3232", "#F7E0E0"),
    ("amber-deep on amber-soft (unreviewed / re-review / medium pills)", "#884E1B", "#FBEBD8"),
    ("sage-deep on sage-soft (approved / high pills)", "#246247", "#E2EDE8"),
    ("citation-deep on citation-soft (in-review pill)", "#225670", "#E1EBEF"),
    ("rose-soft on navy-deep (console error text)", "#F7E0E0", "#17212C"),
    ("rose-soft on navy-soft (error text inside a card)", "#F7E0E0", "#2A3946"),
    ("amber-soft on navy-soft (caution text inside a card)", "#FBEBD8", "#2A3946"),
    ("rose-deep on cream (marketing sign-in error)", "#9A3232", LIGHT_PAGE),
]


@pytest.mark.parametrize(("label", "fg", "bg"), AA_PAIRS)
def test_every_text_pair_clears_wcag_aa(label, fg, bg):
    ratio = contrast(fg, bg)
    assert ratio >= 4.5, f"{label}: {ratio:.2f}:1 — below WCAG AA (4.5:1)"


# --- 3b. the pairs nobody remembered to list ---------------------------------
# AA_PAIRS is a hand-kept list, and the rose-on-rose-soft pills shipped BECAUSE nobody added
# them to it. These three derive their cases from the sources instead.
def _accent_ramps() -> dict[str, dict[str, str]]:
    """`name: { DEFAULT: '#..', deep: '#..', soft: '#..' }` rows of the shared `colors` block."""
    text = SHARED.read_text(encoding="utf-8")
    block = text[text.index("export const colors = {") : text.index("} as const;", text.index("export const colors = {"))]
    ramps: dict[str, dict[str, str]] = {}
    for name, body in re.findall(r"^\s{2}(\w+): \{([^{}]*)\}", block, re.M):
        steps = {k: v.upper() for k, v in re.findall(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'", body)}
        if steps:
            ramps[name] = steps
    return ramps


def _tailwind_colours(cfg: pathlib.Path) -> dict[str, str]:
    """`rose-deep` → hex, as Tailwind resolves class suffixes from a config's colors block."""
    text = cfg.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for name, body in re.findall(r"^\s+(\w+): \{([^{}]*)\},?$", text, re.M):
        for step, value in re.findall(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'", body):
            out[name if step == "DEFAULT" else f"{name}-{step}"] = value.upper()
    for name, value in re.findall(r"^\s+(\w+): '(#[0-9A-Fa-f]{6})',?$", text, re.M):
        out[name] = value.upper()
    return out


def test_every_accent_ramp_keeps_the_deep_on_soft_contract():
    """On a ramp whose `soft` is a light tint, `deep` IS the text colour for a soft pill —
    so it must clear AA on it. (ink/navy are dark surface ramps: their `soft` is not a tint,
    and the luminance test below is what excludes them, not a list.)"""
    checked = []
    for name, steps in _accent_ramps().items():
        if "deep" not in steps or "soft" not in steps or _luminance(steps["soft"]) < 0.6:
            continue
        checked.append(name)
        ratio = contrast(steps["deep"], steps["soft"])
        assert ratio >= 4.5, f"{name}.deep on {name}.soft: {ratio:.2f}:1 — below WCAG AA"
    assert {"sage", "amber", "rose", "citation"} <= set(checked), checked


_APP_PALETTES = {
    "apps/admin": REPO / "apps/admin/tailwind.config.ts",
    "apps/web-marketing": REPO / "apps/web-marketing/tailwind.config.ts",
}
_LITERAL = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|`[^`]*`")


def test_every_soft_pill_in_the_web_apps_clears_aa():
    """A string literal that sets BOTH `bg-<x>-soft` and a `text-<colour>` is a pill whose
    contrast is fully decided in that literal — resolve it through the app's own palette."""
    failures: list[str] = []
    seen = 0
    for app, cfg in _APP_PALETTES.items():
        palette = _tailwind_colours(cfg)
        for path in (REPO / app / "src").rglob("*.tsx"):
            for literal in _LITERAL.findall(path.read_text(encoding="utf-8")):
                bgs = [c for c in re.findall(r"(?<![\w:-])bg-([a-z]+-soft)(?![\w/-])", literal) if c in palette]
                fgs = [c for c in re.findall(r"(?<![\w:-])text-([a-z]+(?:-[a-z]+)?)(?![\w/-])", literal) if c in palette]
                for bg in bgs:
                    for fg in fgs:
                        seen += 1
                        ratio = contrast(palette[fg], palette[bg])
                        if ratio < 4.5:
                            failures.append(f"{path.relative_to(REPO)}: text-{fg} on bg-{bg} = {ratio:.2f}:1")
    assert seen >= 8, f"the scan found only {seen} pills — did the class convention change?"
    assert not failures, "soft pills below WCAG AA:\n  " + "\n  ".join(sorted(set(failures)))


def test_default_rose_is_never_a_text_colour():
    """DEFAULT rose fails AA as text on EVERY surface the palette has (computed here, not
    asserted from memory) — so a bare `text-rose` has no correct placement: `text-rose-soft`
    on the dark console, `text-rose-deep` on a light page or a rose-soft pill."""
    palette = _tailwind_colours(_APP_PALETTES["apps/admin"])
    surfaces = ("navy-deep", "navy", "navy-soft", "surface", "cream", "rose-soft")
    best = max(contrast(palette["rose"], palette[s]) for s in surfaces)
    assert best < 4.5, "rose now clears AA somewhere — relax this ban deliberately, with the pair in AA_PAIRS"
    offenders = [
        f"{path.relative_to(REPO)}:{i}"
        for app in _APP_PALETTES
        for path in (REPO / app / "src").rglob("*.tsx")
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"(?<![\w:-])text-rose(?![\w/-])", line)
    ]
    assert offenders == [], "bare text-rose (max %.2f:1 on any surface):\n  %s" % (best, "\n  ".join(offenders))


def test_money_figure_regression_is_actually_fixed():
    """The bug this palette adoption exists to fix: savings figures rendered sage #3DAA7E at
    2.90:1 — below AA on the most important number in the product."""
    assert contrast("#FFFFFF", "#3DAA7E") < 4.5  # the old value really did fail
    assert contrast("#FFFFFF", "#2E7D5B") >= 4.5  # …and the new one clears it


def test_no_css_variables_as_native_color_props():
    """Audit 2026-08-27 item 1: `var(--c-*)` resolves ONLY on web — as a React Native color
    prop (icon color=, placeholderTextColor=) it renders black/absent on iOS/Android. 72
    sites shipped that way. useThemeColors() is the native-safe path; this scan keeps the
    class extinct, alongside the hardcoded-rgba placeholder pattern (the sign-in bug)."""
    offenders: list[str] = []
    for path in (REPO / "apps/mobile").rglob("*.tsx"):
        if "node_modules" in path.parts or "dist" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), start=1):
            if "var(--c-" in line:
                offenders.append(f"{path.relative_to(REPO)}:{i} var(--c-*) as a prop value")
            if "placeholderTextColor=\"rgba" in line or "placeholderTextColor={'rgba" in line:
                offenders.append(f"{path.relative_to(REPO)}:{i} hardcoded rgba placeholder")
    assert offenders == [], "\n".join(offenders)


def test_admin_and_marketing_palettes_stay_in_sync():
    """Audit 2026-08-27 item 3: apps/admin and apps/web-marketing each hardcode a parallel
    palette with a 'keep in sync' comment doing the enforcement. This test does it instead:
    the two colors blocks must carry the IDENTICAL hex set, and the brand anchors (teal,
    cream) must match @tyndale/shared — so a one-sided edit fails here instead of drifting."""
    import re

    def hexes(path: pathlib.Path) -> set[str]:
        text = path.read_text(encoding="utf-8")
        m = re.search(r"colors: \{(.*?)\n      \}", text, re.S)
        assert m, f"colors block not found in {path}"
        return set(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", m.group(1)))

    admin = hexes(REPO / "apps/admin/tailwind.config.ts")
    marketing = hexes(REPO / "apps/web-marketing/tailwind.config.ts")
    assert admin == marketing, (
        f"palettes drifted — only in admin: {sorted(admin - marketing)}; "
        f"only in marketing: {sorted(marketing - admin)}"
    )
    shared = (REPO / "packages/shared/src/design-tokens.ts").read_text(encoding="utf-8")
    import re as _re

    teal = _re.search(r"teal: '(#[0-9A-Fa-f]{6})'", shared)
    cream = _re.search(r"cream: '(#[0-9A-Fa-f]{6})'", shared)
    assert teal and teal.group(1).upper() in admin, "brand.teal missing from the app palettes"
    assert cream and cream.group(1).upper() in admin, "brand.cream missing from the app palettes"
