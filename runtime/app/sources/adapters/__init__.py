"""Concrete adapters behind the four data interfaces (DL-68).

CO-12A shipped the two "now" adapters over the V1-Lite upload path (UserUploadedSBC,
UserUploadedEOB); the placeholders for the deferred interfaces have since been
replaced by real adapters (PlaceholderAccumulator → ComputedFromUploadedEOBs +
EOBStatedYTD, CO-12B; PlaceholderClinicalEncounter → UserUploadedVisitSummary,
CO-12D). Jonas's wrapper registers OneUpHealth* / eligibility adapters here later
behind the same interfaces, with zero agent change.
"""
