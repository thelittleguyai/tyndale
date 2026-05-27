# Task 29 — Build the synthetic generation runner

**Phase:** 6 · Eval test data
**Who:** Brock + Claude Code
**Estimated time:** 1.5 hours
**Depends on:** Task 28

## What this task does

Creates the Python script that executes the 12 generation prompts against Opus 4.7 and produces the synthetic adversarial cases. Brock runs this once Tasks 26-28 are done; the engineers extend it as needed for re-runs.

## Prompt to paste into Claude Code

```
Create the file `evals/synthetic/run_generation.py` and supporting files.

The runner:
1. Reads each prompt file from generation_prompts/
2. Executes the prompt against Opus 4.7 via Anthropic API
3. Parses the JSON array output
4. Validates each case against evals/golden/schema.json
5. Saves valid cases to evals/synthetic/cases/<taxonomy>/
6. Reports counts and validation failures
7. Updates evals/synthetic/README.md progress table

Use this structure for run_generation.py:

```python
"""
Synthetic adversarial case generator for Tyndale.

USAGE:
    python run_generation.py --taxonomy <name>    # generate one taxonomy
    python run_generation.py --all                 # generate all 12
    python run_generation.py --taxonomy <name> --dry-run  # preview

Requires:
    ANTHROPIC_API_KEY environment variable
    pip install anthropic jsonschema

Cost: roughly $40-80 to generate the full 2,000-case V1 set
(Opus 4.7 input + output tokens × 12 prompts × 200 cases each).
Set ANTHROPIC_BUDGET_LIMIT_USD to hard-cap spending.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import jsonschema

ROOT = Path(__file__).parent
PROMPTS_DIR = ROOT / "generation_prompts"
CASES_DIR = ROOT / "cases"
SCHEMA_PATH = ROOT.parent / "golden" / "schema.json"

MODEL = "claude-opus-4-7"
MAX_TOKENS_PER_REQUEST = 16000  # Opus 4.7 output budget per generation call
BUDGET_LIMIT_USD = float(os.getenv("ANTHROPIC_BUDGET_LIMIT_USD", "100.0"))

# Taxonomies and their target counts (must match the README progress table)
TAXONOMIES = {
    "citation_faithfulness": 200,
    "hallucinated_numbers": 200,
    "policy_version_drift": 150,
    "voice_tier_violations": 250,
    "refusal_correctness": 250,
    "prompt_injection": 200,
    "anticipation_failures": 150,
    "effort_scaling_violations": 100,
    "premature_closure": 150,
    "options_dumping": 100,
    "citation_format_drift": 100,
    "cross_session_phi_leak": 100,
}


def load_prompt(taxonomy: str) -> str:
    """Load the Opus 4.7 generation prompt for a taxonomy."""
    prompt_file = PROMPTS_DIR / f"{taxonomy}.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    content = prompt_file.read_text()
    # Extract the prompt block between ``` markers labeled "Generation prompt for Opus 4.7"
    # TODO: implement extraction logic — for V1, store the prompt in a
    # separate .txt file alongside the .md for simpler parsing
    return content


def load_schema() -> dict:
    """Load the golden example JSON schema."""
    return json.loads(SCHEMA_PATH.read_text())


def generate_for_taxonomy(
    taxonomy: str,
    target_count: int,
    schema: dict,
    client: anthropic.Anthropic,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Generate cases for one taxonomy. Returns (saved_count, failed_count).
    """
    prompt = load_prompt(taxonomy)

    if dry_run:
        print(f"DRY RUN — would generate {target_count} cases for {taxonomy}")
        print(f"Prompt preview (first 500 chars):\n{prompt[:500]}...")
        return (0, 0)

    print(f"Generating {target_count} cases for {taxonomy}...")

    # Generate in batches to stay within max_tokens per request.
    # Each case is ~500 tokens; batch size of 25 fits comfortably.
    BATCH_SIZE = 25
    batches_needed = (target_count + BATCH_SIZE - 1) // BATCH_SIZE
    saved_count = 0
    failed_count = 0

    output_dir = CASES_DIR / taxonomy
    output_dir.mkdir(parents=True, exist_ok=True)

    for batch_idx in range(batches_needed):
        batch_size = min(BATCH_SIZE, target_count - saved_count)
        batch_prompt = prompt.replace("<N>", str(batch_size))

        print(f"  Batch {batch_idx + 1}/{batches_needed} ({batch_size} cases)...")

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS_PER_REQUEST,
                messages=[{"role": "user", "content": batch_prompt}],
            )

            # Parse the JSON array from the response
            text = response.content[0].text
            cases = parse_json_array(text)

            # Validate each case and save
            for case_idx, case in enumerate(cases):
                try:
                    jsonschema.validate(case, schema)
                    # Save as individual file
                    case_id = case.get("id", f"synth_{taxonomy}_{batch_idx}_{case_idx:03d}")
                    case_path = output_dir / f"{case_id}.json"
                    case_path.write_text(json.dumps(case, indent=2))
                    saved_count += 1
                except jsonschema.ValidationError as e:
                    print(f"    ✗ Validation failed: {e.message}")
                    failed_count += 1

        except Exception as e:
            print(f"    ✗ Generation error: {e}")
            failed_count += batch_size

    print(f"  Saved {saved_count}, failed {failed_count}")
    return (saved_count, failed_count)


def parse_json_array(text: str) -> list[dict]:
    """Extract JSON array from model response, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Parse
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array, got object")
    return parsed


def update_readme(results: dict):
    """Update the README progress table with the new counts."""
    readme_path = ROOT / "README.md"
    # TODO: implement table update — for V1, just print results and let
    # the user update manually
    print("\nResults summary:")
    for taxonomy, (saved, failed) in results.items():
        print(f"  {taxonomy}: {saved} saved, {failed} failed")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--taxonomy", help="Generate for one taxonomy")
    group.add_argument("--all", action="store_true", help="Generate all taxonomies")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ:
        sys.exit("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic()
    schema = load_schema()

    if args.taxonomy:
        if args.taxonomy not in TAXONOMIES:
            sys.exit(f"Unknown taxonomy: {args.taxonomy}. Valid: {list(TAXONOMIES.keys())}")
        target_count = TAXONOMIES[args.taxonomy]
        saved, failed = generate_for_taxonomy(
            args.taxonomy, target_count, schema, client, dry_run=args.dry_run
        )
        results = {args.taxonomy: (saved, failed)}
    else:
        results = {}
        for taxonomy, target_count in TAXONOMIES.items():
            results[taxonomy] = generate_for_taxonomy(
                taxonomy, target_count, schema, client, dry_run=args.dry_run
            )

    update_readme(results)


if __name__ == "__main__":
    main()
```

Also create `evals/synthetic/requirements.txt`:

```
anthropic>=0.40.0
jsonschema>=4.0.0
```

And `evals/synthetic/cases/.gitkeep` (empty file) so the directory
exists in git before generation runs.

And add usage notes to `evals/synthetic/README.md`:

## How to run

```bash
# Install dependencies
pip install -r requirements.txt

# Set credentials
export ANTHROPIC_API_KEY=your_key_here
export ANTHROPIC_BUDGET_LIMIT_USD=100  # hard cap

# Dry run first to see what would happen
python run_generation.py --taxonomy citation_faithfulness --dry-run

# Generate one taxonomy
python run_generation.py --taxonomy citation_faithfulness

# Generate all taxonomies
python run_generation.py --all
```

## Cost expectations

Each case is ~500 tokens output + ~1500 tokens input (the generation
prompt). At Opus 4.7 rates, that's roughly $0.03-0.05 per case.

Full V1 generation (~2,000 cases) costs $60-100. Hard-cap with
ANTHROPIC_BUDGET_LIMIT_USD.

## Spot-checking

After generation, Brock spot-checks 10% of cases per taxonomy. Use:

```bash
# List 20 random cases for review
ls evals/synthetic/cases/<taxonomy>/ | shuf -n 20
```

For each spot-checked case, verify:
- The case targets the intended failure mode
- The expected_output_traits are testable
- The case isn't a near-duplicate of another case
- No PII or copyrighted content was generated

If quality is inconsistent, revise the generation prompt and re-run
the taxonomy.

Commit with message "Add synthetic case generation runner".
```

## Done when

- `evals/synthetic/run_generation.py` exists and is syntactically valid Python
- `requirements.txt` exists
- README has the usage notes
- Git log shows the commit

## Next task

[Task 30 — Project README](30_readme.md)
