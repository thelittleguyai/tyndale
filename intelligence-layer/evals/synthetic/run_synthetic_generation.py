"""
Synthetic adversarial case generator for Tyndale's intelligence-layer eval suite.

This script reads the 12 Opus 4.7 generation prompts in ``prompts/``, runs each
against Opus 4.7, validates every returned case against the golden-example schema
(``../golden/schema.json``), and writes the valid cases to ``cases/<taxonomy>/``.

------------------------------------------------------------------------------
TEMPLATE STATUS — does NOT execute in Phase 2E
------------------------------------------------------------------------------
This is a runnable *template*. ``--help`` and ``--dry-run`` work with zero
dependencies installed (anthropic / jsonschema are imported lazily). A real
generation run needs:
  * Anthropic API access (key, or the runtime's LiteLLM proxy), and
  * the two ``# TODO(brock/eng)`` blocks below filled in:
      1. build_client()  — wire the API/proxy client (see Phase 2D).
      2. spot_check()    — the 10% manual-review workflow before promotion.
Until then the script will exit cleanly with an explanatory message rather
than make network calls.

USAGE:
    python run_synthetic_generation.py --taxonomy <name>            # one taxonomy
    python run_synthetic_generation.py --all                        # all 12
    python run_synthetic_generation.py --taxonomy <name> --dry-run  # preview, no API
    python run_synthetic_generation.py --list                       # show taxonomies

Requires (for a live run):
    ANTHROPIC_API_KEY (or runtime LiteLLM proxy creds — see build_client)
    pip install -r requirements.txt   # anthropic, jsonschema

Cost: roughly $10-25 for the full ~2,250-case V1-Lite set on Opus 4.7 with
prompt caching on the shared generation prompt. Set ANTHROPIC_BUDGET_LIMIT_USD
to hard-cap spending; see README.md for the cost breakdown and caveats.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
PROMPTS_DIR = ROOT / "prompts"
CASES_DIR = ROOT / "cases"
SCHEMA_PATH = ROOT.parent / "golden" / "schema.json"

MODEL = "claude-opus-4-7"
MAX_TOKENS_PER_REQUEST = 16000  # Opus 4.7 output budget per generation call
BATCH_SIZE = 25  # cases per request; ~500 output tokens each fits comfortably
BUDGET_LIMIT_USD = float(os.getenv("ANTHROPIC_BUDGET_LIMIT_USD", "30.0"))

# ---------------------------------------------------------------------------
# Taxonomy registry.
#
# Each key is a prompt-file stem in prompts/<key>.md AND the cases/<key>/
# output directory. "category" is the golden-schema `category` enum value the
# generated cases MUST carry (validated post-generation); "subcategory" is the
# expected `subcategory` where the prompt declares one (soft-checked). Several
# prompts share one category (3x bill_error_detection, 2x
# coverage_connection_fhir) but each keeps its own taxonomy bucket so spot-
# checking and re-runs stay scoped to a single failure mode.
#
# Targets must match the README progress table and the "Target case count" in
# each prompt file. Total: 2,250.
# ---------------------------------------------------------------------------
TAXONOMIES: dict[str, dict] = {
    "bill_error_detection_provider_side": {
        "target": 250, "category": "bill_error_detection", "subcategory": "provider_side"},
    "bill_error_detection_payer_side": {
        "target": 250, "category": "bill_error_detection", "subcategory": "payer_side"},
    "bill_error_detection_encounter_verification": {
        "target": 150, "category": "bill_error_detection", "subcategory": "encounter_verification"},
    "cost_estimation_confidence_band": {
        "target": 150, "category": "cost_estimation", "subcategory": None},
    "coverage_connection_manual_extraction": {
        "target": 150, "category": "coverage_connection_fhir", "subcategory": "manual_extraction"},
    "coverage_connection_graceful_degradation": {
        "target": 150, "category": "coverage_connection_fhir", "subcategory": "graceful_degradation"},
    "negotiation_strategy_framework_selection": {
        "target": 150, "category": "negotiation_strategy", "subcategory": None},
    "lead_planner_thinking_loop": {
        "target": 200, "category": "lead_planner", "subcategory": None},
    "math_person_three_number_audit": {
        "target": 200, "category": "math_person", "subcategory": None},
    "voice_tier_a_factual": {
        "target": 150, "category": "tier_a_factual", "subcategory": None},
    "voice_tier_b_legal_citation": {
        "target": 200, "category": "tier_b_legal", "subcategory": None},
    "refusal_correctness": {
        "target": 250, "category": "refusal_correctness", "subcategory": None},
}

# Approximate Opus 4.7 token economics for the budget guard. These are
# placeholders — confirm against live pricing before a full run.
# TODO(brock/eng): replace with current Opus 4.7 per-token rates.
USD_PER_INPUT_TOKEN = 15.0 / 1_000_000
USD_PER_OUTPUT_TOKEN = 75.0 / 1_000_000
EST_INPUT_TOKENS_PER_BATCH = 1800   # shared prompt (cached after first call)
EST_OUTPUT_TOKENS_PER_CASE = 500


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------
def load_prompt(taxonomy: str) -> str:
    """
    Return the Opus 4.7 generation prompt for ``taxonomy``.

    Each prompt file has the meta-prompt in the first fenced code block under
    the "## Generation prompt for Opus 4.7" heading. We extract that block so
    the markdown prose around it (What this generates / V1-Lite note) is not
    sent to the model.
    """
    prompt_file = PROMPTS_DIR / f"{taxonomy}.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    content = prompt_file.read_text()
    block = _extract_generation_block(content)
    if block is None:
        raise ValueError(
            f"Could not find a fenced generation block under "
            f"'## Generation prompt for Opus 4.7' in {prompt_file}"
        )
    if "<N>" not in block:
        raise ValueError(f"Prompt {prompt_file} is missing the <N> count placeholder")
    return block


def _extract_generation_block(markdown: str) -> str | None:
    """
    Pull the contents of the first ``` fenced block that follows the
    "## Generation prompt for Opus 4.7" heading. Returns None if not found.
    """
    heading = re.search(r"^##\s+Generation prompt for Opus 4\.7\s*$", markdown, re.MULTILINE)
    if not heading:
        return None
    after = markdown[heading.end():]
    # First fenced block after the heading: ```[lang]\n ... \n```
    fence = re.search(r"```[^\n]*\n(.*?)\n```", after, re.DOTALL)
    if not fence:
        return None
    return fence.group(1).strip()


def load_schema() -> dict:
    """Load the golden-example JSON schema (shared by golden + synthetic cases)."""
    return json.loads(SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# API client — TODO(brock/eng)
# ---------------------------------------------------------------------------
def build_client():
    """Reuse the RUNTIME's single Claude client factory (CO-18 / DL-79) — share, don't fork.

    The runtime factory (`app.agents.runner._client`) picks Foundry (managed identity — the BAA
    path, no API key) → LiteLLM proxy → Anthropic-direct from the runtime config, so generation
    routes exactly like production. It returns an ASYNC client; we wrap it in a tiny SYNC facade so
    this script's synchronous `call_model` keeps working unchanged (`.messages.create(...)` ->
    `response.content[0].text`).

    Requires the runtime importable (its deps installed) — a live generation runs in the runtime
    env, e.g. `cd runtime && uv run python ../intelligence-layer/evals/synthetic/...`. Offline /
    --dry-run never calls this. Generation stays behind the explicit opt-in (not --dry-run + a
    configured client path).
    """
    import asyncio
    import pathlib
    import sys

    runtime = pathlib.Path(__file__).resolve().parents[3] / "runtime"
    if str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))
    from app.agents.runner import _client  # runtime Foundry→proxy→direct factory (async)

    async_client = _client()

    class _SyncMessages:
        def create(self, **kw):
            return asyncio.run(async_client.messages.create(**kw))

    class _SyncClient:
        messages = _SyncMessages()

    return _SyncClient()


def call_model(client, prompt: str) -> str:
    """Single generation call. Returns the raw text of the model's reply."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_PER_REQUEST,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Output parsing + validation
# ---------------------------------------------------------------------------
def parse_json_array(text: str) -> list[dict]:
    """Extract a JSON array from a model reply, tolerating markdown fences."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):]
    elif text.startswith("```"):
        text = text[len("```"):]
    if text.endswith("```"):
        text = text[: -len("```")]
    text = text.strip()

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON array of cases, got a single object")
    return parsed


def validate_case(case: dict, schema: dict, spec: dict) -> list[str]:
    """
    Validate one generated case. Returns a list of problem strings (empty = OK).

    Checks: (1) JSON Schema conformance, (2) the case carries the taxonomy's
    expected ``category``, (3) ``subcategory`` matches when the taxonomy
    declares one (soft — recorded as a problem so spot-checking can catch
    drift, since the prompt is responsible for setting it).
    """
    import jsonschema  # lazy: only needed on a live run

    problems: list[str] = []
    try:
        jsonschema.validate(case, schema)
    except jsonschema.ValidationError as exc:
        problems.append(f"schema: {exc.message}")
        return problems  # no point checking fields on a schema-invalid case

    expected_cat = spec["category"]
    if case.get("category") != expected_cat:
        problems.append(f"category: expected '{expected_cat}', got '{case.get('category')}'")

    expected_sub = spec.get("subcategory")
    if expected_sub and case.get("subcategory") not in (expected_sub, None):
        problems.append(
            f"subcategory: expected '{expected_sub}' (or omitted), got '{case.get('subcategory')}'"
        )
    return problems


# ---------------------------------------------------------------------------
# Budget guard
# ---------------------------------------------------------------------------
def estimate_cost_usd(target_count: int) -> float:
    """Rough pre-flight cost estimate for ``target_count`` cases."""
    batches = (target_count + BATCH_SIZE - 1) // BATCH_SIZE
    input_cost = batches * EST_INPUT_TOKENS_PER_BATCH * USD_PER_INPUT_TOKEN
    output_cost = target_count * EST_OUTPUT_TOKENS_PER_CASE * USD_PER_OUTPUT_TOKEN
    return input_cost + output_cost


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def generate_for_taxonomy(
    taxonomy: str,
    spec: dict,
    schema: dict,
    client,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Generate cases for one taxonomy. Returns (saved_count, failed_count)."""
    target_count = spec["target"]
    prompt = load_prompt(taxonomy)
    est = estimate_cost_usd(target_count)

    if dry_run:
        print(f"DRY RUN — {taxonomy}")
        print(f"  category={spec['category']} subcategory={spec['subcategory']}")
        print(f"  target={target_count}  est. cost ≈ ${est:0.2f}")
        print(f"  prompt preview (first 400 chars):\n    {prompt[:400].replace(chr(10), chr(10) + '    ')}...")
        return (0, 0)

    print(f"Generating {target_count} cases for {taxonomy} (est. ${est:0.2f})...")
    output_dir = CASES_DIR / taxonomy
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_count = 0
    failed_count = 0
    batches_needed = (target_count + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(batches_needed):
        batch_size = min(BATCH_SIZE, target_count - saved_count - failed_count)
        if batch_size <= 0:
            break
        batch_prompt = prompt.replace("<N>", str(batch_size))
        print(f"  Batch {batch_idx + 1}/{batches_needed} ({batch_size} cases)...")

        try:
            text = call_model(client, batch_prompt)
            cases = parse_json_array(text)
        except Exception as exc:  # noqa: BLE001 — log + keep going to next batch
            print(f"    ✗ Generation/parse error: {exc}")
            failed_count += batch_size
            continue

        for case_idx, case in enumerate(cases):
            problems = validate_case(case, schema, spec)
            if problems:
                for p in problems:
                    print(f"    ✗ {p}")
                failed_count += 1
                continue
            case_id = case.get("id", f"gold_synth_{taxonomy}_{batch_idx}_{case_idx:03d}")
            (output_dir / f"{case_id}.json").write_text(json.dumps(case, indent=2))
            saved_count += 1

    print(f"  → saved {saved_count}, failed {failed_count}")
    return (saved_count, failed_count)


# ---------------------------------------------------------------------------
# Spot-check workflow — TODO(brock/eng)
# ---------------------------------------------------------------------------
def spot_check(taxonomy: str, sample_pct: float = 0.10) -> None:
    """
    Manual-review gate before promoting a taxonomy's cases to the active suite.

    TODO(brock/eng): implement the 10% spot-check workflow. Intended flow:
      1. List ceil(sample_pct * saved) random files from cases/<taxonomy>/.
      2. For each, confirm:
           - it targets the intended failure mode (no scope creep)
           - expected_output_traits are concrete + LLM-judge-testable
           - it is not a near-duplicate of another case
           - no real PII / copyrighted payer text leaked in
      3. Record pass/fail counts back into the README progress table
         (Generated / Spot-checked columns).
      4. If quality is inconsistent, revise prompts/<taxonomy>.md and re-run.

    Until implemented, run the sampling by hand, e.g.:
        ls cases/<taxonomy>/ | sort -R | head -n 20
    """
    raise NotImplementedError(
        "spot_check() is a TODO (10% manual review). See README.md → Spot-check workflow."
    )


def update_readme(results: dict) -> None:
    """
    Refresh the README progress table with the run's counts.

    TODO(brock/eng): rewrite the 'Generated' column in README.md from
    ``results``. For now we just print a summary for manual entry.
    """
    print("\nRun summary  (" + datetime.now(timezone.utc).isoformat(timespec="seconds") + "):")
    total_saved = total_failed = 0
    for taxonomy, (saved, failed) in results.items():
        print(f"  {taxonomy:<46} saved={saved:<5} failed={failed}")
        total_saved += saved
        total_failed += failed
    print(f"  {'TOTAL':<46} saved={total_saved:<5} failed={total_failed}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--taxonomy", choices=sorted(TAXONOMIES), help="Generate for one taxonomy")
    group.add_argument("--all", action="store_true", help="Generate for all 12 taxonomies")
    group.add_argument("--list", action="store_true", help="List taxonomies and targets, then exit")
    parser.add_argument("--dry-run", action="store_true", help="Preview prompts + cost; no API calls")
    args = parser.parse_args()

    if args.list:
        total = 0
        for name, spec in TAXONOMIES.items():
            sub = spec["subcategory"] or "-"
            print(f"  {name:<46} cat={spec['category']:<24} sub={sub:<22} target={spec['target']}")
            total += spec["target"]
        print(f"  {'TOTAL':<46} {'':<29} {'':<26} target={total}")
        return

    schema = load_schema()

    # The client is only needed for a live run; dry-runs never touch the API.
    client = None
    if not args.dry_run:
        # A configured path is required (explicit opt-in): Foundry managed identity (no key),
        # a LiteLLM proxy, or an Anthropic key — mirroring the runtime factory build_client reuses.
        _foundry = os.getenv("USE_FOUNDRY", "").lower() in ("1", "true", "yes")
        if not (
            _foundry
            or "ANTHROPIC_API_KEY" in os.environ
            or "LITELLM_PROXY_KEY" in os.environ
        ):
            sys.exit(
                "No client path configured. Set USE_FOUNDRY=1 (managed identity), "
                "ANTHROPIC_API_KEY, or LiteLLM proxy creds — or use --dry-run to preview."
            )
        client = build_client()  # reuses the runtime Foundry/proxy/direct factory (share)

    if args.taxonomy:
        targets = {args.taxonomy: TAXONOMIES[args.taxonomy]}
    else:
        targets = dict(TAXONOMIES)

    # Pre-flight budget check across everything we're about to generate.
    if not args.dry_run:
        projected = sum(estimate_cost_usd(s["target"]) for s in targets.values())
        if projected > BUDGET_LIMIT_USD:
            sys.exit(
                f"Projected cost ${projected:0.2f} exceeds ANTHROPIC_BUDGET_LIMIT_USD "
                f"${BUDGET_LIMIT_USD:0.2f}. Raise the cap or generate one taxonomy at a time."
            )

    results: dict[str, tuple[int, int]] = {}
    for name, spec in targets.items():
        results[name] = generate_for_taxonomy(name, spec, schema, client, dry_run=args.dry_run)

    if not args.dry_run:
        update_readme(results)
        print(
            "\nNext: run the 10% spot-check before promoting these to the active "
            "Braintrust suite (see spot_check() / README.md)."
        )


if __name__ == "__main__":
    main()
