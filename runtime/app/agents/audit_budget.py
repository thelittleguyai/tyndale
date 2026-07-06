"""Wall-clock + regeneration budget for a real-agent audit run (Item 1, 2026-07-06).

A single ``AuditBudget`` lives in a contextvar for the duration of an audit so the runner's
Stop-gate regeneration loop can stop cleanly when the run has spent its wall-clock ceiling OR
its per-run regeneration cap — the empty-KB citation-regeneration stall that hung audits for
minutes (each regenerate is a full multi-minute model pass).

Read with ``current_audit_budget()``; the orchestrator sets it around the agent calls. The
contextvar propagates through ``await`` (the agents are awaited directly — no task spawn), so
the runner sees it without threading a parameter through every agent wrapper.
"""

from __future__ import annotations

import time
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass
class AuditBudget:
    deadline: float  # a time.monotonic() ceiling
    regen_remaining: int  # per-run Stop-gate regeneration cap (belt to the per-agent <=3)
    regens_used: int = 0

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def take_regen(self) -> bool:
        """Consume one regeneration iff allowed by BOTH the regen cap and the deadline.
        Returns False when spent — the caller must stop regenerating and ship what it has."""
        if self.regen_remaining <= 0 or self.expired():
            return False
        self.regen_remaining -= 1
        self.regens_used += 1
        return True


_AUDIT_BUDGET: ContextVar[AuditBudget | None] = ContextVar("audit_budget", default=None)


def current_audit_budget() -> AuditBudget | None:
    return _AUDIT_BUDGET.get()


def set_audit_budget(budget: AuditBudget) -> Token:
    return _AUDIT_BUDGET.set(budget)


def reset_audit_budget(token: Token) -> None:
    _AUDIT_BUDGET.reset(token)
