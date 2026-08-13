"""Synthetic medical-document PDF generator for the e2e scenario harness (HP-2).

SYNTHETIC IDENTITIES ONLY. Every patient / provider / account number here is fabricated for
testing — this never contains, and must never contain, real PHI. Documents are parameterized
(amounts, dates, codes) by the scenario JSON so scenarios stay fresh and can be regenerated.

The text is written so the real pipeline recognizes it: classifier anchors (see
app/sources/document_classifier.py) pick the document_type, and the OCR text is realistic enough
for the agents to extract line items / amounts / codes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# A single synthetic patient/provider identity used across the suite (obviously fake).
PATIENT = "JORDAN Q. TESTPATIENT"
PROVIDER = "SYNTHETIC VALLEY MEDICAL CENTER"
PAYER = "SYNTHETIC MUTUAL HEALTH PLAN"
# Contact numbers, so the harness can exercise the B4 typed-phone path end to end. Both are in
# the 555-0100..555-0199 range reserved for fiction — these must never reach a real phone.
PROVIDER_PHONE = "(608) 555-0143"
PAYER_PHONE = "1-800-555-0177"


def _lines(c: canvas.Canvas, rows: list[str], *, x: float = inch, top: float = 10 * inch) -> None:
    y = top
    for row in rows:
        if y < inch:  # new page if we run off the bottom
            c.showPage()
            y = top
        c.setFont("Helvetica", 10)
        c.drawString(x, y, row)
        y -= 0.22 * inch


def _money(n: float) -> str:
    return f"${n:,.2f}"


def make_bill(
    path: Path, *, account: str, service_date: str, line_items: list[dict],
    patient: str | None = None, **_: Any,
) -> None:
    """Provider itemized statement. Anchors: STATEMENT / AMOUNT DUE / CPT.

    ``patient`` overrides the suite identity — the attest-and-proceed scenario needs a bill
    whose patient name deliberately MISMATCHES the account holder's profile."""
    total = round(sum(li["charge"] * li.get("units", 1) for li in line_items), 2)
    rows = [
        "ITEMIZED STATEMENT OF CHARGES",
        f"Provider: {PROVIDER}",
        f"Patient: {patient or PATIENT}    Account #: {account}",
        f"Date of Service: {service_date}",
        "",
        "CPT      Description                                Units   Charge",
        "-------------------------------------------------------------------",
    ]
    for li in line_items:
        rows.append(
            f"{li['code']:<8} {li['description'][:38]:<38} {li.get('units', 1):<7} "
            f"{_money(li['charge'])}"
        )
    rows += [
        "-------------------------------------------------------------------",
        f"TOTAL AMOUNT DUE: {_money(total)}",
        "",
        "This is a bill. Please remit payment or contact billing with questions.",
        f"Questions about your bill? Call {PROVIDER_PHONE}",
    ]
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(c, rows)
    c.showPage()
    c.save()


def make_eob(
    path: Path,
    *,
    claim_number: str,
    service_date: str,
    line_items: list[dict],
    member_responsibility: float,
    header: str = "EXPLANATION OF BENEFITS",
    payer: str = PAYER,
    extra: list[str] | None = None,
    **_: Any,
) -> None:
    """Payer EOB. Anchors: EXPLANATION OF BENEFITS / MEMBER RESPONSIBILITY. `header`/`payer`/
    `extra` let a scenario brand this as an MA-EOB, TRICARE EOB, etc."""
    rows = [
        header,
        "THIS IS NOT A BILL",
        f"Payer: {payer}",
        f"Member: {PATIENT}    Claim #: {claim_number}",
        f"Date of Service: {service_date}",
        *(extra or []),
        "",
        "CPT      Billed     Allowed    Plan Paid   Member Resp",
        "-------------------------------------------------------------------",
    ]
    for li in line_items:
        rows.append(
            f"{li['code']:<8} {_money(li['billed']):<10} {_money(li['allowed']):<10} "
            f"{_money(li['plan_paid']):<11} {_money(li['member_resp'])}"
        )
    rows += [
        "-------------------------------------------------------------------",
        f"TOTAL MEMBER RESPONSIBILITY: {_money(member_responsibility)}",
        f"Member Services: {PAYER_PHONE}",
    ]
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(c, rows)
    c.showPage()
    c.save()


def make_msn(
    path: Path, *, service_date: str, line_items: list[dict], maximum_you_may_be_billed: float, **_: Any
) -> None:
    """Medicare Summary Notice. Anchors: MEDICARE SUMMARY NOTICE / MAXIMUM YOU MAY BE BILLED."""
    rows = [
        "MEDICARE SUMMARY NOTICE",
        "This is a summary of your Medicare claims. THIS IS NOT A BILL.",
        f"Beneficiary: {PATIENT}",
        f"Date of Service: {service_date}    Provider: {PROVIDER}",
        "",
        "Service          Amount Charged   Medicare Approved   Medicare Paid",
        "-------------------------------------------------------------------",
    ]
    for li in line_items:
        rows.append(
            f"{li['code']:<16} {_money(li['billed']):<16} {_money(li['allowed']):<19} "
            f"{_money(li['plan_paid'])}"
        )
    rows += [
        "-------------------------------------------------------------------",
        f"MAXIMUM YOU MAY BE BILLED: {_money(maximum_you_may_be_billed)}",
    ]
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(c, rows)
    c.showPage()
    c.save()


def make_collections(path: Path, *, account: str, amount_due: float, **_: Any) -> None:
    """Collections / statement-only notice — NO itemization. Anchors: FINAL NOTICE / PAST DUE."""
    rows = [
        "FINAL NOTICE - PAST DUE ACCOUNT",
        f"RE: Account {account} - {PROVIDER}",
        f"Patient: {PATIENT}",
        "",
        f"Your account is PAST DUE in the amount of {_money(amount_due)}.",
        "This account may be referred to a COLLECTION agency if not paid.",
        "No itemization of charges is included with this notice.",
    ]
    c = canvas.Canvas(str(path), pagesize=letter)
    _lines(c, rows)
    c.showPage()
    c.save()


def make_garbage(path: Path, **_: Any) -> None:
    """A near-empty page — no readable medical content → the pipeline should degrade honestly."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica", 8)
    c.drawString(inch, 5 * inch, ".")  # essentially blank; OCR yields nothing usable
    c.showPage()
    c.save()


def make_blank_pages(path: Path, *, pages: int = 2, **_: Any) -> None:
    """A valid multi-page PDF with NO drawn content — real OCR extracts nothing → the case must
    degrade to extraction_failed, never a 0-item encounter."""
    c = canvas.Canvas(str(path), pagesize=letter)
    for _i in range(max(1, int(pages))):
        c.showPage()  # a page with nothing on it
    c.save()


def make_not_a_bill_txt(path: Path, **_: Any) -> None:
    """A readable .txt that isn't a medical document (a grocery list). NOT a PDF/image, so the
    upload magic-byte check must reject it at the door (422) — it never reaches OCR."""
    path.write_text(
        "GROCERY LIST\n- milk\n- eggs\n- bread\n- bananas\n- coffee\n- paper towels\n- olive oil\n"
    )



def make_insurance_card(path: Path, *, member_id: str = "SYN-123456789", **_: Any) -> None:
    """An insurance CARD image/scan — a real document that carries no auditable charges.
    Anchors match the classifier's card fields (wrongdoc.card branch)."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica", 11)
    _lines(
        c,
        [
            PAYER,
            "MEMBER IDENTIFICATION CARD",
            "",
            f"Member: {PATIENT}",
            f"Member ID: {member_id}",
            "Group Number: SYN-GRP-0042",
            "RxBIN: 610000    RxPCN: SYNTH    RxGRP: SYNRX",
            "",
            "Copay: Office $30   Specialist $60   ER $350",
            "Customer Service: 1-800-000-0000",
        ],
    )
    c.showPage()
    c.save()



def make_summary_bill(
    path: Path, *, account: str, service_date: str, total_charges: float,
    amount_due: float, **_: Any,
) -> None:
    """A SUMMARY statement: charges and a total, deliberately with NO CPT/line-item detail —
    the shape §5.2 coaches the user out of (errors hide in the itemized version)."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica", 11)
    _lines(c, [
        "STATEMENT SUMMARY",
        f"Provider: {PROVIDER}",
        f"Patient: {PATIENT}",
        f"Account #: {account}    Date of Service: {service_date}",
        "",
        "BALANCE FORWARD                                   0.00",
        f"TOTAL CHARGES                                {_money(total_charges)}",
        f"AMOUNT DUE                                   {_money(amount_due)}",
        "",
        "Please pay this amount by the due date shown above.",
        "This is a summary of your account. Call billing with questions.",
    ])
    c.showPage()
    c.save()


def make_bill_photo(
    path: Path, *, account: str, service_date: str, line_items: list[dict], **_: Any
) -> None:
    """The same statement as a JPEG — a PHOTO of the bill rather than a PDF of it (N1 / C1).

    This is what camera capture produces: `CameraCapture` draws the frame to a canvas and hands
    up a `image/jpeg` File at the same 1600px longest edge the client compresses to. The scenario
    exists to prove a photographed bill travels the identical path to a picked file — same
    magic-byte gate, same classifier, same extraction — so the capture surface can't quietly
    become a second, weaker intake.
    """
    from PIL import Image, ImageDraw  # local import: only the photo scenario needs Pillow

    total = round(sum(li["charge"] * li.get("units", 1) for li in line_items), 2)
    rows = [
        "ITEMIZED STATEMENT OF CHARGES",
        f"Provider: {PROVIDER}",
        f"Patient: {PATIENT}    Account #: {account}",
        f"Date of Service: {service_date}",
        "",
        "CPT      Description                                Units   Charge",
        *[
            f"{li['code']:<8} {li['description'][:38]:<38} {li.get('units', 1):<7} "
            f"{_money(li['charge'])}"
            for li in line_items
        ],
        f"TOTAL AMOUNT DUE: {_money(total)}",
        "",
        "This is a bill. Please remit payment or contact billing with questions.",
        f"Questions about your bill? Call {PROVIDER_PHONE}",
    ]
    # 1240x1600 ≈ the 1600px-longest-edge, 3:4 frame the capture path emits.
    img = Image.new("RGB", (1240, 1600), "white")
    draw = ImageDraw.Draw(img)
    y = 60
    for row in rows:
        draw.text((60, y), row, fill="black")
        y += 34
    img.save(path, "JPEG", quality=70)


_MAKERS = {
    "bill": make_bill,
    "bill_photo": make_bill_photo,
    "eob": make_eob,
    "msn": make_msn,
    "collections": make_collections,
    "garbage": make_garbage,
    "blank_pages": make_blank_pages,
    "not_a_bill_txt": make_not_a_bill_txt,
    "insurance_card": make_insurance_card,
    "summary_bill": make_summary_bill,
}


def generate_for_scenario(scenario: dict, out_dir: Path) -> list[Path]:
    """Generate every document declared in a scenario's `documents` list. Returns the file paths
    in declared order. Each doc entry: {"type": "bill"|"eob"|..., "filename": "...", ...params}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, doc in enumerate(scenario.get("documents", [])):
        maker = _MAKERS.get(doc["type"])
        if maker is None:
            raise ValueError(f"unknown document type: {doc['type']}")
        filename = doc.get("filename") or f"{i}_{doc['type']}.pdf"
        path = out_dir / filename
        maker(path, **{k: v for k, v in doc.items() if k not in {"type", "filename"}})
        paths.append(path)
    return paths
