"""Coverage-regime detection (Sprint B, DL-82).

Pure, deterministic classifier over cheap signals — insurance-card extraction fields,
document classification, member-ID patterns, and payer branding. It maps to one of the
seven coverage regimes or returns ``ambiguous``. **Detection is never guessed**: thin or
conflicting evidence returns ``ambiguous`` (with a best-guess ``candidate`` for the confirm
screen to preselect), and the intake verification ladder asks the user rather than
silently defaulting to commercial.

This module intentionally does NOT import the DB model — it consumes a plain
``RegimeSignals`` contract so it stays pure and table-testable. The adapter that builds
``RegimeSignals`` from ``insurance_info`` + document classification lives alongside the
intake wiring (``signals_from_coverage``), keeping the legal/branding heuristics here in
one tested place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.plan_types import PLAN_TYPES

# The 14 canonical regimes (Brock 2026-07-06). Detection outputs one of these or ambiguous.
Regime = Literal[
    "state_regulated_commercial",
    "erisa_self_funded",
    "medicare_traditional",
    "medicare_advantage",
    "medicaid_ffs",
    "medicaid_mco",
    "dual_eligible",
    "self_pay",
    "tricare",
    "va_champva",
    "fehb_pshb",
    "nonfederal_governmental",
    "stldi",
    "excepted_coverage",
]

Confidence = Literal["high", "medium", "low"]

DetectionMethod = Literal[
    "document_format",
    "card_branding",
    "member_id_pattern",
    "user_declared",
    "ambiguous",
]

# The canonical regimes as a runtime tuple (single source of truth — app.plan_types).
REGIMES: tuple[str, ...] = PLAN_TYPES

# --- Medicare Beneficiary Identifier (MBI) -----------------------------------
# 11 chars, positions: N C AN N C AN N C C N N, where N=digit (pos1 is 1-9),
# C=letter excluding S,L,O,I,B,Z, AN=digit-or-C-letter. Dashes/spaces are cosmetic.
_C = "ACDEFGHJKMNPQRTUVWXYZ"  # allowed MBI letters (A-Z minus S L O I B Z)
_MBI_RE = re.compile(
    rf"^[1-9][{_C}][0-9{_C}][0-9][{_C}][0-9{_C}][0-9][{_C}][{_C}][0-9][0-9]$"
)


def is_valid_mbi(raw: str | None) -> bool:
    """True if ``raw`` (dashes/spaces ignored, case-insensitive) is a well-formed MBI."""
    if not raw:
        return False
    cleaned = re.sub(r"[\s-]", "", raw).upper()
    return bool(_MBI_RE.match(cleaned))


# --- branding keyword sets (lowercased substring match) ----------------------
_MEDICARE_MONIKER = ("medicare",)
_MA_KEYWORDS = (
    "medicare advantage", "advantage", "gold plus", "medicare complete",
    "aarp medicare", "medicare hmo", "medicare ppo", "part c", "dual complete",
)
_MEDICAID_KEYWORDS = (
    "medicaid", "medi-cal", "medical assistance", "managed medical assistance",
    "masshealth", "husky health", "soonercare", "tenncare", "apple health",
    "health first colorado", "denali care", "peachcare", "medi-cal managed care",
)
_MEDICAID_MCO_BRANDS = ("molina", "ambetter", "wellcare", "amerigroup", "centene")
_TRICARE_VA_KEYWORDS = (
    "tricare", "humana military", "health net federal", "champva",
    "veterans affairs", "va health", "department of veterans affairs",
    "us family health plan", "chcbp", "community care network",
)
_COMMERCIAL_BRANDS = (
    "blue cross", "blue shield", "bcbs", "anthem", "unitedhealthcare", "uhc",
    "aetna", "cigna", "kaiser", "oscar", "harvard pilgrim", "premera", "regence",
)

# document classification types (Sprint E taxonomy) → strong format signals
_DOC_MSN = "msn"
_DOC_MA_EOB = "ma_eob"
_DOC_MCO_NOTICE = "mco_notice"
_DOC_TRICARE_EOB = "tricare_eob"
_DOC_VA_STATEMENT = "va_statement"
_DOC_COMMUNITY_CARE = "community_care_auth"
_DOC_COMMERCIAL_EOB = "ceob"

# --- v2 (Brock 2026-07-06) signals for the new regimes -----------------------
# STLDI: the legally-required first-page notice — the single highest-confidence signal in the set.
_STLDI_NOTICE = "this is not qualifying health coverage"
# Excepted benefits (HCSMs, fixed indemnity, Farm Bureau): not insurance, no negotiated network.
_EXCEPTED_KEYWORDS = (
    "health care sharing", "healthcare sharing", "health sharing ministry", "sharing ministry",
    "fixed indemnity", "hospital indemnity", "farm bureau",
)
_EXCEPTED_NOTICE = ("not insurance", "not health insurance", "not qualified health")
# FEHB / PSHB: federal + postal employees. "FEP" (BCBS) is SUPPORTING-ONLY, never the sole basis.
_FEHB_KEYWORDS = ("fehb", "pshb", "federal employees health", "postal service health benefits")
_FEDERAL_EMPLOYER_PATTERNS = (
    "postal service", "usps", "u.s. postal", "united states postal", "federal government",
    "office of personnel management",
)
# Non-federal governmental (self-funded state/county/city/school). LOOKS commercial (BCBS admin),
# but the EMPLOYER is a government body — detection routes to the conservative non-ERISA value.
_GOV_EMPLOYER_PATTERNS = (
    "county of", "city of", "state of", "public schools", "school district", "unified school",
    "board of education", "municipal", "township of", "public employees", "teachers retirement",
)
# PACE — a detection OUTCOME that routes to a graceful handoff seam, not a regime value.
_PACE_KEYWORDS = ("program of all-inclusive care", "all-inclusive care for the elderly")
# Grandfathered — the mandated notice text; sets an ATTRIBUTE, never changes the regime.
_GRANDFATHERED_NOTICE = "notice of grandfathered"


@dataclass
class RegimeSignals:
    """Cheap, pre-extracted signals the classifier reasons over. Built by an adapter
    from insurance_info + document classification; kept model-free so the classifier
    stays pure."""

    payer_name: str | None = None
    plan_name: str | None = None
    member_id: str | None = None
    group_number: str | None = None
    # Employer / plan sponsor name — distinguishes FEHB/PSHB (federal/USPS) and non-federal
    # governmental (state/county/city/school) plans that otherwise carry commercial branding.
    employer_name: str | None = None
    rx_bin: str | None = None
    rx_pcn: str | None = None
    # classifications of the documents uploaded to the case (Sprint E doc types).
    document_types: list[str] = field(default_factory=list)
    # explicit user statements from intake.
    self_pay_declared: bool | None = None
    has_second_gov_card: bool | None = None  # e.g. Medicare + Medicaid both on file
    # freeform text pulled off documents (QMB hold-harmless language, etc.).
    document_text_blobs: list[str] = field(default_factory=list)

    def _brand_text(self) -> str:
        return " ".join(t for t in (self.payer_name, self.plan_name) if t).lower()

    def _doc_text(self) -> str:
        return " ".join(self.document_text_blobs).lower()


@dataclass
class RegimeDetection:
    """Classifier output. ``regime`` is None when ambiguous; ``candidate`` is the best
    guess to preselect on the confirm screen even at low confidence. ``verified`` is set
    True only on explicit user confirm or unambiguous document evidence (the ladder)."""

    regime: Regime | None
    candidate: Regime | None
    confidence: Confidence
    method: DetectionMethod
    evidence: list[str]
    verified: bool = False
    # Detected coverage attributes (grandfathered, qmb_status, …) — keys per plan_types.
    attributes: dict = field(default_factory=dict)
    # A non-regime routing outcome (e.g. 'pace') that sends the case to a graceful-handoff seam.
    handoff: str | None = None

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "candidate": self.candidate,
            "confidence": self.confidence,
            "method": self.method,
            "evidence": list(self.evidence),
            "verified": self.verified,
            "attributes": dict(self.attributes),
            "handoff": self.handoff,
        }


def is_valid_regime(value: str | None) -> bool:
    return value in REGIMES


def signals_from_fields(
    coverage: dict | None,
    document_types: list[str] | None = None,
    *,
    self_pay_declared: bool | None = None,
    has_second_gov_card: bool | None = None,
    document_text_blobs: list[str] | None = None,
) -> RegimeSignals:
    """Adapter: build RegimeSignals from a case_files.coverage / insurance_info-shaped
    dict + the case's document classifications. Kept next to the classifier but taking a
    plain dict (not the ORM row) so the classifier stays model-free and unit-testable.
    Field names cover both the coverage-blob aliases (payer_name) and raw card fields
    (insurer)."""
    cov = coverage or {}
    return RegimeSignals(
        payer_name=cov.get("payer_name") or cov.get("insurer"),
        plan_name=cov.get("plan_name"),
        member_id=cov.get("member_id") or cov.get("medicare_medicaid_id"),
        group_number=cov.get("group_number"),
        employer_name=cov.get("employer_name") or cov.get("group_name"),
        rx_bin=cov.get("rx_bin"),
        rx_pcn=cov.get("rx_pcn"),
        document_types=list(document_types or []),
        self_pay_declared=self_pay_declared if self_pay_declared is not None else cov.get("self_pay"),
        has_second_gov_card=(
            has_second_gov_card
            if has_second_gov_card is not None
            else cov.get("has_second_gov_card")
        ),
        document_text_blobs=list(document_text_blobs or []),
    )


def _any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(k in text for k in keywords)


_TRICARE_ONLY = ("tricare", "humana military", "health net federal", "us family health plan", "chcbp")
_VA_ONLY = ("champva", "veterans affairs", "va health", "department of veterans affairs",
            "community care network")


def detect_regime(signals: RegimeSignals) -> RegimeDetection:
    """Classify coverage regime from deterministic signals (14-value vocabulary, Brock
    2026-07-06). Precision-first: only clean cases earn ``high``; conflicting/thin evidence
    returns ambiguous. Never guessed. May also surface coverage attributes + a non-regime
    handoff (PACE)."""
    brand = signals._brand_text()
    doc = signals._doc_text()
    both = f"{brand} {doc}"
    emp = (signals.employer_name or "").lower()
    docs = {d.lower() for d in signals.document_types}
    ev: list[str] = []
    attrs: dict = {}

    # --- attributes + non-regime handoffs gathered first ---
    if _GRANDFATHERED_NOTICE in doc:
        attrs["grandfathered"] = True
        ev.append("carries the mandated Notice of Grandfathered Status")
    if _any(both, _PACE_KEYWORDS):
        ev.append("PACE (all-inclusive care for the elderly) indicated — routed to a handoff")
        return RegimeDetection(None, None, "high", "document_format", ev, attributes=attrs, handoff="pace")

    # --- highest-signal exclusions FIRST: they override commercial branding (wrong-answer risk) ---
    if _STLDI_NOTICE in doc:
        ev.append('carries the mandated "THIS IS NOT QUALIFYING HEALTH COVERAGE" STLDI notice')
        return RegimeDetection("stldi", "stldi", "high", "document_format", ev, attributes=attrs)
    if _any(both, _EXCEPTED_KEYWORDS):
        conf = "high" if _any(doc, _EXCEPTED_NOTICE) else "medium"
        ev.append("branding/notice indicates excepted benefits (HCSM / fixed indemnity / not insurance)")
        return RegimeDetection("excepted_coverage", "excepted_coverage", conf, "card_branding", ev, attributes=attrs)
    fehb_direct = _any(both, _FEHB_KEYWORDS) or _any(emp, _FEDERAL_EMPLOYER_PATTERNS)
    fep_supporting = "fep" in brand and not fehb_direct  # supporting-only, never a sole basis
    if fehb_direct:
        ev.append("FEHB/PSHB plan text or a federal-agency/USPS employer")
        return RegimeDetection("fehb_pshb", "fehb_pshb", "high", "card_branding", ev, attributes=attrs)

    # --- government-coverage evidence ---
    mbi = is_valid_mbi(signals.member_id)
    if mbi:
        ev.append("member id matches the Medicare MBI format")
    has_medicare_moniker = _any(brand, _MEDICARE_MONIKER)
    has_ma = _any(brand, _MA_KEYWORDS) or (has_medicare_moniker and _any(brand, _COMMERCIAL_BRANDS))
    if _DOC_MA_EOB in docs:
        has_ma = True
        ev.append("an MA EOB document is on file")
    elif has_ma:
        ev.append("plan branding names a Medicare Advantage product")

    is_mco = _any(brand, _MEDICAID_MCO_BRANDS) or _DOC_MCO_NOTICE in docs
    has_medicaid = _any(brand, _MEDICAID_KEYWORDS) or (
        _any(brand, _MEDICAID_MCO_BRANDS) and (_DOC_MCO_NOTICE in docs or "medicaid" in doc)
    )
    if has_medicaid:
        ev.append("branding/documents indicate Medicaid or a Medicaid MCO")

    has_traditional_medicare = _DOC_MSN in docs or (mbi and not has_ma) or (
        has_medicare_moniker and not has_ma and not _any(brand, _COMMERCIAL_BRANDS)
    )
    if _DOC_MSN in docs:
        ev.append("a Medicare Summary Notice (MSN) is on file")

    is_tricare = _any(brand, _TRICARE_ONLY) or _DOC_TRICARE_EOB in docs
    is_va = _any(brand, _VA_ONLY) or _DOC_VA_STATEMENT in docs or _DOC_COMMUNITY_CARE in docs
    has_tricare_va = is_tricare or is_va or _any(brand, _TRICARE_VA_KEYWORDS)
    if has_tricare_va:
        ev.append("branding/documents indicate TRICARE, VA, or CHAMPVA")

    qmb_language = "qualified medicare beneficiary" in doc or "should not be billed" in doc
    has_commercial = _any(brand, _COMMERCIAL_BRANDS) and not (
        has_medicare_moniker or has_medicaid or has_tricare_va
    )
    if has_commercial:
        ev.append("commercial payer branding with no government-coverage moniker")
    if signals.group_number:
        ev.append("a commercial group number is present")
    if signals.rx_bin:
        ev.append("an Rx BIN is present")
    if fep_supporting:
        ev.append("note: BCBS 'FEP' branding present (supporting-only, not a sole FEHB basis)")

    # --- resolve (dual > MA > medicare > medicaid > tricare/va > self-pay > gov/commercial) ---
    medicare_any = mbi or has_ma or has_traditional_medicare or has_medicare_moniker
    if medicare_any and (has_medicaid or signals.has_second_gov_card):
        conf = "high" if (qmb_language or signals.has_second_gov_card) else "medium"
        if qmb_language:
            ev.append("document carries QMB / 'you should not be billed' language")
            attrs["qmb_status"] = True  # confirmed QMB → the never-bill check may fire
        if signals.has_second_gov_card:
            ev.append("both a Medicare and a Medicaid card are on file")
        return RegimeDetection("dual_eligible", "dual_eligible", conf, "card_branding", ev, attributes=attrs)

    if has_ma:
        conf = "high" if _DOC_MA_EOB in docs else "medium"
        return RegimeDetection(
            "medicare_advantage", "medicare_advantage", conf,
            "document_format" if _DOC_MA_EOB in docs else "card_branding", ev, attributes=attrs,
        )

    if has_traditional_medicare and not has_commercial:
        conf = "high" if _DOC_MSN in docs else ("medium" if mbi else "low")
        return RegimeDetection(
            "medicare_traditional", "medicare_traditional", conf,
            "document_format" if _DOC_MSN in docs else "member_id_pattern", ev, attributes=attrs,
        )

    if has_medicaid and not has_commercial:
        regime = "medicaid_mco" if is_mco else "medicaid_ffs"
        conf = "high" if (_DOC_MCO_NOTICE in docs and _any(brand, _MEDICAID_KEYWORDS)) else "medium"
        return RegimeDetection(
            regime, regime, conf,
            "document_format" if _DOC_MCO_NOTICE in docs else "card_branding", ev, attributes=attrs,
        )

    if has_tricare_va:
        if is_tricare and not is_va:
            regime = "tricare"
        elif is_va and not is_tricare:
            regime = "va_champva"
        else:
            regime = "tricare" if is_tricare else "va_champva"  # ambiguous/both → default tricare
        doc_backed = bool(docs & {_DOC_TRICARE_EOB, _DOC_VA_STATEMENT, _DOC_COMMUNITY_CARE})
        conf = "high" if doc_backed else ("medium" if (is_tricare ^ is_va) else "low")
        return RegimeDetection(
            regime, regime, conf,
            "document_format" if doc_backed else "card_branding", ev, attributes=attrs,
        )

    no_coverage_evidence = not (medicare_any or has_medicaid or has_tricare_va or has_commercial)
    if signals.self_pay_declared and no_coverage_evidence:
        ev.append("user stated they are uninsured / self-pay and no coverage evidence was found")
        return RegimeDetection("self_pay", "self_pay", "high", "user_declared", ev, attributes=attrs)

    # commercial family: a governmental employer routes to the conservative non-federal value; a
    # stray MBI is a real conflict; otherwise fully-insured commercial (state_regulated_commercial).
    if has_commercial:
        if mbi:
            ev.append("note: an MBI-shaped member id also appears — flagged for confirmation")
            return RegimeDetection(None, "state_regulated_commercial", "low", "ambiguous", ev, attributes=attrs)
        if _any(emp, _GOV_EMPLOYER_PATTERNS):
            ev.append("a state/county/city/school employer — likely a non-federal governmental plan")
            return RegimeDetection(
                "nonfederal_governmental", "nonfederal_governmental", "medium", "card_branding", ev, attributes=attrs
            )
        conf = "high" if (signals.group_number and signals.rx_bin) else "medium"
        return RegimeDetection(
            "state_regulated_commercial", "state_regulated_commercial", conf, "card_branding", ev, attributes=attrs
        )

    # Nothing conclusive → ambiguous. Offer the strongest weak candidate (if any) to preselect.
    candidate: Regime | None = None
    if medicare_any:
        candidate = "medicare_traditional"
    elif has_medicaid:
        candidate = "medicaid_ffs"
    if not ev:
        ev.append("no reliable coverage signal was found")
    return RegimeDetection(None, candidate, "low", "ambiguous", ev, attributes=attrs)
