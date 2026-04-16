"""Tests for workout recommender."""

from datetime import datetime, timedelta

from training_optimization.models.activity import Activity, ActivityType, Lap
from training_optimization.optimizers.workout_recommender import (
    WorkoutKind,
    recommend_next_workout,
)


def _run(days_ago: int, distance_km: float, time_min: float, quality: bool = False):
    laps = ()
    if quality:
        # Create a fast lap to mark as quality
        laps = (Lap(distance_m=2000, duration_s=10 * 60, avg_hr=180),)
    return Activity(
        id=f"test-{days_ago}",
        date=datetime(2026, 4, 15) - timedelta(days=days_ago),
        type=ActivityType.RUN,
        name="Test",
        distance_m=distance_km * 1000,
        moving_time_s=time_min * 60,
        elapsed_time_s=time_min * 60,
        avg_hr=160,
        laps=laps,
    )


def test_recommends_long_run_if_missing():
    # Only short runs, no long run
    activities = [_run(i, 5, 30) for i in range(0, 10)]
    rec = recommend_next_workout(activities, datetime(2026, 4, 15))
    assert rec.kind == WorkoutKind.LONG_RUN


def test_recommends_recovery_day_after_quality():
    activities = [
        _run(0, 10, 50, quality=True),  # Yesterday's quality
        _run(2, 16, 96),  # Recent long run
    ]
    rec = recommend_next_workout(activities, datetime(2026, 4, 15))
    # Should avoid another hard session
    assert rec.kind in {WorkoutKind.CROSS_TRAIN, WorkoutKind.EASY_RUN, WorkoutKind.RECOVERY}


def test_taper_for_race_day():
    activities = [_run(i, 8, 45) for i in range(0, 14)]
    race_date = datetime(2026, 4, 15)  # today
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date)
    assert rec.kind == WorkoutKind.RACE_PACE


def test_taper_day_before_race():
    activities = [_run(i + 1, 8, 45) for i in range(0, 14)]
    race_date = datetime(2026, 4, 16)
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date)
    assert rec.kind == WorkoutKind.REST


def test_recovery_when_overloaded():
    # 10 days of heavy training to build fatigue
    activities = [_run(i, 15, 90, quality=True) for i in range(0, 10)]
    rec = recommend_next_workout(activities, datetime(2026, 4, 15))
    # Should recommend recovery or easy, not more quality
    assert rec.kind in {WorkoutKind.RECOVERY, WorkoutKind.EASY_RUN, WorkoutKind.CROSS_TRAIN}
