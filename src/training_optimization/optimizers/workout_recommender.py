"""Recommend the next workout to maximize progression.

Logic:
1. If TSB is very negative (overloaded) → recovery.
2. If race is within taper window → taper logic.
3. If no long run in 7+ days → long run.
4. If no quality in 4+ days and body is fresh → intervals or tempo.
5. Otherwise → easy run or cross-training.

The goal isn't to fill time with volume, but to place the *next* workout where
it gives the best marginal fitness gain given current state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from training_optimization.models.activity import Activity
from training_optimization.models.fitness_state import FitnessState, compute_fitness_state
from training_optimization.models.training_load import LoadState, current_load_state


class WorkoutKind(str, Enum):
    RECOVERY = "recovery"
    EASY_RUN = "easy_run"
    LONG_RUN = "long_run"
    TEMPO = "tempo"
    INTERVALS = "intervals"
    RACE_PACE = "race_pace"
    CROSS_TRAIN = "cross_train"
    REST = "rest"


@dataclass(frozen=True)
class Recommendation:
    kind: WorkoutKind
    reason: str
    target_distance_km: float | None = None
    target_duration_min: float | None = None
    target_pace_s_per_km: float | None = None
    notes: str = ""


def _days_until_race(as_of: datetime, race_date: datetime | None) -> int | None:
    if race_date is None:
        return None
    return (race_date.date() - as_of.date()).days


def _taper_recommendation(
    days_to_race: int, fitness: FitnessState, load: LoadState
) -> Recommendation | None:
    """Taper logic for last 14 days before race."""
    if days_to_race > 14 or days_to_race < 0:
        return None

    if days_to_race == 0:
        return Recommendation(
            kind=WorkoutKind.RACE_PACE,
            reason="Race day",
            notes="Go race. Trust the training.",
        )

    if days_to_race == 1:
        return Recommendation(
            kind=WorkoutKind.REST,
            reason="Day before race",
            notes="Full rest. Carb load. Legs up.",
        )

    if days_to_race == 2:
        return Recommendation(
            kind=WorkoutKind.EASY_RUN,
            target_distance_km=3,
            target_pace_s_per_km=360,
            reason="Shakeout 2 days before race",
            notes="3 km easy + 4x30s strides",
        )

    if days_to_race <= 4:
        return Recommendation(
            kind=WorkoutKind.EASY_RUN,
            target_distance_km=5,
            target_pace_s_per_km=360,
            reason="Final taper week - keep legs loose",
        )

    if days_to_race <= 7:
        # One final sharpener
        if fitness.days_since_quality >= 3:
            return Recommendation(
                kind=WorkoutKind.INTERVALS,
                target_distance_km=6,
                reason="Race week sharpener",
                notes="Short intervals (5x2min) at race pace to keep legs fast",
            )
        return Recommendation(
            kind=WorkoutKind.EASY_RUN,
            target_distance_km=6,
            reason="Taper week - easy run",
        )

    # 8-14 days out: one last quality block + light long run
    if days_to_race >= 10 and fitness.days_since_long_run >= 6:
        return Recommendation(
            kind=WorkoutKind.LONG_RUN,
            target_distance_km=max(12, fitness.recent_long_run_km * 0.75),
            reason="Final long run before taper intensifies",
            notes="Include 4-5 km at race pace near the end",
        )

    if fitness.days_since_quality >= 4:
        return Recommendation(
            kind=WorkoutKind.TEMPO,
            target_distance_km=10,
            reason="Pre-taper quality session",
            notes="5-6 km at race pace to dial in pacing",
        )

    return Recommendation(
        kind=WorkoutKind.EASY_RUN,
        target_distance_km=7,
        reason="Active recovery during taper",
    )


def recommend_next_workout(
    activities: list[Activity],
    as_of: datetime,
    race_date: datetime | None = None,
) -> Recommendation:
    """Recommend the next workout based on current state and goals."""
    fitness = compute_fitness_state(activities, as_of)
    load = current_load_state(activities, as_of)

    days_to_race = _days_until_race(as_of, race_date)

    # Taper logic overrides everything
    if days_to_race is not None and 0 <= days_to_race <= 14:
        taper = _taper_recommendation(days_to_race, fitness, load)
        if taper is not None:
            return taper

    # Severe fatigue → recovery
    if load.tsb < -25:
        return Recommendation(
            kind=WorkoutKind.RECOVERY,
            reason=f"Heavily overloaded (TSB {load.tsb:.0f}). Rest or easy cross-train.",
            notes="Swim or zone 1 cycling. No running today.",
        )

    # Moderate fatigue → easy only
    if load.tsb < -10 and fitness.days_since_quality < 2:
        return Recommendation(
            kind=WorkoutKind.EASY_RUN,
            target_distance_km=6,
            target_pace_s_per_km=360,
            reason=f"Fatigued after recent quality (TSB {load.tsb:.0f})",
            notes="Active recovery run, keep HR low",
        )

    # Missing long run
    if fitness.days_since_long_run >= 7:
        target = max(14, fitness.recent_long_run_km + 1)  # progressive overload
        return Recommendation(
            kind=WorkoutKind.LONG_RUN,
            target_distance_km=min(target, 22),  # cap at half marathon distance
            target_pace_s_per_km=fitness.recent_threshold_pace_s_per_km * 1.15
            if fitness.recent_threshold_pace_s_per_km
            else 360,
            reason=f"{fitness.days_since_long_run} days since last long run",
            notes="Build aerobic endurance. Keep most of it conversational.",
        )

    # Missing quality
    if fitness.days_since_quality >= 4 and load.tsb >= -5:
        return Recommendation(
            kind=WorkoutKind.INTERVALS,
            target_distance_km=10,
            target_pace_s_per_km=fitness.recent_threshold_pace_s_per_km
            if fitness.recent_threshold_pace_s_per_km
            else 300,
            reason=f"{fitness.days_since_quality} days since last quality session",
            notes="3x10min at threshold OR 5x1km intervals. Progression driver.",
        )

    # Day after quality → cross-train
    if fitness.days_since_quality <= 1:
        return Recommendation(
            kind=WorkoutKind.CROSS_TRAIN,
            target_duration_min=60,
            reason="Day after quality session",
            notes="Zone 1 cycling or swim. Build base without leg impact.",
        )

    # Default: easy run
    return Recommendation(
        kind=WorkoutKind.EASY_RUN,
        target_distance_km=7,
        target_pace_s_per_km=360,
        reason="Maintain aerobic base between quality sessions",
    )
