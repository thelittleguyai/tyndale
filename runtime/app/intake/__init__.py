"""Guided intake (doc 40, Phase 1) — the Intake Planner and the registries it selects from.

CO-1A shipped a wizard with a FIXED step sequence. §A4 replaces it: after every capture the
planner recomputes what the audit still needs (`planner.gap_list`) and picks the next screen
from a registry (`screens.SCREEN_REGISTRY`). Nothing here re-implements an engine signal —
each gap is read from the seam that already owns it (coverage checklist, plan documents,
regime detection, EOB completeness, attest, the encounter confirmations).
"""
