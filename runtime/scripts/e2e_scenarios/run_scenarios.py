"""E2E bill-scenario driver (HP-2).

Drives the REAL Tyndale API through each scenario end-to-end — upload -> extraction -> encounter
verification -> audit -> terminal — and asserts the honest terminal state, the expected finding
types, and that NO MRI-fixture markers leak in. SYNTHETIC identities only (never real PHI).

Auth: a dedicated synthetic test user via the admin-only, dev-only /v1/admin/test-token endpoint.
  * local docker-compose (default): the dev auth stub makes every request the dev admin user, so
    no token is needed; the driver still calls test-token when it can.
  * --dev (deployed dev API, real auth): set TYNDALE_ADMIN_TOKEN to an admin session token so the
    driver can mint the synthetic user's session.

Usage:
  uv run python scripts/e2e_scenarios/run_scenarios.py                 # local docker-compose
  uv run python scripts/e2e_scenarios/run_scenarios.py --dev           # deployed dev API
  uv run python scripts/e2e_scenarios/run_scenarios.py --only duplicate_cpt_line
  uv run python scripts/e2e_scenarios/run_scenarios.py --record        # + assert /v1/record (D5)
  uv run python scripts/e2e_scenarios/run_scenarios.py --generate-only # just make the PDFs

Each run costs real Claude tokens against dev (~1 audit per scenario). Not scheduled.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import re
import sys
import tempfile
import time

import httpx

from generate_docs import generate_for_scenario  # noqa: E402 (run as a script from this dir)

HERE = pathlib.Path(__file__).parent
SCENARIO_DIR = HERE / "scenarios"
LOCAL_URL = "http://localhost:4000"
DEV_URL = "https://api.tyndaleapp.net"
SYNTH_EMAIL = "e2e-runner@e2e.tyndale.test"
COOKIE_NAME = "tyndale_session"  # a session read-name on every env (bare name kept for grace)

# MRI-fixture codes — their presence anywhere in a result means fabricated data leaked (the bug
# HP prompts have chased). NO scenario legitimately uses these.
FIXTURE_MARKERS = ("70553", "A9579", "36000")

POLL_TIMEOUT_S = 600
POLL_INTERVAL_S = 4
EXTRACT_TIMEOUT_S = 180


def log(msg: str) -> None:
    print(msg, flush=True)


def authenticate(
    client: httpx.Client, base_url: str, admin_token: str | None, e2e_secret: str | None
) -> str | None:
    """Mint the synthetic user's session via the admin test-token endpoint. Prefers the stable,
    non-expiring shared secret (X-E2E-Test-Secret, from Key Vault → TYNDALE_E2E_SECRET) and falls
    back to a (7-day) admin session token. Returns the synthetic user_id, or None when running
    against the local dev-user stub (no real auth)."""
    headers = {}
    if e2e_secret:
        headers["X-E2E-Test-Secret"] = e2e_secret
    elif admin_token:
        client.cookies.set(COOKIE_NAME, admin_token)
    try:
        r = client.post(
            f"{base_url}/v1/admin/test-token",
            json={"email": SYNTH_EMAIL},
            headers=headers,
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise SystemExit(f"cannot reach {base_url}: {e}") from e
    if r.status_code == 200:
        body = r.json()
        client.cookies.clear()
        client.cookies.set(COOKIE_NAME, body["token"])
        return body["user_id"]
    if not (admin_token or e2e_secret):
        log(f"  test-token unavailable [{r.status_code}] — proceeding as the local dev user")
        return None
    raise SystemExit(f"test-token failed [{r.status_code}]: {r.text}")


_MIME_BY_SUFFIX = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".heic": "image/heic", ".txt": "text/plain",
}


def _upload(client: httpx.Client, base_url: str, paths: list[pathlib.Path]) -> tuple[int, str]:
    """POST the scenario's documents (MIME inferred from the suffix, so a .txt isn't mislabeled as
    PDF). Returns (status_code, case_file_id) — case_file_id is "" on a non-200 so the caller can
    assert an EXPECTED upload rejection (the magic-byte gate)."""
    files = [
        ("files", (p.name, p.read_bytes(), _MIME_BY_SUFFIX.get(p.suffix.lower(), "application/octet-stream")))
        for p in paths
    ]
    r = client.post(f"{base_url}/v1/upload", files=files, timeout=120)
    if r.status_code != 200:
        return r.status_code, ""
    return 200, r.json()["case_file_id"]


def _extract(client: httpx.Client, base_url: str, case_id: str) -> dict:
    """GET /line-items runs the (synchronous) translate pass on first call and returns the
    ExtractResult — either encounter_verification_pending with line_items, or extraction_failed."""
    r = client.get(f"{base_url}/v1/audit/{case_id}/line-items", timeout=EXTRACT_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def _confirm(client: httpx.Client, base_url: str, case_id: str, extract: dict, enc: dict) -> None:
    default = enc.get("default", "yes")
    overrides = enc.get("overrides", {})
    confirmations = [
        {
            "line_item_id": li["line_item_id"],
            "response": overrides.get(li["code"], default),
            "user_note": None,
        }
        for li in extract.get("line_items", [])
    ]
    r = client.post(
        f"{base_url}/v1/audit/{case_id}/confirmations",
        json={"confirmations": confirmations},
        timeout=60,
    )
    r.raise_for_status()


def _poll_status(client: httpx.Client, base_url: str, case_id: str) -> str:
    terminal = {"audit_complete", "audit_incomplete", "extraction_failed", "resolved", "archived"}
    deadline = time.monotonic() + POLL_TIMEOUT_S
    status = "audit_running"
    while time.monotonic() < deadline:
        r = client.get(f"{base_url}/v1/audit/{case_id}/status", timeout=30)
        r.raise_for_status()
        status = r.json()["status"]
        if status in terminal:
            return status
        time.sleep(POLL_INTERVAL_S)
    return status  # last seen (a timeout — reported as a mismatch)


def _get_audit(client: httpx.Client, base_url: str, case_id: str) -> dict:
    r = client.get(f"{base_url}/v1/audit/{case_id}", timeout=60)
    r.raise_for_status()
    return r.json()


def _fetch_thread(client: httpx.Client, base_url: str, case_id: str) -> list[dict] | None:
    """The case's chat-first thread entries (DL-91) — the per-case conversation's messages."""
    r = client.get(
        f"{base_url}/v1/conversations",
        params={"case_id": case_id, "mode": "per_case", "limit": 1}, timeout=30,
    )
    r.raise_for_status()
    convs = r.json().get("conversations", [])
    if not convs:
        return None
    d = client.get(f"{base_url}/v1/conversations/{convs[0]['conversation_id']}", timeout=30)
    d.raise_for_status()
    return d.json().get("messages", [])


def _chat_first_checks(messages: list[dict] | None, terminal: str, no_placeholders: bool) -> list[str]:
    """Assert the thread matches engine state: (a) a single status card reflecting the terminal
    state, (b) the terminal entry type matches, (c) no placeholder copy under staging config."""
    if messages is None:
        return ["chat-first: no case thread found"]
    fails: list[str] = []
    kinds = [m.get("kind") for m in messages]
    cards = [m for m in messages if m.get("kind") == "status_card_update"]
    if len(cards) != 1:
        fails.append(f"chat-first: expected exactly 1 status card, got {len(cards)}")
    elif terminal in ("audit_complete", "audit_incomplete", "extraction_failed", "not_a_bill"):
        if not (cards[0].get("payload") or {}).get("terminal"):
            fails.append("chat-first: status card not marked terminal at a terminal state")
    if terminal == "audit_complete" and "moment_card" not in kinds:
        fails.append("chat-first: audit_complete but no three-number moment card in the thread")
    if terminal in ("extraction_failed", "not_a_bill"):
        markers = {(m.get("payload") or {}).get("marker") for m in messages}
        if f"terminal:{terminal}" not in markers:
            fails.append(f"chat-first: {terminal} but no terminal message in the thread")
    if no_placeholders and "[PLACEHOLDER-eng]" in json.dumps(messages):
        fails.append("chat-first: [PLACEHOLDER-eng] copy leaked into the thread (staging)")
    return fails


# X1 doctrine checker (Brock D-A) — loaded by file path: intelligence-layer is not a package,
# and the doctrine modules are deliberately self-contained (stdlib-only) for exactly this.
_X1_PATH = (
    HERE.parents[2] / "intelligence-layer" / "evals" / "doctrine" / "x1_close_the_loop.py"
)
_x1_module = None


def _load_x1():
    global _x1_module
    if _x1_module is None:
        spec = importlib.util.spec_from_file_location("x1_close_the_loop", _X1_PATH)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["x1_close_the_loop"] = mod  # dataclasses need the module registered pre-exec
        spec.loader.exec_module(mod)
        _x1_module = mod
    return _x1_module


def _x1_checks(messages: list[dict] | None, terminal: str) -> list[str]:
    """Brock D-A: needs_documents-producing scenarios assert the X1 close-the-loop contract
    over the case thread. nudge_state=None here — the HTTP harness can't see the DB-side
    cadence machinery, so X1(c) is asserted in-process (tests/test_x1_contract.py) and the
    checker records it as a note, never a silent pass."""
    if messages is None:
        return ["x1: no case thread to check (X1 assertions need the chat-first thread)"]
    verdict = _load_x1().check_x1(messages, terminal, nudge_state=None)
    return [] if verdict.passed else [f"x1: {r}" for r in verdict.reasons]


def _attest_checks(client: httpx.Client, base_url: str, case_id: str, messages: list[dict] | None) -> list[str]:
    """§A2 state 1: a name-mismatch case must GATE — an attest_request entry in the thread, and
    encounter verification refused (409) until the relationship is attested."""
    fails: list[str] = []
    kinds = [m.get("kind") for m in (messages or [])]
    if "attest_request" not in kinds:
        fails.append("attest: no attest_request entry in the thread for a name-mismatch case")
    r = client.post(
        f"{base_url}/v1/audit/{case_id}/confirmations",
        json={"confirmations": [{"line_item_id": "probe", "response": "yes"}]},
        timeout=30,
    )
    if r.status_code != 409:
        fails.append(f"attest: confirmations returned {r.status_code}, expected 409 while unattested")
    return fails


def _wrongdoc_checks(messages: list[dict] | None, expected_branch: str) -> list[str]:
    """§A2 state 2: the terminal entry carries the TYPED branch + a next-step affordance."""
    for m in messages or []:
        payload = m.get("payload") or {}
        if payload.get("wrongdoc_branch"):
            fails = []
            if payload["wrongdoc_branch"] != expected_branch:
                fails.append(f"wrongdoc: branch={payload['wrongdoc_branch']}, expected {expected_branch}")
            if not payload.get("next_action"):
                fails.append("wrongdoc: branch carries no next_action (dead end)")
            return fails
    return [f"wrongdoc: no typed branch on the terminal entry (expected {expected_branch})"]


def _reconcile_checks(messages: list[dict] | None) -> list[str]:
    """§A2 state 3: if a reconcile state rendered, its ladder must be well-formed — and the
    last-resort line must NOT be present while an answer or a resolving ask remains."""
    entry = next((m for m in (messages or []) if (m.get("payload") or {}).get("reconcile")), None)
    if entry is None:
        return []  # no material conflict in this run — nothing to assert (not a failure)
    rec = (entry.get("payload") or {})["reconcile"]
    fails: list[str] = []
    rungs = rec.get("rungs") or []
    if not rungs or rungs[0] != "explain":
        fails.append(f"reconcile: ladder must start at explain, got {rungs}")
    if "last_resort" in rungs and "ask_one_input" in rungs:
        fails.append("reconcile: last_resort rendered alongside an unanswered ask (flag-and-send-off)")
    if not rec.get("figures"):
        fails.append("reconcile: no named figures — the conflict must name both sources")
    return fails


def _decline_checks(client: httpx.Client, base_url: str, case_id: str, specs: list[dict]) -> list[str]:
    """§A2 state 4: each utterance declines without dead-ending; the guarantee reply carries no
    probability/promise language ([C] doctrine)."""
    forbidden = re.compile(
        r"\b(?:\d{1,3}\s?%|percent chance|probability|odds are|likely to win|you will win|"
        r"guarantee[ds]?|i promise|good chance|strong chance|almost certain)\b",
        re.IGNORECASE,
    )
    fails: list[str] = []
    for spec in specs or []:
        r = client.post(
            f"{base_url}/v1/messages",
            json={"case_file_id": case_id, "content": spec["utterance"], "mode": "per_case"},
            timeout=120,
        )
        if r.status_code != 200:
            fails.append(f"decline[{spec['kind']}]: POST /v1/messages -> {r.status_code}")
            continue
        body = r.text
        if len(body.strip()) < 40:
            fails.append(f"decline[{spec['kind']}]: response too short to be a real reframe")
        if spec["kind"] == "guarantee" and (hit := forbidden.search(body)):
            fails.append(f"decline[guarantee]: prediction language leaked: {hit.group(0)!r}")
    return fails


def _data_quality_checks(messages: list[dict] | None, expected_kind: str) -> list[str]:
    """F3/F4: the §5.1 / §5.2 state must actually render, carrying its detection kind — and a
    partial read must never print a guessed number."""
    for m in messages or []:
        dq = (m.get("payload") or {}).get("data_quality")
        if dq and dq.get("kind") == expected_kind:
            fails = []
            if expected_kind == "partial_read":
                if not dq.get("unreadable_label"):
                    fails.append("data-quality: partial read didn't name the unreadable part")
                if not dq.get("readable"):
                    fails.append("data-quality: partial read reported nothing readable")
            return fails
    return [f"data-quality: no {expected_kind} entry in the thread"]


def _free_text_verify_checks(client: httpx.Client, base_url: str, case_id: str, spec: dict) -> list[str]:
    """D4b: a free-text verification reply maps to a PRE-SELECTABLE suggestion and commits NOTHING
    (the tap does). POST the utterance, then assert a suggestion in the thread + that the case is
    still pending verification (the invariant). The normal _confirm afterwards is the confirming
    tap that actually advances the audit."""
    fails: list[str] = []
    r = client.post(
        f"{base_url}/v1/audit/{case_id}/verify-text", json={"utterance": spec["utterance"]}, timeout=30
    )
    if r.status_code != 200:
        return [f"free-text: verify-text status {r.status_code}"]
    want = spec.get("expect_result", "mapped")
    if r.json().get("result") != want:
        fails.append(f"free-text: result={r.json().get('result')!r} expected {want!r}")
    thread = _fetch_thread(client, base_url, case_id)
    if not any(m.get("kind") == "verification_suggestion" for m in (thread or [])):
        fails.append("free-text: no verification_suggestion posted to the thread")
    st = client.get(f"{base_url}/v1/audit/{case_id}/status", timeout=30).json().get("status")
    if st != "encounter_verification_pending":
        fails.append(f"free-text INVARIANT: status advanced to {st!r} — free text must commit nothing")
    return fails


def _check(scenario: dict, terminal: str, extract: dict, audit: dict | None) -> list[str]:
    """Assert the scenario's expectations. Returns a list of failure strings (empty == pass)."""
    exp = scenario["expect"]
    fails: list[str] = []
    # `terminal` may be a single value or a list of acceptable honest terminals (e.g. a blank /
    # garbage PDF may land on extraction_failed OR not_a_bill depending on whether real DI extracts
    # any trivial text — both are honest no-encounter states, which is what actually matters).
    want = exp["terminal"]
    ok = terminal in want if isinstance(want, list) else terminal == want
    if not ok:
        fails.append(f"terminal={terminal!r} expected {want!r}")
    # A degradation scenario must NEVER reach the encounter screen: the honest-failure states carry
    # zero line items. Assert both, so a regression that dead-ends on "0 of 0" is caught.
    if exp.get("no_encounter"):
        n = len(extract.get("line_items") or [])
        if n:
            fails.append(f"{n} line items on a failure state — must be 0 (never reach encounter)")
        if terminal == "encounter_verification_pending":
            fails.append("reached encounter_verification_pending — expected an honest failure state")
    # Anti-fabrication: no fixture line items may leak, INCLUDING on the extraction_failed path
    # (this is what the old unreadable_document assertion missed — it only checked the audit).
    eblob = json.dumps(extract).lower()
    for marker in FIXTURE_MARKERS:
        if marker.lower() in eblob:
            fails.append(f"FIXTURE MARKER {marker!r} leaked into the extract result")
    if audit is not None:
        if exp.get("incomplete_reason", "unset") != "unset":
            got = audit.get("incomplete_reason")
            if got != exp["incomplete_reason"]:
                fails.append(f"incomplete_reason={got!r} expected {exp['incomplete_reason']!r}")
        blob = json.dumps(audit).lower()
        for marker in FIXTURE_MARKERS:
            if marker.lower() in blob:
                fails.append(f"FIXTURE MARKER {marker!r} leaked into the result")
        findings = audit.get("findings", [])
        if "max_findings" in exp and len(findings) > exp["max_findings"]:
            fails.append(f"{len(findings)} findings > max {exp['max_findings']}")
        for want in exp.get("finding_types", []):
            hay = " ".join(
                f"{f.get('category', '')} {f.get('finding_type', '')} "
                f"{json.dumps(f.get('facts', {}))} {json.dumps(f.get('recommendation', {}))}"
                for f in findings
            ).lower()
            if want.lower() not in hay:
                fails.append(f"no finding matching {want!r}")
    return fails


def _record_checks(client: httpx.Client, base_url: str, case_id: str, terminal: str) -> list[str]:
    """After a scenario reaches its terminal state, the Tyndale Record (D5, DL-91 §5) must show
    this sub-case with the right status — and recovered_so_far MUST be $0, because the harness
    never confirms an outcome. A findings estimate leaking into 'recovered' would show up here as
    a non-zero tally (the §4 confirmed-only rule, proven end-to-end)."""
    r = client.get(f"{base_url}/v1/record", timeout=30)
    if r.status_code != 200:
        return [f"record: GET /v1/record -> {r.status_code} (is ENABLE_RECORD_VIEW on the target?)"]
    rows = {x["case_file_id"]: x for x in r.json().get("sub_cases", [])}
    row = rows.get(case_id)
    if row is None:
        return [f"record: sub-case {case_id} absent from /v1/record"]
    fails: list[str] = []
    if row.get("status") != terminal:
        fails.append(f"record: row status {row.get('status')} != terminal {terminal}")
    if row.get("recovered_so_far", 0.0) != 0.0:
        fails.append(
            f"record: recovered_so_far={row['recovered_so_far']} with no confirmed outcome "
            "(a finding ESTIMATE leaked into recovered — §4 violation)"
        )
    tn = row.get("three_number")
    if tn is not None and not any(float(v) for v in tn.values()):
        fails.append("record: three_number is all-zeros — a no-number case must be None, not {0,0,0}")
    # The row TITLE is provider/date, never the status (the status is the trailing chip).
    title = (row.get("provider") or "Bill review").strip().lower()
    _STATUS_TITLES = {
        "results ready", "needs documents", "verify your visit", "auditing",
        "couldn't read", "not a bill", "in progress", "resolved",
    }
    if title in _STATUS_TITLES:
        fails.append(f"record: row title {title!r} is a status string — expected provider/date")
    return fails


# Which generated document types actually PRINT each identifier (see generate_docs.py). An MSN
# is payer-issued but carries no claim number, so it isn't listed — the harness asserts what the
# fixtures contain, not what the type could theoretically hold.
_PROVIDER_DOC_TYPES = frozenset({"bill", "summary_bill", "collections"})
_PAYER_DOC_TYPES = frozenset({"eob"})


def _call_identifier_checks(
    client: httpx.Client, base_url: str, case_id: str, scenario: dict
) -> list[str]:
    """B4 / L7 — the pinned strip renders from TYPED data only.

    The generated documents print an account number on the bill and a claim number on the EOB,
    so a scenario carrying both must surface both on the sub-case, and each gameplan step must
    quote the identifier belonging to the party IT calls. The negative half matters as much:
    a scenario with no bill must not produce an account number from somewhere else.
    """
    want_account = any(d.get("type") in _PROVIDER_DOC_TYPES for d in scenario.get("documents", []))
    want_claim = any(d.get("type") in _PAYER_DOC_TYPES for d in scenario.get("documents", []))
    r = client.get(f"{base_url}/v1/case/{case_id}/summary", timeout=30)
    if r.status_code != 200:
        return [f"call-ids: GET /v1/case/{case_id}/summary -> {r.status_code}"]
    summary = r.json()
    fails: list[str] = []
    if want_account and not summary.get("account_number"):
        fails.append("call-ids: bill uploaded but no typed account_number on the sub-case")
    if want_claim and not summary.get("claim_number"):
        fails.append("call-ids: EOB uploaded but no typed claim_number on the sub-case")
    if not want_account and summary.get("account_number"):
        fails.append(
            f"call-ids: account_number={summary['account_number']!r} with no provider document — "
            "an identifier appeared from a source that doesn't assign it"
        )

    _EXPECTED_KIND = {"payer": "claim", "provider": "account"}
    for step in summary.get("gameplan", []):
        kind, number = step.get("reference_kind"), step.get("reference_number")
        if kind is not None and kind != _EXPECTED_KIND.get(step.get("party")):
            fails.append(
                f"call-ids: step {step.get('index')} calls the {step.get('party')} but quotes a "
                f"{kind} number — the wrong reference wastes the call"
            )
        if (kind is None) != (number is None):
            fails.append(f"call-ids: step {step.get('index')} has kind={kind!r} number={number!r}")
        # Never a raw slot, never a blank where a number should be.
        if number is not None and (not str(number).strip() or "{" in str(number)):
            fails.append(f"call-ids: step {step.get('index')} reference {number!r} is not a number")
    return fails


def _record_aggregate_checks(client: httpx.Client, base_url: str) -> dict:
    """Suite-level Record sanity after many uploads (DL-91 §5): the multi-upload user has ≥2 rows,
    and the honest aggregates hold — total_recovered is $0 (no outcomes confirmed anywhere) and no
    total is negative."""
    fails: list[str] = []
    r = client.get(f"{base_url}/v1/record", timeout=30)
    if r.status_code != 200:
        fails.append(f"GET /v1/record -> {r.status_code} (is ENABLE_RECORD_VIEW on the target?)")
    else:
        body = r.json()
        subs = body.get("sub_cases", [])
        agg = body.get("aggregates", {})
        if len(subs) < 2:
            fails.append(f"expected >=2 sub-cases after multiple uploads, got {len(subs)}")
        if agg.get("total_recovered", -1.0) != 0.0:
            fails.append(f"total_recovered={agg.get('total_recovered')} but no outcome was confirmed")
        for k in ("total_billed_reviewed", "total_identified", "open_items"):
            if agg.get(k, 0) < 0:
                fails.append(f"aggregate {k}={agg.get(k)} is negative")
    return {"name": "record_aggregates", "case_id": "", "terminal": "-", "timings": {},
            "pass": not fails, "fails": fails}


def run_scenario(
    client: httpx.Client, base_url: str, scenario: dict, workdir: pathlib.Path,
    *, chat_first: bool = False, no_placeholders: bool = False, record: bool = False,
) -> dict:
    name = scenario["name"]
    exp = scenario.get("expect", {})
    timings: dict[str, float] = {}
    case_id = ""
    try:
        paths = generate_for_scenario(scenario, workdir / name)

        t = time.monotonic()
        up_status, case_id = _upload(client, base_url, paths)
        timings["upload_s"] = round(time.monotonic() - t, 1)

        # Upload-rejection scenarios (e.g. a non-document .txt): assert the 4xx at the door and
        # that NO case was created — the magic-byte gate, exercised end-to-end.
        if "upload_rejected" in exp:
            fails = []
            if up_status != exp["upload_rejected"]:
                fails.append(f"upload status={up_status} expected {exp['upload_rejected']}")
            if case_id:
                fails.append("a case was created despite an expected upload rejection")
            return {"name": name, "case_id": case_id, "terminal": f"upload_{up_status}",
                    "timings": timings, "pass": not fails, "fails": fails}
        if up_status != 200:
            return {"name": name, "case_id": "", "terminal": f"upload_{up_status}",
                    "timings": timings, "pass": False, "fails": [f"unexpected upload {up_status}"]}

        t = time.monotonic()
        extract = _extract(client, base_url, case_id)
        timings["extract_s"] = round(time.monotonic() - t, 1)

        terminal = extract.get("status", "")

        # §A2 state 1: an attest-gated case terminates HERE by design — the flow must not
        # proceed to encounter/audit while the attestation is outstanding, so asserting the
        # gate IS the scenario.
        if exp.get("attest_required"):
            fails = _attest_checks(client, base_url, case_id, _fetch_thread(client, base_url, case_id))
            return {"name": name, "case_id": case_id, "terminal": f"attest_gated:{terminal}",
                    "timings": timings, "pass": not fails, "fails": fails}

        # D4b free-text variant: map an utterance to a suggestion (commits nothing) BEFORE the tap.
        pre_fails: list[str] = []
        if chat_first and scenario.get("chat_first_verify") and terminal == "encounter_verification_pending":
            pre_fails = _free_text_verify_checks(
                client, base_url, case_id, scenario["chat_first_verify"]
            )
        audit: dict | None = None
        # The honest-failure states are terminal at the extract step — no encounter/audit.
        if terminal not in ("extraction_failed", "not_a_bill"):
            _confirm(client, base_url, case_id, extract, scenario.get("encounter", {}))
            t = time.monotonic()
            terminal = _poll_status(client, base_url, case_id)
            timings["audit_s"] = round(time.monotonic() - t, 1)
            audit = _get_audit(client, base_url, case_id)

        fails = pre_fails + _check(scenario, terminal, extract, audit)
        if chat_first and case_id:
            thread = _fetch_thread(client, base_url, case_id)
            fails = fails + _chat_first_checks(thread, terminal, no_placeholders)
            if exp.get("assert_x1"):
                fails = fails + _x1_checks(thread, terminal)
            if exp.get("wrongdoc_branch"):
                fails = fails + _wrongdoc_checks(thread, exp["wrongdoc_branch"])
            if exp.get("reconcile_no_premature_last_resort"):
                fails = fails + _reconcile_checks(thread)
            if exp.get("data_quality_kind"):
                fails = fails + _data_quality_checks(thread, exp["data_quality_kind"])
        if scenario.get("chat_declines") and case_id:
            fails = fails + _decline_checks(client, base_url, case_id, scenario["chat_declines"])
        if record and case_id:
            fails = fails + _record_checks(client, base_url, case_id, terminal)
            fails = fails + _call_identifier_checks(client, base_url, case_id, scenario)
        return {"name": name, "case_id": case_id, "terminal": terminal, "timings": timings,
                "pass": not fails, "fails": fails}
    except Exception as e:  # noqa: BLE001 — one scenario's failure never aborts the suite
        return {"name": name, "case_id": case_id, "terminal": "ERROR", "timings": timings,
                "pass": False, "fails": [f"{type(e).__name__}: {e}"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Tyndale e2e scenario harness (synthetic only)")
    ap.add_argument("--dev", action="store_true", help="target the deployed dev API")
    ap.add_argument("--base-url", default=None, help="override the target base URL")
    ap.add_argument("--only", action="append", default=[], help="run only these scenario names")
    ap.add_argument("--generate-only", action="store_true", help="only generate the PDFs, no run")
    ap.add_argument("--chat-first", action="store_true",
                    help="also assert the chat-first thread matches engine state (DL-91; target "
                         "server must have ENABLE_CHAT_FIRST_AUDIT on)")
    ap.add_argument("--assert-no-placeholders", action="store_true",
                    help="fail if [PLACEHOLDER-eng] copy appears in the thread (staging config)")
    ap.add_argument("--record", action="store_true",
                    help="also assert each sub-case appears in /v1/record with the right status + "
                         "honest $0-recovered, plus a suite-level aggregate check (DL-91 D5 §5; "
                         "target server must have ENABLE_RECORD_VIEW on)")
    args = ap.parse_args()

    base_url = args.base_url or (DEV_URL if args.dev else LOCAL_URL)
    scenarios = [json.loads(p.read_text()) for p in sorted(SCENARIO_DIR.glob("*.json"))]
    if args.only:
        scenarios = [s for s in scenarios if s["name"] in set(args.only)]
    if not scenarios:
        raise SystemExit("no scenarios matched")

    workdir = pathlib.Path(tempfile.mkdtemp(prefix="e2e_docs_"))
    log(f"generating documents into {workdir}")
    if args.generate_only:
        for s in scenarios:
            generate_for_scenario(s, workdir / s["name"])
        log(f"generated docs for {len(scenarios)} scenarios; skipping run (--generate-only)")
        return 0

    log(f"target: {base_url}")
    with httpx.Client(follow_redirects=True) as client:
        uid = authenticate(
            client,
            base_url,
            os.environ.get("TYNDALE_ADMIN_TOKEN"),
            os.environ.get("TYNDALE_E2E_SECRET"),
        )
        log(f"authenticated as {uid or 'dev-user'}\n")
        results = [
            run_scenario(client, base_url, s, workdir, chat_first=args.chat_first,
                         no_placeholders=args.assert_no_placeholders, record=args.record)
            for s in scenarios
        ]
        # Suite-level Record check: after every upload, the multi-upload user's Record must hold
        # ≥2 sub-cases with honest aggregates (DL-91 §5). Skipped unless we ran real scenarios.
        if args.record and not args.only:
            results.append(_record_aggregate_checks(client, base_url))

    # --- report ---
    log("\n" + "=" * 78)
    log(f"{'SCENARIO':<30} {'RESULT':<7} {'TERMINAL':<20} TIMINGS")
    log("-" * 78)
    for r in results:
        mark = "PASS" if r["pass"] else "FAIL"
        tim = " ".join(f"{k}={v}" for k, v in r["timings"].items())
        log(f"{r['name']:<30} {mark:<7} {r['terminal']:<20} {tim}")
        if not r["pass"]:
            log(f"    case_file_id={r['case_id'] or '(none)'}")
            for f in r["fails"]:
                log(f"      - {f}")
    passed = sum(1 for r in results if r["pass"])
    log("=" * 78)
    log(f"RESULT: {passed}/{len(results)} scenarios passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
