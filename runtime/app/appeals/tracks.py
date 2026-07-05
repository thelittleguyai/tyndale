"""Appeal escalation-ladder state machine (Sprint G, shadow-mode DL-55/56).

The ladder: ``call → supervisor → internal_appeal → external_review →
cms_or_state_complaint``. Pure transition logic here; persistence is the ``appeal_tracks``
table. All of this stays dark (admin read-only, no user surfaces) until
``ENABLE_APPEALS_CASEMGMT`` is flipped — this sprint builds clocks + states only.
"""

from __future__ import annotations

# The escalation states, in ladder order.
APPEAL_STATES: tuple[str, ...] = (
    "call",
    "supervisor",
    "internal_appeal",
    "external_review",
    "cms_or_state_complaint",
)

# Per-state allowed next states. A strict ladder: each state may advance to the next one;
# the last is terminal. (Brock's playbook may later add lateral moves — kept explicit here.)
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "call": ("supervisor",),
    "supervisor": ("internal_appeal",),
    "internal_appeal": ("external_review",),
    "external_review": ("cms_or_state_complaint",),
    "cms_or_state_complaint": (),
}


class InvalidAppealTransition(Exception):
    def __init__(self, from_state: str, to_state: str) -> None:
        self.from_state, self.to_state = from_state, to_state
        super().__init__(f"invalid appeal transition: {from_state!r} → {to_state!r}")


def is_valid_state(state: str) -> bool:
    return state in APPEAL_STATES


def next_states(state: str) -> tuple[str, ...]:
    return ALLOWED_TRANSITIONS.get(state, ())


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in ALLOWED_TRANSITIONS.get(from_state, ())


def is_terminal(state: str) -> bool:
    return state in APPEAL_STATES and not ALLOWED_TRANSITIONS.get(state)
