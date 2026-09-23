"""Retrieval is a dependency, not a decoration (e2e 2026-09-23 B1).

Dev ran for days with every knowledge tool erroring — Voyage 429 on embeddings and a
deterministic 400 on rerank — while Qdrant reported healthy, the audit shipped a [B] legal
claim on zero retrieved chunks, and the sweep stayed green. These pin:

  * the rerank request is Voyage's documented body and nothing else (the 400 was our own
    ``instruction`` field — recorded contract from the probe on 2026-09-23);
  * a failed rerank degrades to the vector order, never to a failed search;
  * embeddings are rate-limited, cached per query, batched, and fail as ONE typed reason;
  * the audit records what it retrieved, downgrades an unsourced legal claim, and says so;
  * the System page carries ``retrieval_degraded`` + failed crons on one alert list;
  * the harness fails a scenario that expects retrieval when any knowledge call errored.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.knowledge import embeddings, health
from app.knowledge import rerank as rerank_mod
from app.knowledge import search as search_mod

# ── the recorded contract: what Voyage's rerank endpoint accepts (probe, 2026-09-23) ─────
VOYAGE_UNKNOWN_ARG_400 = (
    "The request body is not valid JSON, or some arguments were not specified properly. "
    "In particular, Argument '{arg}' is not supported by our API"
)


def _voyage_rerank_handler(request: httpx.Request) -> httpx.Response:
    """Behaves as the live endpoint did on 2026-09-23: validates the body BEFORE auth —
    an unknown argument is a 400 with the exact detail above — then scores documents by
    length (deterministic) and honours top_k."""
    body = json.loads(request.content)
    extra = sorted(set(body) - set(rerank_mod.RERANK_REQUEST_FIELDS))
    if extra:
        return httpx.Response(400, json={"detail": VOYAGE_UNKNOWN_ARG_400.format(arg=extra[0])})
    if not isinstance(body.get("documents"), list) or not body["documents"]:
        return httpx.Response(400, json={"detail": "documents must be a non-empty list"})
    if len(body["documents"]) > rerank_mod.MAX_RERANK_DOCUMENTS:
        return httpx.Response(400, json={"detail": "too many documents"})
    ranked = sorted(range(len(body["documents"])), key=lambda i: -len(body["documents"][i]))
    top_k = body.get("top_k") or len(ranked)
    data = [{"index": i, "relevance_score": round(1.0 - n * 0.1, 3)} for n, i in enumerate(ranked[:top_k])]
    return httpx.Response(200, json={"object": "list", "data": data, "model": body["model"], "usage": {"total_tokens": 10}})


def _mock_rerank_client(monkeypatch, handler=_voyage_rerank_handler):
    monkeypatch.setattr(rerank_mod, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.fixture(autouse=True)
def _clean_ledgers():
    health.reset()
    embeddings.cache_clear()
    yield
    health.reset()
    embeddings.cache_clear()


# ── rerank ───────────────────────────────────────────────────────────────────────────────
def test_rerank_body_is_the_documented_contract_and_the_instruction_rides_in_the_query():
    body, index_map = rerank_mod.build_rerank_payload(
        "which code is correct", ["doc a", "", "   ", "a longer document c"], top_n=8,
        instruction="Prefer the controlling statute.",
    )
    assert set(body) <= rerank_mod.RERANK_REQUEST_FIELDS and "instruction" not in body
    assert body["query"].startswith("Prefer the controlling statute.") and body["query"].endswith("which code is correct")
    assert body["documents"] == ["doc a", "a longer document c"] and index_map == [0, 3]  # empties dropped, positions kept
    assert body["top_k"] == 2  # never more than the documents sent
    assert body["model"] == rerank_mod.RERANK_MODEL


@pytest.mark.asyncio
async def test_rerank_against_the_recorded_endpoint_maps_indexes_back(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")
    _mock_rerank_client(monkeypatch)
    docs = ["short", "", "the longest document of them all", "medium one"]
    out = await rerank_mod.rerank("q", docs, top_n=2, instruction="Rank by specificity.")
    assert [r.index for r in out] == [2, 3]  # original positions, the empty one never sent
    assert out[0].document == docs[2] and out[0].score > out[1].score
    assert health.snapshot()["voyage"]["rerank"]["last_status"] == 200


@pytest.mark.asyncio
async def test_the_old_payload_shape_is_exactly_what_the_endpoint_rejects(monkeypatch):
    """The bug, recorded: send `instruction` as a body field and the endpoint answers 400
    naming it. Our builder no longer produces that shape (asserted above)."""
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")
    async with httpx.AsyncClient(transport=httpx.MockTransport(_voyage_rerank_handler)) as client:
        r = await client.post(rerank_mod.VOYAGE_RERANK_URL, json={"query": "q", "documents": ["a"], "model": "rerank-2.5", "top_k": 1, "instruction": "x"})
    assert r.status_code == 400 and "Argument 'instruction' is not supported" in r.json()["detail"]


@pytest.mark.asyncio
async def test_a_failed_rerank_degrades_to_vector_order_never_a_failed_search(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")
    _mock_rerank_client(monkeypatch, lambda req: httpx.Response(400, json={"detail": "nope"}))
    hits = [search_mod.Hit(id=i, score=1.0 - i * 0.1, payload={"chunk_text": f"t{i}"}) for i in range(5)]
    out = await search_mod._rerank_or_degrade("laws_regulations", "q", hits, top_n=3)
    assert [h.id for h in out] == [0, 1, 2]  # the vector order, truncated — not an exception
    assert health.snapshot()["voyage"]["rerank"]["last_status"] == 400
    with pytest.raises(rerank_mod.RerankUnavailable):
        await rerank_mod.rerank("q", ["a"], top_n=1)


# ── embeddings: limiter, cache, batching, typed failure ──────────────────────────────────
class _Resp:
    def __init__(self, status: int, data: dict | None = None, headers: dict | None = None, text: str = ""):
        self.status_code, self._data, self.headers, self.text = status, data or {}, headers or {}, text

    def json(self):
        return self._data


def _client_with(seq: list[_Resp], calls: list[dict]):
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def post(self, _url, json=None, headers=None):
            calls.append(json)
            return seq[min(len(calls) - 1, len(seq) - 1)]

    return _Client


def _flat_ok(payload: dict) -> _Resp:
    return _Resp(200, {"data": [{"embedding": [float(len(t))] + [0.0] * 1023} for t in payload["input"]]})


@pytest.mark.asyncio
async def test_query_cache_and_batching_share_one_call(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")
    calls: list[dict] = []

    async def fake_post(url, payload):
        calls.append(payload)
        return _flat_ok(payload).json()

    monkeypatch.setattr(embeddings, "_post_voyage", fake_post)
    vecs = await embeddings.embed_queries(["cpt 29881", "cpt 01402", "cpt 29881"], "voyage-3-large")
    assert len(calls) == 1 and calls[0]["input"] == ["cpt 29881", "cpt 01402"]  # de-duplicated, ONE call
    assert vecs[0] == vecs[2]
    again = await embeddings.embed("cpt 01402", "voyage-3-large")
    assert len(calls) == 1 and again == vecs[1]  # answered from the cache — no second call
    embeddings.cache_clear()
    await embeddings.embed("cpt 01402", "voyage-3-large")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_429_is_retried_with_backoff_then_fails_as_one_typed_reason(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")
    slept: list[float] = []

    async def _sleep(s):
        slept.append(s)

    monkeypatch.setattr(embeddings.asyncio, "sleep", _sleep)
    calls: list[dict] = []
    seq = [_Resp(429, headers={"retry-after": "0"}, text="rate"), _Resp(429, headers={"retry-after": "2"}, text="rate"), _flat_ok({"input": ["q"]})]
    monkeypatch.setattr(embeddings.httpx, "AsyncClient", lambda *a, **k: _client_with(seq, calls)())
    out = await embeddings.embed_batch(["q"], "voyage-3-large")
    assert len(calls) == 3 and slept == [0.0, 2.0] and len(out[0]) == 1024
    assert health.snapshot()["voyage"]["embeddings"]["errors"] == 2

    calls.clear()
    monkeypatch.setattr(embeddings.httpx, "AsyncClient", lambda *a, **k: _client_with([_Resp(429, text="quota")], calls)())
    with pytest.raises(embeddings.EmbeddingUnavailable):
        await embeddings.embed_batch(["q2"], "voyage-3-large")
    assert len(calls) == embeddings._MAX_EMBED_RETRIES  # every retry spent, then ONE typed failure


@pytest.mark.asyncio
async def test_the_token_bucket_paces_a_burst():
    bucket = embeddings._TokenBucket(rpm=6000)  # 100/s, burst 600
    bucket.tokens, bucket.capacity = 1.0, 1.0
    assert await bucket.acquire() == 0.0
    waited = await bucket.acquire()  # the second one must wait for a refill
    assert 0.0 < waited <= 0.02


@pytest.mark.asyncio
async def test_a_knowledge_tool_reports_retrieval_unavailable_and_records_health(monkeypatch):
    from app.tools import call_tool

    async def boom(*a, **k):
        raise embeddings.EmbeddingUnavailable("voyage embeddings 429: quota")

    monkeypatch.setattr("app.tools.knowledge_tools.search_and_rerank", boom)
    out = await call_tool("qdrant_search_billing_codes", {"query": "cpt 29881"})
    assert out["error"] == "retrieval_unavailable" and out["hits"] == [] and "429" in out["reason"]
    snap = health.snapshot()
    assert snap["window_errors"] == 1 and snap["status"] == "degraded"


# ── the audit: record → downgrade → say so ─────────────────────────────────────────────
def _tc(name: str, result: dict) -> dict:
    return {"name": name, "input": {"query": "q"}, "result": result}


def test_retrieval_record_states_from_the_runs_tool_calls():
    from app.agents.retrieval_grounding import retrieval_record

    hit = {"hits": [{"id": "src_a1", "score": 0.9, "payload": {"authority": "ACA §2707", "src_id": "src_a1"}}], "count": 1}
    err = {"error": "retrieval_unavailable", "reason": "voyage 429", "hits": [], "count": 0}
    assert retrieval_record([_tc("qdrant_search_laws_regulations", hit), _tc("pg_case_file_get", {"x": 1})])["status"] == "ok"
    rec = retrieval_record([_tc("qdrant_search_laws_regulations", err), _tc("qdrant_search_billing_codes", err)])
    assert rec["status"] == "unavailable" and rec["calls"] == 2 and rec["errors"] == 2 and rec["chunks"] == 0
    rec = retrieval_record([_tc("qdrant_search_laws_regulations", hit), _tc("qdrant_search_billing_codes", err)])
    assert rec["status"] == "degraded" and rec["chunks"] == 1 and rec["chunk_ids"] == ["src_a1"]
    assert retrieval_record([])["status"] == "ok" and retrieval_record([])["calls"] == 0


@pytest.mark.asyncio
async def test_an_unsourced_legal_claim_is_downgraded_and_a_sourced_one_stands(client: AsyncClient):
    from sqlalchemy import select

    from app.agents import retrieval_grounding as rg
    from app.agents.grounding import finding_tier, resolve_source
    from app.db.base import AsyncSessionLocal
    from app.db.models.case_files import CaseFile
    from app.db.models.findings import Finding

    up = await client.post("/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 x", "application/pdf")})
    case_id = up.json()["case_file_id"]
    chunks = [{"id": "src_ok", "src_id": "src_ok", "authority": "ERISA §503", "chunk_text": "…"}]

    def finding(category, legal_claim):
        return Finding(case_file_id=uuid.UUID(case_id), finding_type="payer_side", category=category,
                       subagent_source="lead_planner", voice_tier="B", facts={"x": 1}, legal_claim=legal_claim,
                       recommendation={"action": "call the insurer"})

    async with AsyncSessionLocal() as s:
        s.add(finding("unsourced", {"claim": "required under ACA §2707 and PHSA §2707", "citations": [{"authority": "ACA §2707", "src_id": "src_zz"}]}))
        s.add(finding("by_id", {"claim": "180 days to appeal", "citations": [{"authority": "ERISA", "src_id": "src_ok"}]}))
        s.add(finding("by_authority", {"claim": "180 days to appeal", "citations": [{"authority": "ERISA §503"}]}))
        s.add(finding("no_claim", None))
        await s.commit()
    try:
        downgraded = await rg.ground_legal_claims(case_id, chunks)
        assert downgraded == ["unsourced"]
        async with AsyncSessionLocal() as s:
            rows = {f.category: f for f in (await s.execute(select(Finding).where(Finding.case_file_id == uuid.UUID(case_id)))).scalars()}
        f = rows["unsourced"]
        assert f.voice_tier == "C" and f.legal_claim["downgraded"] == "no_retrieved_source"
        assert "claim" not in f.legal_claim and f.legal_claim["unsourced"]["claim"].startswith("required under")
        assert f.recommendation["worth_checking"].startswith("Worth checking:")
        assert finding_tier(SimpleNamespace(citations=[], legal_claim=f.legal_claim)) == "fact"
        assert resolve_source(SimpleNamespace(citations=[], legal_claim=f.legal_claim, facts={})) is None
        assert rows["by_id"].voice_tier == "B" and "claim" in rows["by_id"].legal_claim
        assert rows["by_authority"].voice_tier == "B"
        # second pass: idempotent — a downgraded claim is not a claim, nothing changes
        assert await rg.ground_legal_claims(case_id, chunks) == []

        # the first-class flag + provenance: recorded on the case, read by the audit payload
        await rg.record_retrieval_on_case(case_id, rg.retrieval_record([_tc("qdrant_search_laws_regulations", {"error": "retrieval_unavailable", "hits": []})]))
        async with AsyncSessionLocal() as s:
            cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))).scalar_one()
        assert rg.retrieval_unavailable(cf) and rg.retrieval_entry(cf)["errors"] == 1
        r = await client.get(f"/v1/audit/{case_id}")
        assert r.status_code == 200, r.text
        prov = r.json()["audit_provenance"]
        assert prov["retrieval_unavailable"] is True and prov["retrieval"]["status"] == "unavailable"
        assert any("rules corpus could not be reached" in a for a in prov["assumptions"])
        # the downgraded finding reaches the client as a fact-tier observation, no bare claim
        out = {f["category"]: f for f in r.json()["findings"]}
        assert out["unsourced"]["tier"] == "fact" and out["unsourced"]["voice_tier"] == "C" and out["unsourced"]["citations"] == []
    finally:
        from sqlalchemy import delete

        async with AsyncSessionLocal() as s:
            await s.execute(delete(Finding).where(Finding.case_file_id == uuid.UUID(case_id)))
            row = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
            await s.commit()


def test_the_user_facing_keys_exist_and_the_thread_renders_the_notice():
    from app.agents.context_loader import orchestration_step
    from app.agents.thread_bridge import RENDER_PATH_KEYS

    assert "retrieval.unavailable_notice" in RENDER_PATH_KEYS
    for key in ("retrieval.unavailable_notice", "finding.worth_checking"):
        text = orchestration_step(key)
        assert text and not text.startswith("<MISSING") and "{" not in text


# ── ops: the System page signal + the alert path ───────────────────────────────────────
@pytest.mark.asyncio
async def test_system_health_carries_retrieval_degraded_and_failed_crons_on_one_alert_list(client: AsyncClient):
    from app.db.base import AsyncSessionLocal
    from app.db.models.cron_run_log import CronRunLog

    for _ in range(3):
        health.record_tool_call("qdrant_search_laws_regulations", False, error="voyage 429")
    health.record_voyage("embeddings", False, status=429, error="Too Many Requests")
    async with AsyncSessionLocal() as s:
        row = CronRunLog(cron_name="cms_ncd_lcd_bulk", status="failed", triggered_source="scheduled", error_message="boom")
        s.add(row)
        await s.commit()
        run_id = row.run_id
    try:
        body = (await client.get("/v1/admin/system/health")).json()
        assert body["retrieval"]["status"] == "degraded"
        assert body["retrieval"]["live"]["voyage"]["embeddings"]["last_status"] == 429
        kinds = {a["kind"] for a in body["alerts"]}
        assert {"retrieval_degraded", "cron_failed"} <= kinds
        cron = next(a for a in body["alerts"] if a["kind"] == "cron_failed")
        assert "cms_ncd_lcd_bulk" in cron["detail"] and cron["action"]
        assert any(c["cron_name"] == "cms_ncd_lcd_bulk" for c in body["failed_crons"])
    finally:
        async with AsyncSessionLocal() as s:
            r = await s.get(CronRunLog, run_id)
            if r is not None:
                await s.delete(r)
            await s.commit()


# ── the harness assertion ──────────────────────────────────────────────────────────────
def test_harness_fails_a_scenario_that_expects_retrieval_when_any_knowledge_call_errored():
    import importlib.util
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve().parents[1] / "scripts/e2e_scenarios"
    sys.path.insert(0, str(here))  # the harness imports its sibling generate_docs bare
    root = here / "run_scenarios.py"
    spec = importlib.util.spec_from_file_location("run_scenarios", root)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok = {"audit_provenance": {"retrieval": {"status": "ok", "calls": 6, "errors": 0}}}
    down = {"audit_provenance": {"retrieval": {"status": "unavailable", "calls": 6, "errors": 6, "error_reasons": ["retrieval_unavailable"]}}}
    assert mod._retrieval_checks(ok) == []
    assert any("6 of 6" in f for f in mod._retrieval_checks(down))
    assert mod._retrieval_checks({"audit_provenance": {}})  # no record at all is a failure too
    assert any("NO knowledge-tool calls" in f for f in mod._retrieval_checks({"audit_provenance": {"retrieval": {"status": "ok", "calls": 0, "errors": 0}}}))
    scenarios = pathlib.Path(__file__).resolve().parents[1] / "scripts/e2e_scenarios/scenarios"
    tagged = [p.stem for p in scenarios.glob("*.json") if json.loads(p.read_text()).get("expects_retrieval")]
    assert {"upcoded_em_level", "unbundled_panel", "s07_knee_arthroscopy", "clean_bill_matching_eob"} <= set(tagged)


def test_harness_flags_content_rendered_beneath_a_working_status_card():
    """B4 (2026-09-23): the harness reads the thread during every machine phase and fails a
    scenario whose thread carried renderable content while the card was spinning."""
    import importlib.util
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve().parents[1] / "scripts/e2e_scenarios"
    sys.path.insert(0, str(here))
    spec = importlib.util.spec_from_file_location("run_scenarios_b4", here / "run_scenarios.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    clean = [
        {"kind": "status_card_update", "payload": {"stages": []}},
        {"kind": "system_message", "payload": {"marker": "ack"}, "content": "Got your bill."},
        {"kind": "attest_request", "payload": {"marker": "attest"}},
        {"kind": "message", "role": "user", "content": "hi"},
    ]
    assert mod._renderable_while_working(clean) == []
    leaky = clean + [
        {"kind": "system_message", "payload": {"marker": "dataquality:partial", "data_quality": {"kind": "partial_read"}}, "content": "I read most of this…"},
        {"kind": "verification_request", "payload": {}},
        {"kind": "message", "role": "assistant", "content": "Here is what I found so far"},
    ]
    leaks = mod._renderable_while_working(leaky)
    assert len(leaks) == 3 and any("dataquality:partial" in x for x in leaks)
    # entries already on the thread before the phase began (the verification cards the user
    # answered during the pause) are NOT leaks — only what APPEARS mid-run is (dev, 2026-09-23)
    baseline = {mod._entry_id(m) for m in leaky[:-1]}
    assert mod._renderable_while_working(leaky, baseline) == ["message:'Here is what I found so far'"]
    assert mod._renderable_while_working([{"kind": "system_message", "payload": {"marker": "audit_start"}}]) == []
    mod._working_phase_leaks["case-x"] = ["in_progress: system_message:'dataquality:partial'"]
    assert mod._working_phase_checks("case-x") and mod._working_phase_checks("case-x") == []  # consumed once
    assert "in_progress" in mod.MACHINE_WORKING

