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
from functools import lru_cache
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


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
