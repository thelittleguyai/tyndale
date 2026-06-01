"""Per-source bulk parsers (Phase CO-3A / CO-2A.1).

Each data source (CMS MCD policies, Medicare PFS, Hospital MRF, TiC MRF) gets a
parser that STREAMS records out of a downloaded bulk file. Two record shapes:
PolicyRecord (narrative policy text → Qdrant via the CO-2A pipeline) and
RateRecord (structured price → transparency_rates in Postgres).

Add a new source: subclass BulkSourceParser, implement parse_file() as an async
generator, add an ingestion entry point + cron + tests. See ../README.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ingestion.blob_storage import BlobStorage


@dataclass
class PolicyRecord:
    """Narrative coverage policy (CMS NCD/LCD) — feeds chunk → embed → upsert."""

    policy_id: str
    policy_type: str  # 'NCD' | 'LCD'
    title: str
    effective_date: str | None
    last_modified: str | None
    sections: list[dict]  # [{heading, body, applicable_codes, section_number}]
    mac: str | None = None  # LCD only
    state: str | None = None  # LCD only


@dataclass
class RateRecord:
    """A structured price row — feeds transparency_rates (Postgres)."""

    code: str
    rate: float
    rate_type: str  # 'allowable' | 'negotiated' | 'cash' | 'gross' | 'min' | 'max'
    source: str  # 'medicare_pfs' | 'hospital_mrf' | 'tic_mrf'
    code_type: str | None = None  # 'CPT' | 'HCPCS' | 'DRG'
    payer: str | None = None
    hospital_id: str | None = None
    location_zip3: str | None = None
    effective_year: int | None = None
    raw_metadata: dict = field(default_factory=dict)


ParsedRecord = PolicyRecord | RateRecord


class BulkSourceParser(ABC):
    """Streams ParsedRecords from a downloaded bulk file in blob storage."""

    source_name: str = "abstract"

    @abstractmethod
    def parse_file(
        self, blob_path: str, blob_storage: "BlobStorage"
    ) -> AsyncIterator[ParsedRecord]:
        """Async-generate parsed records from the file at ``blob_path``."""
        raise NotImplementedError
