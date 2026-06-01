# Bulk data ingestion (Phase CO-3A + CO-2A.1)

Shared bulk-download infrastructure + per-source parsers feeding two sinks:
narrative coverage policy → Qdrant (`payer_policies`); structured price → Postgres
(`transparency_rates`).

## Architecture

```
BulkDownloader ──> BlobStorage ──> BulkSourceParser ──> sink
  (resume,           (Azure Blob       (per-source)        ├─ PolicyRecord → chunk → embed → upsert (Qdrant)
   cache, robots)     or local FS)                         └─ RateRecord   → transparency_rates (Postgres)
```

- `bulk_download.py` — `BulkDownloader`: HEAD probe, idempotent cache (sidecar
  `.meta.json` on Last-Modified), resume-on-failure (Range), per-host throttle +
  concurrency cap, robots check. httpx client + robots checker are injectable (tests
  use `httpx.MockTransport`).
- `blob_storage.py` — `BlobStorage`: Azure Blob when `AZURE_STORAGE_CONNECTION_STRING`
  is set, else local FS (`bulk_local_dir`). `materialize_local()` gives parsers a real
  path for `zipfile`/`csv`/`gzip`.
- `parsers/` — `BulkSourceParser` ABC; each `parse_file()` is an async generator
  yielding `PolicyRecord` (CMS MCD) or `RateRecord` (price sources).
- `ghost_rate_filter.py` — DL-63 ghost detection + confidence scoring (tunable).
- `rates_repo.py` — persist to `transparency_rates` / `_staging`, Medicare baseline +
  corroboration lookups.
- `../knowledge/cost_estimation.py` — `estimate_cost()`: confidence-banded estimate
  combining sources (CO-002 Item 3: always a band, never a point).

## Sources (verify URLs/formats at implementation time)

| Source | Real URL | Format | Sink |
|--------|----------|--------|------|
| CMS MCD (CO-2A.1) | `downloads.cms.gov/medicare-coverage-database/downloads/exports/all_data.zip` ✅ verified | ZIP of CSVs (`*_list.csv` + `*_text.csv`, joined on id) | Qdrant |
| Medicare PFS | `cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files` ✅ page live | per-year ZIP → PPRRVU CSV; allowable = TOTAL_RVU × CF × GPCI | `transparency_rates` |
| Hospital MRF | per hospital (`data/top_100_hospitals.csv`) | CMS v2.0 JSON (or CSV) | `transparency_rates_staging` (DL-59) |
| TiC MRF | per payer index (`data/tier1_payer_tic_indices.csv`) | JSON-Lines (gzip), streamed | `transparency_rates` (ghost-filtered) |

Hospital MRF URLs + the full top-100 hospital curation, and per-payer TiC index URLs,
need per-source verification — the committed CSVs are STARTER sets (see their headers).

## Adding a new source (Sprint C+, DL-58)

1. Implement `BulkSourceParser` in `parsers/<source>.py`.
2. Add an ingestion entry point (`<source>.py`) wiring download → parse → persist.
3. New sources land in `transparency_rates_staging` first (DL-59); promote to live after
   a ≥90% extraction-confidence sample.
4. Add a cron in `../crons/`, and tests in `../../tests/test_bulk_data_foundation.py`.

## Cost per run

Medicare PFS ~$0 (small). Hospital MRF top-100 ~$5–20. TiC Tier-1 ~$50–200 (large
download + processing). CMS MCD bulk dominated by Claude extraction (~$0.02/policy,
capped by `MAX_POLICIES_PER_RUN`). Crons are manual-trigger; the Container Apps Job
scheduler is follow-on infra.
