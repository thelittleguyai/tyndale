"""Crisis classifier (DL-04) — real Haiku layer + deterministic keyword fallback.

No DB / no LLM needed: the keyword screen runs offline, and the Haiku layer is
exercised by monkeypatching the client factory / creds gate.
"""

from __future__ import annotations

import importlib

import pytest

from app.hooks.contracts import CrisisClassifierInput

# app.hooks.__init__ re-exports the crisis_classifier FUNCTION, which shadows the
# submodule of the same name — so `from app.hooks import crisis_classifier` (and
# even `import app.hooks.crisis_classifier as cc`) both bind the function, not the
# module. Load the module explicitly so monkeypatching its internals takes effect.
cc = importlib.import_module("app.hooks.crisis_classifier")


# --- keyword fallback (no creds → deterministic screen) ----------------------
@pytest.mark.asyncio
async def test_keyword_fallback_screens_obvious_crisis(monkeypatch):
    # No real classifier path → keyword screen is the only layer.
    monkeypatch.setattr(cc, "_real_classifier_enabled", lambda: False)
    for msg in (
        "I don't want to be here anymore.",
        "I've been thinking about suicide.",
        "I might overdose tonight.",
        "I want to hurt myself.",
    ):
        res = await cc.crisis_classifier_async(CrisisClassifierInput(raw_message=msg))
        assert res.crisis_detected is True, msg


@pytest.mark.asyncio
async def test_benign_message_not_detected(monkeypatch):
    monkeypatch.setattr(cc, "_real_classifier_enabled", lambda: False)
    for msg in (
        "This bill is killing me, can you help?",
        "My insurer denied a $1,200 claim.",
        "What does CPT 27447 mean?",
    ):
        res = await cc.crisis_classifier_async(CrisisClassifierInput(raw_message=msg))
        assert res.crisis_detected is False, msg


# --- Haiku layer: positive signal --------------------------------------------
@pytest.mark.asyncio
async def test_haiku_positive_detected(monkeypatch):
    monkeypatch.setattr(cc, "_real_classifier_enabled", lambda: True)

    async def _yes(_msg):
        return True

    monkeypatch.setattr(cc, "_haiku_detects_crisis", _yes)
    res = await cc.crisis_classifier_async(
        CrisisClassifierInput(raw_message="a message with no obvious keyword")
    )
    assert res.crisis_detected is True


# --- Haiku raises → keyword fallback still screens obvious cases --------------
@pytest.mark.asyncio
async def test_haiku_raises_falls_back_to_keyword(monkeypatch):
    monkeypatch.setattr(cc, "_real_classifier_enabled", lambda: True)

    async def _boom(_msg):
        raise RuntimeError("classifier down / timeout")

    monkeypatch.setattr(cc, "_haiku_detects_crisis", _boom)

    # Obvious keyword case still screens even though Haiku errored (fail-safe).
    hit = await cc.crisis_classifier_async(
        CrisisClassifierInput(raw_message="I'm going to kill myself")
    )
    assert hit.crisis_detected is True

    # Benign case: Haiku errored, keyword screen says no → not detected (never
    # fails OPEN into a false positive that blocks normal billing help... but note
    # it also never fails open on a real crisis, which the case above proves).
    benign = await cc.crisis_classifier_async(
        CrisisClassifierInput(raw_message="please explain my deductible")
    )
    assert benign.crisis_detected is False


# --- Haiku says NO but keyword fires → honor the keyword (no false negatives) -
@pytest.mark.asyncio
async def test_keyword_overrides_haiku_negative(monkeypatch):
    monkeypatch.setattr(cc, "_real_classifier_enabled", lambda: True)

    async def _no(_msg):
        return False

    monkeypatch.setattr(cc, "_haiku_detects_crisis", _no)
    res = await cc.crisis_classifier_async(
        CrisisClassifierInput(raw_message="I want to end my life")
    )
    assert res.crisis_detected is True


# --- sync entry point works outside a running loop ---------------------------
def test_sync_entrypoint_keyword_screen(monkeypatch):
    monkeypatch.setattr(cc, "_real_classifier_enabled", lambda: False)
    assert (
        cc.crisis_classifier(CrisisClassifierInput(raw_message="I want to die")).crisis_detected
        is True
    )
    assert (
        cc.crisis_classifier(
            CrisisClassifierInput(raw_message="help me read my EOB")
        ).crisis_detected
        is False
    )
