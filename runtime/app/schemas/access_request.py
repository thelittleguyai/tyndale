"""Access/deletion request intake shapes (§A2 state 5 / script §12 — stub)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# access = "what do you hold about this person"; deletion = "delete it"; correction = "fix it".
RequestType = Literal["access", "deletion", "correction"]


class AccessRequestIn(BaseModel):
    request_type: RequestType
    patient_name: str = Field(..., min_length=1, max_length=200)
    contact: str = Field(..., min_length=3, max_length=320, description="email or phone to reply to")
    relationship: str | None = Field(default=None, max_length=100)
    details: str | None = Field(default=None, max_length=2000)


class AccessRequestResult(BaseModel):
    received: bool
    # Receipt copy only. NEVER carries whether any record exists — the response is identical
    # whether or not the person appears anywhere in Tyndale.
    message: str
