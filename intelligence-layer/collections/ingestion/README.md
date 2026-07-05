# `laws_regulations` ingestion — authoring guide (DL-81 / DL-84)

This directory is the hand-off point for the **50-state + DC surprise-billing seed** and any
other `laws_regulations` content. Author records as JSONL (one JSON object per line) matching
`../schemas/laws_regulations.json`, validate locally, then load them into Qdrant.

> **Content ownership.** The *schema* and *loader* are the engineering team's. The *legal
> content* — statute text, the X6 classification of each authority, `checkable_facts`,
> `defeaters`, and `scope` — is Brock's / counsel's (TODO(brock-content)). This guide shows the
> shape and the mechanics, not the legal calls.

## The record shape

Every record MUST carry all required fields. See the schema for exact types; the fields that
are new in the X6 revision (DL-84) and easy to get wrong:

| Field | What it is |
|---|---|
| `x6_classification` | `CATEGORICAL` — the rule applies flatly once the authority is on point (e.g. ERISA's 180-day appeal window). `CONDITIONAL` — the protection turns on facts about the encounter. |
| `checkable_facts` | The encounter facts that must hold for a **CONDITIONAL** protection to apply (e.g. `"service was non-emergency"`, `"out-of-network provider at an in-network facility"`). **Required non-empty when `CONDITIONAL`**; leave `[]` for `CATEGORICAL`. |
| `defeaters` | Facts that defeat an otherwise-applicable protection (e.g. `"valid NSA notice-and-consent obtained"`, `"plan is ERISA self-funded so state law is preempted"`). May be `[]`. |
| `scope.plan_types_bound` | Which coverage populations this authority actually binds. **State** surprise-billing statutes typically bind `["state_regulated_commercial"]` and **NOT** `erisa_self_funded` — that preemption boundary is the whole reason this field exists. |
| `scope.ground_ambulance_covered` | Whether this authority's balance-billing protection reaches **ground ambulance**. For a surprise-billing record this MUST be an explicit `true`/`false` — the seed gate rejects `null`. Use `null` only on records where ground ambulance is genuinely not applicable (e.g. an appeals-deadline statute). |
| `as_of` | The date the classification / statute snapshot was verified by the reviewer. Surfaced in citations. |

### Affirmative "no law here" records (DL-81)

When a jurisdiction has **no** protection in an area, author an affirmative record rather than
leaving a silent gap — the absence must be *retrievable* so Tyndale can tell the user "neither
federal nor state law prohibits this bill here." Set `document_type: "no_state_law"` and
`statute`/`section` to `null` (allowed for that type only). The ground-ambulance gap is the
canonical case (ground ambulance is excluded from the federal No Surprises Act).

## One record per jurisdiction is the launch gate

`runtime/scripts/check_state_seed.py` requires **51 jurisdictions** (`state_AL` … `state_WY`
plus `state_DC`), each schema-valid, each with an `x6_classification` and a **non-null**
`scope.ground_ambulance_covered`, and each self-retrieving on a balance-billing query. NSA /
state-balance-billing checks do **not** ship (`ENABLE_NSA_CHECKS` stays `false`) until it is
green — see DL-81.

## Validate before loading

```bash
# 1. Schema-validate every line of your JSONL against the collection schema.
#    jsonschema lives in the runtime venv, so run it through uv from the repo root:
JSONL=intelligence-layer/collections/ingestion/laws_regulations.example.jsonl \
uv run --project runtime python - <<'PY'
import json, os
from jsonschema import Draft7Validator
schema = json.load(open("intelligence-layer/collections/schemas/laws_regulations.json"))
v = Draft7Validator(schema)
bad = 0
for i, line in enumerate(open(os.environ["JSONL"]), 1):
    line = line.strip()
    if not line:
        continue
    rec = json.loads(line)
    errs = sorted(v.iter_errors(rec), key=lambda e: list(e.path))
    if errs:
        bad += 1
        print(f"line {i} [{rec.get('chunk_id','?')}]: {errs[0].message}")
print("INVALID" if bad else "all lines valid")
PY

# 2. After loading into a live Qdrant, run the 51-jurisdiction launch gate:
cd runtime && uv run python scripts/check_state_seed.py            # full gate (needs Voyage embeddings for the retrieval smoke)
cd runtime && uv run python scripts/check_state_seed.py --no-retrieval   # structural checks only
```

`laws_regulations.example.jsonl` in this directory is a two-line worked example — one real
CONDITIONAL state statute and one `no_state_law` record — that passes step 1. Copy its shape.
