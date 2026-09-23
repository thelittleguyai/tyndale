"""§10.4's promise, kept (e2e re-test 2026-09-23, item 3).

"Give it another moment, or I'll email you the moment I've got it working again" rendered on
every system_error — and nothing ever re-ran a system_error audit, so the recovery email
(migration 0040) could never fire: its trigger looked for a system_error → audit_complete
write, and every run goes through audit_running first. Now:

  * the audit_retry cron re-runs a system_error audit, bounded (15 min, then 1 h, then a
    person), with the failed run's writes cleared first;
  * the recovered run's terminal write fires the recovery email — once;
  * the apology promises the email only where BOTH the email and the auto-recovery exist;
  * Admin › System's system_error item is read from the cases (not a per-replica counter),
    split into "recovering" and "needs a person", and an Azure Monitor rule mails a person.
"""

from __future__ import annotations

import pathlib
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.agents import orchestrator
from app.agents.runner import RunResult
from app.config import get_settings
from app.crons import audit_retry_cron
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding

REPO = pathlib.Path(__file__).resolve().parents[2]


async def _system_error_case(client: AsyncClient, *, failed_ago=timedelta(minutes=20), attempts=0) -> str:
    up = await client.post("/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))])
    case_id = up.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        # what the failed run left behind: a half-written finding nobody was ever shown
        s.add(Finding(case_file_id=uuid.UUID(case_id), finding_type="provider_side", category="stale_from_the_failed_run",
                      subagent_source="bill_detective", voice_tier="A", facts={}))
        await s.commit()
        await s.execute(
            update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)).values(
                status="audit_incomplete", audit_incomplete_reason="system_error",
                recovery_attempts=attempts, recovery_retry_after=None,
                updated_at=datetime.now(timezone.utc) - failed_ago,
            )
        )
        await s.commit()
    return case_id


async def _row(case_id: str) -> CaseFile:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))).scalar_one()


async def _park_other_system_errors(keep: str) -> None:
    """The shared local DB can hold system_error cases from other runs — keep them out of the
    sweep's way (it claims the OLDEST due row first)."""
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(CaseFile)
            .where(CaseFile.audit_incomplete_reason == "system_error", CaseFile.case_file_id != uuid.UUID(keep))
            .values(recovery_retry_after=datetime.now(timezone.utc) + timedelta(days=30))
        )
        await s.commit()


def _real_agents_that_complete(monkeypatch):
    """The re-run's agents: Math Person writes the three numbers, the Lead Planner composes."""
    from app.agents import bill_detective, lead_planner, math_person

    async def _bd(case_file_id, *, mode, confirmations, session=None):
        return RunResult(final_text="bd", tool_calls=[], usage={})

    async def _mp(case_file_id, *, accumulator=None, session=None):
        async with AsyncSessionLocal() as s:
            s.add(Finding(case_file_id=uuid.UUID(case_file_id), finding_type="payer_side", category="deductible_misapplied",
                          subagent_source="math_person", voice_tier="A",
                          facts={"provider_billed": 7600.0, "eob_member_responsibility": 538.0, "tyndale_computed": 412.0}))
            await s.commit()
        return RunResult(final_text="mp", tool_calls=[], usage={})

    async def _lp(*_a, **_k):
        return RunResult(final_text="Recovered summary.", tool_calls=[], usage={})

    monkeypatch.setattr(bill_detective, "run", _bd)
    monkeypatch.setattr(math_person, "run", _mp)
    monkeypatch.setattr(lead_planner, "compose_final", _lp)
    s = get_settings()
    monkeypatch.setattr(s, "use_real_claude", True)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test-fake")
    monkeypatch.setattr(s, "litellm_proxy_url", None)


# ── the re-run, and the email it finally makes true ─────────────────────────────────────
@pytest.mark.asyncio
async def test_a_recovered_audit_completes_clean_and_emails_its_user_once(client: AsyncClient, monkeypatch):
    from app.notify import audit_ready

    case_id = await _system_error_case(client)
    _real_agents_that_complete(monkeypatch)
    monkeypatch.setattr(get_settings(), "enable_audit_ready_email", True)
    sent: list[str] = []

    async def _send(to, subject, text, html, *, kind):
        sent.append(kind)
        return True

    monkeypatch.setattr(audit_ready, "send_product_email", _send)
    async with AsyncSessionLocal() as s:  # the sweep's claim: an attempt spent
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)).values(recovery_attempts=1))
        await s.commit()

    result = await orchestrator.finalize_audit(case_id, recovery=True)

    assert result is not None and result.status == "complete" and result.audit is not None
    row = await _row(case_id)
    assert row.status == "audit_complete" and row.audit_incomplete_reason is None
    assert "recovery" in sent and row.recovery_email_sent_at is not None  # §10.4, finally true
    assert row.recovery_attempts == 0 and row.recovery_retry_after is None  # the episode is over
    async with AsyncSessionLocal() as s:
        cats = {f.category for f in (await s.execute(select(Finding).where(Finding.case_file_id == uuid.UUID(case_id)))).scalars()}
    assert "stale_from_the_failed_run" not in cats and "deductible_misapplied" in cats  # no duplicates

    # the email is sent once — a later re-audit of the same case does not repeat it
    sent.clear()
    await orchestrator._set_status(case_id, "audit_running")
    await orchestrator._set_status(case_id, "audit_complete")
    assert "recovery" not in sent


@pytest.mark.asyncio
async def test_a_case_that_moved_on_is_never_re_run(client: AsyncClient):
    case_id = await _system_error_case(client)
    async with AsyncSessionLocal() as s:
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)).values(audit_incomplete_reason="needs_documents"))
        await s.commit()
    assert await orchestrator.finalize_audit(case_id, recovery=True) is None
    row = await _row(case_id)
    assert row.status == "audit_incomplete" and row.audit_incomplete_reason == "needs_documents"


# ── the bounded sweep ───────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_the_sweep_waits_then_re_runs_twice_then_hands_it_to_a_person(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "audit_wall_clock_budget_seconds", 1)
    fresh = await _system_error_case(client, failed_ago=timedelta(minutes=2))
    await _park_other_system_errors(fresh)
    runs: list[str] = []

    async def _still_broken(case_file_id):
        runs.append(case_file_id)
        return None  # finalize wrote system_error again

    # failed two minutes ago: not due yet (the provider was throttling a moment ago)
    assert (await audit_retry_cron.recover_system_errors(time.monotonic() + 120, rerun=_still_broken))["failed_again"] == 0
    assert runs == []

    async with AsyncSessionLocal() as s:
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(fresh)).values(
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=20)))
        await s.commit()
    tally = await audit_retry_cron.recover_system_errors(time.monotonic() + 120, rerun=_still_broken)
    assert tally["failed_again"] == 1 and runs == [fresh]
    row = await _row(fresh)
    assert row.recovery_attempts == 1
    assert timedelta(minutes=59) < row.recovery_retry_after - datetime.now(timezone.utc) <= timedelta(hours=1)

    # an hour later: the second and last re-run fails too → a person
    async with AsyncSessionLocal() as s:
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(fresh)).values(
            recovery_retry_after=datetime.now(timezone.utc) - timedelta(minutes=1)))
        await s.commit()
    tally = await audit_retry_cron.recover_system_errors(time.monotonic() + 120, rerun=_still_broken)
    assert tally["exhausted"] == 1 and (await _row(fresh)).recovery_attempts == 2
    # …and the scheduled sweep leaves it alone from then on
    async with AsyncSessionLocal() as s:
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(fresh)).values(
            recovery_retry_after=datetime.now(timezone.utc) - timedelta(minutes=1)))
        await s.commit()
    assert sum((await audit_retry_cron.recover_system_errors(time.monotonic() + 120, rerun=_still_broken)).values()) == 0

    # the admin's force pass (after fixing the cause) takes it past the cap
    async def _fixed(case_file_id):
        await orchestrator._set_status(case_file_id, "audit_running")
        await orchestrator._set_status(case_file_id, "audit_complete")
        return object()

    tally = await audit_retry_cron.recover_system_errors(time.monotonic() + 120, force=True, rerun=_fixed)
    assert tally["recovered"] == 1 and (await _row(fresh)).status == "audit_complete"


@pytest.mark.asyncio
async def test_old_failures_and_ones_the_healer_holds_are_not_touched(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "audit_wall_clock_budget_seconds", 1)
    old = await _system_error_case(client, failed_ago=timedelta(days=3))
    held = await _system_error_case(client)
    await _park_other_system_errors(old)
    async with AsyncSessionLocal() as s:
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(held)).values(
            reconcile_token=uuid.uuid4(), recovery_retry_after=None))
        await s.commit()
    runs: list[str] = []

    async def _rerun(case_file_id):
        runs.append(case_file_id)

    await audit_retry_cron.recover_system_errors(time.monotonic() + 120, rerun=_rerun)
    assert old not in runs and held not in runs


def test_a_re_run_only_happens_where_it_would_be_the_same_run(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "enable_audit_auto_recovery", False)
    assert audit_retry_cron.recovery_blocker() == "auto_recovery_disabled"
    monkeypatch.setattr(s, "enable_audit_auto_recovery", True)
    monkeypatch.setattr(s, "use_real_claude", False)
    assert audit_retry_cron.recovery_blocker() == "claude_not_configured"
    monkeypatch.setattr(s, "use_real_claude", True)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test-fake")
    monkeypatch.setattr(s, "use_real_ocr", False)
    # the agents re-read the documents: without real OCR they would read the STUB bill
    assert audit_retry_cron.recovery_blocker() == "ocr_not_configured"
    monkeypatch.setattr(s, "use_real_ocr", True)
    monkeypatch.setattr(s, "azure_doc_intelligence_endpoint", "https://di.test")
    monkeypatch.setattr(s, "azure_doc_intelligence_key", "k")
    assert audit_retry_cron.recovery_blocker() is None


# ── the promise renders only where it is true ───────────────────────────────────────────
@pytest.mark.parametrize(
    ("email", "recovery", "key"),
    [(True, True, "system_error"), (True, False, "system_error_no_email"),
     (False, True, "system_error_no_email"), (False, False, "system_error_no_email")],
)
@pytest.mark.asyncio
async def test_the_apology_promises_an_email_only_where_one_can_come(client: AsyncClient, monkeypatch, email, recovery, key):
    from app.agents import thread_bridge
    from app.agents.context_loader import orchestration_step
    from app.db.models.messages import Message

    s = get_settings()
    monkeypatch.setattr(s, "enable_chat_first_audit", True)
    monkeypatch.setattr(s, "enable_audit_ready_email", email)
    monkeypatch.setattr(s, "enable_audit_auto_recovery", recovery)
    up = await client.post("/v1/upload", files=[("files", ("b.pdf", b"%PDF-1.4 x", "application/pdf"))])
    case_id, conv_id = up.json()["case_file_id"], up.json()["conversation_id"]
    async with AsyncSessionLocal() as db:
        await db.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)).values(
            status="audit_incomplete", audit_incomplete_reason="system_error"))
        await db.commit()
    await thread_bridge.bridge_case_state(case_id)
    async with AsyncSessionLocal() as db:
        msgs = list((await db.execute(select(Message).where(Message.conversation_id == uuid.UUID(conv_id)))).scalars())
    apology = next(m for m in msgs if (m.payload or {}).get("marker") == "terminal:system_error")
    assert apology.content == orchestration_step(key)
    assert ("email you" in apology.content) == (key == "system_error")


# ── Admin › System: durable, split, actionable ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_the_system_page_reads_system_errors_from_the_cases(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_audit_auto_recovery", True)
    recovering = await _system_error_case(client)
    stuck = await _system_error_case(client, attempts=audit_retry_cron.RECOVERY_MAX_ATTEMPTS)
    body = (await client.get("/v1/admin/system/health")).json()
    se = body["system_errors"]
    assert se["recovering"] >= 1 and se["needs_a_person"] >= 1 and se["auto_recovery"] is True
    assert stuck in se["needs_a_person_cases"] or len(se["needs_a_person_cases"]) == 5
    kinds = {a["kind"]: a for a in body["alerts"]}
    assert "system_error" in kinds and "gave up" in kinds["system_error"]["detail"]
    assert "audit_retry_force" in kinds["system_error"]["action"]
    assert "system_error_recovering" in kinds and kinds["system_error_recovering"]["severity"] == "medium"
    del recovering

    # auto-recovery OFF: every open failure is a person's
    monkeypatch.setattr(get_settings(), "enable_audit_auto_recovery", False)
    body = (await client.get("/v1/admin/system/health")).json()
    assert body["system_errors"]["recovering"] == 0
    assert "automatic recovery is OFF" in {a["kind"]: a for a in body["alerts"]}["system_error"]["detail"]


# ── the alert path reaches a person ─────────────────────────────────────────────────────
def test_an_alert_rule_mails_a_person_on_the_lines_the_code_really_logs():
    tf = (REPO / "infra/envs/dev/monitoring.tf").read_text()
    rule = re.search(r'resource "azurerm_monitor_scheduled_query_rules_alert_v2" "audit_system_error" \{(.*?)\n\}', tf, re.S)
    assert rule, "the alert rule is gone"
    lines = re.findall(r'contains "([a-z_.]+)"', rule.group(1))
    assert set(lines) == {"audit.system_error", "orchestrator.finalize.failed", "audit_retry.recovery_exhausted"}
    source = "\n".join(p.read_text() for p in (REPO / "runtime/app").rglob("*.py"))
    for line in lines:  # a rename breaks HERE, not silently in the alert
        assert f'"{line}"' in source, line
    assert re.search(r'resource "azurerm_monitor_action_group" "needs_a_person" \{\s*count\s*=\s*var\.alert_email != "" \? 1 : 0', tf)
    variables = (REPO / "infra/envs/dev/variables.tf").read_text()
    assert 'variable "alert_email"' in variables and 'variable "enable_audit_auto_recovery"' in variables
    checklist = (REPO / "docs/build-kit/GO_LIVE_CHECKLIST.md").read_text()
    assert "audit-system-error" in checklist and "alert_email" in checklist


def test_the_recovery_job_reads_documents_the_way_the_runtime_does():
    tf = (REPO / "infra/envs/dev/crons.tf").read_text()
    for name in ("USE_REAL_OCR", "AZURE_DOC_INTELLIGENCE_ENDPOINT", "AZURE_DOC_INTELLIGENCE_KEY"):
        assert re.search(rf'for_each = contains\(local\.claude_crons, each\.key\) \? \[1\] : \[\]\s*content \{{\s*name\s*= "{name}"', tf), name
    assert 'name  = "ENABLE_AUDIT_AUTO_RECOVERY"' in tf  # every cron: the bridge reads it
