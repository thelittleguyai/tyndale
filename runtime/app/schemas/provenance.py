"""Provenance — typed source attribution for every data-interface return (DL-69).

Mirrors packages/shared/src/provenance.ts one-for-one.

Supersedes the bare ``extraction_source: "upload"`` string the upload-extract
tools used to emit. ``as_of`` is mandatory for AccumulatorSource (accumulator
math is freshness-sensitive); ``AccumulatorResult`` in app/sources/base.py
enforces that. ``Provenance`` is a strict superset of what is persisted today, so
threading it into tool returns / the case file / findings is purely additive.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProvenanceSourceKind = Literal["user_upload", "public_data", "computed", "vendor"]


class Provenance(BaseModel):
    adapter: str = Field(description='Adapter that produced the value, e.g. "UserUploadedSBC"')
    source_kind: ProvenanceSourceKind
    as_of: datetime | None = Field(
        default=None,
        description="ISO datetime the data is current as-of. Mandatory for AccumulatorSource (DL-69).",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="0.0–1.0 confidence in the value")
    assumptions: list[str] = Field(default_factory=list)
