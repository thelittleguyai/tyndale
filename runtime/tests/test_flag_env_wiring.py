"""Every runtime bool flag must be wired to a Container Apps env var (deep review, finding 1+2).

This class of bug has now happened twice. A sweep de-orphaned nine flags; the very next
feature (`enable_audit_ready_email`) shipped orphaned again — the flag that makes D3's "I'll
email you" true could not be turned on in ANY deployed environment, and nothing failed. A
convention that has to be remembered is not a mechanism; this test is the mechanism.

**The rule:** a `bool` setting on `Settings` must appear as an `env { name = "UPPER_CASE" }`
block in `infra/envs/dev/compute.tf`, so a cutover is a tfvars flip rather than a code change.

**The allowlist** below is for bools that are deliberately NOT tfvars-controlled. Each is a
hardening default that should be true everywhere real and is only ever turned off for local
http / the test suite — exposing them as environment knobs would make "weaken the security
posture" a one-line plan diff on a machine nobody is watching. That's the opposite of what
this test is protecting.

Adding a bool to the allowlist is a deliberate act: it requires a reason here, in this file,
next to the name.
"""

from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
CONFIG_PY = REPO / "runtime/app/config.py"
COMPUTE_TF = REPO / "infra/envs/dev/compute.tf"
VARIABLES_TF = REPO / "infra/envs/dev/variables.tf"

# name -> why it is not an env knob
ALLOWLIST: dict[str, str] = {
    "cookie_secure": (
        "Hardening default (True). False only for http://localhost; a deployed env must never "
        "be able to drop the Secure attribute via a plan diff."
    ),
    "session_cookie_secure_prefix": (
        "Hardening default (True) and coupled to cookie_secure — a __Secure- cookie over plain "
        "http is rejected by browsers, so it moves with cookie_secure or not at all."
    ),
    "rate_limit_enabled": (
        "Hardening default (True). Disabled only by the test suite via env; making it a tfvars "
        "knob would let a deploy silently remove magic-link abuse protection."
    ),
    "security_headers_enabled": (
        "Hardening default (True). Same reasoning — headers off is never a deployment choice."
    ),
}

_BOOL_SETTING = re.compile(r"^\s{4}([a-z][a-z0-9_]*)\s*:\s*bool\s*=", re.MULTILINE)


def _bool_settings() -> set[str]:
    """Bool fields declared on Settings. Indentation-anchored: class-body fields sit at four
    spaces, so locals inside methods can't be mistaken for settings."""
    return set(_BOOL_SETTING.findall(CONFIG_PY.read_text(encoding="utf-8")))


def _tf_env_names() -> set[str]:
    return set(re.findall(r'name\s*=\s*"([A-Z][A-Z0-9_]*)"', COMPUTE_TF.read_text(encoding="utf-8")))


def _tf_variables() -> set[str]:
    return set(re.findall(r'^variable\s+"([a-z0-9_]+)"', VARIABLES_TF.read_text(encoding="utf-8"), re.MULTILINE))


def test_the_introspection_actually_finds_settings():
    """Guards the guard: a regex that silently matched nothing would make every assertion
    below vacuously true, which is exactly how this bug survives a test."""
    found = _bool_settings()
    assert len(found) >= 15, f"only found {len(found)} bool settings — the parser is broken"
    for known in ("enable_audit_ready_email", "enable_billing", "use_real_claude"):
        assert known in found, f"{known} not detected — the parser is broken"
    assert len(_tf_env_names()) >= 20, "compute.tf env parsing is broken"


def test_every_bool_flag_has_container_app_env_wiring():
    """THE regression test. A new flag with no env block fails here, by name."""
    orphans = sorted(
        name
        for name in _bool_settings()
        if name not in ALLOWLIST and name.upper() not in _tf_env_names()
    )
    assert not orphans, (
        "runtime bool flags with no env wiring in infra/envs/dev/compute.tf — they cannot be "
        "turned on in any deployed environment:\n  "
        + "\n  ".join(orphans)
        + "\n\nAdd an env block (+ a variable and a tfvars line), or add the flag to ALLOWLIST "
        "in this file with the reason it is not a deployment knob."
    )


def test_every_wired_flag_has_a_terraform_variable():
    """An env block referencing a var that doesn't exist fails `terraform validate`, but only
    if someone runs it — catch it here, where CI already runs."""
    missing = sorted(
        name
        for name in _bool_settings()
        if name not in ALLOWLIST and name.upper() in _tf_env_names() and name not in _tf_variables()
    )
    assert not missing, f"env-wired flags with no terraform variable: {missing}"


def test_allowlisted_flags_are_documented_and_real():
    """An allowlist entry for a setting that no longer exists is dead weight that makes the
    next reader trust it less."""
    settings = _bool_settings()
    for name, reason in ALLOWLIST.items():
        assert name in settings, f"ALLOWLIST names {name!r}, which is not a bool setting anymore"
        assert len(reason) > 40, f"{name} needs a real reason, not a placeholder"


def test_the_three_flags_this_test_was_written_for_are_wired():
    """The specific regression the 2026-08-13 deep review found. Named so a future rewrite of
    the generic check above can't quietly drop the case that motivated it."""
    env = _tf_env_names()
    for flag in ("ENABLE_AUDIT_READY_EMAIL", "USE_REAL_CRISIS_CLASSIFIER", "ALLOW_FIXTURE_FALLBACK"):
        assert flag in env, f"{flag} lost its env wiring"


# ── audit 2026-08-27 item 4: the CRON jobs' env, per container block ────────────────
CRONS_TF = REPO / "infra/envs/dev/crons.tf"


def _cron_env_names() -> set[str]:
    """Env names inside crons.tf's job CONTAINER block specifically — a whole-file regex
    would false-pass names wired anywhere in the file (the failure mode this test's
    compute.tf sibling narrowly avoids by that file being single-purpose)."""
    text = CRONS_TF.read_text(encoding="utf-8")
    start = text.index("container {")
    # crude but structural: the container block ends at the template close; envs only
    # appear inside it in this file.
    block = text[start:]
    return set(re.findall(r'name\s*=\s*"([A-Z][A-Z0-9_]*)"', block))


def test_cron_jobs_carry_what_the_crons_actually_read():
    """The nudge cron read enable_nudge_emails + the SendGrid pair from Settings while the
    job env carried none of them — every send silently skipped (third life of this bug).
    The set here is audited from app/crons/* + app/notify/*: extend it when a cron gains
    a Settings read."""
    needed = {
        "DATABASE_URL",
        "QDRANT_URL",
        "QDRANT_API_KEY",
        "AZURE_STORAGE_CONNECTION_STRING",
        "AUDIT_LOG_ENC_KEY",
        "ENABLE_NUDGE_EMAILS",
        "ENABLE_AUDIT_READY_EMAIL",
        "SENDGRID_FROM_EMAIL",
        "SENDGRID_API_KEY",
        "AUTH_SUCCESS_REDIRECT",
    }
    missing = needed - _cron_env_names()
    assert missing == set(), f"cron job env missing: {sorted(missing)}"
