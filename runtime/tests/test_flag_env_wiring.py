"""Every runtime bool flag must be wired to a Container Apps env var (deep review, finding 1+2).

This class of bug has now happened twice. A sweep de-orphaned nine flags; the very next
feature (`enable_audit_ready_email`) shipped orphaned again — the flag that makes D3's "I'll
email you" true could not be turned on in ANY deployed environment, and nothing failed. A
convention that has to be remembered is not a mechanism; this test is the mechanism.

**The rule:** a `bool` setting on `Settings` must appear as an `env { name = "UPPER_CASE" }`
block in the RUNTIME container app in `infra/envs/dev/compute.tf`, so a cutover is a tfvars
flip rather than a code change. compute.tf holds seven env-bearing resources (runtime, the
migrations + seed jobs, qdrant, wrapper, marketing, admin) — the parse is per resource, so a
name wired to the admin app can't false-pass a runtime flag.

**The cron half** (bottom of this file) is DERIVED, not remembered: an AST walk collects every
`Settings` read reachable from the cron entrypoints and asserts the cron container carries
whatever the runtime container carries. The previous hand-curated "needed" list was itself a
remembered convention — it missed ENABLE_RECORD_VIEW, four of the five REVIEW_TRIGGER_* flags
and ENABLE_NSA_CHECKS (deep review C4, 2026-09-18).

**The allowlist** below is for bools that are deliberately NOT tfvars-controlled. Each is a
hardening default that should be true everywhere real and is only ever turned off for local
http / the test suite — exposing them as environment knobs would make "weaken the security
posture" a one-line plan diff on a machine nobody is watching. That's the opposite of what
this test is protecting.

Adding a bool to the allowlist is a deliberate act: it requires a reason here, in this file,
next to the name.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

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


_ENV_NAME = re.compile(r'name\s*=\s*"([A-Z][A-Z0-9_]*)"')


def _resource_block(tf_text: str, rtype: str, rname: str) -> str:
    """The full text of ONE `resource "<type>" "<name>" { … }` block, by brace matching. HCL
    strings in these files never contain braces outside `${…}` interpolations, which balance."""
    m = re.search(rf'^resource "{re.escape(rtype)}" "{re.escape(rname)}" \{{', tf_text, re.MULTILINE)
    assert m, f'resource "{rtype}" "{rname}" not found'
    i, depth = m.end(), 1
    while depth:
        depth += {"{": 1, "}": -1}.get(tf_text[i], 0)
        i += 1
    return tf_text[m.start() : i]


def _tf_env_names() -> set[str]:
    """Env names on the RUNTIME container app only (static `env {}` and `dynamic "env"`
    blocks). The whole-file regex this replaces would have accepted a name wired to any of
    compute.tf's seven env-bearing resources."""
    block = _resource_block(COMPUTE_TF.read_text(encoding="utf-8"), "azurerm_container_app", "runtime")
    return set(_ENV_NAME.findall(block))


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


# ── the CRON jobs' env: derived from what the cron path actually reads ─────────────────────
CRONS_TF = REPO / "infra/envs/dev/crons.tf"
APP_DIR = REPO / "runtime/app"

# Where a cron's execution starts. `python -m app.crons <name>` runs app/crons/*; the
# stuck_audits cron runs the boot sweep, which goes through the orchestrator's status chokepoint
# into the thread bridge, the review queue and the notify package.
CRON_ROOT_GLOBS = (
    "crons/*.py",
    "startup_reconcile.py",
    "agents/thread_bridge.py",
    "review/queue.py",
    "notify/*.py",
)

_AGENTS = (
    "Agent execution via the Anthropic-direct / proxy fallbacks. Only audit_retry calls Claude "
    "from a cron (e2e re-test 2026-09-23), and it does so through Foundry — its Foundry env is "
    "wired (crons.tf, local.claude_crons); the direct key and the fixture fallback never are."
)
_DEFAULT = (
    "A code default in EVERY container — no terraform variable, no env block anywhere — so the "
    "runtime and the crons cannot disagree. If it ever becomes a deployment knob, wire BOTH."
)

# Settings the cron path can reach statically but legitimately does not carry.
#   RUNTIME_ONLY            — wired to the runtime container; meaningless in a cron.
#   CODE_DEFAULT_EVERYWHERE — wired nowhere. The test ENFORCES that: the day one of these gets a
#                             runtime env block, it fails until the cron block gets one too
#                             (that is exactly the C4 failure shape).
RUNTIME_ONLY: dict[str, str] = {
    "allow_fixture_fallback": _AGENTS,
    "anthropic_api_key": _AGENTS,
}
CODE_DEFAULT_EVERYWHERE: dict[str, str] = {
    "audit_max_regenerations": _DEFAULT,
    "azure_doc_intelligence_model": _DEFAULT,
    "azure_storage_bulk_container": _DEFAULT,
    "bulk_local_dir": _DEFAULT,
    "litellm_proxy_url": _DEFAULT,
    "nudge_first_days": _DEFAULT,
    "nudge_second_days": _DEFAULT,
    "synthetic_email_suffixes": _DEFAULT,
}


def _cron_env_names() -> set[str]:
    """Env names on the cron job resource (every scheduled cron shares one for_each block)."""
    block = _resource_block(CRONS_TF.read_text(encoding="utf-8"), "azurerm_container_app_job", "cron")
    return set(_ENV_NAME.findall(block))


def _settings_fields() -> tuple[set[str], dict[str, set[str]]]:
    """(declared fields, {property/method name -> fields it reads via self.})."""
    tree = ast.parse((APP_DIR / "config.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Settings")
    fields = {
        n.target.id for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    }
    derived = {
        n.name: {
            a.attr
            for a in ast.walk(n)
            if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == "self"
        }
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return fields, derived


def _module_file(dotted: str) -> pathlib.Path | None:
    base = APP_DIR.parent / dotted.replace(".", "/")
    for cand in (base.with_suffix(".py"), base / "__init__.py"):
        if cand.exists():
            return cand
    return None


def _direct_app_imports(path: pathlib.Path) -> set[pathlib.Path]:
    """`app.*` modules a file imports — including lazy, function-level imports (ast.walk)."""
    out: set[pathlib.Path] = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] == "app":
            for dotted in (n.module, *(f"{n.module}.{a.name}" for a in n.names)):
                if f := _module_file(dotted):
                    out.add(f)
        elif isinstance(n, ast.Import):
            out.update(f for a in n.names if a.name.split(".")[0] == "app" and (f := _module_file(a.name)))
    return out


def _is_get_settings(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Name) and node.func.id == "get_settings")
        or (isinstance(node.func, ast.Attribute) and node.func.attr == "get_settings")
    )


def _attribute_reads_on_settings(path: pathlib.Path) -> set[str]:
    """Attribute names read off a Settings object: `get_settings().x`, and `<alias>.x` where the
    alias is a parameter called settings/_settings or a name assigned from an expression that
    calls get_settings() (`s = settings or get_settings()`). Over-collects (an alias `s` may be a
    DB session elsewhere in the file) — the caller keeps only real Settings fields."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = {"settings", "_settings"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(_is_get_settings(c) for c in ast.walk(n.value)):
            aliases.update(tgt.id for tgt in n.targets if isinstance(tgt, ast.Name))
    found: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and (
            _is_get_settings(n.value) or (isinstance(n.value, ast.Name) and n.value.id in aliases)
        ):
            found.add(n.attr)
    return found


def _cron_path_setting_reads() -> dict[str, set[str]]:
    """{settings field -> modules that read it} over the cron roots + their direct imports."""
    fields, derived = _settings_fields()
    roots = {p for g in CRON_ROOT_GLOBS for p in APP_DIR.glob(g) if p.name != "__init__.py"}
    modules = set(roots)
    for r in roots:
        modules |= _direct_app_imports(r)
    modules.discard(APP_DIR / "config.py")
    out: dict[str, set[str]] = {}
    for mod in modules:
        for attr in _attribute_reads_on_settings(mod):
            hit = {attr} if attr in fields else (derived.get(attr, set()) & fields)
            for f in hit:
                out.setdefault(f, set()).add(str(mod.relative_to(APP_DIR)))
    return out


def test_the_cron_walk_actually_finds_reads():
    """Guards the guard — an AST walk that silently found nothing would make the parity
    assertion vacuous. Known reads, each through a different syntactic route."""
    reads = _cron_path_setting_reads()
    assert len(reads) >= 25, f"only {len(reads)} settings reads found — the walk is broken"
    assert "crons/nudge_cron.py" in reads["enable_nudge_emails"]  # get_settings().x in a cron
    assert "review/queue.py" in reads["review_trigger_canary"]  # s = settings or get_settings()
    assert "agents/thread_bridge.py" in reads["enable_record_view"]
    assert "startup_reconcile.py" in reads["audit_wall_clock_budget_seconds"]
    assert "notify/email.py" in reads["synthetic_email_suffixes"]  # via a Settings @property
    assert "agents/orchestrator.py" in reads["enable_nsa_checks"]  # a DIRECT IMPORT of a root
    assert len(_cron_env_names()) >= 15 and "DATABASE_URL" in _cron_env_names()


def test_cron_path_settings_reads_are_wired_to_the_cron_container():
    """THE mechanism (deep review C4). For every Settings field the cron path reads:
      * wired to the runtime container  ->  must be wired to the cron container too, or a
        tfvars flip reaches the API and not the cron (unless RUNTIME_ONLY says why not);
      * wired to neither               ->  must be DECLARED a code default, so adding a new
        Settings read to a cron forces a decision instead of silently riding a default."""
    reads = _cron_path_setting_reads()
    runtime_env, cron_env = _tf_env_names(), _cron_env_names()
    unwired, undeclared = [], []
    for field, mods in sorted(reads.items()):
        env = field.upper()
        if env in cron_env or field in RUNTIME_ONLY:
            continue
        where = ", ".join(sorted(mods))
        if env in runtime_env:
            unwired.append(f"{env}  (read in: {where})")
        elif field not in CODE_DEFAULT_EVERYWHERE:
            undeclared.append(f"{env}  (read in: {where})")
    assert not unwired, (
        "wired to the RUNTIME container but not the CRON container — a tfvars flip would apply "
        "to the API and not to the crons (infra/envs/dev/crons.tf):\n  " + "\n  ".join(unwired)
    )
    assert not undeclared, (
        "read on the cron path and wired to NO container. Wire it to both (variables.tf + "
        "compute.tf + crons.tf), or declare it in CODE_DEFAULT_EVERYWHERE with the reason:\n  "
        + "\n  ".join(undeclared)
    )


def test_cron_parity_exemptions_are_real_and_honest():
    fields, _ = _settings_fields()
    reads = _cron_path_setting_reads()
    runtime_env, cron_env = _tf_env_names(), _cron_env_names()
    assert not (set(RUNTIME_ONLY) & set(CODE_DEFAULT_EVERYWHERE))
    for name, reason in {**RUNTIME_ONLY, **CODE_DEFAULT_EVERYWHERE}.items():
        assert name in fields, f"{name!r} is not a Settings field any more — drop the exemption"
        assert name in reads, f"{name!r} is no longer read on the cron path — drop the exemption"
        assert len(reason) > 40, f"{name} needs a real reason"
    for name in RUNTIME_ONLY:
        assert name.upper() in runtime_env, f"{name} is RUNTIME_ONLY but the runtime doesn't wire it"
        assert name.upper() not in cron_env, f"{name} is wired to the crons — drop the exemption"
    for name in CODE_DEFAULT_EVERYWHERE:
        assert name.upper() not in runtime_env, (
            f"{name} is declared a code default everywhere, but the RUNTIME container now wires "
            "it — wire the cron container too and remove it from CODE_DEFAULT_EVERYWHERE"
        )
        assert name.upper() not in cron_env, f"{name} is wired to the crons — drop the exemption"


def test_the_cron_gaps_this_mechanism_was_written_for_are_closed():
    """Named so a future rewrite of the walk can't quietly drop the cases that motivated it:
    67885b7's email flags, then the deep review's record view / review triggers / budget."""
    env = _cron_env_names()
    for name in (
        "ENABLE_NUDGE_EMAILS", "ENABLE_AUDIT_READY_EMAIL", "SENDGRID_FROM_EMAIL", "SENDGRID_API_KEY",
        "ENABLE_CHAT_FIRST_AUDIT", "ENABLE_RECORD_VIEW", "ENABLE_NSA_CHECKS",
        "REVIEW_SAMPLE_PCT", "REVIEW_TRIGGER_FIRST_CASE", "REVIEW_TRIGGER_LOW_CONFIDENCE",
        "REVIEW_TRIGGER_SYSTEM_ERROR", "REVIEW_TRIGGER_CANARY", "REVIEW_TRIGGER_GUARD_DROP",
        "REVIEW_TRIGGER_MATERIAL_DISAGREEMENT",
        "AUDIT_WALL_CLOCK_BUDGET_SECONDS", "AUDIT_RECONCILE_STALE_SECONDS",
    ):  # fmt: skip
        assert name in env, f"{name} lost its cron env wiring"


def test_review_sample_dial_is_env_wired():
    """Human Review §7-2d: the dial is an INT, so the bool sweep above doesn't see it — pin
    it explicitly (env in compute.tf + a terraform variable), like the flags."""
    assert "REVIEW_SAMPLE_PCT" in _tf_env_names()
    assert 'variable "review_sample_pct"' in VARIABLES_TF.read_text(encoding="utf-8")


def test_reconcile_stale_threshold_is_env_wired_for_runtime_and_cron():
    """Deep review C2: the healer's threshold floor is an INT (the bool sweep doesn't see it)
    and is read by TWO containers — the runtime's boot sweep and the stuck_audits cron. A flip
    in tfvars must reach both, or they disagree about which audits are dead."""
    assert "AUDIT_RECONCILE_STALE_SECONDS" in _tf_env_names()
    assert "AUDIT_RECONCILE_STALE_SECONDS" in _cron_env_names()
    assert 'variable "audit_reconcile_stale_seconds"' in VARIABLES_TF.read_text(encoding="utf-8")



def test_audit_budget_is_env_wired_for_runtime_and_cron():
    """The healer's threshold is max(3 x AUDIT_WALL_CLOCK_BUDGET_SECONDS, the floor). The budget
    was wired NOWHERE — the runtime and the cron agreed only because they shared a code
    default, so tuning it would have needed a code change, and a future env on one side only
    would have made them disagree about which audits are dead."""
    assert "AUDIT_WALL_CLOCK_BUDGET_SECONDS" in _tf_env_names()
    assert "AUDIT_WALL_CLOCK_BUDGET_SECONDS" in _cron_env_names()
    assert 'variable "audit_wall_clock_budget_seconds"' in VARIABLES_TF.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "env_name",
    ["INTAKE_MODE_DEFAULT", "INTAKE_MODE_COHORT_PCT", "GUIDED_HIDDEN_SURFACES", "UNLOCK_GATE_MODE"],
)
def test_guided_intake_settings_are_env_wired_for_runtime_and_cron(env_name):
    """Doc 40 §D. None of the four is a bool, so the sweep above cannot see them — pinned here.
    BOTH containers: the API resolves a user's front door and renders the unlock moment, and
    the cron paths (reconcile, nudge) project the same case state the planner wrote. A tfvars
    flip that reached one container and not the other is the 67885b7 failure shape."""
    assert env_name in _tf_env_names(), f"{env_name} is not wired to the runtime container"
    assert env_name in _cron_env_names(), f"{env_name} is not wired to the cron container"
    assert f'variable "{env_name.lower()}"' in VARIABLES_TF.read_text(encoding="utf-8")


def test_the_two_provisional_defaults_are_the_documented_ones():
    """Two open decisions ship as data (doc 40 open questions 1 and 2). The code default, the
    terraform default and the documented default must be the same value — a disagreement
    would mean the env you deploy is not the behaviour you reviewed."""
    from app.config import Settings

    fields = Settings.model_fields
    tf = VARIABLES_TF.read_text(encoding="utf-8")
    for name in ("guided_hidden_surfaces", "unlock_gate_mode", "intake_mode_default"):
        default = fields[name].default
        block = tf[tf.index(f'variable "{name}"') :]
        block = block[: block.index("\n}\n")]
        assert f'default     = "{default}"' in block, (name, default)
    assert fields["intake_mode_cohort_pct"].default == 0
