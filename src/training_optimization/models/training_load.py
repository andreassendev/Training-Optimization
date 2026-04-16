"""Banister impulse-response model for training load.

CTL (Chronic Training Load): fitness, 42-day exponential average.
ATL (Acute Training Load): fatigue, 7-day exponential average.
TSB (Training Stress Balance): form, CTL - ATL. Positive = fresh, negative = tired.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import exp

from training_optimization.models.activity import Activity, ActivityType


@dataclass(frozen=True)
class LoadState:
    as_of: date
    ctl: float  # fitness
    atl: float  # fatigue
    tsb: float  # form (ctl - atl)

    @property
    def zone(self) -> str:
        """Simple readiness zone based on TSB."""
        if self.tsb > 15:
            return "detrained"
        if self.tsb > 5:
            return "fresh"
        if self.tsb > -10:
            return "neutral"
        if self.tsb > -25:
            return "fatigued"
        return "overloaded"


def activity_training_load(activity: Activity) -> float:
    """Estimate training load (TSS-equivalent) for a single activity.

    Without power data, we use a duration + intensity factor based on HR.
    A 1-hour threshold effort ≈ 100 units.
    """
    if activity.moving_time_s <= 0:
        return 0.0

    duration_hours = activity.moving_time_s / 3600

    # Default intensity factor by activity type
    default_if = {
        ActivityType.RUN: 0.75,
        ActivityType.RIDE: 0.60,
        ActivityType.SWIM: 0.70,
        ActivityType.STRENGTH: 0.50,
        ActivityType.WALK: 0.40,
        ActivityType.OTHER: 0.50,
    }.get(activity.type, 0.5)

    # If we have HR, adjust intensity (assume max HR 195)
    # A better model would use per-athlete max HR
    intensity_factor = default_if
    if activity.avg_hr is not None and activity.avg_hr > 0:
        # HR as fraction of max; cap at 1.0
        assumed_max = 195
        hr_fraction = min(activity.avg_hr / assumed_max, 1.0)
        intensity_factor = hr_fraction

    # Quality sessions with fast laps bump intensity
    if activity.is_quality_session():
        intensity_factor = max(intensity_factor, 0.85)

    return duration_hours * (intensity_factor ** 2) * 100


def compute_load_history(
    activities: list[Activity], ctl_tau: int = 42, atl_tau: int = 7
) -> list[LoadState]:
    """Compute daily CTL/ATL/TSB values from activity history.

    Uses exponentially weighted moving averages (Banister model).
    """
    if not activities:
        return []

    # Aggregate daily load
    sorted_acts = sorted(activities, key=lambda a: a.date)
    daily_load: dict[date, float] = {}
    for act in sorted_acts:
        d = act.date.date()
        daily_load[d] = daily_load.get(d, 0) + activity_training_load(act)

    # Iterate day by day from first activity to last
    start = min(daily_load.keys())
    end = max(daily_load.keys())

    ctl_decay = exp(-1 / ctl_tau)
    atl_decay = exp(-1 / atl_tau)

    ctl, atl = 0.0, 0.0
    history: list[LoadState] = []
    current = start
    while current <= end:
        load = daily_load.get(current, 0.0)
        ctl = ctl * ctl_decay + load * (1 - ctl_decay)
        atl = atl * atl_decay + load * (1 - atl_decay)
        history.append(LoadState(as_of=current, ctl=ctl, atl=atl, tsb=ctl - atl))
        current += timedelta(days=1)

    return history


def current_load_state(activities: list[Activity], as_of: datetime) -> LoadState:
    """Get current CTL/ATL/TSB as of a specific date."""
    history = compute_load_history(activities)
    target = as_of.date()

    # Find the latest state at or before target date
    candidates = [h for h in history if h.as_of <= target]
    if not candidates:
        return LoadState(as_of=target, ctl=0, atl=0, tsb=0)
    return candidates[-1]
