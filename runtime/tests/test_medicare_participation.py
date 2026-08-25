"""Medicare participation (Brock 2026-08-22, §2.3): resolve silently, degrade honestly."""

from __future__ import annotations

from app.sources.medicare_participation import (
    OPT_OUT_RATES,
    ParticipationResult,
    resolve_participation,
)


class _Answering:
    def __init__(self, answer: bool | None) -> None:
        self.answer = answer

    def is_opted_out(self, npi: str) -> bool | None:  # noqa: ARG002
        return self.answer


def test_unresolvable_degrades_to_participating_with_internal_low_confidence():
    r = resolve_participation("1234567890", "cardiology")  # shipped stub: unknown
    assert r.participating is True and r.resolved is False
    assert r.confidence == "assumed_low_confidence"
    assert "98%" in r.source  # the prior, recorded internally — never a user-facing claim


def test_resolved_answers_win_over_the_prior():
    opted = resolve_participation("1", "psychiatry", source=_Answering(True))
    assert opted.participating is False and opted.resolved and opted.confidence == "resolved"
    participating = resolve_participation("1", None, source=_Answering(False))
    assert participating.participating is True and participating.resolved


def test_specialty_awareness_is_internal_risk_ranking_only():
    assert resolve_participation("1", "Psychiatry").specialty_opt_out_rate == 0.081
    assert resolve_participation("1", "plastic surgery").specialty_opt_out_rate == 0.045
    assert resolve_participation("1", "cardiology").specialty_opt_out_rate == 0.012
    assert isinstance(resolve_participation(None), ParticipationResult)  # no NPI → prior
    assert OPT_OUT_RATES["_overall"] == 0.012
