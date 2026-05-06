"""Generate triathlon training programs.

Tailored for an athlete with:
- Strength training background (heavy, doesn't need more lifting volume)
- Strong run base (sub 1:55 half marathon)
- New to cycling (bike just bought)
- Average swimmer (~1:50/100m)
- Prefers quality over volume (1 interval + 1 long run on running side)

Programs use 7 weekly slots:
- 1 interval/tempo run (quality)
- 1 long run (quality)
- 2 swim sessions
- 2 bike sessions (build cycling base)
- 1 strength session (upper body or full body) - optional plyo on bike day
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum


class TriathlonDistance(str, Enum):
    SPRINT = "sprint"  # 750m / 20km / 5km
    OLYMPIC = "olympic"  # 1.5km / 40km / 10km
    HALF_IRONMAN = "70.3"  # 1.9km / 90km / 21.1km
    IRONMAN = "ironman"  # 3.8km / 180km / 42.2km

    @property
    def distances(self) -> tuple[float, float, float]:
        """Returns (swim_km, bike_km, run_km)."""
        return {
            TriathlonDistance.SPRINT: (0.75, 20.0, 5.0),
            TriathlonDistance.OLYMPIC: (1.5, 40.0, 10.0),
            TriathlonDistance.HALF_IRONMAN: (1.9, 90.0, 21.1),
            TriathlonDistance.IRONMAN: (3.8, 180.0, 42.2),
        }[self]


@dataclass(frozen=True)
class Workout:
    name: str
    sport: str  # swim, bike, run, strength, rest, brick
    duration_min: int
    intensity: str  # zone1, zone2, threshold, race_pace, mixed, rest
    notes: str = ""
    weather_sensitive: bool = False  # outdoor activity that depends on weather


@dataclass(frozen=True)
class WeekPlan:
    week_number: int
    block: str
    start_date: date
    workouts: tuple[Workout, ...]
    focus: str = ""

    @property
    def total_duration_min(self) -> int:
        return sum(w.duration_min for w in self.workouts)


@dataclass(frozen=True)
class TriathlonProgram:
    distance: TriathlonDistance
    race_date: date
    start_date: date
    weeks: tuple[WeekPlan, ...]
    athlete_notes: str = ""


# === Block templates ===
# Each block defines the typical 7-day structure. Adjusted per block phase.


def _base_week(week_num: int, start: date) -> WeekPlan:
    """Base block: build aerobic base, learn to ride bike, build swim volume."""
    workouts = (
        Workout(
            "Intervall løp",
            "run",
            55,
            "threshold",
            "Eks: 3x10 min terskel eller 5x4 min, 2 km opp/ned",
        ),
        Workout(
            "Sykkel sone 1-2",
            "bike",
            60,
            "zone1",
            "Bli kjent med sykkelen. Høy kadens (90+).",
            weather_sensitive=True,
        ),
        Workout("Svøm teknikk", "swim", 45, "zone2", "Drills + 1500m steady"),
        Workout(
            "Overkropp + plyo",
            "strength",
            55,
            "mixed",
            "Push/pull + 15 min plyo (box jumps, pogo, bounding)",
        ),
        Workout(
            "Sykkel sone 1-2",
            "bike",
            75,
            "zone2",
            "Lengre tur. Inkluder noen kuper for håndtering.",
            weather_sensitive=True,
        ),
        Workout("Svøm utholdenhet", "swim", 50, "zone2", "Continuous 2000m"),
        Workout(
            "Langtur",
            "run",
            75,
            "zone2",
            "12-15 km. Siste 3 km moderat.",
            weather_sensitive=True,
        ),
    )
    return WeekPlan(
        week_number=week_num,
        block="base",
        start_date=start,
        workouts=workouts,
        focus="Aerob base + lære sykkelen + bygge svømmevolum.",
    )


def _build_week(week_num: int, start: date) -> WeekPlan:
    """Build block: introduce race-pace work and brick sessions."""
    workouts = (
        Workout(
            "Intervall løp",
            "run",
            55,
            "threshold",
            "Eks: 4x6 min terskel @ 5:00-5:10 pace",
        ),
        Workout(
            "Sykkel intervall",
            "bike",
            70,
            "threshold",
            "3x10 min FTP + zone 1 mellom. Tren håndtering.",
            weather_sensitive=True,
        ),
        Workout("Svøm intervaller", "swim", 50, "threshold", "10x100m på 2:00"),
        Workout(
            "Overkropp + plyo",
            "strength",
            55,
            "mixed",
            "Tunge løft (4-6 reps) + reaktiv plyo",
        ),
        Workout(
            "Brick (sykkel → løp)",
            "brick",
            90,
            "mixed",
            "60 min sykkel zone 2 + 20 min løp @ race pace",
            weather_sensitive=True,
        ),
        Workout(
            "Svøm race pace", "swim", 45, "race_pace", "Race-distanse hard + 500m easy"
        ),
        Workout(
            "Langtur progressiv",
            "run",
            75,
            "mixed",
            "14-16 km, siste 4 km @ race pace",
            weather_sensitive=True,
        ),
    )
    return WeekPlan(
        week_number=week_num,
        block="build",
        start_date=start,
        workouts=workouts,
        focus="Race-pace introduksjon. Brick-økter er nøkkelen.",
    )


def _peak_week(week_num: int, start: date) -> WeekPlan:
    """Peak block: race-specific intensity."""
    workouts = (
        Workout(
            "Intervall løp",
            "run",
            55,
            "race_pace",
            "8x800m @ 5k pace eller 5x1km @ race pace",
        ),
        Workout(
            "Sykkel VO2max",
            "bike",
            70,
            "race_pace",
            "5x4 min hard + zone 1 mellom",
            weather_sensitive=True,
        ),
        Workout(
            "Svøm race sim",
            "swim",
            45,
            "race_pace",
            "Race-distanse hardt etterfulgt av 500m easy",
        ),
        Workout(
            "Overkropp lett", "strength", 40, "mixed", "Lettere vekter, fokus stabilitet"
        ),
        Workout(
            "Race-pace brick",
            "brick",
            90,
            "race_pace",
            "60 min sykkel + 20 min løp - ALLE ved race pace",
            weather_sensitive=True,
        ),
        Workout("Svøm taper", "swim", 30, "zone2", "1500m steady"),
        Workout(
            "Race-pace langtur",
            "run",
            70,
            "race_pace",
            "10-12 km med 6 km @ race pace",
            weather_sensitive=True,
        ),
    )
    return WeekPlan(
        week_number=week_num,
        block="peak",
        start_date=start,
        workouts=workouts,
        focus="Race-spesifikk intensitet. Kroppen lærer race-følelsen.",
    )


def _taper_week(week_num: int, start: date, days_to_race: int) -> WeekPlan:
    """Taper block: reduce volume, keep some intensity."""
    if days_to_race <= 7:
        # Race week
        workouts = (
            Workout("Svøm shakeout", "swim", 25, "zone2", "1000m + 4x50m strides"),
            Workout(
                "Sykkel easy", "bike", 30, "zone1", "Spin out", weather_sensitive=True
            ),
            Workout("Hvile", "rest", 0, "rest", ""),
            Workout(
                "Løp + strides",
                "run",
                25,
                "zone2",
                "3 km easy + 4x30s strides",
                weather_sensitive=True,
            ),
            Workout(
                "Sykkel opener",
                "bike",
                30,
                "zone1",
                "30 min med 3x1 min fast",
                weather_sensitive=True,
            ),
            Workout("Hvile", "rest", 0, "rest", "Carb load. Utstyrssjekk."),
            Workout("RACEDAG", "race", 0, "race_pace", "Stol på treningen!"),
        )
        return WeekPlan(
            week_number=week_num,
            block="taper",
            start_date=start,
            workouts=workouts,
            focus="Race week. Mindre er mer.",
        )
    workouts = (
        Workout(
            "Intervall kort",
            "run",
            45,
            "race_pace",
            "5x2 min @ race pace",
            weather_sensitive=True,
        ),
        Workout(
            "Sykkel mod",
            "bike",
            50,
            "zone2",
            "Siste 15 min @ race pace",
            weather_sensitive=True,
        ),
        Workout("Svøm mod", "swim", 35, "zone2", "1500m + 4x100m race pace"),
        Workout("Overkropp lett", "strength", 30, "mixed", "Lett, bare bevegelse"),
        Workout(
            "Mini brick",
            "brick",
            60,
            "mixed",
            "40 min sykkel + 15 min løp",
            weather_sensitive=True,
        ),
        Workout("Svøm easy", "swim", 25, "zone1", "1000m rolig"),
        Workout(
            "Løp easy",
            "run",
            45,
            "zone2",
            "8 km rolig",
            weather_sensitive=True,
        ),
    )
    return WeekPlan(
        week_number=week_num,
        block="taper",
        start_date=start,
        workouts=workouts,
        focus="50% volum-kutt, hold litt intensitet.",
    )


def generate_triathlon_program(
    distance: TriathlonDistance,
    race_date: date,
    start_date: date | None = None,
    weeks_total: int | None = None,
) -> TriathlonProgram:
    """Generate a triathlon program tailored for the athlete profile."""
    if weeks_total is None:
        weeks_total = {
            TriathlonDistance.SPRINT: 12,
            TriathlonDistance.OLYMPIC: 16,
            TriathlonDistance.HALF_IRONMAN: 20,
            TriathlonDistance.IRONMAN: 28,
        }[distance]

    if start_date is None:
        start_date = race_date - timedelta(weeks=weeks_total)

    taper_weeks = 2
    peak_weeks = max(2, weeks_total // 8)
    build_weeks = max(3, weeks_total // 3)
    base_weeks = weeks_total - taper_weeks - peak_weeks - build_weeks

    weeks: list[WeekPlan] = []
    cursor = start_date
    week_num = 1

    for _ in range(base_weeks):
        weeks.append(_base_week(week_num, cursor))
        cursor += timedelta(weeks=1)
        week_num += 1

    for _ in range(build_weeks):
        weeks.append(_build_week(week_num, cursor))
        cursor += timedelta(weeks=1)
        week_num += 1

    for _ in range(peak_weeks):
        weeks.append(_peak_week(week_num, cursor))
        cursor += timedelta(weeks=1)
        week_num += 1

    for _ in range(taper_weeks):
        days_to_race = (race_date - cursor).days
        weeks.append(_taper_week(week_num, cursor, days_to_race))
        cursor += timedelta(weeks=1)
        week_num += 1

    return TriathlonProgram(
        distance=distance,
        race_date=race_date,
        start_date=start_date,
        weeks=tuple(weeks),
    )
