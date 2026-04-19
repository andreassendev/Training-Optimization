"""Tests for readiness score computation."""

from datetime import datetime, timedelta

from training_optimization.models.activity import Activity, ActivityType, Lap
from training_optimization.models.readiness import (
    ReadinessInputs,
    compute_readiness,
)


def _run(days_ago: int, distance_km: float, time_min: float, quality: bool = False):
    laps = ()
    if quality:
        laps = (Lap(distance_m=2000, duration_s=10 * 60, avg_hr=180),)
    return Activity(
        id=f"test-{days_ago}",
        date=datetime(2026, 4, 19) - timedelta(days=days_ago),
        type=ActivityType.RUN,
        name="Test",
        distance_m=distance_km * 1000,
        moving_time_s=time_min * 60,
        elapsed_time_s=time_min * 60,
        avg_hr=160,
        laps=laps,
    )


def test_no_inputs_and_no_history_yields_mid_score():
    score = compute_readiness([], datetime(2026, 4, 19))
    # Only recency component fires; no history → 100 for recency weight
    assert score.score == 100.0
    assert score.zone == "ready"


def test_hard_session_today_lowers_score():
    activities = [_run(0, 10, 50, quality=True)]
    score = compute_readiness(activities, datetime(2026, 4, 19))
    assert score.days_since_hard == 0
    assert score.zone in {"recover", "caution"}


def test_hrv_suppressed_drops_score():
    activities = [_run(3, 16, 96)]  # long run 3 days ago
    inputs = ReadinessInputs(hrv_rmssd=45.0, hrv_baseline=60.0)  # -25% deviation
    score = compute_readiness(activities, datetime(2026, 4, 19), inputs)
    # HRV suppressed, but recency is +3d fresh
    assert score.score < 80
    assert any("HRV" in n for n in score.notes)


def test_all_signals_green_produces_high_score():
    activities = [_run(5, 10, 60)]
    inputs = ReadinessInputs(
        hrv_rmssd=65.0,
        hrv_baseline=60.0,  # +8.3%
        resting_hr=48.0,
        rhr_baseline=50.0,  # -2 bpm
        sleep_hours=8.5,
        subjective_score=9,
    )
    score = compute_readiness(activities, datetime(2026, 4, 19), inputs)
    assert score.score >= 90
    assert score.zone == "ready"


def test_elevated_rhr_lowers_score():
    activities = [_run(4, 10, 60)]
    inputs = ReadinessInputs(resting_hr=58.0, rhr_baseline=50.0)  # +8 bpm
    score = compute_readiness(activities, datetime(2026, 4, 19), inputs)
    assert any("RHR" in n and "elevated" in n for n in score.notes)
    assert score.score < 80


def test_short_sleep_lowers_score():
    activities = [_run(4, 10, 60)]
    inputs = ReadinessInputs(sleep_hours=4.0)
    score = compute_readiness(activities, datetime(2026, 4, 19), inputs)
    assert any("short" in n for n in score.notes)


def test_subjective_score_influences_output():
    activities = [_run(4, 10, 60)]
    low = compute_readiness(
        activities, datetime(2026, 4, 19), ReadinessInputs(subjective_score=3)
    )
    high = compute_readiness(
        activities, datetime(2026, 4, 19), ReadinessInputs(subjective_score=9)
    )
    assert high.score > low.score


def test_missing_components_redistribute_weights():
    # Only recency + subjective: weights should normalize
    activities = [_run(5, 10, 60)]
    score = compute_readiness(
        activities, datetime(2026, 4, 19), ReadinessInputs(subjective_score=10)
    )
    # Recency=100, subjective=100 → score 100 regardless of missing weights
    assert score.score == 100.0
