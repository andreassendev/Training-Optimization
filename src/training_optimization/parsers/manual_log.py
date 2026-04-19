"""Parse a minimal manual activity log (our own CSV format).

Unlike the Strava export parser, this reads a human-friendly format the athlete
can edit by hand:

    date,type,distance_km,duration_min,avg_hr,max_hr,elevation_m,name
    2026-04-17,run,5.0,30,150,,,Easy jog
    2026-04-15,run,10.0,55,170,185,50,3x10 min threshold

All fields except date, type, distance_km, duration_min are optional.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from training_optimization.models.activity import Activity, ActivityType

MANUAL_LOG_HEADER = [
    "date",
    "type",
    "distance_km",
    "duration_min",
    "avg_hr",
    "max_hr",
    "elevation_m",
    "name",
]


_TYPE_MAP = {
    "run": ActivityType.RUN,
    "ride": ActivityType.RIDE,
    "bike": ActivityType.RIDE,
    "cycling": ActivityType.RIDE,
    "swim": ActivityType.SWIM,
    "strength": ActivityType.STRENGTH,
    "weights": ActivityType.STRENGTH,
    "walk": ActivityType.WALK,
    "hike": ActivityType.WALK,
}


def _parse_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_manual_log(csv_path: str | Path) -> list[Activity]:
    """Parse a manual activity log into Activity objects."""
    csv_path = Path(csv_path)
    activities: list[Activity] = []

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            date = _parse_date(row.get("date", ""))
            if date is None:
                continue
            act_type = _TYPE_MAP.get(
                (row.get("type") or "").strip().lower(), ActivityType.OTHER
            )
            distance_km = _parse_float(row.get("distance_km")) or 0.0
            duration_min = _parse_float(row.get("duration_min")) or 0.0
            moving_s = duration_min * 60

            activities.append(
                Activity(
                    id=f"manual-{i}-{date.date().isoformat()}",
                    date=date,
                    type=act_type,
                    name=(row.get("name") or "").strip(),
                    distance_m=distance_km * 1000,
                    moving_time_s=moving_s,
                    elapsed_time_s=moving_s,
                    avg_hr=_parse_float(row.get("avg_hr")),
                    max_hr=_parse_float(row.get("max_hr")),
                    elevation_gain_m=_parse_float(row.get("elevation_m")) or 0.0,
                )
            )

    activities.sort(key=lambda a: a.date)
    return activities


def append_manual_log(
    csv_path: str | Path,
    *,
    date: datetime,
    activity_type: str,
    distance_km: float,
    duration_min: float,
    avg_hr: float | None = None,
    max_hr: float | None = None,
    elevation_m: float | None = None,
    name: str = "",
) -> None:
    """Append a single activity row to a manual log CSV, creating it if needed."""
    csv_path = Path(csv_path)
    file_exists = csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(MANUAL_LOG_HEADER)
        writer.writerow(
            [
                date.strftime("%Y-%m-%d"),
                activity_type,
                f"{distance_km:g}",
                f"{duration_min:g}",
                "" if avg_hr is None else f"{avg_hr:g}",
                "" if max_hr is None else f"{max_hr:g}",
                "" if elevation_m is None else f"{elevation_m:g}",
                name,
            ]
        )
