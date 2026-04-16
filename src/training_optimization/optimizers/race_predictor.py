"""Predict race times from current fitness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from training_optimization.models.activity import Activity
from training_optimization.models.fitness_state import (
    compute_fitness_state,
    vdot_to_race_time,
)


@dataclass(frozen=True)
class RacePrediction:
    distance_km: float
    time_seconds: float
    vdot: float

    @property
    def time_str(self) -> str:
        t = int(self.time_seconds)
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @property
    def pace_s_per_km(self) -> float:
        if self.distance_km <= 0:
            return 0
        return self.time_seconds / self.distance_km

    @property
    def pace_str(self) -> str:
        p = int(self.pace_s_per_km)
        return f"{p // 60}:{p % 60:02d} /km"


def predict_race(
    activities: list[Activity], distance_km: float, as_of: datetime
) -> RacePrediction:
    """Predict race time for given distance based on recent training."""
    fitness = compute_fitness_state(activities, as_of)
    time_s = vdot_to_race_time(fitness.vdot_estimate, distance_km)
    return RacePrediction(
        distance_km=distance_km, time_seconds=time_s, vdot=fitness.vdot_estimate
    )
