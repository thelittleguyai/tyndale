"""CMS NCD/LCD ingestion (Phase CO-2A).

Discovery + extraction + chunking + embedding + upsert of Medicare National and
Local Coverage Determinations into the existing payer_policies Qdrant collection
(payer='CMS'), retrievable by the same qdrant_search_payer_policies tool with the
same mandatory effective-date filter. See intelligence-layer/reference and the
qdrant_search_payer_policies tool description.
"""
