"""The render-path key manifest (deep review nit 3).

A key missing from the registry doesn't crash — the loader returns the literal marker
`<MISSING-script: key>`. That is the right behaviour in dev (visible, greppable, testable) and
the worst possible thing to first notice in production, where it lands in a user's thread. A
malformed or truncated future copy drop was the open path to exactly that.

`RENDER_PATH_KEYS` in the bridge is the manifest, and `assert_production_safety` refuses a
staging/prod boot if any of them is absent. The risk with any hand-maintained list is that it
goes stale, so the first test below walks the bridge's own AST: add a new
`orchestration_step("...")` call without listing the key and CI fails.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from app.agents.context_loader import load_orchestration_script
from app.agents.thread_bridge import RENDER_PATH_KEYS
from app.config import Settings

BRIDGE = pathlib.Path(__file__).resolve().parents[1] / "app/agents/thread_bridge.py"


def _literal_keys_rendered_by_the_bridge() -> set[str]:
    """Every `orchestration_step("literal")` in the bridge. Keys chosen dynamically (a dict
    lookup, a ternary) can't be seen this way — those are listed in the manifest by hand and
    covered by the registry-presence test below."""
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "orchestration_step"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.add(node.args[0].value)
    return found


def test_the_ast_walk_actually_finds_calls():
    """Guards the guard — a parser that found nothing would make the next test vacuous."""
    found = _literal_keys_rendered_by_the_bridge()
    assert len(found) >= 15, f"only found {len(found)} rendered keys — the parser is broken"
    assert "three_number_reveal" in found


def test_every_key_the_bridge_renders_is_in_the_manifest():
    """Stops the manifest going stale: a new bridge string must be declared."""
    unlisted = sorted(_literal_keys_rendered_by_the_bridge() - RENDER_PATH_KEYS)
    assert not unlisted, (
        "thread_bridge renders these keys but they aren't in RENDER_PATH_KEYS, so a copy drop "
        "that omitted them would ship <MISSING-script> markers to users:\n  "
        + "\n  ".join(unlisted)
    )


def test_every_manifest_key_exists_in_the_registry_today():
    """The invariant the boot gate enforces, asserted against the current script."""
    missing = sorted(RENDER_PATH_KEYS - set(load_orchestration_script()))
    assert not missing, f"render-path keys absent from the registry: {missing}"


def test_staging_boots_with_the_current_script(monkeypatch):
    """Manifest completeness proven via the boot check — with the two DELIBERATE §3.11
    placeholders (unlock_more.*, rung-2) simulated as authored, since their block is a
    separate, intended gate (see test_orchestration_script). Every RENDER_PATH_KEY must
    exist; only the §3.11 pair may be unauthored."""
    from app.agents import context_loader
    from app.agents.context_loader import load_orchestration_script

    authored = dict(load_orchestration_script())
    for key in ("unlock_more.intro", "unlock_more.item_hint"):
        assert key in authored, f"render-path key {key} missing from the script"
        authored[key] = '[A] "authored stand-in"'
    monkeypatch.setattr(context_loader, "load_orchestration_script", lambda: authored)
    # HIGH-1 (2026-08-19): a staging boot also demands real auth + no fixture fallback;
    # this test stays about the render-path manifest.
    Settings(
        node_env="staging", use_real_auth=True, allow_fixture_fallback=False
    ).assert_production_safety()


def test_a_missing_render_path_key_blocks_the_staging_boot(monkeypatch):
    """The gate itself. Simulate a truncated copy drop and confirm staging refuses to start,
    naming the key — rather than booting and rendering the marker to a user."""
    from app.agents import context_loader

    full = dict(load_orchestration_script())
    victim = "three_number_reveal"
    assert victim in full
    full.pop(victim)
    monkeypatch.setattr(context_loader, "load_orchestration_script", lambda: full)

    with pytest.raises(RuntimeError, match=victim):
        Settings(node_env="staging").assert_production_safety()


def test_dev_still_boots_with_a_missing_key(monkeypatch):
    """Dev must NOT be blocked: the marker is a useful development signal, and blocking local
    work on an in-progress copy drop is how people learn to bypass the gate."""
    from app.agents import context_loader

    partial = dict(load_orchestration_script())
    partial.pop("three_number_reveal")
    monkeypatch.setattr(context_loader, "load_orchestration_script", lambda: partial)

    Settings(node_env="development").assert_production_safety()  # no raise
