"""The audit-ready email (D3) — §2.2's "I'll email you the moment it's ready".

The load-bearing tests here are the three honesty properties, not the plumbing:

1. **No PHI leaves the building.** The message says a review finished and to sign in — no
   amount, provider, date, claim number, or finding. Asserted against the real DL-47 guard.
2. **A send that didn't happen is never recorded as sent.** This is the exact bug the nudge
   cron had: it logged success without calling SendGrid, stamped its ledger, and lost the
   email permanently because the ledger blocks retries.
3. **The in-app promise renders only when the promise is true.** §2.2 stays withheld until
   this environment actually sends the email.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from httpx import AsyncClient

from app.hooks.pre_tool_use import evaluate_send_email
from app.notify import audit_ready
from app.notify.audit_ready import _bodies, should_send


# --- 1 · which transitions earn an email -------------------------------------------------
def test_both_terminal_outcomes_email_the_user():
    """A user who was told "I'll email you when it's ready" and then needs to supply a
    document has still left and is still waiting. Emailing only on success would keep the
    promise exactly when it's easy and break it when the user most needs to hear from us."""
    assert should_send("audit_complete", None) is True
    assert should_send("audit_incomplete", "needs_documents") is True


def test_a_system_error_does_not_email():
    """We don't push a failure into someone's inbox with nothing for them to do — the thread
    says it and the admin System page is alerted."""
    assert should_send("audit_incomplete", "system_error") is False


def test_non_terminal_transitions_never_email():
    for status in ("open", "audit_running", "encounter_verified", "not_a_bill", "extraction_failed"):
        assert should_send(status, None) is False, status


# --- 2 · PHI discipline (DL-47) ----------------------------------------------------------
@pytest.mark.parametrize("ready", [True, False])
def test_the_email_body_carries_nothing_about_the_bill(ready: bool):
    """Nothing case-specific is interpolated at all — only the sign-in URL — so there is no
    path by which an amount or a provider name reaches an inbox."""
    subject, text, html = _bodies(ready, "https://app.example.test/signed-in")
    blob = f"{subject} {text} {html}"
    for leak in ("$", "MRI", "Beloit", "claim", "account #", "deductible", "diagnosis"):
        assert leak.lower() not in blob.lower(), f"{leak!r} reached the email body"


@pytest.mark.parametrize("ready", [True, False])
def test_the_real_phi_guard_approves_both_bodies(ready: bool):
    """Asserted through the actual DL-47 guard, not a re-implementation of it — if the guard
    tightens, this fails and the copy gets fixed rather than the send being blocked in prod."""
    subject, text, _ = _bodies(ready, "https://app.example.test/signed-in")
    decision = evaluate_send_email({"to": "someone@example.test", "subject": subject, "body": text})
    assert decision.approved, decision.block_reason


def test_the_two_bodies_say_different_things():
    ready_text = _bodies(True, "u")[1]
    needs_text = _bodies(False, "u")[1]
    assert ready_text != needs_text
    assert "ready" in _bodies(True, "u")[0].lower()
    assert "still need" in needs_text.lower()


# --- 3 · exactly-once, and never "sent" without a send -----------------------------------
class _Case:
    def __init__(self, status="audit_complete", reason=None, sent_at=None):
        self.case_file_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.status = status
        self.audit_incomplete_reason = reason
        self.audit_ready_email_sent_at = sent_at


class _User:
    def __init__(self, email="member@example.test", blocked=False, deleted=None):
        self.user_id = uuid.uuid4()
        self.email = email
        self.is_blocked = blocked
        self.soft_deleted_at = deleted


def _patch_db(monkeypatch, case, user):
    """Stand in for AsyncSessionLocal so the policy is testable without a DB round-trip."""

    class _Result:
        def __init__(self, obj):
            self._obj = obj

        def scalar_one_or_none(self):
            return self._obj

    class _Session:
        async def execute(self, stmt):
            # The case query selects CaseFile; the user query selects User.
            entity = str(stmt).lower()
            return _Result(user if "users" in entity else case)

        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(audit_ready, "AsyncSessionLocal", lambda: _Session())


@pytest.mark.asyncio
async def test_a_failed_send_is_not_stamped_so_it_retries(monkeypatch):
    """THE bug the nudge cron had. If the provider didn't accept it, the case must stay
    unstamped — a lost email is worse than a duplicate attempt at the same state."""
    case, user = _Case(), _User()
    _patch_db(monkeypatch, case, user)
    monkeypatch.setattr(audit_ready, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": True, "auth_success_redirect": "https://app.example.test"})())
    monkeypatch.setattr(audit_ready, "send_product_email", _always(False))

    assert await audit_ready.send_audit_ready_email(str(case.case_file_id)) is False
    assert case.audit_ready_email_sent_at is None  # NOT recorded — the next transition retries


@pytest.mark.asyncio
async def test_a_successful_send_is_stamped_once(monkeypatch):
    case, user = _Case(), _User()
    _patch_db(monkeypatch, case, user)
    monkeypatch.setattr(audit_ready, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": True, "auth_success_redirect": "https://app.example.test"})())
    calls: list[str] = []

    async def _send(to, subject, text, html=None, *, kind):
        calls.append(subject)
        return True

    monkeypatch.setattr(audit_ready, "send_product_email", _send)
    assert await audit_ready.send_audit_ready_email(str(case.case_file_id)) is True
    assert case.audit_ready_email_sent_at is not None
    # Second call: already stamped -> no second message.
    assert await audit_ready.send_audit_ready_email(str(case.case_file_id)) is False
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_nothing_sends_while_the_flag_is_off(monkeypatch):
    case, user = _Case(), _User()
    _patch_db(monkeypatch, case, user)
    monkeypatch.setattr(audit_ready, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": False, "auth_success_redirect": "x"})())
    monkeypatch.setattr(audit_ready, "send_product_email", _always(True))
    assert await audit_ready.send_audit_ready_email(str(case.case_file_id)) is False
    assert case.audit_ready_email_sent_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user",
    [_User(email=""), _User(blocked=True), _User(deleted=datetime.datetime.now(datetime.timezone.utc))],
    ids=["no-email", "blocked", "soft-deleted"],
)
async def test_we_do_not_mail_accounts_we_should_not(monkeypatch, user):
    case = _Case()
    _patch_db(monkeypatch, case, user)
    monkeypatch.setattr(audit_ready, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": True, "auth_success_redirect": "x"})())
    monkeypatch.setattr(audit_ready, "send_product_email", _always(True))
    assert await audit_ready.send_audit_ready_email(str(case.case_file_id)) is False


def _always(value: bool):
    async def _f(*a, **kw):
        return value

    return _f


# --- 4 · D3: the in-app line follows the email, not the other way round ------------------
@pytest.mark.asyncio
async def test_the_leave_and_return_line_is_withheld_until_this_env_sends(client: AsyncClient):
    from app.config import get_settings

    assert get_settings().enable_audit_ready_email is False, "test premise: not enabled here"
    assert (await client.get("/v1/copy/status")).json()["leave_and_return"] is None


@pytest.mark.asyncio
async def test_the_line_renders_once_the_email_is_switched_on(client: AsyncClient, monkeypatch):
    """The promise becomes true, so it gets made. No code change needed — just the flag."""
    from app.routes import copy as copy_route

    monkeypatch.setattr(copy_route, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": True})())
    body = (await client.get("/v1/copy/status")).json()
    assert body["leave_and_return"] and "email you the moment it's ready" in body["leave_and_return"]


def test_the_gate_is_the_audit_ready_flag_not_the_nudge_flag(monkeypatch):
    """The nudge is a +3d reminder about a missing document — a different promise. Wiring
    §2.2 to it would let the line render off the wrong switch."""
    from app.routes import copy as copy_route

    monkeypatch.setattr(copy_route, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": False, "enable_nudge_emails": True})())
    assert copy_route._leave_and_return_is_honest() is False


# ── §10.4 — the recovery email (system_error -> audit_complete) ──────────────────────────
def test_recovery_body_is_phi_free_and_passes_the_real_guard():
    from app.notify.audit_ready import _recovery_bodies

    subject, text, html = _recovery_bodies("https://app.example.test/signed-in")
    blob = f"{subject} {text} {html}".lower()
    for leak in ("$", "mri", "beloit", "claim", "account #", "deductible"):
        assert leak not in blob, f"{leak!r} reached the recovery email"
    decision = evaluate_send_email({"to": "m@example.test", "subject": subject, "body": text})
    assert decision.approved, decision.block_reason


@pytest.mark.asyncio
async def test_recovery_sends_once_and_only_for_completed_cases(monkeypatch):
    case, user = _Case(status="audit_complete"), _User()
    case.recovery_email_sent_at = None
    _patch_db(monkeypatch, case, user)
    monkeypatch.setattr(audit_ready, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": True, "auth_success_redirect": "https://app.example.test"})())
    sends: list[str] = []

    async def _send(to, subject, text, html=None, *, kind):
        sends.append(kind)
        return True

    monkeypatch.setattr(audit_ready, "send_product_email", _send)
    assert await audit_ready.send_recovery_email(str(case.case_file_id)) is True
    assert case.recovery_email_sent_at is not None and sends == ["recovery"]
    # exactly once
    assert await audit_ready.send_recovery_email(str(case.case_file_id)) is False
    assert sends == ["recovery"]


@pytest.mark.asyncio
async def test_recovery_never_sends_for_a_still_broken_case_or_with_the_flag_off(monkeypatch):
    broken = _Case(status="audit_incomplete", reason="system_error")
    broken.recovery_email_sent_at = None
    _patch_db(monkeypatch, broken, _User())
    monkeypatch.setattr(audit_ready, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": True, "auth_success_redirect": "x"})())
    monkeypatch.setattr(audit_ready, "send_product_email", _always(True))
    assert await audit_ready.send_recovery_email(str(broken.case_file_id)) is False

    done = _Case(status="audit_complete")
    done.recovery_email_sent_at = None
    _patch_db(monkeypatch, done, _User())
    monkeypatch.setattr(audit_ready, "get_settings", lambda: type("S", (), {
        "enable_audit_ready_email": False, "auth_success_redirect": "x"})())
    assert await audit_ready.send_recovery_email(str(done.case_file_id)) is False


def test_system_error_thread_key_follows_the_flag(monkeypatch):
    """The §10.4 clause renders ONLY where the email actually sends — D3's pattern. Flag on →
    his full string (with the promise, now true); flag off → the no-email variant."""
    from app.agents import thread_bridge
    from app.agents.context_loader import orchestration_step

    full = orchestration_step("system_error")
    trimmed = orchestration_step("system_error_no_email")
    assert "email you" in full and "email you" not in trimmed
    assert not trimmed.startswith("<MISSING-script:")
    # Both keys are in the render-path manifest so a copy drop can't strand either state.
    assert {"system_error", "system_error_no_email"} <= thread_bridge.RENDER_PATH_KEYS


# ── synthetic recipients never reach the provider (2026-08-18) ───────────────────────────
@pytest.mark.asyncio
async def test_synthetic_e2e_recipients_are_never_sent_to_sendgrid(monkeypatch):
    """The sweep fired ~15 real sends at @e2e.tyndale.test — a reserved TLD that can never
    deliver — in under an hour: a spam-trap signature that can get the SendGrid account
    paused (the 2026-08-18 mail-send 401s). Synthetic recipients short-circuit BEFORE any
    network call, and return False so exactly-once stamps stay honest."""
    from app.notify import email as email_mod

    called: list[str] = []

    class _NeverClient:
        def __init__(self, *a, **kw):
            called.append("client")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise AssertionError("a synthetic recipient reached the provider")

    monkeypatch.setattr(email_mod, "get_settings", lambda: type("S", (), {
        "sendgrid_api_key": "SG.real-looking-key", "sendgrid_from_email": "no-reply@t.test"})())
    monkeypatch.setattr(email_mod.httpx, "AsyncClient", _NeverClient)

    ok = await email_mod.send_product_email(
        "e2e-runner@e2e.tyndale.test", "Your review is ready", "Sign in to see it.",
        kind="audit_ready",
    )
    assert ok is False and called == []
