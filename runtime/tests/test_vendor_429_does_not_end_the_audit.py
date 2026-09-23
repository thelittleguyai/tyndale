"""A vendor 429 must not end an audit that has findings (e2e re-test 2026-09-23, item 1).

The specimen (f6e5c56d) persisted three findings and the three numbers, then ONE Foundry
``RateLimitError`` on the Lead Planner's summary call ended it ``system_error``. Now: every
audit-path Claude call backs off (2 → 16 s, Retry-After honoured, the audit budget respected);
a summary the provider still refuses ships the reveal as ``audit_complete`` with the summary
OWED; the audit_retry cron writes it later with a summary-only tool list; and no knowledge tool
ever raises out of the tool.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

import anthropic
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, update

from app.agents import claude_retry, lead_planner, llm_health, orchestrator, runner
from app.agents.audit_budget import AuditBudget, reset_audit_budget, set_audit_budget
from app.agents.context_loader import orchestration_step
from app.agents.llm_health import ProviderUnavailableError
from app.agents.runner import RunResult
from app.config import get_settings
from app.crons import audit_retry_cron
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding

_REQ = httpx.Request("POST", "https://foundry.test/anthropic/v1/messages")


def _rate_limit(headers: dict | None = None) -> anthropic.RateLimitError:
    return anthropic.RateLimitError("429", response=httpx.Response(429, headers=headers or {}, request=_REQ), body=None)


def _overloaded() -> anthropic.InternalServerError:
    return anthropic.InternalServerError("529", response=httpx.Response(529, request=_REQ), body=None)


def _bad_request() -> anthropic.BadRequestError:
    return anthropic.BadRequestError("400", response=httpx.Response(400, request=_REQ), body=None)


class _Script:
    """messages.create that plays a script: an exception is raised, anything else returned."""

    def __init__(self, *steps):
        self.steps, self.calls = list(steps), 0
        self.messages = self

    async def create(self, **_kw):
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


async def _call(client, sleeps):
    async def _sleep(s):
        sleeps.append(s)

    return await claude_retry.create_message(client, actor="lead_planner", case_file_id="c", sleep=_sleep, model="m")


# ── the backoff policy ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_a_429_is_retried_with_exponential_waits_then_succeeds():
    sleeps: list[float] = []
    before = llm_health.rate_limit_snapshot()["count"]
    client = _Script(_rate_limit(), _rate_limit(), "ok")
    assert await _call(client, sleeps) == "ok"
    assert client.calls == 3 and sleeps == [2.0, 4.0]
    assert llm_health.rate_limit_snapshot()["count"] == before + 2  # the System page sees them


@pytest.mark.asyncio
async def test_the_providers_retry_after_is_honoured_when_it_asks_for_longer():
    sleeps: list[float] = []
    await _call(_Script(_rate_limit({"retry-after": "7"}), _rate_limit({"retry-after-ms": "12500"}), "ok"), sleeps)
    assert sleeps == [7.0, 12.5]
    sleeps.clear()
    await _call(_Script(_rate_limit({"retry-after": "1"}), "ok"), sleeps)
    assert sleeps == [2.0]  # a SHORTER hint never undercuts the backoff


@pytest.mark.asyncio
async def test_four_attempts_then_the_error_is_raised():
    sleeps: list[float] = []
    client = _Script(*[_rate_limit() for _ in range(6)])
    with pytest.raises(anthropic.RateLimitError):
        await _call(client, sleeps)
    assert client.calls == claude_retry.MAX_ATTEMPTS == 4 and sleeps == [2.0, 4.0, 8.0]
    assert claude_retry.backoff_delay(5, None) == claude_retry.MAX_DELAY_S == 16.0  # the cap


@pytest.mark.asyncio
async def test_overload_and_connection_errors_are_retried_a_client_error_is_not():
    sleeps: list[float] = []
    assert await _call(_Script(_overloaded(), anthropic.APIConnectionError(request=_REQ), "ok"), sleeps) == "ok"
    sleeps.clear()
    client = _Script(_bad_request(), "never")
    with pytest.raises(anthropic.BadRequestError):
        await _call(client, sleeps)
    assert client.calls == 1 and sleeps == []


@pytest.mark.asyncio
async def test_a_wait_the_audit_budget_cannot_afford_is_not_taken():
    token = set_audit_budget(AuditBudget(deadline=time.monotonic() + 8, regen_remaining=0))
    try:
        sleeps: list[float] = []
        client = _Script(_rate_limit({"retry-after": "10"}), "ok")
        with pytest.raises(anthropic.RateLimitError):
            await _call(client, sleeps)
        assert client.calls == 1 and sleeps == []
    finally:
        reset_audit_budget(token)


@pytest.mark.asyncio
async def test_a_provider_asking_for_more_than_a_minute_is_not_waited_on_inside_an_audit():
    sleeps: list[float] = []
    client = _Script(_rate_limit({"retry-after": "120"}), "ok")
    with pytest.raises(anthropic.RateLimitError):
        await _call(client, sleeps)
    assert sleeps == []


@pytest.mark.asyncio
async def test_the_sdks_own_retries_are_off_so_the_policy_is_bounded():
    seen = {}

    class _WithOptions(_Script):
        def with_options(self, **kw):
            seen.update(kw)
            return self

    await _call(_WithOptions("ok"), [])
    assert seen == {"max_retries": 0}


@pytest.mark.asyncio
async def test_the_fault_seam_throttles_without_reaching_the_provider():
    sleeps: list[float] = []
    client = _Script()  # would IndexError if ever called
    token = claude_retry.FAULT.set("rate_limit")
    try:
        with pytest.raises(anthropic.RateLimitError):
            await _call(client, sleeps)
    finally:
        claude_retry.FAULT.reset(token)
    assert client.calls == 0 and sleeps == [2.0, 4.0, 8.0]


# ── the run: a refused summary ships the reveal with the summary OWED ────────────────────
class _Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Usage:
    input_tokens = output_tokens = 5


class _Resp:
    def __init__(self, text):
        self.content, self.stop_reason, self.usage = [_Blk(type="text", text=text)], "end_turn", _Usage()


class _AgentsButTheSummaryIsThrottled:
    """Bill Detective and Math Person answer; every Lead Planner compose attempt is a 429."""

    def __init__(self):
        self.messages = self
        self.summary_attempts = 0

    async def create(self, **kw):
        first = str(kw["messages"][0]["content"])
        if "Lead Planner. Compose the final" in first:
            self.summary_attempts += 1
            raise _rate_limit()
        return _Resp("Reviewed the bill and the EOB.")


async def _complete_case_with_numbers(client: AsyncClient) -> str:
    up = await client.post("/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))])
    case_id = up.json()["case_file_id"]
    cid = uuid.UUID(case_id)
    async with AsyncSessionLocal() as s:
        s.add(Finding(
            case_file_id=cid, finding_type="payer_side", category="deductible_misapplied",
            subagent_source="math_person", voice_tier="A",
            facts={"provider_billed": 7600.0, "eob_member_responsibility": 538.0, "tyndale_computed": 412.0},
        ))
        await s.commit()
    return case_id


@pytest.mark.asyncio
async def test_a_summary_the_provider_refuses_ships_the_reveal_with_the_summary_owed(client: AsyncClient, monkeypatch):
    case_id = await _complete_case_with_numbers(client)
    s = get_settings()
    monkeypatch.setattr(s, "use_real_claude", True)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test-fake")
    monkeypatch.setattr(s, "litellm_proxy_url", None)
    monkeypatch.setattr(claude_retry, "BASE_DELAY_S", 0.0)  # no real waiting in the suite
    fake = _AgentsButTheSummaryIsThrottled()
    monkeypatch.setattr(runner, "_client", lambda: fake)
    alerts_before = llm_health.system_alerts()["count"]
    try:
        result = await orchestrator.finalize_audit(case_id)

        # the specimen's shape: this was system_error. Now it is a complete audit, summary owed.
        assert fake.summary_attempts == claude_retry.MAX_ATTEMPTS  # the backoff really ran
        assert result.status == "complete" and result.audit is not None and result.findings
        assert result.incomplete_reason is None
        assert result.summary == "" and result.summary_pending is True
        assert result.summary_pending_notice == orchestration_step("summary.pending_notice")
        assert llm_health.system_alerts()["count"] == alerts_before  # nothing to apologise for
        async with AsyncSessionLocal() as db:
            cf = (await db.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))).scalar_one()
        assert cf.status == "audit_complete" and cf.audit_incomplete_reason is None
        assert cf.summary_pending is True and cf.summary_retry_attempts == 0
        assert cf.summary_inputs == {"bill_detective": "Reviewed the bill and the EOB.", "math_person": "Reviewed the bill and the EOB."}
        due = cf.summary_retry_after - datetime.now(timezone.utc)
        assert timedelta(minutes=4) < due <= timedelta(minutes=5)

        # every later read says the same thing (the user's re-fetch, the results page)
        got = (await client.get(f"/v1/audit/{case_id}")).json()
        assert got["summary_pending"] is True and got["summary_pending_notice"] and got["summary"] == ""
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Finding).where(Finding.case_file_id == uuid.UUID(case_id)))
            await db.commit()


def _agents_fakes(monkeypatch, lp):
    async def _bd(case_file_id, *, mode, confirmations, session=None):
        return RunResult(final_text="bd-findings", tool_calls=[], usage={})

    async def _mp(case_file_id, *, accumulator=None, session=None):
        return RunResult(final_text="mp-numbers", tool_calls=[], usage={})

    from app.agents import bill_detective, math_person

    monkeypatch.setattr(bill_detective, "run", _bd)
    monkeypatch.setattr(math_person, "run", _mp)
    monkeypatch.setattr(orchestrator.lead_planner, "compose_final", lp)


@pytest.mark.asyncio
async def test_a_refusal_on_the_grounding_regeneration_defers_the_summary_too(monkeypatch):
    async def _lp(*_a, **_k):
        return RunResult(final_text="composed", tool_calls=[], usage={})

    async def _regen_refused(*_a, **_k):
        raise ProviderUnavailableError()

    _agents_fakes(monkeypatch, _lp)
    monkeypatch.setattr(orchestrator, "_ground_prose", _regen_refused)
    run = await orchestrator._run_real_agents(str(uuid.uuid4()), None, [], AuditBudget(deadline=time.monotonic() + 600, regen_remaining=1))
    assert run.composed == "" and run.summary_pending is True
    assert run.summary_inputs == {"bill_detective": "bd-findings", "math_person": "mp-numbers"}


@pytest.mark.asyncio
async def test_a_budget_spent_before_the_summary_defers_it_instead_of_dropping_it(monkeypatch):
    async def _lp(*_a, **_k):
        raise AssertionError("the Lead Planner must not start once the budget is spent")

    _agents_fakes(monkeypatch, _lp)
    run = await orchestrator._run_real_agents(str(uuid.uuid4()), None, [], AuditBudget(deadline=time.monotonic() - 1, regen_remaining=0))
    assert run.summary_pending is True and run.budget_stopped is True


@pytest.mark.asyncio
async def test_a_summary_is_only_ever_owed_on_a_complete_audit(client: AsyncClient):
    """An incomplete audit is re-run whole, never patched with a late summary."""
    up = await client.post("/v1/upload", files=[("files", ("n.pdf", b"%PDF-1.4 x", "application/pdf"))])
    case_id = up.json()["case_file_id"]
    budget = AuditBudget(deadline=time.monotonic() + 600, regen_remaining=0)
    result = await orchestrator._finalize_result(
        case_id, "", budget, False, time.monotonic(), {}, "stub", manage_status=True,
        summary_pending=True, summary_inputs={"bill_detective": "x", "math_person": "y"},
    )
    assert result.status == "audit_incomplete" and not result.summary_pending
    async with AsyncSessionLocal() as db:
        cf = (await db.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))).scalar_one()
    assert cf.summary_pending is False and cf.summary_inputs is None


# ── the retry ───────────────────────────────────────────────────────────────────────────
async def _owed(client: AsyncClient, *, due_in=timedelta(minutes=-1), attempts=0) -> str:
    case_id = await _complete_case_with_numbers(client)
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)).values(
                status="audit_complete", audit_summary="", summary_pending=True,
                summary_inputs={"bill_detective": "bd text", "math_person": "mp text"},
                summary_retry_attempts=attempts,
                summary_retry_after=datetime.now(timezone.utc) + due_in,
            )
        )
        await s.commit()
    return case_id


async def _row(case_id: str) -> CaseFile:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))).scalar_one()


async def _park_other_owed_summaries(keep: str) -> None:
    """The shared local DB may hold owed summaries from earlier runs — the sweep claims the
    OLDEST due row, so keep them out of this test's way."""
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(CaseFile)
            .where(CaseFile.summary_pending.is_(True), CaseFile.case_file_id != uuid.UUID(keep))
            .values(summary_retry_after=datetime.now(timezone.utc) + timedelta(days=1))
        )
        await s.commit()


@pytest.mark.asyncio
async def test_the_retry_writes_the_owed_summary_with_the_summary_only_tools(client: AsyncClient, monkeypatch):
    case_id = await _owed(client)
    await _park_other_owed_summaries(case_id)
    seen: dict = {}

    async def _lp(case_file_id, bd, mp, *, session=None, extra_instruction=None, tool_names=None):
        seen.update(case=case_file_id, bd=bd, mp=mp, tools=list(tool_names or []))
        return RunResult(final_text="Your audit, in plain words.", tool_calls=[], usage={})

    monkeypatch.setattr(lead_planner, "compose_final", _lp)
    tally = await audit_retry_cron.retry_pending_summaries(time.monotonic() + 30)
    assert tally["written"] == 1
    row = await _row(case_id)
    assert row.summary_pending is False and row.summary_inputs is None
    assert row.audit_summary == "Your audit, in plain words."
    assert seen["bd"] == "bd text" and seen["mp"] == "mp text"
    # summary only: no finding writes, no notify, and NO document OCR (a cron without real OCR
    # would answer with the stub bill) — deadlines only because this run never wrote one
    for banned in ("pg_upsert_finding", "notify_user", "bill_ocr_extract", "upload_extract_eob", "upload_extract_coverage"):
        assert banned not in seen["tools"]
    assert "pg_deadline_upsert" in seen["tools"] and "pg_case_file_get" in seen["tools"]
    # the result page now carries it, and the notice is gone
    got = (await client.get(f"/v1/audit/{case_id}")).json()
    assert got["summary"] == "Your audit, in plain words." and not got["summary_pending"]


@pytest.mark.asyncio
async def test_a_retry_the_provider_still_refuses_backs_off_then_stops_promising(client: AsyncClient):
    case_id = await _owed(client)
    await _park_other_owed_summaries(case_id)

    async def _refused(_case_id):
        return None

    tally = await audit_retry_cron.retry_pending_summaries(time.monotonic() + 30, compose=_refused)
    assert tally == {"written": 0, "backoff": 1, "exhausted": 0, "superseded": 0}
    row = await _row(case_id)
    assert row.summary_pending and row.summary_retry_attempts == 1
    assert timedelta(minutes=14) < row.summary_retry_after - datetime.now(timezone.utc) <= timedelta(minutes=15)

    # the last allowed attempt: spent → the page stops promising a summary that is not coming
    async with AsyncSessionLocal() as s:
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)).values(
            summary_retry_attempts=audit_retry_cron.SUMMARY_MAX_ATTEMPTS - 1,
            summary_retry_after=datetime.now(timezone.utc) - timedelta(minutes=1),
        ))
        await s.commit()
    tally = await audit_retry_cron.retry_pending_summaries(time.monotonic() + 30, compose=_refused)
    assert tally["exhausted"] == 1
    row = await _row(case_id)
    assert row.summary_pending is False and row.summary_inputs is None
    assert not (await client.get(f"/v1/audit/{case_id}")).json()["summary_pending"]


@pytest.mark.asyncio
async def test_overlapping_sweeps_never_claim_the_same_row_and_a_rerun_wins(client: AsyncClient):
    case_id = await _owed(client)
    await _park_other_owed_summaries(case_id)
    now = datetime.now(timezone.utc)
    first = await audit_retry_cron._claim_summary(now)
    assert first == (case_id, 1)
    assert await audit_retry_cron._claim_summary(now) is None  # leased

    # a fresh run in between: the owed summary is void (that run writes its own)
    await orchestrator._set_status(case_id, "audit_running")
    row = await _row(case_id)
    assert row.summary_pending is False and row.summary_inputs is None
    assert await orchestrator.compose_pending_summary(case_id) is None


@pytest.mark.asyncio
async def test_the_cron_does_nothing_where_claude_is_not_configured(monkeypatch):
    monkeypatch.setattr(get_settings(), "use_real_claude", False)
    assert await audit_retry_cron.run_audit_retry_cron() == {"skipped": "claude_not_configured"}


def test_the_cron_is_registered_and_scheduled_with_claude_and_only_it_is():
    import pathlib
    import re

    from app.crons.registry import CRON_REGISTRY

    assert "audit_retry" in CRON_REGISTRY
    tf = (pathlib.Path(__file__).resolve().parents[2] / "infra/envs/dev/crons.tf").read_text()
    assert re.search(r'audit_retry\s*=\s*\{ cron = "\*/15 \* \* \* \*", timeout = 900 \}', tf)
    assert 'claude_crons = toset(["audit_retry"])' in tf
    # every Claude env block is conditional on that set — the ingestion crons stay stubbed
    for name in ("USE_REAL_CLAUDE", "USE_FOUNDRY", "FOUNDRY_ENDPOINT", "AZURE_CLIENT_ID"):
        block = re.search(rf'dynamic "env" \{{\s*for_each = contains\(local\.claude_crons, each\.key\) \? \[1\] : \[\]\s*content \{{\s*name\s*= "{name}"', tf)
        assert block, name


# ── the dev-only fault seam ─────────────────────────────────────────────────────────────
def test_the_fault_is_honoured_only_for_a_synthetic_user_outside_production(monkeypatch):
    from app import faults

    ok = "claude_429:lead_planner"
    assert faults.accepted_fault(ok, user_email="e2e+x@e2e.tyndale.test") == ok
    assert faults.accepted_fault(ok, user_email="person@example.com") is None
    assert faults.accepted_fault("claude_429:everything", user_email="e2e+x@e2e.tyndale.test") is None
    assert faults.accepted_fault(None, user_email="e2e+x@e2e.tyndale.test") is None
    monkeypatch.setattr(get_settings(), "node_env", "staging")
    assert faults.accepted_fault(ok, user_email="e2e+x@e2e.tyndale.test") is None

    with faults.injected({ok}, "bill_detective") as hit:
        assert not hit and claude_retry.FAULT.get() is None
    with faults.injected({ok}, "lead_planner") as hit:
        assert hit and claude_retry.FAULT.get() == "rate_limit"
    assert claude_retry.FAULT.get() is None


@pytest.mark.asyncio
async def test_the_upload_records_an_accepted_fault_on_the_case(client: AsyncClient, monkeypatch):
    import app.notify.email as email_mod

    headers = {"X-Tyndale-Fault": "claude_429:lead_planner"}
    up = await client.post("/v1/upload", files=[("files", ("b.pdf", b"%PDF-1.4 x", "application/pdf"))], headers=headers)
    plain = await _row(up.json()["case_file_id"])
    assert not [e for e in (plain.research_log or []) if e.get("kind") == "fault_injection"]  # the dev user is real

    monkeypatch.setattr(email_mod, "is_synthetic_email", lambda _e: True)
    up = await client.post("/v1/upload", files=[("files", ("b.pdf", b"%PDF-1.4 x", "application/pdf"))], headers=headers)
    row = await _row(up.json()["case_file_id"])
    from app.faults import case_faults

    assert case_faults(row) == {"claude_429:lead_planner"}


# ── Voyage / Qdrant: a knowledge tool never raises ───────────────────────────────────────
@pytest.mark.asyncio
async def test_a_knowledge_tool_never_raises_out_of_the_tool(monkeypatch):
    from app.tools import call_tool, knowledge_tools

    async def _down(**_kw):
        raise httpx.ReadTimeout("qdrant timed out")

    monkeypatch.setattr(knowledge_tools, "search_and_rerank", _down)
    direct = await knowledge_tools._qdrant_search_billing_codes({"query": "01402 anesthesia"})
    assert direct["error"] == knowledge_tools.RETRIEVAL_UNAVAILABLE and direct["hits"] == []
    assert "ReadTimeout" in direct["reason"]
    via = await call_tool("qdrant_search_billing_codes", {"query": "01402 anesthesia"})
    assert via["error"] == knowledge_tools.RETRIEVAL_UNAVAILABLE


# ── the harness asserts it on dev ───────────────────────────────────────────────────────
def test_the_harness_sends_the_fault_and_asserts_the_owed_summary():
    import importlib.util
    import json
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve().parents[1] / "scripts/e2e_scenarios"
    sys.path.insert(0, str(here))
    spec = importlib.util.spec_from_file_location("run_scenarios", here / "run_scenarios.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    scenario = json.loads((here / "scenarios/s07_knee_arthroscopy_summary_429.json").read_text())
    assert scenario["fault"] == "claude_429:lead_planner" and scenario["expect"]["summary_pending"] is True
    assert scenario["expect"]["terminal"] == "audit_complete"

    seen = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["fault"] = request.headers.get("X-Tyndale-Fault")
        return httpx.Response(200, json={"case_file_id": "c1"})

    with httpx.Client(transport=httpx.MockTransport(_handler)) as c:
        assert mod._upload(c, "http://t", [], fault="claude_429:lead_planner") == (200, "c1")
    assert seen["fault"] == "claude_429:lead_planner"

    owed = {"audit": {"tyndale_computed": 1}, "summary": "", "summary_pending": True, "summary_pending_notice": "still writing"}
    assert mod._summary_pending_checks(owed, True) == []
    assert mod._summary_pending_checks({**owed, "summary_pending": False}, True) == ["summary_pending=False expected True"]
    assert any("fault did not bite" in f for f in mod._summary_pending_checks({**owed, "summary": "text"}, True))
    assert any("no notice" in f for f in mod._summary_pending_checks({**owed, "summary_pending_notice": None}, True))
