"""CO-17 — insurance-card extraction: map + merge + stub fallback."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.sources.insurance_card import (
    map_card_result,
    merge_card_sides,
    run_insurance_card_ocr,
)


@pytest.mark.asyncio
async def test_stub_fallback_when_ocr_off(monkeypatch):
    monkeypatch.setattr(get_settings(), "use_real_ocr", False)
    res = await run_insurance_card_ocr(b"\x89PNG fake image bytes")
    assert res["_stub"] is True
    assert res["doc_type"] == "prebuilt-healthInsuranceCard.us"
    assert res["fields"]["Insurer"]["value"] == "Blue Shield PPO"


def test_map_card_result_maps_into_insurance_info_shape():
    projected = {
        "fields": {
            "Insurer": {"value": "Aetna", "confidence": 0.95},
            "IdNumber.Number": {"value": "W123456789", "confidence": 0.9},
            "IdNumber.Prefix": {"value": "W", "confidence": 0.8},
            "Member.Name": {"value": "JOHN DOE", "confidence": 0.92},
            "Member.BirthDate": {"value": "1985-02-03", "confidence": 0.7},
            "PrescriptionInfo.RxBIN": {"value": "610502", "confidence": 0.85},
            "Copays": {"value": [{"Benefit": "PCP", "Amount": "$20"}], "confidence": 0.6},
            "UnmappedField": {"value": "ignored", "confidence": 0.99},
        }
    }
    mapped = map_card_result(projected)
    assert mapped["insurer"]["value"] == "Aetna"
    assert mapped["member_id"]["value"] == "W123456789"
    assert mapped["member_id_prefix"]["value"] == "W"
    assert mapped["member_name"]["value"] == "JOHN DOE"
    assert mapped["member_birth_date"]["value"] == "1985-02-03"
    assert mapped["rx_bin"]["value"] == "610502"
    assert mapped["copays"]["value"] == [{"Benefit": "PCP", "Amount": "$20"}]
    assert mapped["insurer"]["confidence"] == 0.95  # carried for the merge step
    assert "UnmappedField" not in mapped  # unmapped Azure field dropped


def test_map_skips_null_values():
    projected = {
        "fields": {
            "Insurer": {"value": None, "confidence": 0.9},
            "GroupNumber": {"value": "G1", "confidence": 0.8},
        }
    }
    mapped = map_card_result(projected)
    assert "insurer" not in mapped
    assert mapped["group_number"]["value"] == "G1"


def test_merge_prefers_higher_confidence_non_null():
    front = {
        "insurer": {"value": "Aetna (front)", "confidence": 0.6},
        "member_id": {"value": "FRONT123", "confidence": 0.95},
        "group_number": {"value": "GF", "confidence": 0.5},
    }
    back = {
        "insurer": {"value": "Aetna (back)", "confidence": 0.9},  # higher -> wins
        "rx_bin": {"value": "610502", "confidence": 0.88},  # back-only
        "group_number": {"value": "GB", "confidence": 0.4},  # lower -> loses
    }
    merged = merge_card_sides(front, back)
    assert merged["insurer"] == "Aetna (back)"  # higher confidence
    assert merged["member_id"] == "FRONT123"  # front-only
    assert merged["rx_bin"] == "610502"  # back-only
    assert merged["group_number"] == "GF"  # front had higher confidence
    assert all(not isinstance(v, dict) for v in merged.values())  # plain values


def test_merge_handles_single_side():
    front = map_card_result({"fields": {"Insurer": {"value": "Cigna", "confidence": 0.9}}})
    merged = merge_card_sides(front, {})  # only one side uploaded
    assert merged["insurer"] == "Cigna"
