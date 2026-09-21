"""Workflow invariants that used to live only in comments (deep review 2/3, 2026-09-18).

Each of these was a real failure or a near miss:
  * the sweep and the deploy SHARED a concurrency group — GitHub keeps one pending run per group,
    so a sweep dispatched while a deploy sat queued replaced it and that commit never reached dev;
  * the runtime suite ran twice on every push that touched runtime/** (standalone + deploy gate);
  * the "skip the standalone run" rule is only safe while its path list matches deploy-runtime's.
Parsed from the YAML, so a drift fails here rather than in production.
"""

from __future__ import annotations

import pathlib
import re

import yaml

WF = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WF / name).read_text(encoding="utf-8"))


def _on(doc: dict) -> dict:
    return doc.get("on") or doc.get(True)  # PyYAML reads the bare key `on` as boolean True


def _steps(doc: dict, job: str) -> list[dict]:
    return doc["jobs"][job]["steps"]


def test_the_sweep_and_the_deploy_never_share_a_concurrency_group():
    deploy, sweep = _load("deploy-runtime.yml"), _load("e2e-scenarios.yml")
    assert deploy["concurrency"]["group"] != sweep["concurrency"]["group"]
    for doc in (deploy, sweep):
        assert doc["concurrency"]["cancel-in-progress"] is False  # never kill a RUNNING one
    # …because the sweep yields instead: it needs to SEE deploy runs, read-only
    assert sweep["permissions"]["actions"] == "read"
    run_step = next(s for s in _steps(sweep, "scenarios") if s.get("name") == "Run scenarios against dev")
    assert run_step["env"]["GITHUB_TOKEN"] == "${{ github.token }}"
    assert "exit $code" in run_step["run"] and "-eq 3" in run_step["run"]  # the yield is surfaced


def test_the_sweep_is_capped_and_always_tears_down():
    sweep = _load("e2e-scenarios.yml")
    assert sweep["jobs"]["scenarios"]["timeout-minutes"] == 150
    teardown = _steps(sweep, "scenarios")[-1]
    assert "always()" in teardown["if"] and "--cleanup-only" in teardown["run"]
    # dispatch inputs reach the script through env, never interpolated into it
    run_step = next(s for s in _steps(sweep, "scenarios") if s.get("name") == "Run scenarios against dev")
    assert "${{ inputs." not in run_step["run"]


def _regex_for(paths: list[str]) -> str:
    parts = []
    for p in paths:
        parts.append(re.escape(p[:-2]).replace("\\-", "-") if p.endswith("/**") else re.escape(p).replace("\\-", "-") + "$")
    return "^(" + "|".join(parts) + ")"


def test_runtime_ci_steps_aside_for_exactly_the_pushes_the_deploy_will_test():
    deploy, ci = _load("deploy-runtime.yml"), _load("runtime-ci.yml")
    deploy_paths = _on(deploy)["push"]["paths"]
    decide = _steps(ci, "scope")[0]
    assert decide["env"]["DEPLOY_PATHS"] == _regex_for(deploy_paths), (
        "runtime-ci's DEPLOY_PATHS no longer mirrors deploy-runtime's on.push.paths — a push "
        "could skip the standalone suite without the deploy gate running it (or run it twice)"
    )
    rx = re.compile(decide["env"]["DEPLOY_PATHS"])
    for hit in ("runtime/app/main.py", "packages/shared/src/x.ts", ".github/workflows/deploy-runtime.yml"):
        assert rx.search(hit), hit
    for miss in ("apps/admin/src/x.tsx", "infra/envs/dev/crons.tf", "docs/build-kit/33.md",
                 "packages/other/x.ts", ".github/workflows/deploy-runtime.yml.bak",
                 "intelligence-layer/prompts/README.md", "__lookup_failed__"):
        assert not rx.search(miss), miss  # these pushes still get the standalone suite
    # the gate call can never be skipped, and both real jobs hang off the decision
    assert deploy["jobs"]["ci"]["with"]["gate"] is True
    assert _on(ci)["workflow_call"]["inputs"]["gate"]["default"] is False
    for job in ("tests", "migrations"):
        assert ci["jobs"][job]["needs"] == "scope"
        assert ci["jobs"][job]["if"] == "needs.scope.outputs.run == 'true'"
    assert 'run=true' in decide["run"] and '"$GATE" != "true"' in decide["run"]  # default is RUN


def test_the_deploy_still_waits_for_its_own_suite():
    deploy = _load("deploy-runtime.yml")
    assert deploy["jobs"]["deploy"]["needs"] == "ci"


def test_terraform_ci_checks_the_hcl_without_credentials():
    tf = _load("terraform-ci.yml")
    text = (WF / "terraform-ci.yml").read_text(encoding="utf-8")
    runs = " ".join(s.get("run", "") for s in _steps(tf, "validate"))
    assert "fmt -check" in runs and "init -backend=false" in runs and "validate" in runs
    assert "terraform plan" not in runs and "azure/login" not in text  # no creds, so no plan
    assert tf.get("permissions") == {"contents": "read"}
    assert "infra/**" in _on(tf)["push"]["paths"] and "infra/**" in _on(tf)["pull_request"]["paths"]


def test_the_app_deploy_polls_for_the_new_revision_instead_of_sleeping():
    app = (WF / "deploy-app.yml").read_text(encoding="utf-8")
    assert not re.search(r"^\s*sleep 30\b", app, re.MULTILINE)  # as a COMMAND (a comment names it)
    assert "seq 1 24" in app and "sleep 5" in app  # 24 x 5 s = the 120 s bound
    assert app.count("check-route-matrix.mjs") == 2  # the run + its single retry
