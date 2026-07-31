"""Load Tyndale's authoring assets from ``intelligence-layer/`` into agent context.

Lazy + lru_cache'd so the disk reads happen once per process. The behavioral
core gets prepended IN FULL to every subagent system prompt (Change Order 001
item 1). Skills get appended after the subagent prompt — Bill Detective
loads ``bill_error_detection``, Math Person loads ``coverage_connection_fhir``
+ ``cost_estimation``.

Repo layout:
    intelligence-layer/
      reference/behavioral_core.md
      subagents/lead_planner/v1_lite/system_prompt.md   # V1-Lite Lead Planner
      subagents/lead_planner/system_prompt.md           # full V1 Lead Planner
      subagents/bill_detective/system_prompt.md
      subagents/math_person/system_prompt.md
      skills/<skill_name>/SKILL.md
      skills/<skill_name>/00_diagnostic_index.md   # if present

The root is derived from this file's location (``runtime/app/agents/`` →
parent → parent → parent → ``intelligence-layer/``). Override via the
``TYNDALE_INTELLIGENCE_LAYER_ROOT`` env var for tests.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import structlog

log = structlog.get_logger(__name__)

# Engineering seed-copy sentinel for the orchestration script (D1, Brock 2026-07-10). A
# staging/production boot fails while any active script value still carries this prefix.
PLACEHOLDER_PREFIX = "[PLACEHOLDER-eng]"

_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
# One `## <key>` heading (on its own line) → its string body, up to the next `## `.
# Keys are snake_case with optional dot namespacing (`attest.intro`, `wrongdoc.card`) —
# Brock's §3/§5/§10/§12 keys are dot-namespaced, so the charset admits dots. Meta headings
# like `## Variables (…)` (not a bare identifier) are ignored.
_SCRIPT_KEY_RE = re.compile(
    r"^##\s+([a-z][a-z0-9_.]*)\s*$\n+(.+?)(?=\n##\s|\Z)", re.DOTALL | re.MULTILINE
)

# --- Voice-tier tags (security-week item 5; Brock's script format) -----------
# A value body may LEAD with a voice-tier tag — `[A]` fact / `[B]` legal-coverage
# claim / `[C]` strategy — which GOVERNS rendering and is never shown to users:
#   * the tag is stripped before any render (and before the placeholder guard);
#   * [B] strings require a citation payload at render time — without one the
#     graceful-degradation variant renders instead (never an uncited legal claim);
#   * [C] strings must not carry outcome-prediction slots (asserted at load).
# Untagged values default to tier A (plain fact copy), which is every current
# placeholder — Brock's tagged file drops in with no loader change.
_TIER_TAG_RE = re.compile(r"\A\[([ABC])\]\s*")
# Outcome-prediction slots are forbidden EVERYWHERE by doctrine, and load-asserted
# for [C] strategy strings specifically ("[C] never predicts an outcome").
_FORBIDDEN_PREDICTION_SLOT_RE = re.compile(
    r"\{\{\s*(?:win_probability|success_probability|success_rate|likelihood|odds_of|chance_of)"
    r"[a-z_]*\s*\}\}",
    re.IGNORECASE,
)

# In-process doctrine-violation counter (mirrors analytics' DROP_COUNTER pattern):
# `b_without_citation:<key>` increments each time a [B] string would have rendered
# uncited and the degradation variant rendered instead.
DOCTRINE_VIOLATIONS: Counter[str] = Counter()


class ScriptEntry(NamedTuple):
    """One orchestration-script registry entry: the render text (tag stripped) + its tier."""

    text: str
    tier: str  # "A" | "B" | "C"


def _intelligence_layer_root() -> Path:
    override = os.environ.get("TYNDALE_INTELLIGENCE_LAYER_ROOT")
    if override:
        return Path(override).resolve()
    # runtime/app/agents/context_loader.py -> repo_root/intelligence-layer
    here = Path(__file__).resolve()
    return here.parents[3] / "intelligence-layer"


def _read(rel: str) -> str:
    path = _intelligence_layer_root() / rel
    if not path.exists():
        log.warning("context_loader.missing", path=str(path))
        return f"<MISSING: {rel}>\n"
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_orchestration_registry() -> dict[str, ScriptEntry]:
    """Parse ``prompts/orchestration_script.md`` → ``{key: ScriptEntry(text, tier)}``.

    Each ``## <snake_case_key>`` heading delimits one system-authored thread string; the YAML
    frontmatter, the ``# title``, and the ``## Variables (…)`` meta section are ignored. A
    leading ``[A]/[B]/[C]`` voice-tier tag is parsed OFF the value (default tier A) — tags
    govern rendering and are never part of the render text. Loaded verbatim otherwise —
    engineering never copy-edits these values.

    Load-time doctrine assert: a [C] strategy string carrying an outcome-prediction slot
    (``{{win_probability}}``-style) raises — that copy must never boot, in any environment.
    The full key→tier inventory is logged once for the eval judge."""
    text = _read("prompts/orchestration_script.md")
    if text.startswith("<MISSING:"):
        return {}
    text = _FRONTMATTER_RE.sub("", text, count=1)
    registry: dict[str, ScriptEntry] = {}
    for m in _SCRIPT_KEY_RE.finditer(text):
        key, body = m.group(1), m.group(2).strip()
        tag = _TIER_TAG_RE.match(body)
        tier = tag.group(1) if tag else "A"
        body = _TIER_TAG_RE.sub("", body, count=1).strip()
        if tier == "C" and (hit := _FORBIDDEN_PREDICTION_SLOT_RE.search(body)):
            raise ValueError(
                f"orchestration_script key '{key}' is [C] strategy copy but carries the "
                f"outcome-prediction slot {hit.group(0)!r} — [C] never predicts an outcome "
                "(voice-tier doctrine); fix the authored script"
            )
        registry[key] = ScriptEntry(text=body, tier=tier)
    log.info(
        "orchestration_script.key_inventory",  # for the judge: the full key→tier map
        keys={k: e.tier for k, e in registry.items()},
        counts=dict(Counter(e.tier for e in registry.values())),
    )
    return registry


def load_orchestration_script() -> dict[str, str]:
    """Back-compat view of the registry: ``{key: render_text}`` with tier tags stripped —
    exactly what the placeholder guard and existing callers expect (a tagged
    ``[B] [PLACEHOLDER-eng] …`` value still startswith-matches the placeholder prefix)."""
    return {k: e.text for k, e in load_orchestration_registry().items()}


def _clear_script_caches() -> None:
    load_orchestration_registry.cache_clear()


# Tests clear via load_orchestration_script.cache_clear() (the pre-registry seam) — keep it
# working by pointing it at the real (registry) cache.
load_orchestration_script.cache_clear = _clear_script_caches  # type: ignore[attr-defined]


def orchestration_tier(key: str) -> str | None:
    """The voice tier ("A"|"B"|"C") for a script key, or None when the key is absent."""
    entry = load_orchestration_registry().get(key)
    return entry.tier if entry else None


def _interpolate(text: str, variables: dict[str, object]) -> str:
    for name, val in variables.items():
        text = text.replace(f"{{{{{name}}}}}", str(val))
    return text


def orchestration_step(key: str, /, citation: dict | None = None, **variables: object) -> str:
    """The thread string for ``key`` with ``{{var}}`` slots interpolated.

    Voice-tier enforcement (item 5): a [B] legal/coverage string REQUIRES a ``citation``
    payload — rendered without one, the graceful-degradation variant renders instead
    (``<key>_degraded`` if authored, else ``generic_degraded``, else a neutral engineering
    line that makes no legal claim) and the ``doctrine_violation`` counter increments.
    Never an uncited legal claim; never a crash; tags never reach the output.

    Returns an explicit ``<MISSING-script: key>`` marker (never a silent empty string) when
    the key is absent, so a missing key is visible in the thread and catchable in tests.
    Unknown slots are left as-is."""
    registry = load_orchestration_registry()
    entry = registry.get(key)
    if entry is None:
        return f"<MISSING-script: {key}>"
    if entry.tier == "B" and not citation:
        DOCTRINE_VIOLATIONS[f"b_without_citation:{key}"] += 1
        log.warning("doctrine_violation", kind="b_without_citation", key=key)
        fallback = registry.get(f"{key}_degraded") or registry.get("generic_degraded")
        if fallback is not None:
            return _interpolate(fallback.text, variables)
        # Last-resort neutral line (no legal claim). Seeded as `generic_degraded` in the
        # placeholder script so this literal should never fire with an authored file.
        return (
            "I can't show you the exact rule text behind this yet — I've flagged it and "
            "will follow up with the citation."
        )
    return _interpolate(entry.text, variables)


@lru_cache(maxsize=1)
def load_behavioral_core() -> str:
    return _read("reference/behavioral_core.md")


@lru_cache(maxsize=1)
def load_voice_tiering() -> str:
    return _read("reference/voice_tiering.md")


@lru_cache(maxsize=1)
def load_citations() -> str:
    return _read("reference/citations.md")


@lru_cache(maxsize=1)
def load_refusals() -> str:
    return _read("reference/refusals.md")


@lru_cache(maxsize=1)
def load_v1lite_lead_planner_prompt() -> str:
    return _read("subagents/lead_planner/v1_lite/system_prompt.md")


@lru_cache(maxsize=1)
def load_bill_detective_prompt() -> str:
    return _read("subagents/bill_detective/system_prompt.md")


@lru_cache(maxsize=1)
def load_math_person_prompt() -> str:
    return _read("subagents/math_person/system_prompt.md")


@lru_cache(maxsize=32)
def load_skill(skill_name: str) -> str:
    """Concatenate SKILL.md + 00_diagnostic_index.md (if present) for a Skill.

    The deeper reference files inside each Skill's subdirs intentionally do
    NOT load here — they're meant to be surfaced by the diagnostic index as
    the model's investigation calls for them (two-layer Skill architecture
    per intelligence-layer/skills/<skill>/README.md). For V1-Lite walking
    skeleton, the surface layer is sufficient.
    """
    base = _intelligence_layer_root() / "skills" / skill_name
    chunks: list[str] = []
    for fname in ("SKILL.md", "00_diagnostic_index.md"):
        p = base / fname
        if p.exists():
            chunks.append(f"## {skill_name}/{fname}\n\n{p.read_text(encoding='utf-8')}")
    if not chunks:
        log.warning("context_loader.skill_missing", skill=skill_name)
        return f"<MISSING SKILL: {skill_name}>\n"
    return "\n\n---\n\n".join(chunks)


def compose_system_prompt(
    subagent_name: str,
    *,
    include_skills: list[str] | None = None,
) -> list[dict]:
    """Build a Claude API ``system`` array for a subagent.

    Returned shape uses Anthropic's prompt-caching blocks — behavioral_core,
    voice_tiering, and the subagent prompt are all cache-marked since they
    don't change session-to-session.
    """
    behavioral = load_behavioral_core()
    voice = load_voice_tiering()
    citations = load_citations()

    if subagent_name == "lead_planner_v1_lite":
        subagent_prompt = load_v1lite_lead_planner_prompt()
    elif subagent_name == "bill_detective":
        subagent_prompt = load_bill_detective_prompt()
    elif subagent_name == "math_person":
        subagent_prompt = load_math_person_prompt()
    else:
        raise ValueError(f"unknown subagent: {subagent_name}")

    blocks: list[dict] = [
        # The behavioral core is prepended in full to EVERY agent session per
        # Change Order 001 item 1. Cached aggressively.
        {
            "type": "text",
            "text": f"# Behavioral Core (prepended to every Tyndale agent session)\n\n{behavioral}",
            "cache_control": {"type": "ephemeral"},
        },
        # Voice tiering + citations format — referenced from behavioral_core but
        # included verbatim so the model has them in context.
        {
            "type": "text",
            "text": f"# Voice Tiering\n\n{voice}\n\n# Citations\n\n{citations}",
            "cache_control": {"type": "ephemeral"},
        },
        # The subagent's own system prompt.
        {
            "type": "text",
            "text": f"# Subagent System Prompt — {subagent_name}\n\n{subagent_prompt}",
            "cache_control": {"type": "ephemeral"},
        },
    ]

    if include_skills:
        skills_text = "\n\n---\n\n".join(load_skill(s) for s in include_skills)
        blocks.append(
            {
                "type": "text",
                "text": f"# Skills loaded for this session\n\n{skills_text}",
                "cache_control": {"type": "ephemeral"},
            }
        )

    return blocks


@lru_cache(maxsize=4)
def load_chat_mode_prompt(mode: str) -> str:
    """Load a CO-10 chat-mode system prompt (``per_case`` or ``freeform``)."""
    if mode not in ("per_case", "freeform"):
        raise ValueError(f"unknown chat mode: {mode}")
    return _read(f"prompts/chat_modes/{mode}_mode.md")


def compose_chat_system_prompt(mode: str) -> list[dict]:
    """Build the Claude ``system`` array for a chat turn (Phase CO-10).

    Same cached behavioral-core + voice-tiering + citations stack every agent
    gets, then the mode-specific chat prompt (per_case vs freeform). The mode
    prompt is what makes per-case mode case-aware and freeform mode emit the
    create_case_cta when a specific situation is described.
    """
    behavioral = load_behavioral_core()
    voice = load_voice_tiering()
    citations = load_citations()
    mode_prompt = load_chat_mode_prompt(mode)

    return [
        {
            "type": "text",
            "text": f"# Behavioral Core (prepended to every Tyndale agent session)\n\n{behavioral}",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"# Voice Tiering\n\n{voice}\n\n# Citations\n\n{citations}",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"# Chat Mode — {mode}\n\n{mode_prompt}",
            "cache_control": {"type": "ephemeral"},
        },
    ]
