"""error_detection_rules schema extension (Brock 38 §3, 2026-08-22) — the contract tests
that gate Tranche 2 landing cleanly.

Four rule_classes; applicable_codes required IFF provider_coding (both directions);
responsible_party required and plumbed rule → finding → API; payer-side rules retrievable
without any code filter; the JSON authoring schema and the programmatic validator can't
drift apart.
"""

from __future__ import annotations

import json
import pathlib
import uuid

import pytest
from httpx import AsyncClient

from app.agents.grounding import apply_finding_tier, derive_responsible_party
from app.knowledge.rule_schema import (
    PAYER_SIDE_RULE_TYPES,
    RULE_CLASSES,
    RULE_TYPES,
    validate_error_detection_rule,
)

_IL = pathlib.Path(__file__).resolve().parents[2] / "intelligence-layer" / "collections"

GOLDEN_PAYER_RULE = {
    "rule_id": "payer_deductible_misapplication_v1",
    "rule_type": "deductible_misapplication",
    "rule_class": "payer_adjudication",
    "responsible_party": "payer",
    "effective_date_start": "2024-01-01",
    "effective_date_end": None,
    "payer": None,
    "authority": "CMS",
    "narrative_text": (
        "When the EOB applies a deductible to a service after the member's accumulated "
        "deductible has already been met for the plan year, the member responsibility is "
        "overstated. Compare the applied-deductible amount against the year-to-date "
        "accumulator position; a charge exceeding the remaining deductible is an "
        "adjudication error and the claim should be reprocessed."
    ),
    "structured_rule_id": None,
}


def _coding_rule(**over) -> dict:
    base = {
        "rule_id": "ncci_ptp_x_y", "rule_type": "ncci_ptp", "rule_class": "provider_coding",
        "responsible_party": "provider", "applicable_codes": ["80053", "85025"],
        "effective_date_start": "2024-01-01", "effective_date_end": None,
        "authority": "CMS", "narrative_text": "…",
    }
    base.update(over)
    return base


# ── ingestion validator ─────────────────────────────────────────────────────────────
def test_all_four_rule_classes_accepted():
    for rc in RULE_CLASSES:
        payload = _coding_rule(rule_class=rc)
        if rc != "provider_coding":
            payload.pop("applicable_codes")
            payload["rule_type"] = "deductible_misapplication"
            payload["responsible_party"] = "payer"
        assert validate_error_detection_rule(payload) == [], rc


def test_provider_coding_without_codes_rejected_by_name():
    payload = _coding_rule()
    payload.pop("applicable_codes")
    assert "provider_coding_requires_applicable_codes" in validate_error_detection_rule(payload)


def test_payer_rule_with_codes_is_allowed_not_required():
    with_codes = dict(GOLDEN_PAYER_RULE, applicable_codes=["99213"])
    assert validate_error_detection_rule(with_codes) == []
    assert validate_error_detection_rule(dict(GOLDEN_PAYER_RULE)) == []


def test_unknown_class_and_type_rejected_with_named_reasons():
    reasons = validate_error_detection_rule(_coding_rule(rule_class="vibes"))
    assert "unknown_rule_class:vibes" in reasons
    reasons = validate_error_detection_rule(_coding_rule(rule_type="astrology"))
    assert "unknown_rule_type:astrology" in reasons
    reasons = validate_error_detection_rule(_coding_rule(responsible_party="the moon"))
    assert "unknown_responsible_party:the moon" in reasons


# ── the JSON authoring schema and this module can't drift ───────────────────────────
def test_json_schema_mirrors_the_python_contract():
    schema = json.loads((_IL / "schemas" / "error_detection_rules.json").read_text())
    props = schema["properties"]
    assert tuple(props["rule_class"]["enum"]) == RULE_CLASSES
    assert set(props["rule_type"]["enum"]) == set(RULE_TYPES)
    assert set(PAYER_SIDE_RULE_TYPES) <= set(props["rule_type"]["enum"])
    assert "applicable_codes" not in schema["required"]
    assert {"rule_class", "responsible_party"} <= set(schema["required"])
    # The conditional, enforced by the actual validator the seed path uses:
    from jsonschema import Draft7Validator

    v = Draft7Validator(schema)
    bad = _coding_rule()
    bad.pop("applicable_codes")
    assert any("applicable_codes" in e.message for e in v.iter_errors(bad))
    assert not list(v.iter_errors(dict(GOLDEN_PAYER_RULE)))  # payer rule, no codes → valid


def test_fixture_file_conforms_and_carries_the_backfill():
    from jsonschema import Draft7Validator

    schema = json.loads((_IL / "schemas" / "error_detection_rules.json").read_text())
    records = json.loads((_IL / "fixtures" / "error_detection_rules.json").read_text())["records"]
    v = Draft7Validator(schema)
    for r in records:
        assert not list(v.iter_errors(r)), r["rule_id"]
        assert validate_error_detection_rule(r) == [], r["rule_id"]
    # The noted exceptions: ACA preventive rules describe PAYER cost-sharing errors.
    aca = [r for r in records if r["rule_type"] == "aca_preventive"]
    assert aca and all(r["rule_class"] == "legal_protection" and r["responsible_party"] == "payer" for r in aca)
    assert any(r["rule_id"] == GOLDEN_PAYER_RULE["rule_id"] for r in records)


# ── retrieval: payer rules are found WITHOUT any code filter ────────────────────────
@pytest.mark.asyncio
async def test_golden_payer_rule_round_trips_without_code_filter(monkeypatch):
    from qdrant_client import models

    from app.knowledge import client as client_mod
    from app.knowledge import search as search_mod

    async def fake_embed(text: str, model: str, dim: int = 1024) -> list[float]:
        # Deterministic tiny vector; identical for ingest + query so cosine ≈ 1.
        return [1.0, 0.0, 0.0, 0.0]

    monkeypatch.setattr(search_mod, "embed", fake_embed)
    client = client_mod.get_client()
    name = "error_detection_rules"
    if await client.collection_exists(name):
        await client.delete_collection(name)
    await client.create_collection(
        name, vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE)
    )
    await client.upsert(
        name,
        points=[models.PointStruct(id=1, vector=[1.0, 0.0, 0.0, 0.0], payload=GOLDEN_PAYER_RULE)],
    )
    try:
        hits = await search_mod.search(name, "EOB applied deductible after it was met")
        assert hits and hits[0].payload["rule_id"] == GOLDEN_PAYER_RULE["rule_id"]
        assert "applicable_codes" not in hits[0].payload  # nothing filtered it out for lacking codes
        scoped = await search_mod.search(
            name, "deductible misapplication", filters={"rule_class": "payer_adjudication"}
        )
        assert scoped and scoped[0].payload["responsible_party"] == "payer"
    finally:
        await client.delete_collection(name)


# ── attribution: rule → finding → API ───────────────────────────────────────────────
def _finding(**kw):
    from app.agents.grounding import finding_source_line
    from app.schemas.case_file import FindingOut

    base = dict(
        finding_id="f1", finding_type="payer_side", category="deductible_misapplied",
        subagent_source="math_person", voice_tier="A", facts={},
    )
    base.update(kw)
    f = FindingOut(**base)
    f.source_line, f.has_source = finding_source_line(f)
    return f


def test_responsible_party_derivation_rule_value_wins():
    # The rule's responsible_party, carried via facts (per the tool description), wins.
    f = apply_finding_tier(_finding(finding_type="provider_side",
                                    facts={"responsible_party": "payer"}))
    assert f.responsible_party == "payer"
    # Without it, the finding_type maps; junk values are ignored, not honored.
    assert derive_responsible_party(_finding()) == "payer"
    assert derive_responsible_party(_finding(finding_type="provider_side")) == "provider"
    assert derive_responsible_party(_finding(finding_type="encounter_mismatch")) == "either"
    assert derive_responsible_party(_finding(facts={"responsible_party": "aliens"})) == "payer"


@pytest.mark.asyncio
async def test_finding_carries_responsible_party_through_the_api(client: AsyncClient):
    from sqlalchemy import select

    from app.db.base import AsyncSessionLocal
    from app.db.models.case_files import CaseFile
    from app.db.models.findings import Finding

    up = await client.post(
        "/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 x", "application/pdf")}
    )
    case_id = up.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        s.add(Finding(
            case_file_id=uuid.UUID(case_id), finding_type="payer_side",
            category="deductible_misapplied", subagent_source="math_person", voice_tier="A",
            facts={"responsible_party": "payer", "gap": 240.0},
        ))
        await s.commit()
    try:
        r = await client.get(f"/v1/audit/{case_id}")
        assert r.status_code == 200, r.text
        f = r.json()["findings"][0]
        assert f["responsible_party"] == "payer"
    finally:
        async with AsyncSessionLocal() as s:
            from sqlalchemy import delete

            await s.execute(delete(Finding).where(Finding.case_file_id == uuid.UUID(case_id)))
            row = (await s.execute(
                select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id))
            )).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
            await s.commit()
