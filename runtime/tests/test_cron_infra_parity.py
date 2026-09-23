"""Every registered cron must actually be scheduled (deep review, finding 3).

`analytics_rollup` and `nudge` were registered in `app/crons/registry.py` — importable,
triggerable by hand from the admin console, covered by unit tests — and had no container-app
job in `crons.tf`. So nightly aggregation never ran in any deployed environment and the
dashboard's daily metrics silently didn't accumulate. Nothing was broken; something just
never happened, which is the hardest kind of gap to notice.

The registry is the source of truth for what crons exist; `crons.tf` is the source of truth
for what runs. This test asserts they agree, in both directions:

- a registered cron with no job → it will never run
- a scheduled job with no registry entry → `python -m app.crons <name>` fails at runtime,
  which surfaces as a red job in Azure rather than anywhere anyone is looking

It parses the .tf directly rather than diffing against a checked-in JSON export: an export
is a third copy that itself goes stale, and the point here is to have no copies.
"""

from __future__ import annotations

import pathlib
import re

from app.crons.registry import CRON_REGISTRY

CRONS_TF = pathlib.Path(__file__).resolve().parents[2] / "infra/envs/dev/crons.tf"

# name -> why it has no schedule
UNSCHEDULED_BY_DESIGN: dict[str, str] = {
    "noop": "manual smoke-test only — it exists so an admin can verify the trigger → run-log "
            "pipeline without side effects, so scheduling it would just add noise",
    "audit_retry_force": "manual by design (e2e re-test 2026-09-23 item 3) — the lever a person "
                         "pulls from Admin › System › crons once a system_error's cause is fixed; "
                         "it re-runs past the attempt cap, which a schedule must never do",
}


def _scheduled_cron_names() -> set[str]:
    """Keys of the `scheduled_crons` locals map in crons.tf."""
    text = CRONS_TF.read_text(encoding="utf-8")
    block = re.search(r"scheduled_crons\s*=\s*\{(.*?)\n  \}", text, re.DOTALL)
    assert block, "could not find the scheduled_crons locals block in crons.tf"
    return set(re.findall(r"^\s*([a-z][a-z0-9_]*)\s*=\s*\{", block.group(1), re.MULTILINE))


def test_the_tf_parser_actually_finds_jobs():
    """Guards the guard — a regex that matched nothing would make the parity check vacuous."""
    found = _scheduled_cron_names()
    assert len(found) >= 6, f"only parsed {len(found)} scheduled crons — the parser is broken"
    assert "qdrant_snapshot" in found


def test_every_registered_cron_is_scheduled():
    """THE finding. A cron nobody scheduled is a feature nobody runs."""
    missing = sorted(set(CRON_REGISTRY) - _scheduled_cron_names() - set(UNSCHEDULED_BY_DESIGN))
    assert not missing, (
        "crons registered in app/crons/registry.py with no container-app job in "
        "infra/envs/dev/crons.tf — these will never run in a deployed environment:\n  "
        + "\n  ".join(missing)
        + "\n\nAdd them to the scheduled_crons locals, or add them to UNSCHEDULED_BY_DESIGN "
        "in this file with the reason."
    )


def test_every_scheduled_job_maps_to_a_real_cron():
    """The other direction: a job whose name isn't in the registry fails inside the container
    (`python -m app.crons <name>`), where the failure is a red job in Azure rather than
    anything anyone watches."""
    unknown = sorted(_scheduled_cron_names() - set(CRON_REGISTRY))
    assert not unknown, f"scheduled jobs with no registry entry: {unknown}"


def test_the_two_crons_this_test_was_written_for_are_scheduled():
    """Named explicitly so a future rewrite of the generic checks can't quietly drop the case
    that motivated them."""
    scheduled = _scheduled_cron_names()
    assert "analytics_rollup" in scheduled, "nightly aggregation is unscheduled again"
    assert "nudge" in scheduled, "the nudge cron is unscheduled again"


def test_unscheduled_exceptions_are_real_and_documented():
    for name, reason in UNSCHEDULED_BY_DESIGN.items():
        assert name in CRON_REGISTRY, f"UNSCHEDULED_BY_DESIGN names {name!r}, which isn't registered"
        assert len(reason) > 40, f"{name} needs a real reason"


# ── the deploy workflow's cron image roll finds jobs by terraform's name prefix ───────────
def test_the_cron_image_roll_uses_the_prefix_terraform_names_the_jobs_with():
    """deploy-runtime rolls every scheduled job to the new image by NAME PREFIX. The filter used
    to carry two literals — one of them dead (`${CONTAINER_APP}-cron-` = tyndale-dev-runtime-cron-,
    which no job has ever matched) — and nothing tied the live one to terraform. A prefix change
    would have left every cron on its old image, silently (deep review 2/3)."""
    import yaml

    repo = pathlib.Path(__file__).resolve().parents[2]
    main_tf = (repo / "infra/envs/dev/main.tf").read_text(encoding="utf-8")
    variables_tf = (repo / "infra/envs/dev/variables.tf").read_text(encoding="utf-8")
    crons_tf = CRONS_TF.read_text(encoding="utf-8")
    workflow_text = (repo / ".github/workflows/deploy-runtime.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)

    # terraform: name_prefix = "tyndale-${local.env}", env = var.environment (default "dev")
    assert re.search(r'name_prefix\s*=\s*"tyndale-\$\{local\.env\}"', main_tf)
    assert re.search(r"env\s*=\s*var\.environment", main_tf)
    env_default = re.search(
        r'variable "environment" \{.*?default\s*=\s*"([a-z]+)"', variables_tf, re.DOTALL
    ).group(1)
    tf_prefix = f"tyndale-{env_default}"
    assert '"${local.name_prefix}-cron-${replace(each.key, "_", "-")}"' in crons_tf

    env = workflow["env"]
    assert env["NAME_PREFIX"] == tf_prefix
    for key in ("CONTAINER_APP", "MIGRATION_JOB", "RESOURCE_GROUP"):
        assert env[key].startswith(f"{tf_prefix}-"), f"{key} is not under the terraform name prefix"
    roll = next(
        s for s in workflow["jobs"]["deploy"]["steps"] if s.get("name") == "Update cron job images"
    )["run"]
    assert 'CRON_PREFIX="${NAME_PREFIX}-cron-"' in roll
    assert "${CONTAINER_APP}-cron-" not in workflow_text  # the dead clause is gone
    assert "tyndale-dev-cron-" not in roll  # no second hard-coded literal
    assert "exit 1" in roll  # zero matches is an error, never a silent no-op

    # every scheduled cron's job name really does start with that prefix (32-char truncation kept)
    for name in _scheduled_cron_names():
        job = f"{tf_prefix}-cron-{name.replace('_', '-')}"[:32]
        assert job.startswith(f"{tf_prefix}-cron-")
