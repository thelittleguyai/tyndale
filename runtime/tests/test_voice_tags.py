"""Voice-tier tag renderer (security-week item 5, prep for Brock's authored script).

[A]/[B]/[C] tags on orchestration-script values GOVERN rendering: [B] legal/coverage strings
never render without a citation payload (graceful degradation + doctrine_violation counter
instead), [C] strategy strings refuse to load with outcome-prediction slots, and tags are
never stripped INTO output — no raw tag ever reaches a user. Pull-in day is a file swap."""

from __future__ import annotations

import pytest

from app.agents.context_loader import (
    DOCTRINE_VIOLATIONS,
    PLACEHOLDER_PREFIX,
    load_orchestration_registry,
    load_orchestration_script,
    orchestration_step,
    orchestration_tier,
)


@pytest.fixture
def script(monkeypatch, tmp_path):
    """Point the loader at a temp script (same seam as conftest's real_orchestration_script);
    yields a writer: script('## key\\n[B] body…') → caches cleared both directions."""
    prompts = tmp_path / "prompts"
    prompts.mkdir()

    def write(body: str) -> None:
        (prompts / "orchestration_script.md").write_text(f"---\nversion: 9.9.9\n---\n\n{body}")
        load_orchestration_script.cache_clear()

    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    load_orchestration_script.cache_clear()
    yield write
    load_orchestration_script.cache_clear()


def test_tags_parsed_into_tiers_and_stripped_from_text(script):
    script(
        "## plain_fact\nJust a fact.\n\n"
        "## legal_claim\n[B] Under your plan's terms, this service is covered at {{pct}}%.\n\n"
        "## strategy_line\n[C] Call the billing office first — it's the shortest path here.\n\n"
        "## tagged_fact\n[A] Also a fact.\n"
    )
    reg = load_orchestration_registry()
    assert {k: e.tier for k, e in reg.items()} == {
        "plain_fact": "A", "legal_claim": "B", "strategy_line": "C", "tagged_fact": "A",
    }
    for entry in reg.values():
        assert not entry.text.startswith(("[A]", "[B]", "[C]"))
    assert orchestration_tier("legal_claim") == "B"
    assert orchestration_tier("missing_key") is None


def test_b_without_citation_degrades_and_counts_never_renders_the_claim(script):
    script(
        "## legal_claim\n[B] Under 42 CFR this charge is capped at {{cap}}.\n\n"
        "## legal_claim_degraded\nI need to pull the exact rule text for {{cap}} before I state it.\n"
    )
    DOCTRINE_VIOLATIONS.clear()
    out = orchestration_step("legal_claim", cap="$50")
    assert "42 CFR" not in out  # the uncited legal claim NEVER renders
    assert out == "I need to pull the exact rule text for $50 before I state it."
    assert DOCTRINE_VIOLATIONS["b_without_citation:legal_claim"] == 1

    cited = orchestration_step("legal_claim", citation={"source": "42 CFR §411.15"}, cap="$50")
    assert cited == "Under 42 CFR this charge is capped at $50."
    assert DOCTRINE_VIOLATIONS["b_without_citation:legal_claim"] == 1  # no new violation


def test_b_fallback_ladder_generic_then_neutral_literal(script):
    script(
        "## legal_claim\n[B] Statute says so.\n\n"
        "## generic_degraded\nNo citation on hand yet — flagged for follow-up.\n"
    )
    assert orchestration_step("legal_claim") == "No citation on hand yet — flagged for follow-up."

    script("## legal_claim\n[B] Statute says so.\n")  # no degraded siblings at all
    out = orchestration_step("legal_claim")
    assert "Statute" not in out and out  # neutral engineering line, never the claim, never empty


def test_c_with_prediction_slot_refuses_to_load(script):
    script("## strategy\n[C] You have a {{win_probability}} chance if you appeal.\n")
    with pytest.raises(ValueError, match="win_probability"):
        load_orchestration_registry()


def test_tags_never_appear_in_rendered_output(script):
    script(
        "## a_key\n[A] Fact line.\n\n## b_key\n[B] Claim line.\n\n"
        "## b_key_degraded\nDegraded line.\n\n## c_key\n[C] Strategy line.\n"
    )
    rendered = [
        orchestration_step("a_key"),
        orchestration_step("b_key"),  # degrades
        orchestration_step("b_key", citation={"source": "x"}),
        orchestration_step("c_key"),
    ]
    for out in rendered:
        assert "[A]" not in out and "[B]" not in out and "[C]" not in out


def test_placeholder_guard_still_sees_placeholder_behind_a_tag(script):
    script(f"## k\n[B] {PLACEHOLDER_PREFIX} seeded value.\n")
    assert load_orchestration_script()["k"].startswith(PLACEHOLDER_PREFIX)


def test_repo_script_parses_with_brocks_tiers_and_source_markers():
    """The authored file (v1 content drop): every key carries a valid tier and a source marker
    naming the section of 33_orchestration_script.md it came from."""
    load_orchestration_script.cache_clear()
    try:
        reg = load_orchestration_registry()
        assert reg, "repo orchestration script must parse"
        assert all(e.tier in ("A", "B", "C") for e in reg.values())
        assert {e.tier for e in reg.values()} != {"A"}, "Brock's [C] strategy tags must survive"
        assert all(e.source for e in reg.values()), "every key needs a §/UNMAPPED/ENG marker"
        assert "generic_degraded" in reg  # the [B]-without-citation fallback
        # Markers never leak into rendered copy.
        assert not any("<!--" in e.text for e in reg.values())
    finally:
        load_orchestration_script.cache_clear()


def test_registry_and_script_views_stay_in_sync(script):
    script("## k1\n[B] body {{v}}.\n\n## k2\nplain.\n")
    assert set(load_orchestration_registry()) == set(load_orchestration_script())
    assert load_orchestration_script()["k1"] == "body {{v}}."  # stripped view everywhere


def test_interpolation_still_works_on_tagged_values(script):
    script("## k\n[A] Hello {{name}}.\n")
    assert orchestration_step("k", name="Amy") == "Hello Amy."
