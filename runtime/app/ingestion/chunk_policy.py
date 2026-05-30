"""Chunking + embedding + upsert for CMS NCD/LCD policies (Phase CO-2A).

Per developer-spec §8: ONE chunk per policy section, with the section heading
inline at the top of each chunk's text and full parent context in metadata. Each
chunk lands in the existing payer_policies Qdrant collection with payer='CMS',
embedded with voyage-3-large via the shared embeddings client and upserted via the
shared Qdrant client — the same path seed_fixtures.py uses, so retrieval +
effective-date filtering work identically to the rest of the collection.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

import structlog
from qdrant_client import models

from app.ingestion.cms_ncd_lcd import LcdDocument, NcdDocument
from app.ingestion.extract_policy import ExtractedPolicy
from app.knowledge.client import ensure_collection, get_client
from app.knowledge.collections import COLLECTIONS
from app.knowledge.embeddings import embed_batch, model_for

log = structlog.get_logger(__name__)

_COLLECTION = "payer_policies"
# Same namespace + key scheme as scripts/seed_fixtures.py so ids are stable and
# re-ingesting the same version is an idempotent overwrite (no duplicate points).
_NS = uuid.UUID("9f1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d")


@dataclass
class PolicyChunk:
    chunk_id: str
    chunk_text: str
    payer: str
    policy_id: str
    version: str
    effective_date_start: str | None
    effective_date_end: str | None
    applicable_codes: list[str]
    plan_type: str
    jurisdiction: str
    last_verified_date: str
    parent_title: str
    parent_part: str | None = None
    parent_subpart: str | None = None
    section_heading: str | None = None
    section_number: str | None = None

    def point_id(self) -> str:
        return str(uuid.uuid5(_NS, f"{_COLLECTION}:{self.chunk_id}"))

    def to_payload(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "chunk_text": self.chunk_text,
            "payer": self.payer,
            "policy_id": self.policy_id,
            "version": self.version,
            "effective_date_start": self.effective_date_start,
            "effective_date_end": self.effective_date_end,
            "applicable_codes": self.applicable_codes,
            "plan_type": self.plan_type,
            "jurisdiction": self.jurisdiction,
            "last_verified_date": self.last_verified_date,
            "parent_title": self.parent_title,
            "parent_part": self.parent_part,
            "parent_subpart": self.parent_subpart,
            "section_heading": self.section_heading,
            "section_number": self.section_number,
        }


def _today_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def chunk_policy(
    extracted: ExtractedPolicy,
    document: NcdDocument | LcdDocument,
) -> list[PolicyChunk]:
    """One PolicyChunk per section; heading inline at top of chunk_text."""
    is_lcd = isinstance(document, LcdDocument)
    policy_id = document.policy_id
    eff_start = (
        extracted.effective_date_start.isoformat()
        if extracted.effective_date_start
        else (document.effective_date[:10] if document.effective_date else None)
    )
    eff_end = extracted.effective_date_end.isoformat() if extracted.effective_date_end else None
    version = eff_start or (document.last_modified or "unversioned")
    if is_lcd:
        st = (document.state or "").upper()  # type: ignore[union-attr]
        jurisdiction = f"state_{st}" if st else "state_unknown"
    else:
        jurisdiction = "federal"
    verified = _today_iso()

    chunks: list[PolicyChunk] = []
    for s in document.sections:
        heading = s.heading or "General"
        chunk_text = f"{heading}\n\n{s.body}".strip()
        chunks.append(
            PolicyChunk(
                chunk_id=f"{policy_id}#{s.section_number or len(chunks) + 1}",
                chunk_text=chunk_text,
                payer="CMS",
                policy_id=policy_id,
                version=version,
                effective_date_start=eff_start,
                effective_date_end=eff_end,
                applicable_codes=list(s.applicable_codes),
                plan_type="Medicare",
                jurisdiction=jurisdiction,
                last_verified_date=verified,
                parent_title=document.title,
                parent_part=document.parent_part,
                parent_subpart=document.parent_subpart,
                section_heading=heading,
                section_number=s.section_number,
            )
        )
    return chunks


async def embed_and_upsert(chunks: list[PolicyChunk]) -> int:
    """Embed each chunk's text (voyage-3-large) and upsert into payer_policies.

    Idempotent: stable point ids mean re-ingesting the same version overwrites
    in place. Returns the number of points upserted."""
    if not chunks:
        return 0
    await ensure_collection(_COLLECTION, vector_size=COLLECTIONS[_COLLECTION].vector_size)
    texts = [c.chunk_text for c in chunks]
    vectors = await embed_batch(
        texts, model_for(_COLLECTION), dim=COLLECTIONS[_COLLECTION].vector_size
    )
    points = [
        models.PointStruct(id=c.point_id(), vector=vec, payload=c.to_payload())
        for c, vec in zip(chunks, vectors)
    ]
    await get_client().upsert(collection_name=_COLLECTION, points=points)
    log.info("ingestion.upsert", collection=_COLLECTION, points=len(points))
    return len(points)
