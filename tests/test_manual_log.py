"""Tests for manual log parser."""

from datetime import datetime
from pathlib import Path

from training_optimization.models.activity import ActivityType
from training_optimization.parsers.manual_log import (
    append_manual_log,
    parse_manual_log,
)


def test_parse_empty_log(tmp_path: Path):
    csv = tmp_path / "log.csv"
    csv.write_text("date,type,distance_km,duration_min,avg_hr,max_hr,elevation_m,name\n")
    assert parse_manual_log(csv) == []


def test_parse_single_run(tmp_path: Path):
    csv = tmp_path / "log.csv"
    csv.write_text(
        "date,type,distance_km,duration_min,avg_hr,max_hr,elevation_m,name\n"
        "2026-04-17,run,5.0,30,150,,,Easy jog\n"
    )
    activities = parse_manual_log(csv)
    assert len(activities) == 1
    act = activities[0]
    assert act.type == ActivityType.RUN
    assert act.distance_km == 5.0
    assert act.moving_time_s == 30 * 60
    assert act.avg_hr == 150
    assert act.max_hr is None
    assert act.name == "Easy jog"


def test_parse_skips_invalid_date(tmp_path: Path):
    csv = tmp_path / "log.csv"
    csv.write_text(
        "date,type,distance_km,duration_min,avg_hr,max_hr,elevation_m,name\n"
        "not-a-date,run,5.0,30,150,,,Broken\n"
        "2026-04-17,run,5.0,30,150,,,Good\n"
    )
    activities = parse_manual_log(csv)
    assert len(activities) == 1
    assert activities[0].name == "Good"


def test_append_creates_file_with_header(tmp_path: Path):
    csv = tmp_path / "log.csv"
    append_manual_log(
        csv,
        date=datetime(2026, 4, 17),
        activity_type="run",
        distance_km=5.0,
        duration_min=30.0,
        avg_hr=150,
        name="Easy jog",
    )
    content = csv.read_text()
    assert content.startswith("date,type,distance_km,duration_min")
    assert "2026-04-17,run,5,30,150,,,Easy jog" in content


def test_append_twice_reuses_header(tmp_path: Path):
    csv = tmp_path / "log.csv"
    append_manual_log(
        csv,
        date=datetime(2026, 4, 17),
        activity_type="run",
        distance_km=5.0,
        duration_min=30.0,
    )
    append_manual_log(
        csv,
        date=datetime(2026, 4, 18),
        activity_type="run",
        distance_km=6.0,
        duration_min=36.0,
    )
    lines = csv.read_text().strip().splitlines()
    assert len(lines) == 3  # header + 2 rows


def test_roundtrip_append_then_parse(tmp_path: Path):
    csv = tmp_path / "log.csv"
    append_manual_log(
        csv,
        date=datetime(2026, 4, 17),
        activity_type="run",
        distance_km=5.0,
        duration_min=30.0,
        avg_hr=150,
    )
    activities = parse_manual_log(csv)
    assert len(activities) == 1
    assert activities[0].type == ActivityType.RUN
    assert activities[0].distance_km == 5.0
    assert activities[0].avg_hr == 150
