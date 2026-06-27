"""Insurance-card extraction (CO-17) — Azure DI prebuilt-healthInsuranceCard.us.

``run_insurance_card_ocr`` runs the dedicated health-insurance-card model (a DIFFERENT
prebuilt model than the prebuilt-document OCR in extraction.py) on card image bytes,
with a realistic stub fallback when use_real_ocr is off or DI creds are missing.

``map_card_result`` maps the projected Azure fields into the insurance_info column
shape (pure); ``merge_card_sides`` reconciles the front + back, preferring the
higher-confidence non-null value per field.

NOTE: the Azure field-name mapping (Member.*, IdNumber.*, PrescriptionInfo.*, …) is
best-effort against the documented prebuilt-healthInsuranceCard.us schema; validate it
against a real card scan. The project → map → merge structure is what's locked + tested.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import get_settings
from app.sources.extraction import _di_client

log = structlog.get_logger(__name__)

_CARD_MODEL = "prebuilt-healthInsuranceCard.us"

# insurance_info column  ->  projected (dotted) Azure field path.
_FIELD_MAP: dict[str, str] = {
    "insurer": "Insurer",
    "member_name": "Member.Name",
    "member_birth_date": "Member.BirthDate",
    "member_gender": "Member.Gender",
    "member_employer": "Member.Employer",
    "member_id_suffix": "Member.IdNumberSuffix",
    "member_id": "IdNumber.Number",
    "member_id_prefix": "IdNumber.Prefix",
    "group_number": "GroupNumber",
    "plan_name": "Plan.Name",
    "plan_number": "Plan.Number",
    "plan_type": "Plan.Type",
    "payer_id": "Payer.Id",
    "payer_phone": "Payer.PhoneNumber",
    "payer_address": "Payer.Address",
    "effective_date": "EffectiveDate",
    "rx_bin": "PrescriptionInfo.RxBIN",
    "rx_pcn": "PrescriptionInfo.RxPCN",
    "rx_grp": "PrescriptionInfo.RxGRP",
    "rx_id": "PrescriptionInfo.RxId",
    "rx_plan": "PrescriptionInfo.RxPlan",
    "pbm": "Pbm",
    "medicare_medicaid_id": "MedicareMedicaidInfo.Id",
    "medicare_part_a_date": "MedicareMedicaidInfo.PartADate",
    "medicare_part_b_date": "MedicareMedicaidInfo.PartBDate",
}
# Date-typed insurance_info columns (the route parses these to a date on write).
DATE_FIELDS = frozenset(
    {"member_birth_date", "effective_date", "medicare_part_a_date", "medicare_part_b_date"}
)


# --- OCR --------------------------------------------------------------------
async def run_insurance_card_ocr(image_bytes: bytes) -> dict[str, Any]:
    """Project a card image into {doc_type, _stub, fields{path: {value, confidence}}}.
    Azure prebuilt-healthInsuranceCard.us when real OCR is on + creds present; a
    realistic stub otherwise. Never raises on extraction — callers treat a thin/empty
    projection as a soft failure."""
    settings = get_settings()
    if not settings.use_real_ocr:
        return _stub_card_result()
    client = _di_client()
    if client is None:
        log.warning("insurance_card.di_credentials_missing")
        return _stub_card_result()
    try:
        poller = client.begin_analyze_document(_CARD_MODEL, body=image_bytes)
        result = poller.result()
        doc = result.documents[0] if getattr(result, "documents", None) else None
        return _project_azure_card(doc)
    except Exception as exc:  # noqa: BLE001 — a bad scan is a soft failure, never a 500
        log.warning("insurance_card.ocr_failed", error=str(exc))
        return {"doc_type": _CARD_MODEL, "_stub": False, "fields": {}, "error": str(exc)}


def _field_value(field: Any) -> Any:
    """Best value out of an Azure DocumentField, falling back to .content."""
    for attr in ("value_string", "value_phone_number", "value_country_region"):
        v = getattr(field, attr, None)
        if v is not None:
            return v
    d = getattr(field, "value_date", None)
    if d is not None:
        return d.isoformat() if hasattr(d, "isoformat") else str(d)
    n = getattr(field, "value_number", None)
    if n is not None:
        return n
    return getattr(field, "content", None)


def _flatten_fields(fields: dict, prefix: str, out: dict) -> None:
    for name, field in (fields or {}).items():
        path = f"{prefix}.{name}" if prefix else name
        obj = getattr(field, "value_object", None)
        arr = getattr(field, "value_array", None)
        conf = getattr(field, "confidence", 0.0) or 0.0
        if obj:
            _flatten_fields(obj, path, out)
        elif arr is not None:
            items: list = []
            for el in arr:
                el_obj = getattr(el, "value_object", None)
                items.append(
                    {k: _field_value(v) for k, v in el_obj.items()} if el_obj else _field_value(el)
                )
            out[path] = {"value": items, "confidence": conf}
        else:
            out[path] = {"value": _field_value(field), "confidence": conf}


def _project_azure_card(doc: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if doc is not None:
        _flatten_fields(getattr(doc, "fields", {}) or {}, "", fields)
    return {"doc_type": _CARD_MODEL, "_stub": False, "fields": fields}


def _stub_card_result() -> dict[str, Any]:
    """Deterministic, realistic FRONT-of-card projection for dev/CI/tests."""
    return {
        "doc_type": _CARD_MODEL,
        "_stub": True,
        "fields": {
            "Insurer": {"value": "Blue Shield PPO", "confidence": 0.97},
            "Member.Name": {"value": "JANE Q PUBLIC", "confidence": 0.94},
            "Member.BirthDate": {"value": "1990-04-15", "confidence": 0.88},
            "IdNumber.Number": {"value": "XEG123456789", "confidence": 0.96},
            "IdNumber.Prefix": {"value": "XEG", "confidence": 0.9},
            "GroupNumber": {"value": "GRP0099", "confidence": 0.93},
            "Plan.Name": {"value": "PPO Gold", "confidence": 0.85},
            "PrescriptionInfo.RxBIN": {"value": "003858", "confidence": 0.9},
            "PrescriptionInfo.RxPCN": {"value": "A4", "confidence": 0.88},
            "Copays": {
                "value": [
                    {"Benefit": "Office Visit", "Amount": "$25"},
                    {"Benefit": "Emergency Room", "Amount": "$300"},
                ],
                "confidence": 0.8,
            },
            "Payer.PhoneNumber": {"value": "1-800-555-1212", "confidence": 0.9},
        },
    }


# --- map + merge (pure) -----------------------------------------------------
def map_card_result(projected: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map a projected card result into {insurance_info_column: {value, confidence}}.
    Only fields actually present (non-null) are emitted. Pure."""
    fields = projected.get("fields", {}) or {}
    out: dict[str, dict[str, Any]] = {}
    for col, path in _FIELD_MAP.items():
        f = fields.get(path)
        if f and f.get("value") is not None:
            out[col] = {"value": f["value"], "confidence": float(f.get("confidence") or 0.0)}
    copays = fields.get("Copays")
    if copays and copays.get("value"):
        out["copays"] = {
            "value": copays["value"],
            "confidence": float(copays.get("confidence") or 0.0),
        }
    return out


def _pick(a: dict | None, b: dict | None) -> dict | None:
    """Higher-confidence non-null of two {value, confidence} entries."""
    if a is None:
        return b
    if b is None:
        return a
    return a if a.get("confidence", 0.0) >= b.get("confidence", 0.0) else b


def merge_card_sides(
    front: dict[str, dict[str, Any]], back: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Reconcile two mapped sides into plain insurance_info column values, preferring
    the higher-confidence non-null per field. Returns {column: value}."""
    merged: dict[str, Any] = {}
    for key in set(front) | set(back):
        chosen = _pick(front.get(key), back.get(key))
        if chosen is not None and chosen.get("value") is not None:
            merged[key] = chosen["value"]
    return merged
