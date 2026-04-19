"""Tests for workout recommender."""

from datetime import datetime, timedelta

from training_optimization.models.activity import Activity, ActivityType, Lap
from training_optimization.models.readiness import ReadinessScore
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


def test_peak_block_early_recommends_long_run_if_missing():
    # 26 days out, no long run in recent history — sparse easy runs keep TSB reasonable
    activities = [_run(2, 6, 36), _run(5, 6, 36), _run(9, 6, 36)]
    race_date = datetime(2026, 4, 15) + timedelta(days=26)
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date)
    assert rec.kind == WorkoutKind.LONG_RUN
    assert "Progressive build" in rec.notes


def test_peak_block_late_long_run_includes_race_pace():
    # 18 days out, no long run recently
    activities = [_run(2, 6, 36), _run(5, 6, 36), _run(9, 6, 36)]
    race_date = datetime(2026, 4, 15) + timedelta(days=18)
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date)
    assert rec.kind == WorkoutKind.LONG_RUN
    assert "race pace" in rec.notes.lower()


def test_peak_block_early_recommends_threshold_tempo():
    # 25 days out, recent long run but no quality for 3+ days
    activities = [
        _run(3, 16, 96),  # long run 3 days ago
        _run(6, 6, 36),
        _run(9, 6, 36),
    ]
    race_date = datetime(2026, 4, 15) + timedelta(days=25)
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date)
    assert rec.kind == WorkoutKind.TEMPO


def test_peak_block_late_recommends_race_pace_intervals():
    # 17 days out, recent long run, quality overdue
    activities = [
        _run(3, 14, 84),  # long run 3 days ago
        _run(6, 6, 36),
        _run(9, 6, 36),
    ]
    race_date = datetime(2026, 4, 15) + timedelta(days=17)
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date)
    assert rec.kind == WorkoutKind.RACE_PACE


def test_peak_block_cross_train_day_after_quality():
    # 20 days out, quality yesterday → don't stack another hard day
    activities = [
        _run(0, 10, 50, quality=True),
        _run(2, 14, 84),
        *[_run(i, 6, 36) for i in range(4, 10)],
    ]
    race_date = datetime(2026, 4, 15) + timedelta(days=20)
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date)
    assert rec.kind in {WorkoutKind.CROSS_TRAIN, WorkoutKind.EASY_RUN, WorkoutKind.RECOVERY}


def test_low_readiness_downgrades_hard_session_to_easy():
    # Setup that would normally recommend a quality session
    activities = [
        _run(3, 14, 84),
        _run(6, 6, 36),
        _run(9, 6, 36),
    ]
    race_date = datetime(2026, 4, 15) + timedelta(days=17)
    readiness = ReadinessScore(
        as_of=datetime(2026, 4, 15), score=45.0, days_since_hard=3, notes=("HRV -12%",)
    )
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date, readiness)
    assert rec.kind == WorkoutKind.EASY_RUN
    assert "Readiness" in rec.reason


def test_very_low_readiness_forces_recovery():
    activities = [
        _run(3, 14, 84),
        _run(6, 6, 36),
        _run(9, 6, 36),
    ]
    race_date = datetime(2026, 4, 15) + timedelta(days=17)
    readiness = ReadinessScore(
        as_of=datetime(2026, 4, 15), score=25.0, days_since_hard=3, notes=("Sick",)
    )
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date, readiness)
    assert rec.kind == WorkoutKind.RECOVERY


def test_race_day_not_downgraded_by_low_readiness():
    activities = [_run(i + 1, 8, 45) for i in range(0, 14)]
    race_date = datetime(2026, 4, 15)
    readiness = ReadinessScore(
        as_of=datetime(2026, 4, 15), score=20.0, days_since_hard=5, notes=("Nervous",)
    )
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date, readiness)
    # Race day: never downgrade, trust the training
    assert rec.kind == WorkoutKind.RACE_PACE


def test_high_readiness_preserves_hard_session():
    activities = [
        _run(3, 14, 84),
        _run(6, 6, 36),
        _run(9, 6, 36),
    ]
    race_date = datetime(2026, 4, 15) + timedelta(days=17)
    readiness = ReadinessScore(
        as_of=datetime(2026, 4, 15), score=92.0, days_since_hard=3, notes=("All green",)
    )
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date, readiness)
    assert rec.kind == WorkoutKind.RACE_PACE


def test_beyond_peak_block_falls_through_to_general_rules():
    # 30 days out → outside peak window, general rules apply
    activities = [_run(i, 5, 30) for i in range(0, 10)]
    race_date = datetime(2026, 4, 15) + timedelta(days=30)
    rec = recommend_next_workout(activities, datetime(2026, 4, 15), race_date)
    # No long run in history → general logic still recommends long run
    assert rec.kind == WorkoutKind.LONG_RUN
    # But reason should NOT mention peak block
    assert "peak block" not in rec.reason.lower()
