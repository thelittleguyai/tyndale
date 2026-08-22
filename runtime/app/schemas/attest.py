"""Attest-and-proceed request/response shapes (§A2 state 1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.attest import RELATIONSHIPS


class AttestRequest(BaseModel):
    # Closed enum — a free-text relationship would be unauditable (and PHI-shaped).
    relationship: str = Field(..., description=f"one of {RELATIONSHIPS}")
    # The menu's "this person is deceased" option — drives the estate edge prompt.
    patient_deceased: bool = False


class AttestResult(BaseModel):
    case_file_id: str
    attest_status: str  # attested | declined
    case_status: str
    confirmation: str  # the rendered confirm/decline line
    # Elevated edge-case prompts (teen / deceased) — guidance, never blocks.
    edge_prompts: list[str] = Field(default_factory=list)
