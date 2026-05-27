"""Stubbed Azure Document Intelligence OCR (Phase 1C).

Returns canned extracted text while USE_REAL_OCR is false. Phase 2 wires real
Document Intelligence.
"""

from __future__ import annotations

from typing import Any


def stub_extract(filename: str, content: bytes) -> dict[str, Any]:
    return {
        "stub": True,
        "filename": filename,
        "byte_count": len(content),
        "ocr_text": (
            "STUB OCR — Hospital statement. CPT 70553 MRI brain w/o & w/ contrast. "
            "Billed $1,200."
        ),
        "fields": {"document_type": "bill", "total_billed": 1200.0},
    }
