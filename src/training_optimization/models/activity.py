"""Core data model for a single training activity."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ActivityType(str, Enum):
    RUN = "run"
    RIDE = "ride"
    SWIM = "swim"
    STRENGTH = "strength"
    WALK = "walk"
    OTHER = "other"


@dataclass(frozen=True)
class Lap:
    """A single lap/split within an activity."""

    distance_m: float
    duration_s: float
    avg_hr: float | None = None
    max_hr: float | None = None
    avg_pace_s_per_km: float | None = None

    @property
    def pace_s_per_km(self) -> float:
        if self.avg_pace_s_per_km is not None:
            return self.avg_pace_s_per_km
        if self.distance_m <= 0:
            return 0.0
        return self.duration_s / (self.distance_m / 1000)


@dataclass(frozen=True)
class Activity:
    """A single training activity with optional detailed data."""

    id: str
    date: datetime
    type: ActivityType
    name: str
    distance_m: float
    moving_time_s: float
    elapsed_time_s: float
    avg_hr: float | None = None
    max_hr: float | None = None
    elevation_gain_m: float = 0.0
    avg_cadence: float | None = None
    laps: tuple[Lap, ...] = field(default_factory=tuple)

    @property
    def distance_km(self) -> float:
        return self.distance_m / 1000

    @property
    def avg_pace_s_per_km(self) -> float:
        if self.distance_m <= 0:
            return 0.0
        return self.moving_time_s / (self.distance_m / 1000)

    @property
    def avg_pace_min_per_km(self) -> float:
        return self.avg_pace_s_per_km / 60

    def is_quality_session(self, pace_threshold_s_per_km: float = 330) -> bool:
        """True if activity has intervals, tempo work, or sustained fast pace.

        Checks three signals (in priority order):
        1. Laps faster than threshold (most reliable when available).
        2. Activity name hints (intervall, tempo, NxM, progressive, etc).
        3. Average pace faster than threshold on a run of 4km+ with elevated HR.
        """
        if self.type != ActivityType.RUN:
            return False

        # Lap-based detection (requires .fit file data)
        if self.laps and any(
            lap.pace_s_per_km < pace_threshold_s_per_km and lap.distance_m > 500
            for lap in self.laps
        ):
            return True

        # Name-based detection
        name_lower = self.name.lower()
        keywords = ("interval", "intervall", "tempo", "progressiv", "threshold", "terskel")
        if any(kw in name_lower for kw in keywords):
            return True
        # Pattern like "3x10", "5x4", "4x1km"
        import re
        if re.search(r"\d+\s*x\s*\d+", name_lower):
            return True

        # Pace-based detection (when no lap data)
        if (
            self.distance_km >= 4
            and self.avg_pace_s_per_km > 0
            and self.avg_pace_s_per_km < pace_threshold_s_per_km
        ):
            return True

        return False

    def is_long_run(self, min_distance_km: float = 14.0) -> bool:
        return self.type == ActivityType.RUN and self.distance_km >= min_distance_km
