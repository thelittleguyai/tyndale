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
  uv run python scripts/e2e_scenarios/run_scenarios.py --generate-only # just make the PDFs

Each run costs real Claude tokens against dev (~1 audit per scenario). Not scheduled.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
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


def run_scenario(client: httpx.Client, base_url: str, scenario: dict, workdir: pathlib.Path) -> dict:
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
        audit: dict | None = None
        # The honest-failure states are terminal at the extract step — no encounter/audit.
        if terminal not in ("extraction_failed", "not_a_bill"):
            _confirm(client, base_url, case_id, extract, scenario.get("encounter", {}))
            t = time.monotonic()
            terminal = _poll_status(client, base_url, case_id)
            timings["audit_s"] = round(time.monotonic() - t, 1)
            audit = _get_audit(client, base_url, case_id)

        fails = _check(scenario, terminal, extract, audit)
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
        results = [run_scenario(client, base_url, s, workdir) for s in scenarios]

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
