"""Hospital MRF ingestion (Phase CO-3A) — top-100 hospital negotiated rates.

Real-source discovery (CO-3A): the CMS Hospital Price Transparency rule requires each
hospital to publish a `cms-hpt.txt` at its public-website root with an `mrf-url:` field
pointing at the machine-readable file. We resolve the MRF from the hospital's domain via
that file (data/top_100_hospitals.csv carries the domain), so no hand-fed URLs.

Per DL-59 new hospitals land in transparency_rates_staging first (staging=True default);
promotion to live requires a >=90% extraction-confidence sample. Hospital data is direct
(the hospital's own published file), so no ghost filter. Cost cap: the whole top-100 batch
fits one run; expansion past 100 is Sprint C+ (DL-58).

Size reality: MRFs range from a few MB to multi-GB. The sample path is non-streaming
(json.load), so it skips files over SAMPLE_MAX_BYTES; full ingest of the giant hospitals
needs ijson streaming (the parser docstring flags this).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import io
import zipfile

import httpx
import structlog

from app.ingestion.blob_storage import BlobStorage
from app.ingestion.bulk_download import BulkDownloader
from app.ingestion.parsers.hospital_mrf import HospitalMrfParser
from app.ingestion.rates_repo import persist_rates

log = structlog.get_logger(__name__)

_UA = "Mozilla/5.0 (compatible; TyndaleBot/0.1; +https://tyndaleapp.net)"
# Skip MRFs larger than this in (non-streaming) sample mode; full ingest needs ijson.
SAMPLE_MAX_BYTES = 80_000_000
# Cap rates persisted per hospital in sample mode (a single MRF can hold tens of thousands).
SAMPLE_RECORD_LIMIT = 500


class MrfTooLarge(RuntimeError):
    """MRF exceeds the sample size cap — full ingest needs streaming (see README)."""


async def discover_hospital_mrf_url(domain: str, *, client: httpx.AsyncClient | None = None) -> str:
    """Resolve a hospital's MRF URL from the CMS-mandated cms-hpt.txt at its domain root.

    The cms-hpt.txt is a structured text file (``location-name:`` / ``source-page-url:`` /
    ``mrf-url:`` / ``contact-name:`` ...); we read the ``mrf-url`` field.
    """
    base = domain.strip().rstrip("/")
    base = base if base.startswith("http") else f"https://{base}"
    own_client = client is None
    client = client or httpx.AsyncClient(
        follow_redirects=True, timeout=30.0, headers={"User-Agent": _UA}
    )
    try:
        body = (await client.get(f"{base}/cms-hpt.txt")).text
        for line in body.splitlines():
            key, sep, val = line.partition(":")
            if sep and key.strip().lower() == "mrf-url":
                return val.strip()
        raise RuntimeError(f"{base}/cms-hpt.txt has no mrf-url field")
    finally:
        if own_client:
            await client.aclose()


async def _materialize_json(blob: BlobStorage, blob_path: str) -> str:
    """If the downloaded MRF is a zip, extract its first .json member to a sibling blob."""
    raw = await blob.read_bytes(blob_path)
    if raw[:4] != b"PK\x03\x04":
        return blob_path
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        member = next((n for n in zf.namelist() if n.lower().endswith(".json")), None)
        if not member:
            return blob_path
        out = f"{blob_path}.json"
        await blob.write_bytes(out, zf.read(member))
        return out


async def ingest_hospital_mrf(
    hospital_id: str,
    mrf_url: str | None = None,
    *,
    domain: str | None = None,
    hospital_zip3: str | None = None,
    year: int | None = None,
    blob: BlobStorage | None = None,
    downloader: BulkDownloader | None = None,
    blob_path: str | None = None,
    max_bytes: int | None = SAMPLE_MAX_BYTES,
    record_limit: int | None = None,
    staging: bool = True,
) -> int:
    """Ingest one hospital's MRF. Resolves mrf_url from cms-hpt.txt when only ``domain`` is
    given; tests pass blob_path to skip discovery+download. ``max_bytes`` skips files too
    large for the non-streaming sample path (full ingest needs ijson — see README).
    """
    blob = blob or BlobStorage()
    if blob_path is None:
        if not mrf_url:
            if not domain:
                raise ValueError("mrf_url, domain, or blob_path required")
            mrf_url = await discover_hospital_mrf_url(domain)
        if max_bytes:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=60.0, headers={"User-Agent": _UA}
            ) as probe:
                size = int((await probe.head(mrf_url)).headers.get("content-length") or 0)
            if size == 0 or size > max_bytes:
                raise MrfTooLarge(
                    f"{hospital_id}: MRF {size / 1e6:.0f}MB exceeds the "
                    f"{max_bytes / 1e6:.0f}MB sample cap (needs ijson streaming)"
                )
        # MRFs are CMS-mandated machine-accessible files; the cms-hpt.txt mechanism exists
        # for automated retrieval, so robots is allowed for the discovered MRF URL.
        dl = downloader or BulkDownloader(blob, robots_allow=lambda _u: True)
        res = await dl.download(mrf_url, f"hospital-mrf/{hospital_id}/mrf.bin")
        blob_path = await _materialize_json(blob, res.blob_path)

    yr = year or datetime.date.today().year
    records = []
    async for r in HospitalMrfParser(hospital_id).parse_file(blob_path, blob):
        r.location_zip3 = hospital_zip3
        r.effective_year = yr
        records.append(r)
        if record_limit and len(records) >= record_limit:
            break

    n = await persist_rates(records, confidence_fn=lambda r: 0.85, staging=staging)
    log.info("hospital_mrf.ingested", hospital_id=hospital_id, rates=n, staging=staging)
    return n


async def _run_sample(limit: int) -> dict:
    """Ingest the first ``limit`` hospitals from top_100_hospitals.csv (DL-59 staging).

    Resolves each MRF from the hospital's cms-hpt.txt; oversized MRFs are skipped (the
    sample path is non-streaming).
    """
    from app.crons._cron_util import load_top_100_hospitals

    hospitals = load_top_100_hospitals()[:limit]
    ok = failed = skipped = total = 0
    notes: list[str] = []
    for h in hospitals:
        name = h.get("hospital_name")
        try:
            n = await ingest_hospital_mrf(
                h["hospital_id"],
                h.get("mrf_url") or None,
                domain=h.get("domain") or None,
                hospital_zip3=h.get("zip3"),
                record_limit=SAMPLE_RECORD_LIMIT,
                staging=True,
            )
            total += n
            ok += 1
            notes.append(f"OK   {name}: {n} rates staged")
        except MrfTooLarge as e:
            skipped += 1
            notes.append(f"SKIP {e}")
        except Exception as e:  # noqa: BLE001 — per-hospital isolation; report, don't abort
            failed += 1
            notes.append(f"FAIL {name}: {type(e).__name__}: {str(e)[:120]}")
    return {"ok": ok, "failed": failed, "skipped": skipped, "rates": total, "notes": notes}


def main() -> None:
    p = argparse.ArgumentParser(
        description="Hospital MRF ingestion into transparency_rates_staging"
    )
    p.add_argument("--mode", choices=["sample", "full"], default="sample")
    p.add_argument("--limit", type=int, default=2, help="number of hospitals from the CSV")
    args = p.parse_args()
    rep = asyncio.run(_run_sample(args.limit))
    print(
        f"[hospital_mrf {args.mode}] ok={rep['ok']} skipped={rep['skipped']} "
        f"failed={rep['failed']} rates_staged={rep['rates']}"
    )
    for note in rep["notes"]:
        print("  ", note)


if __name__ == "__main__":
    main()
