"""Scheduled / background jobs.

Phase 2J adds outcome_followup as a synchronous, frontend-driven scan (called
by GET /v1/feedback/outcome-prompts). Phase 4 wires the real scheduled cron +
notify_user pushes against the same scan function.
"""
