"""Fabrication-canary scan. A marker ANYWHERE in the result is a failure — no allow-rule.

History: Brock's 2026-09-17 option (b) ledgered one benign signature (Bill Detective's notes
naming a canary while reasoning about the CPT family of a code genuinely on the bill —
70553 beside a billed 70551). The same week's re-pick chose markers that share a family with
no real code, which made that rule unreachable; it was retired 2026-09-18 (deep review) and
these tests are the negatives that remain."""

import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "e2e_scenarios"))

import run_scenarios  # noqa: E402
from run_scenarios import (  # noqa: E402
    EXIT_YIELDED,
    _failed_case_ids,
    _marker_pattern,
    _pick_active,
    _RateLimitBudget,
    _retrying,
    _run_all,
    _run_tag,
    _scan_extract_markers,
    _wait_for_deploys,
    _warm,
)
from run_scenarios import (  # noqa: E402
    FIXTURE_MARKERS,
    _marker_hits,
    _scan_audit_markers,
)

# The exact 2026-08-25 signature (captured_bill_photo, --inspect): a 70551 bill, notes naming
# the family siblings.
_NOTE = (
    "Only 70551 billed — the without-contrast variant (lowest complexity of the "
    "70551/70552/70553 family); no upcoding signal. Single line item, single DOS."
)


def _audit_with(path_field: str, text: str) -> dict:
    facts = {"notes": text} if path_field == "notes" else {"summary": text}
    return {
        "findings": [{"category": "diagnostic_complete_no_errors_found", "facts": facts}],
        "summary": "ok",
    }


def test_the_old_family_reasoning_signature_no_longer_hits_at_all():
    """The note that tripped the 2026-08-25 sweep names 70551/70552/70553 — none of which is a
    marker any more. No hit, so nothing to ledger: the allow-rule had nothing left to allow."""
    assert "70553" not in FIXTURE_MARKERS
    assert _scan_audit_markers(_audit_with("notes", _NOTE)) == []


def test_a_current_marker_in_analyst_notes_fails_even_with_family_language():
    """What the retired rule would have waved through for the old set is a hard failure for the
    new one — there is no field, and no phrasing, in which a canary is acceptable."""
    for marker in FIXTURE_MARKERS:
        note = f"Only 99284 billed — lowest complexity of the 99284/{marker} family; no upcoding signal."
        fails = _scan_audit_markers(_audit_with("notes", note))
        assert fails == [f"FIXTURE MARKER {marker!r} leaked into the result at $.findings[0].facts.notes"]


def test_any_other_field_trips_too():
    assert _scan_audit_markers(_audit_with("summary", "Consider 02417 as an alternative charge."))


def test_the_allow_rule_and_its_ledger_entry_are_gone():
    for name in ("_marker_benign", "_bill_codes", "_family_prefix", "_FAMILY_LANG_RE", "_BENIGN_LEDGER_KEY"):
        assert not hasattr(run_scenarios, name), f"{name} is retired — a marker hit has no exceptions"
    cfg = run_scenarios._load_doctrine("doctrine_config")
    assert not [k for k in cfg.X_KNOWN_GAPS if k.startswith("canary:")]


def test_final_canary_set_is_structurally_unassigned():
    assert FIXTURE_MARKERS == ("02417", "05821", "Z4411")
    for m in ("02417", "05821"):  # the five-digit CPT gap between anesthesia and surgery
        assert 2000 <= int(m) <= 9999 and len(m) == 5
    assert FIXTURE_MARKERS[2][0] == "Z"  # HCPCS Level II letter never nationally assigned
    assert _marker_hits("05821", "code 05821 billed") and not _marker_hits("05821", "cost 105821.00")


def test_warm_up_retries_a_cold_target_then_gives_up():
    """2026-09-18: a scale-to-zero cold start blew the 30 s preflight. The warm-up retries
    with a delay and only exits once every attempt failed."""
    calls: list[int] = []
    slept: list[float] = []

    def flaky() -> None:
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("cold")

    assert _warm(flaky, attempts=3, delay_s=2.0, sleep=slept.append) == 3
    assert slept == [2.0, 2.0]

    def dead() -> None:
        raise ConnectionError("down")

    with pytest.raises(SystemExit, match="cannot reach target after 2 attempts"):
        _warm(dead, attempts=2, delay_s=0.0, sleep=slept.append)


def test_retrying_returns_the_value_and_treats_a_5xx_as_transient():
    """The mid-cutover 500 on test-token (sweep 35378477176): a 5xx raised inside fetch is
    retried like a transport error and the eventual response is returned."""
    seen: list[int] = []

    def mint():
        seen.append(1)
        if len(seen) == 1:
            raise RuntimeError("test-token 500: internal_server_error")
        return {"status": 200}

    assert _retrying(mint, attempts=4, delay_s=0.0, sleep=lambda _s: None, what="test-token") == {"status": 200}
    assert len(seen) == 2


# ── deep review C1 (2026-09-18): the trailing boundary must not swallow a sentence end ──────
_MARKERS = ("02417", "05821", "Z4411")

_HIT_TEMPLATES = [
    "The bill shows CPT {m}.",  # sentence-final — THE defect: '.' used to be a boundary violation
    "HCPCS {m}.\nNext paragraph",  # sentence-final before a newline
    "billed as ({m}) on the statement",  # parenthesized
    "codes {m}, 99284 and others",  # comma-followed
    "{m}",  # the whole string
    "code {m}; see the EOB",  # semicolon-followed
    "“{m}” appears twice",  # quoted
    "{m}. {m}.",  # twice, both sentence-final
]
_MISS_TEMPLATES = [
    "1{m}.00",  # inside a longer number — the 105821.00 case
    "{m}.50",  # decimal continuation — a number, not the code
    "{m}.0",  # decimal continuation, single digit
    "{m}7",  # continues as a longer number
    "A{m}",  # continues a longer alphanumeric token
    "{m}X",  # mid-word
    "12.{m}",  # a decimal FRACTION ending in the digits
    "ref{m}id",  # buried in an identifier
]


@pytest.mark.parametrize("marker", _MARKERS)
@pytest.mark.parametrize("template", _HIT_TEMPLATES)
def test_marker_hits_in_every_natural_prose_position(marker, template):
    text = template.format(m=marker)
    assert _marker_hits(marker, text), f"{marker!r} must hit in {text!r}"
    assert _marker_hits(marker, text.lower()), "the extract scan lowercases its blob"


@pytest.mark.parametrize("marker", _MARKERS)
@pytest.mark.parametrize("template", _MISS_TEMPLATES)
def test_marker_never_fires_inside_a_longer_token_or_a_decimal(marker, template):
    text = template.format(m=marker)
    assert not _marker_hits(marker, text), f"{marker!r} must NOT hit in {text!r}"


def test_the_two_cases_the_prompt_names_verbatim():
    assert _marker_hits("02417", "billed CPT 02417.")
    assert _marker_hits("Z4411", "HCPCS Z4411.")
    assert not _marker_hits("05821", "105821.00")
    assert not _marker_hits("02417", "02417.50")


def test_the_adopted_pattern_is_pinned():
    """Brock's prompt examples depend on marker behaviour — the exact regex is part of the
    contract, so a silent edit shows up here."""
    assert _marker_pattern("02417") == r"(?<![0-9A-Za-z.])02417(?![0-9A-Za-z]|\.\d)"


@pytest.mark.parametrize("marker", _MARKERS)
def test_both_scans_catch_a_sentence_final_marker(marker):
    """The extract scan (whole payload as one lowercased blob) and the audit scan (per string
    field) both go through the same boundary rule."""
    extract = {"line_items": [{"code": "99284", "plain_language_translation": f"Imaging billed as {marker}."}]}
    assert _scan_extract_markers(extract) == [f"FIXTURE MARKER {marker!r} leaked into the extract result"]
    audit = {"summary": f"Your bill includes {marker}.", "findings": [{"facts": {"gap": 12.5}}]}
    assert _scan_audit_markers(audit) == [f"FIXTURE MARKER {marker!r} leaked into the result at $.summary"]


def test_both_scans_stay_quiet_on_decimals_and_longer_numbers():
    extract = {"line_items": [{"code": "99284", "billed_amount": 105821.00, "note": "total 02417.50 and 1Z4411"}]}
    assert _scan_extract_markers(extract) == []
    audit = {"summary": "Charges of 105821.00 and 02417.50; ref AZ4411X.", "findings": []}
    assert _scan_audit_markers(audit) == []


def test_teardown_keeps_only_the_failed_scenarios_cases():
    """Deep review C5: a sweep tears its synthetic identity down, but a FAILED scenario's case
    stays so `--inspect` still has something to look at."""
    results = [
        {"name": "a", "pass": True, "case_id": "11111111-1111-1111-1111-111111111111"},
        {"name": "b", "pass": False, "case_id": "22222222-2222-2222-2222-222222222222"},
        {"name": "c", "pass": False, "case_id": ""},  # failed before a case existed
        {"name": "record_aggregates", "pass": True, "case_id": ""},
    ]
    assert _failed_case_ids(results) == ["22222222-2222-2222-2222-222222222222"]
    assert _failed_case_ids([]) == []


# ══ deep review 2/3 (2026-09-18): identity per ATTEMPT, the deploy interlock, the 429 budget ══


def test_a_rerun_mints_a_fresh_identity():
    """'Re-run jobs' keeps GITHUB_RUN_ID — without the attempt, a re-run inherited the first
    attempt's identity and its spent 20-uploads/hour budget (the case e75cc21 set out to fix)."""
    first = _run_tag({"GITHUB_RUN_ID": "35383490200", "GITHUB_RUN_ATTEMPT": "1"})
    rerun = _run_tag({"GITHUB_RUN_ID": "35383490200", "GITHUB_RUN_ATTEMPT": "2"})
    assert (first, rerun) == ("35383490200-1", "35383490200-2")
    assert _run_tag({"GITHUB_RUN_ID": "7"}) == "7-1"  # attempt absent -> first
    local = _run_tag({})
    assert len(local) == 14 and local.isdigit()  # UTC timestamp outside CI
    assert run_scenarios.SYNTH_EMAIL.endswith("@e2e.tyndale.test")


def test_only_unfinished_deploys_count_as_active():
    runs = [
        {"id": 1, "status": "completed", "html_url": "u1"},
        {"id": 2, "status": "in_progress", "html_url": "u2"},
        {"id": 3, "status": "queued", "html_url": "u3"},
        {"id": 4, "status": "pending", "html_url": "u4"},
    ]
    assert [r["id"] for r in _pick_active(runs)] == [2, 3, 4]
    assert _pick_active([]) == [] and _pick_active([{"id": 9, "status": "completed"}]) == []


def test_the_sweep_waits_for_a_deploy_before_starting_and_gives_up_after_the_bound():
    polls = iter([[{"status": "in_progress", "url": "u"}], [{"status": "in_progress", "url": "u"}], []])
    slept: list[int] = []
    assert _wait_for_deploys(active=lambda: next(polls), sleep=slept.append, clock=lambda: 0.0) is True
    assert slept == [30, 30]  # two polls, then clear

    ticks = iter([0.0, 10.0, 99_999.0])
    stuck = _wait_for_deploys(
        max_wait_s=1200, active=lambda: [{"status": "queued", "url": "u"}],
        sleep=lambda _s: None, clock=lambda: next(ticks),
    )
    assert stuck is False  # still deploying after the bound -> the caller yields, never races


def test_the_sweep_yields_at_a_scenario_boundary_when_a_deploy_begins():
    scenarios = [{"name": n} for n in ("a", "b", "c", "d")]
    ran: list[str] = []

    def run_one(s):
        ran.append(s["name"])
        return {"name": s["name"], "pass": True, "case_id": "x", "terminal": "audit_complete", "timings": {}}

    # no deploy at the a|b boundary; one has begun by b|c
    checks = iter([[], [{"status": "queued", "url": "https://gh/run/9"}]])
    results, stopped = _run_all(scenarios, run_one, active=lambda: next(checks), budget=_RateLimitBudget())
    assert ran == ["a", "b"]  # c and d never uploaded anything
    assert "yielded to deploy https://gh/run/9" in stopped
    assert [(r["name"], r.get("skipped", False)) for r in results] == [
        ("a", False), ("b", False), ("c", True), ("d", True),
    ]
    assert all(r["terminal"] == "SKIPPED" and not r["pass"] for r in results[2:])
    assert _failed_case_ids(results) == []  # a skipped scenario has no case to keep
    assert EXIT_YIELDED == 3

    # the boundary check never runs BEFORE the first scenario (that is _wait_for_deploys' job)
    ran.clear()
    results, stopped = _run_all(scenarios[:1], run_one, active=lambda: [{"status": "queued", "url": "u"}])
    assert ran == ["a"] and stopped is None


def test_the_429_budget_stops_the_run_cleanly_instead_of_sleeping_for_hours():
    """Unbounded, 23 scenarios x up to 900 s of Retry-After is ~5.5 h of sleeping, and the job
    is hard-killed at the 150-min cap with no summary at all."""
    b = _RateLimitBudget(budget_s=1800)
    assert b.spend(900) and b.spend(900) and b.waited_s == 1800 and not b.exhausted
    assert b.spend(1) is False and b.exhausted and b.waited_s == 1800  # refused, not slept

    scenarios = [{"name": n} for n in ("a", "b", "c")]
    budget = _RateLimitBudget(budget_s=600)
    ran: list[str] = []

    def run_one(s):
        ran.append(s["name"])
        if s["name"] == "a":
            budget.spend(900)  # a's upload hit a 429 it could not afford to wait out
        return {"name": s["name"], "pass": s["name"] != "a", "case_id": "", "terminal": "upload_429", "timings": {}}

    results, stopped = _run_all(scenarios, run_one, active=lambda: [], budget=budget)
    assert ran == ["a"] and "rate-limit budget spent" in stopped
    assert [r.get("skipped", False) for r in results] == [False, True, True]


def test_the_harness_never_sends_a_real_address_to_the_delete_endpoint(monkeypatch):
    """The cleanup endpoint refuses non-synthetic addresses (400) — and the harness refuses before
    it calls, so a typo'd E2E_SYNTH_EMAIL / `identity` input can't even be transmitted."""
    assert run_scenarios._is_synthetic("e2e-runner+35383490200-1@e2e.tyndale.test")
    assert run_scenarios._is_synthetic("  E2E-Runner@E2E.TYNDALE.TEST ")
    for bad in ("phil@example.com", "x@e2e.tyndale.test.evil.com", "", None):
        assert not run_scenarios._is_synthetic(bad)

    called: list[str] = []
    monkeypatch.setenv("TYNDALE_E2E_SECRET", "s3cret")
    monkeypatch.setattr(run_scenarios.httpx, "Client", lambda **k: called.append("client") or None)
    assert run_scenarios._teardown("https://api.example", "phil@example.com", []) is None
    assert called == []  # no client was ever constructed — nothing left the process
