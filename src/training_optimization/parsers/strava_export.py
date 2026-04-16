"""Parse Strava bulk export (activities.csv) into Activity objects.

Strava's activities.csv has duplicate column names (e.g. 'Distance' appears twice:
first as summary distance in km, then as detailed distance in meters). We need
to use csv.reader and map by position to handle this correctly.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from training_optimization.models.activity import Activity, ActivityType


_TYPE_MAP = {
    "Run": ActivityType.RUN,
    "Ride": ActivityType.RIDE,
    "E-Bike Ride": ActivityType.RIDE,
    "Swim": ActivityType.SWIM,
    "Weight Training": ActivityType.STRENGTH,
    "Workout": ActivityType.STRENGTH,
    "Walk": ActivityType.WALK,
    "Hike": ActivityType.WALK,
}


def _parse_date(raw: str) -> datetime | None:
    for fmt in ("%b %d, %Y, %I:%M:%S %p", "%b %d, %Y, %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _find_column_indices(header: list[str]) -> dict[str, int]:
    """Map logical column names to their first occurrence in the header.

    For columns that appear twice (Distance, Elapsed Time, Moving Time), the
    first occurrence holds the summary value that Strava displays in the UI.
    """
    wanted = {
        "Activity ID",
        "Activity Date",
        "Activity Type",
        "Activity Name",
        "Distance",
        "Elapsed Time",
        "Moving Time",
        "Average Heart Rate",
        "Max Heart Rate",
        "Elevation Gain",
    }
    result: dict[str, int] = {}
    for i, col in enumerate(header):
        if col in wanted and col not in result:
            result[col] = i
    return result


def parse_strava_export(csv_path: str | Path) -> list[Activity]:
    """Parse Strava's activities.csv export file into a list of activities."""
    csv_path = Path(csv_path)
    activities: list[Activity] = []

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = _find_column_indices(header)

        for row in reader:
            if not row or len(row) <= max(idx.values(), default=0):
                continue

            date = _parse_date(row[idx.get("Activity Date", -1)] if "Activity Date" in idx else "")
            if date is None:
                continue

            act_type = _TYPE_MAP.get(
                row[idx["Activity Type"]] if "Activity Type" in idx else "",
                ActivityType.OTHER,
            )

            # First Distance column is summary (km in Strava export)
            distance_km = _parse_float(row[idx["Distance"]]) if "Distance" in idx else 0

            activities.append(
                Activity(
                    id=row[idx["Activity ID"]] if "Activity ID" in idx else "",
                    date=date,
                    type=act_type,
                    name=row[idx["Activity Name"]] if "Activity Name" in idx else "",
                    distance_m=(distance_km or 0) * 1000,
                    moving_time_s=_parse_float(
                        row[idx["Moving Time"]] if "Moving Time" in idx else None
                    )
                    or 0,
                    elapsed_time_s=_parse_float(
                        row[idx["Elapsed Time"]] if "Elapsed Time" in idx else None
                    )
                    or 0,
                    avg_hr=_parse_float(
                        row[idx["Average Heart Rate"]]
                        if "Average Heart Rate" in idx
                        else None
                    ),
                    max_hr=_parse_float(
                        row[idx["Max Heart Rate"]] if "Max Heart Rate" in idx else None
                    ),
                    elevation_gain_m=_parse_float(
                        row[idx["Elevation Gain"]] if "Elevation Gain" in idx else None
                    )
                    or 0,
                )
            )

    activities.sort(key=lambda a: a.date)
    return activities
