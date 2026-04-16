"""Tests for training load model."""

from datetime import datetime, timedelta

from training_optimization.models.activity import Activity, ActivityType
from training_optimization.models.training_load import (
    activity_training_load,
    compute_load_history,
    current_load_state,
)


def _make_activity(days_ago: int, type_: ActivityType, duration_min: float, avg_hr: float = 150):
    return Activity(
        id=f"test-{days_ago}",
        date=datetime(2026, 4, 15) - timedelta(days=days_ago),
        type=type_,
        name="Test",
        distance_m=10000,
        moving_time_s=duration_min * 60,
        elapsed_time_s=duration_min * 60,
        avg_hr=avg_hr,
    )


def test_load_for_one_hour_threshold_run():
    act = _make_activity(0, ActivityType.RUN, 60, avg_hr=170)
    load = activity_training_load(act)
    # High HR, 1 hour = meaningful load
    assert 50 < load < 100


def test_load_for_strength_session():
    act = _make_activity(0, ActivityType.STRENGTH, 60, avg_hr=120)
    load = activity_training_load(act)
    # Strength has lower default IF
    assert load < 50


def test_tsb_goes_negative_with_hard_week():
    # Week of daily hard runs → fatigued
    activities = [
        _make_activity(i, ActivityType.RUN, 60, avg_hr=170) for i in range(0, 7)
    ]
    state = current_load_state(activities, datetime(2026, 4, 15))
    assert state.tsb < 0


def test_load_history_returns_daily_states():
    activities = [_make_activity(i, ActivityType.RUN, 45) for i in range(0, 7)]
    history = compute_load_history(activities)
    assert len(history) == 7
