"""Tests for fitness state computation."""

from datetime import datetime, timedelta

from training_optimization.models.activity import Activity, ActivityType, Lap
from training_optimization.models.fitness_state import (
    compute_efficiency_factor,
    compute_fitness_state,
    vdot_from_race,
)


def _make_run(
    date: datetime,
    distance_km: float,
    time_min: float,
    avg_hr: float | None = 160,
    laps: tuple[Lap, ...] = (),
) -> Activity:
    return Activity(
        id=f"test-{date.isoformat()}",
        date=date,
        type=ActivityType.RUN,
        name="Test run",
        distance_m=distance_km * 1000,
        moving_time_s=time_min * 60,
        elapsed_time_s=time_min * 60,
        avg_hr=avg_hr,
        laps=laps,
    )


def test_vdot_from_known_race():
    # 5 km in 20 min ≈ VDOT 50
    vdot = vdot_from_race(5.0, 20 * 60)
    assert 48 < vdot < 52


def test_vdot_half_marathon_1h55():
    # 21.1 km in 1:55 (tested value from Daniels formula)
    vdot = vdot_from_race(21.1, 115 * 60)
    assert 36 < vdot < 42


def test_efficiency_factor_rejects_short_run():
    act = _make_run(datetime(2026, 3, 1), distance_km=2, time_min=12)
    assert compute_efficiency_factor(act) is None


def test_efficiency_factor_computes_for_aerobic_run():
    act = _make_run(datetime(2026, 3, 1), distance_km=10, time_min=60, avg_hr=150)
    ef = compute_efficiency_factor(act)
    # 10000 m / (150 * 60) = 1.11 m/beat
    assert ef is not None
    assert 1.0 < ef < 1.2


def test_fitness_state_tracks_ef_trend():
    now = datetime(2026, 4, 1)
    # Older runs: slower / more effort
    old_runs = [
        _make_run(now - timedelta(days=45 + i * 3), 8, 52, avg_hr=165)
        for i in range(5)
    ]
    # Recent runs: faster / less effort (fitter)
    new_runs = [
        _make_run(now - timedelta(days=i * 3), 8, 48, avg_hr=155)
        for i in range(5)
    ]

    state = compute_fitness_state(old_runs + new_runs, now)
    assert state.ef_trend_4w > 0


def test_fitness_state_days_since_long_run():
    now = datetime(2026, 4, 15)
    long_run = _make_run(now - timedelta(days=5), 16, 95)
    state = compute_fitness_state([long_run], now)
    assert state.days_since_long_run == 5
    assert state.recent_long_run_km == 16
