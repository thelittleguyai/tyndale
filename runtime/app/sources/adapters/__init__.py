"""Concrete adapters behind the four data interfaces (DL-68).

CO-12A ships the two "now" adapters over the V1-Lite upload path (UserUploadedSBC,
UserUploadedEOB) plus thin placeholders for the interfaces whose engines land
later (PlaceholderAccumulator → CO-12B, PlaceholderClinicalEncounter → CO-12D).
Jonas's wrapper registers OneUpHealth* / eligibility adapters here later behind
the same interfaces, with zero agent change.
"""
