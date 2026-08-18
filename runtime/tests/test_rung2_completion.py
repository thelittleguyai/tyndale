"""Rung-2 completion — the SBC gate removed (2026-08-18).

Phil's ruling on the first full dev sweep: an audit COMPLETES at the achievable rung.
The load-bearing properties:

  1. The model is bounded arithmetic — never below 0, never above the anchor, and the
     range collapses toward stated coverage values (more documents → tighter truth).
  2. The engine anchors ONLY on document-stated money (EOB allowed > EOB billed > line
     total) and returns None with no anchor — {0,0,0}-as-complete stays impossible
     (CO-15 T2.3), and the true needs_documents case (no itemized detail AND no EOB)
     still parks honestly.
  3. Anchors no document stated stay None — a bill-only case shows no invented EOB figure.
  4. The X3 qualifier follows the tier: none at tier 0 (hedging a complete figure is its
     own X3 failure), point at tier 1, range at tier ≥2 — naming a real input.
"""

from types import SimpleNamespace

from app.agents.orchestrator import _rung2_three_numbers
from app.agents.thread_bridge import _x3_qualifier
from app.sources.cost_share_model import member_cost_share, rung2_range
from app.sources.extraction import eob_money_figures

EOB_TEXT = (
    "ACME HEALTH EXPLANATION OF BENEFITS\nCLAIM: E2E-CLM-777\n"
    "BILLED $3,700.00\nALLOWED $1,800.00\nPATIENT RESPONSIBILITY $360.00"
)


def _case(status="audit_running", line_items=None, documents=None, coverage=None):
    return SimpleNamespace(
        status=status,
        line_items=line_items or [],
        documents=documents or [],
        coverage=coverage,
    )


def _eob_doc(text=EOB_TEXT):
    return {"document_type": "eob", "extraction_status": "extracted", "ocr_text": text}


# --- 1 · the model is bounded arithmetic -------------------------------------------------
def test_member_cost_share_bounds_and_shape():
    # Deductible swallows everything when it exceeds the anchor.
    assert member_cost_share(900, 8000, 0.2) == 900.0
    # Deductible met: pure coinsurance.
    assert member_cost_share(1000, 0, 0.2) == 200.0
    # Split: 500 deductible + 20% of the remaining 500.
    assert member_cost_share(1000, 500, 0.2) == 600.0
    # Never negative, never above the anchor.
    assert member_cost_share(0, 500, 0.2) == 0.0
    assert member_cost_share(100, 50, 5.0) == 100.0


def test_range_tightens_as_coverage_is_stated():
    wide = rung2_range(1800.0, None, anchor_kind="allowed")
    stated = rung2_range(
        1800.0,
        {"deductible_amount": 500.0, "oop_max_amount": 6000.0, "coinsurance_percent": 0.2},
        anchor_kind="allowed",
    )
    assert wide.high - wide.low > stated.high - stated.low
    assert wide.missing_inputs and not stated.missing_inputs
    # Stated terms: the only spread left is deductible-met vs not.
    assert stated.low == member_cost_share(1800, 0, 0.2)
    assert stated.high == member_cost_share(1800, 500, 0.2)


def test_range_is_always_inside_the_bounds():
    r = rung2_range(900.0, None, anchor_kind="billed")
    assert 0.0 <= r.low <= r.base <= r.high <= 900.0


# --- 2/3 · document-grounded anchors only ------------------------------------------------
def test_anchor_precedence_allowed_over_billed_over_lines():
    case = _case(
        line_items=[{"billed_amount": 3700.0}],
        documents=[_eob_doc()],
    )
    out = _rung2_three_numbers(case)
    assert out is not None
    assert out["anchor_kind"] == "allowed"  # $1,800 — the true cost-share base
    assert out["provider_billed"] == 3700.0  # the itemized lines, not the EOB restatement
    assert out["eob_member_responsibility"] == 360.0
    assert 0.0 <= out["tyndale_computed"] <= 1800.0


# ── the priors gate (Phil, 2026-08-18): placeholder priors suppress the visible range ─────
def test_placeholder_priors_suppress_the_visible_range():
    """Every prior is placeholder-flagged today, so a range built on them must not render —
    the figure ships point-form until Brock's researched values land."""
    out = _rung2_three_numbers(_case(documents=[_eob_doc()]))
    assert out is not None
    assert out["tyndale_computed_low"] is None and out["tyndale_computed_high"] is None
    assert 0.0 <= out["tyndale_computed"] <= 1800.0  # the point value still ships


def test_real_flagged_priors_activate_the_range(monkeypatch):
    """Brock's data drop is the activation switch: flipping placeholder=False per entry
    turns the range on with zero code change."""
    from app.sources import cost_share_model
    from app.sources.missing_data_priors import InputPrior

    real = {
        "deductible_amount": InputPrior(
            low=500.0, base=2000.0, high=8000.0, unit="usd",
            source="brock_2026", placeholder=False,
        ),
        "coinsurance_percent": InputPrior(
            low=0.10, base=0.20, high=0.40, unit="fraction",
            source="brock_2026", placeholder=False,
        ),
    }
    monkeypatch.setattr(cost_share_model, "MISSING_DATA_PRIORS", real)
    out = _rung2_three_numbers(_case(documents=[_eob_doc()]))
    assert out is not None
    assert out["tyndale_computed_low"] is not None
    assert 0.0 <= out["tyndale_computed_low"] <= out["tyndale_computed_high"] <= 1800.0


def test_stated_coverage_never_counts_as_placeholder():
    """A range whose spread comes only from stated plan terms (deductible-met vs not)
    consumed no priors — it renders regardless of the placeholder table."""
    r = rung2_range(
        1800.0,
        {"deductible_amount": 500.0, "oop_max_amount": 6000.0, "coinsurance_percent": 0.2},
        anchor_kind="allowed",
    )
    assert r.placeholder_basis is False


def test_bill_only_completes_with_no_invented_eob_number():
    case = _case(line_items=[{"billed_amount": 1850.0}, {"billed_amount": 185.0}])
    out = _rung2_three_numbers(case)
    assert out is not None
    assert out["provider_billed"] == 2035.0
    assert out["eob_member_responsibility"] is None  # no EOB — no number to show
    assert out["anchor_kind"] == "billed"


def test_no_document_money_anywhere_stays_needs_documents():
    """The Beloit day-one shape: no itemized detail AND no EOB figures — rung-2 refuses,
    and the honest needs_documents terminal still applies."""
    assert _rung2_three_numbers(_case()) is None
    assert _rung2_three_numbers(None) is None
    # An EOB document whose text yields no dollars is not an anchor.
    case = _case(documents=[_eob_doc("EXPLANATION OF BENEFITS — figures illegible")])
    assert _rung2_three_numbers(case) is None


def test_eob_money_figures_reads_the_labels():
    figs = eob_money_figures(EOB_TEXT)
    assert figs == {
        "billed_amount": 3700.0,
        "allowed_amount": 1800.0,
        "patient_responsibility": 360.0,
    }


# --- 4 · the X3 qualifier follows the tier -----------------------------------------------
def _audit(low=None, high=None, computed=500.0):
    return SimpleNamespace(
        tyndale_computed=computed, tyndale_computed_low=low, tyndale_computed_high=high
    )


def _disclosure(tier, missing, chase=None):
    return SimpleNamespace(tier=tier, missing_inputs=missing, chase_inputs=chase or [])


def test_tier_zero_forbids_a_qualifier():
    assert _x3_qualifier(_audit(), _disclosure(0, [])) is None
    assert _x3_qualifier(_audit(), _disclosure(0, ["deductible_amount"])) is None


def test_tier_two_with_a_range_gets_the_range_form_naming_the_input():
    q = _x3_qualifier(
        _audit(low=90.0, high=900.0),
        _disclosure(2, ["deductible_amount"], chase=["deductible_amount"]),
    )
    assert q["form"] == "range" and q["same_unit"] is True
    assert q["names"] == ["deductible"]
    assert "until I see your deductible" in q["text"]
    assert "$90.00" in q["text"] and "$900.00" in q["text"]


def test_tier_one_gets_the_point_form():
    q = _x3_qualifier(_audit(), _disclosure(1, ["coinsurance_percent"]))
    assert q["form"] == "point"
    assert q["names"] == ["coinsurance rate"]
    assert "estimated" not in q["text"].lower()  # generic qualifiers fail X3
