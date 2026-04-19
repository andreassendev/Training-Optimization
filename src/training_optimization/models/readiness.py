"""Composite readiness score from subjective and objective inputs.

Combines biometric signals (HRV, resting HR, sleep), recent hard-session
recency, and optional subjective input into a single 0-100 score.

The score is only as good as its inputs: with no HRV or RHR baseline, it
degrades to a recency+subjective estimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from training_optimization.models.activity import Activity


@dataclass(frozen=True)
class ReadinessInputs:
    """Raw daily inputs for readiness calculation.

    All fields are optional; the score degrades gracefully with missing data.
    """

    hrv_rmssd: float | None = None  # current RMSSD in ms
    hrv_baseline: float | None = None  # 7-14 day trailing average RMSSD
    resting_hr: float | None = None  # current RHR in bpm
    rhr_baseline: float | None = None  # 7-14 day trailing average RHR
    sleep_hours: float | None = None  # last night
    subjective_score: int | None = None  # 1-10 how the athlete feels


@dataclass(frozen=True)
class ReadinessScore:
    """Output of readiness calculation."""

    as_of: datetime
    score: float  # 0-100 composite
    days_since_hard: int
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def zone(self) -> str:
        if self.score >= 80:
            return "ready"
        if self.score >= 60:
            return "neutral"
        if self.score >= 40:
            return "caution"
        return "recover"


def _days_since_hard_session(activities: list[Activity], as_of: datetime) -> int:
    """Days since the last quality or long run."""
    last = max(
        (
            a.date
            for a in activities
            if a.is_quality_session() or a.is_long_run()
        ),
        default=None,
    )
    if last is None:
        return 999
    return max(0, (as_of - last).days)


def _hrv_component(inputs: ReadinessInputs) -> tuple[float | None, str | None]:
    """Score contribution from HRV deviation. Returns (score 0-100, note)."""
    if inputs.hrv_rmssd is None or inputs.hrv_baseline is None or inputs.hrv_baseline <= 0:
        return None, None
    deviation_pct = (inputs.hrv_rmssd - inputs.hrv_baseline) / inputs.hrv_baseline * 100
    # +5% or better → 100, -10% or worse → 0, linear between
    if deviation_pct >= 5:
        return 100.0, f"HRV {deviation_pct:+.1f}% vs baseline"
    if deviation_pct <= -10:
        return 0.0, f"HRV {deviation_pct:+.1f}% vs baseline (suppressed)"
    # Linear interpolation from -10% (0) to +5% (100)
    score = (deviation_pct + 10) / 15 * 100
    return score, f"HRV {deviation_pct:+.1f}% vs baseline"


def _rhr_component(inputs: ReadinessInputs) -> tuple[float | None, str | None]:
    """Score from resting HR elevation. Lower RHR vs baseline = better."""
    if inputs.resting_hr is None or inputs.rhr_baseline is None:
        return None, None
    elevation = inputs.resting_hr - inputs.rhr_baseline
    # At or below baseline → 100; +7 bpm or more → 0
    if elevation <= 0:
        return 100.0, f"RHR {elevation:+.0f} bpm vs baseline"
    if elevation >= 7:
        return 0.0, f"RHR {elevation:+.0f} bpm (elevated)"
    score = (7 - elevation) / 7 * 100
    return score, f"RHR {elevation:+.0f} bpm vs baseline"


def _sleep_component(inputs: ReadinessInputs) -> tuple[float | None, str | None]:
    """Score from last night's sleep hours."""
    if inputs.sleep_hours is None:
        return None, None
    # 8h+ = 100, 5h or less = 0
    if inputs.sleep_hours >= 8:
        return 100.0, f"Sleep {inputs.sleep_hours:.1f}h"
    if inputs.sleep_hours <= 5:
        return 0.0, f"Sleep {inputs.sleep_hours:.1f}h (short)"
    score = (inputs.sleep_hours - 5) / 3 * 100
    return score, f"Sleep {inputs.sleep_hours:.1f}h"


def _subjective_component(inputs: ReadinessInputs) -> tuple[float | None, str | None]:
    """Self-reported 1-10 mapped to 0-100."""
    if inputs.subjective_score is None:
        return None, None
    clamped = max(1, min(10, inputs.subjective_score))
    return (clamped - 1) / 9 * 100, f"Subjective {clamped}/10"


def _recency_component(days_since_hard: int) -> tuple[float, str]:
    """Score from days since last hard session. Monotonic up to 3 days."""
    if days_since_hard >= 3:
        return 100.0, f"{days_since_hard}d since hard session"
    if days_since_hard <= 0:
        return 20.0, "Hard session today"
    # 1 day = 50, 2 days = 75
    return 20 + days_since_hard * 27.5, f"{days_since_hard}d since hard session"


def compute_readiness(
    activities: list[Activity],
    as_of: datetime,
    inputs: ReadinessInputs | None = None,
) -> ReadinessScore:
    """Compute composite readiness score.

    Weights: HRV 30%, RHR 20%, Sleep 15%, Subjective 15%, Recency 20%.
    Missing components are redistributed proportionally across what remains.
    """
    inputs = inputs or ReadinessInputs()
    days_since_hard = _days_since_hard_session(activities, as_of)

    weights = {
        "hrv": 0.30,
        "rhr": 0.20,
        "sleep": 0.15,
        "subjective": 0.15,
        "recency": 0.20,
    }
    components: dict[str, tuple[float, str | None]] = {}

    for key, fn in (
        ("hrv", _hrv_component(inputs)),
        ("rhr", _rhr_component(inputs)),
        ("sleep", _sleep_component(inputs)),
        ("subjective", _subjective_component(inputs)),
    ):
        score, note = fn
        if score is not None:
            components[key] = (score, note)

    recency_score, recency_note = _recency_component(days_since_hard)
    components["recency"] = (recency_score, recency_note)

    total_weight = sum(weights[k] for k in components)
    if total_weight == 0:
        final_score = 50.0
    else:
        weighted = sum(components[k][0] * weights[k] for k in components)
        final_score = weighted / total_weight

    notes = tuple(note for _, note in components.values() if note)
    return ReadinessScore(
        as_of=as_of,
        score=round(final_score, 1),
        days_since_hard=days_since_hard,
        notes=notes,
    )
