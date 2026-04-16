"""Compute current fitness state from recent activities.

Key metrics for progression tracking:
- Efficiency Factor (EF): distance per heartbeat. Higher = fitter.
- Aerobic Threshold Pace: pace sustainable at ~85% max HR.
- VDOT estimate: Jack Daniels' race-equivalency metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from training_optimization.models.activity import Activity, ActivityType


@dataclass(frozen=True)
class FitnessState:
    """Snapshot of current running fitness."""

    as_of: datetime
    ef_running: float  # meters per heartbeat (running only)
    ef_trend_4w: float  # change in EF over last 4 weeks (positive = improving)
    vdot_estimate: float
    recent_long_run_km: float
    recent_threshold_pace_s_per_km: float | None
    weekly_run_km: float
    days_since_long_run: int
    days_since_quality: int

    def race_time_estimate(self, distance_km: float) -> float | None:
        """Estimate race time in seconds for given distance using VDOT."""
        if self.vdot_estimate <= 0:
            return None
        return vdot_to_race_time(self.vdot_estimate, distance_km)


def compute_efficiency_factor(activity: Activity) -> float | None:
    """EF = meters per heartbeat. Higher = better fitness at same effort.

    Only meaningful for aerobic runs (not intervals, not sprints).
    """
    if activity.type != ActivityType.RUN:
        return None
    if activity.avg_hr is None or activity.avg_hr <= 0:
        return None
    if activity.distance_m <= 0 or activity.moving_time_s <= 0:
        return None
    # Skip if too short or likely intervals (high HR on short run)
    if activity.distance_km < 4:
        return None

    beats = activity.avg_hr * (activity.moving_time_s / 60)
    return activity.distance_m / beats


def vdot_from_race(distance_km: float, time_s: float) -> float:
    """Jack Daniels' VDOT estimate from a race performance.

    Formula from Daniels' Running Formula (2nd ed).
    """
    if distance_km <= 0 or time_s <= 0:
        return 0.0

    t_min = time_s / 60
    v_m_per_min = (distance_km * 1000) / t_min

    # Percent of VO2max sustained for this duration
    pct_vo2max = (
        0.8
        + 0.1894393 * pow(2.71828, -0.012778 * t_min)
        + 0.2989558 * pow(2.71828, -0.1932605 * t_min)
    )

    # VO2 demand for this velocity
    vo2_demand = -4.60 + 0.182258 * v_m_per_min + 0.000104 * v_m_per_min * v_m_per_min

    vdot = vo2_demand / pct_vo2max
    return round(vdot, 1)


def vdot_to_race_time(vdot: float, distance_km: float) -> float:
    """Invert VDOT to estimate race time for distance (seconds).

    Uses iterative search since the formula isn't directly invertible.
    """
    # Binary search for time that matches this VDOT at this distance
    lo, hi = 60.0, 36000.0  # 1 min to 10 hours
    for _ in range(60):
        mid = (lo + hi) / 2
        computed_vdot = vdot_from_race(distance_km, mid)
        if computed_vdot > vdot:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def estimate_vdot_from_recent(
    activities: list[Activity], as_of: datetime, lookback_days: int = 42
) -> float:
    """Estimate current VDOT from recent quality efforts.

    Uses the best lap-level performance across recent quality sessions.
    """
    cutoff = as_of - timedelta(days=lookback_days)
    best_vdot = 0.0

    for act in activities:
        if act.date < cutoff or act.type != ActivityType.RUN:
            continue
        # Check full activity as race-like effort
        if act.is_long_run(min_distance_km=10) and act.avg_pace_s_per_km < 360:
            v = vdot_from_race(act.distance_km, act.moving_time_s)
            if v > best_vdot:
                best_vdot = v
        # Check fast lap segments (>= 2km, < 5:00/km)
        for lap in act.laps:
            if lap.distance_m < 2000 or lap.pace_s_per_km > 300:
                continue
            v = vdot_from_race(lap.distance_m / 1000, lap.duration_s)
            if v > best_vdot:
                best_vdot = v

    return best_vdot


def compute_fitness_state(activities: list[Activity], as_of: datetime) -> FitnessState:
    """Compute current fitness state from activity history."""
    # EF over recent easy/steady runs
    recent_4w = [
        a
        for a in activities
        if a.date >= as_of - timedelta(days=28) and a.type == ActivityType.RUN
    ]
    previous_4w = [
        a
        for a in activities
        if as_of - timedelta(days=56) <= a.date < as_of - timedelta(days=28)
        and a.type == ActivityType.RUN
    ]

    efs_recent = [ef for a in recent_4w if (ef := compute_efficiency_factor(a)) is not None]
    efs_previous = [ef for a in previous_4w if (ef := compute_efficiency_factor(a)) is not None]

    avg_ef = sum(efs_recent) / len(efs_recent) if efs_recent else 0.0
    avg_ef_prev = sum(efs_previous) / len(efs_previous) if efs_previous else avg_ef
    ef_trend = avg_ef - avg_ef_prev

    vdot = estimate_vdot_from_recent(activities, as_of)

    # Weekly volume (running only)
    week_ago = as_of - timedelta(days=7)
    weekly_km = sum(a.distance_km for a in activities if a.date >= week_ago and a.type == ActivityType.RUN)

    # Recent long run
    long_runs = [a for a in recent_4w if a.is_long_run()]
    recent_long_km = max((a.distance_km for a in long_runs), default=0.0)

    # Days since events
    last_long = max((a.date for a in activities if a.is_long_run()), default=None)
    last_quality = max(
        (a.date for a in activities if a.is_quality_session()), default=None
    )
    days_since_long = (as_of - last_long).days if last_long else 999
    days_since_quality = (as_of - last_quality).days if last_quality else 999

    # Threshold pace: fastest pace sustained for 10+ min in recent quality
    threshold_pace = None
    for act in recent_4w:
        for lap in act.laps:
            if lap.duration_s >= 600 and lap.distance_m >= 2000:
                if threshold_pace is None or lap.pace_s_per_km < threshold_pace:
                    threshold_pace = lap.pace_s_per_km

    return FitnessState(
        as_of=as_of,
        ef_running=avg_ef,
        ef_trend_4w=ef_trend,
        vdot_estimate=vdot,
        recent_long_run_km=recent_long_km,
        recent_threshold_pace_s_per_km=threshold_pace,
        weekly_run_km=weekly_km,
        days_since_long_run=days_since_long,
        days_since_quality=days_since_quality,
    )
