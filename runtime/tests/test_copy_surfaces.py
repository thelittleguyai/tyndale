"""Authored-but-unsurfaced strings, now wired (conformance C3/C4/D3/D8).

The load-bearing one is D3: §2.2 promises "I'll email you the moment it's ready". We only make
that promise if we can keep it — see test_leave_and_return_is_withheld_until_email_is_wired.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.agents.context_loader import load_orchestration_registry, orchestration_step


@pytest.mark.asyncio
async def test_upload_surface_serves_brocks_authored_strings(client: AsyncClient):
    """C3 + C4: the upload screen's copy comes from the REGISTRY, not the app bundle."""
    r = await client.get("/v1/copy/upload")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trust_microcopy"] == orchestration_step("upload_trust_microcopy")  # C4 §1.2
    assert body["just_the_bill"] == orchestration_step("upload_just_the_bill")  # C3 §1.3
    assert body["record_frame"] == orchestration_step("record_first_upload_frame")  # §1.1
    # Verbatim — not paraphrased into the response.
    assert "Encrypted. Never sold. Used only for your audit." in body["trust_microcopy"]
    assert "Just have the bill?" in body["just_the_bill"]


@pytest.mark.asyncio
async def test_leave_and_return_is_withheld_until_email_is_wired(client: AsyncClient):
    """D3 — the honesty gate.

    §2.2 says "you can leave; I'll email you the moment it's ready." Today
    `enable_nudge_emails` is false AND there is no audit-ready email at all (the only outbound
    mail is the document-chase nudge), so rendering it would promise something the product does
    not do. The endpoint withholds it instead — a missing line is honest, a false promise is
    not. It appears automatically once the flag is on."""
    from app.config import get_settings

    assert get_settings().enable_nudge_emails is False, "test premise: email is not wired yet"
    r = await client.get("/v1/copy/status")
    assert r.status_code == 200
    assert r.json()["leave_and_return"] is None  # withheld, not rendered
    # …but the string itself IS authored and in the registry, ready to render.
    assert "status_leave_and_return" in load_orchestration_registry()


@pytest.mark.asyncio
async def test_leave_and_return_renders_once_email_is_wired(client: AsyncClient, monkeypatch):
    """The other half of the gate: flip the flag and the promise is kept, so it renders."""
    from app.config import get_settings
    from app.routes import copy as copy_route

    monkeypatch.setattr(copy_route, "_leave_and_return_is_honest", lambda: True)
    r = await client.get("/v1/copy/status")
    assert r.json()["leave_and_return"] == orchestration_step("status_leave_and_return")
    assert "I'll email you the moment it's ready" in r.json()["leave_and_return"]
    get_settings()  # (no state mutated)


@pytest.mark.asyncio
async def test_capture_copy_is_served_to_the_camera_surface(client: AsyncClient):
    """N1 · C1/C5 — the capture prompts and buttons come from the registry like every other
    string, so the app bundle never becomes a second source of product voice."""
    body = (await client.get("/v1/copy/upload")).json()
    for field, key in (
        ("capture_prompt_bill", "capture.prompt_bill"),
        ("capture_prompt_card", "capture.prompt_card"),
        ("capture_looks_good", "capture.looks_good"),
        ("capture_retake", "capture.retake"),
        ("capture_add_page", "capture.add_page"),
    ):
        assert body[field] == orchestration_step(key), field


@pytest.mark.asyncio
async def test_access_request_surface_can_render_the_intake(client: AsyncClient):
    """Deep review finding 4 — the route and its encrypted event existed, but nothing in the
    app could reach them. The screen renders off this surface, so an empty one is a
    statutory right with no way in."""
    r = await client.get("/v1/copy/access_request")
    assert r.status_code == 200, r.text
    body = r.json()
    for field in ("settings_label", "intro", "type_label", "name_label", "contact_label", "submit"):
        assert body[field], f"{field} is empty — the intake screen can't render"
    assert body["intro"] == orchestration_step("access_request.intro")


def test_access_request_copy_never_implies_a_lookup():
    """The receipt is identical whether or not the person appears anywhere in Tyndale. Copy
    that says "we'll check" or "if we find" turns an intake into a disclosure channel."""
    for key in ("access_request.settings_label", "access_request.intro", "access_request.received"):
        lowered = orchestration_step(key).lower()
        for tell in ("if we find", "we'll check", "we will check", "search our", "look up your"):
            assert tell not in lowered, f"{key} implies a lookup this intake does not do"


def test_capture_copy_claims_nothing_about_readability():
    """Delta B2, at the copy layer. The prototype's capture surface promises "I'll frame the
    edges for you and check it's readable" and stamps a green "Looks readable" badge. We detect
    no document edges and make no readability claim, so no string here may imply either — the
    confirm button is the USER accepting the photo, not us grading it."""
    strings = {
        k: orchestration_step(k)
        for k in (
            "capture.prompt_bill",
            "capture.prompt_card",
            "capture.looks_good",
            "capture.retake",
            "capture.add_page",
        )
    }
    for key, text in strings.items():
        lowered = text.lower()
        assert "readable" not in lowered, f"{key} claims readability we never checked"
        assert "frame the edges" not in lowered, f"{key} promises edge detection we don't do"
        assert not text.startswith("<MISSING-script:"), key


def test_a_placeholder_is_withheld_from_the_client_not_rendered(monkeypatch):
    """A `[PLACEHOLDER-eng]` seed exists so the staging boot gate can BLOCK on it — it is not
    copy. The endpoint treats one like a missing key so a button can never read
    "[PLACEHOLDER-eng] Retake" to a dev user."""
    from app.routes.copy import _is_renderable

    assert _is_renderable("Retake") is True
    assert _is_renderable("[PLACEHOLDER-eng] Retake") is False
    assert _is_renderable("<MISSING-script: capture.retake>") is False


@pytest.mark.asyncio
async def test_unknown_surface_is_404_not_an_arbitrary_key_reader(client: AsyncClient):
    """Named, closed surfaces — never a general "read any registry key" endpoint."""
    assert (await client.get("/v1/copy/decline")).status_code == 404
    assert (await client.get("/v1/copy/attest.intro")).status_code == 404


def test_not_sure_acknowledgment_string_exists_and_is_brocks():
    """D8 §4.4 — the copy that makes "not sure" visibly honoured."""
    text = orchestration_step("verification_not_sure")
    assert "not sure" in text.lower()
    assert "honest answer" in text
    assert not text.startswith("<MISSING-script:")


@pytest.mark.asyncio
async def test_not_sure_answer_posts_the_acknowledgment_to_the_thread(monkeypatch):
    """D8 — the audit proceeds AROUND an unsure item and the thread says so. Asserted at the
    bridge seam (the route's own path kicks a real audit)."""
    from app.agents import thread_bridge

    posted: list[str] = []

    async def _fake_post(case_file_id, *, role, kind, payload=None, content=None):
        posted.append(content or "")
        return "conv"

    monkeypatch.setattr(thread_bridge, "_post", _fake_post)
    await thread_bridge.post_not_sure_acknowledgment("00000000-0000-0000-0000-000000000001")
    assert posted and posted[0] == orchestration_step("verification_not_sure")
