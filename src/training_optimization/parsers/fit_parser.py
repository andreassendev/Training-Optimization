"""Parse Garmin/Strava .fit and .fit.gz files into Activity objects."""

from __future__ import annotations

import gzip
from datetime import datetime, timezone
from pathlib import Path

import fitparse

from training_optimization.models.activity import Activity, ActivityType, Lap


def _activity_type_from_sport(sport: str | None) -> ActivityType:
    if not sport:
        return ActivityType.OTHER
    s = sport.lower()
    mapping = {
        "running": ActivityType.RUN,
        "cycling": ActivityType.RIDE,
        "swimming": ActivityType.SWIM,
        "strength_training": ActivityType.STRENGTH,
        "training": ActivityType.STRENGTH,
        "walking": ActivityType.WALK,
    }
    return mapping.get(s, ActivityType.OTHER)


def _open_fit(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rb")
    return open(path, "rb")


def parse_fit_file(path: str | Path) -> Activity | None:
    """Parse a .fit or .fit.gz file into an Activity.

    Returns None if the file cannot be parsed or contains no records.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    with _open_fit(path) as f:
        fit = fitparse.FitFile(f)

        session = None
        for msg in fit.get_messages("session"):
            session = {field.name: field.value for field in msg.fields}
            break

        laps: list[Lap] = []
        for msg in fit.get_messages("lap"):
            data = {field.name: field.value for field in msg.fields}
            distance = data.get("total_distance") or 0
            duration = data.get("total_timer_time") or 0
            if distance <= 0 or duration <= 0:
                continue
            laps.append(
                Lap(
                    distance_m=float(distance),
                    duration_s=float(duration),
                    avg_hr=data.get("avg_heart_rate"),
                    max_hr=data.get("max_heart_rate"),
                )
            )

        if session is None:
            return None

        sport = session.get("sport")
        start_time = session.get("start_time") or datetime.now(timezone.utc)
        distance = float(session.get("total_distance") or 0)
        moving_time = float(session.get("total_timer_time") or 0)
        elapsed_time = float(session.get("total_elapsed_time") or moving_time)

        return Activity(
            id=path.stem.replace(".fit", ""),
            date=start_time if isinstance(start_time, datetime) else datetime.now(timezone.utc),
            type=_activity_type_from_sport(str(sport) if sport else None),
            name=path.stem,
            distance_m=distance,
            moving_time_s=moving_time,
            elapsed_time_s=elapsed_time,
            avg_hr=session.get("avg_heart_rate"),
            max_hr=session.get("max_heart_rate"),
            elevation_gain_m=float(session.get("total_ascent") or 0),
            avg_cadence=session.get("avg_cadence"),
            laps=tuple(laps),
        )
