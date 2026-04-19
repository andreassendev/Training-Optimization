"""Command-line interface for training optimization."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from training_optimization.models.fitness_state import compute_fitness_state
from training_optimization.models.readiness import ReadinessInputs, compute_readiness
from training_optimization.models.training_load import (
    compute_load_history,
    current_load_state,
)
from training_optimization.optimizers.race_predictor import predict_race
from training_optimization.optimizers.workout_recommender import recommend_next_workout
from training_optimization.parsers.manual_log import append_manual_log, parse_manual_log
from training_optimization.parsers.strava_export import parse_strava_export

console = Console()

MANUAL_LOG_FILENAME = "manual_log.csv"
STRAVA_FILENAME = "activities.csv"


def _resolve_data_files(data_path: Path) -> tuple[Path | None, Path | None]:
    """Return (strava_csv, manual_csv) from either a file or a directory."""
    if data_path.is_file():
        # Treat a single file as Strava export by default
        return data_path, None
    strava = data_path / STRAVA_FILENAME
    manual = data_path / MANUAL_LOG_FILENAME
    return (strava if strava.exists() else None, manual if manual.exists() else None)


def _load_activities(data_path: Path):
    strava_csv, manual_csv = _resolve_data_files(data_path)
    if strava_csv is None and manual_csv is None:
        raise click.ClickException(
            f"No activity data found at {data_path} "
            f"(expected {STRAVA_FILENAME} or {MANUAL_LOG_FILENAME})"
        )
    activities = []
    if strava_csv is not None:
        activities.extend(parse_strava_export(strava_csv))
    if manual_csv is not None:
        activities.extend(parse_manual_log(manual_csv))
    activities.sort(key=lambda a: a.date)
    return activities


def _fmt_pace(seconds_per_km: float | None) -> str:
    if seconds_per_km is None or seconds_per_km <= 0:
        return "-"
    s = int(seconds_per_km)
    return f"{s // 60}:{s % 60:02d}/km"


@click.group()
def cli():
    """Training Optimization - optimize your progression."""
    pass


@cli.command()
@click.option("--data", type=click.Path(exists=True, path_type=Path), required=True)
def analyze(data: Path):
    """Analyze current fitness state from training data."""
    activities = _load_activities(data)
    as_of = datetime.now()

    fitness = compute_fitness_state(activities, as_of)
    load = current_load_state(activities, as_of)

    table = Table(title="Current Fitness State", show_header=False)
    table.add_column("Metric")
    table.add_column("Value")

    table.add_row("Activities analyzed", str(len(activities)))
    table.add_row("VDOT estimate", f"{fitness.vdot_estimate:.1f}")
    table.add_row("Efficiency Factor", f"{fitness.ef_running:.2f} m/beat")
    trend = "+" if fitness.ef_trend_4w > 0 else ""
    table.add_row("EF trend (4w)", f"{trend}{fitness.ef_trend_4w:.3f}")
    table.add_row("Weekly run volume", f"{fitness.weekly_run_km:.1f} km")
    table.add_row("Recent long run", f"{fitness.recent_long_run_km:.1f} km")
    table.add_row("Threshold pace", _fmt_pace(fitness.recent_threshold_pace_s_per_km))
    table.add_row("Days since long run", str(fitness.days_since_long_run))
    table.add_row("Days since quality", str(fitness.days_since_quality))
    table.add_section()
    table.add_row("CTL (fitness)", f"{load.ctl:.1f}")
    table.add_row("ATL (fatigue)", f"{load.atl:.1f}")
    table.add_row("TSB (form)", f"{load.tsb:+.1f}")
    table.add_row("Zone", load.zone)

    console.print(table)


@cli.command()
@click.option("--data", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--distance", type=float, default=21.0975, help="Race distance in km")
def predict(data: Path, distance: float):
    """Predict race time for a given distance."""
    activities = _load_activities(data)
    prediction = predict_race(activities, distance, datetime.now())

    console.print(f"\n[bold]Race prediction for {distance:.2f} km[/bold]")
    console.print(f"  VDOT: [cyan]{prediction.vdot:.1f}[/cyan]")
    console.print(f"  Predicted time: [green]{prediction.time_str}[/green]")
    console.print(f"  Predicted pace: [yellow]{prediction.pace_str}[/yellow]\n")


@cli.command()
@click.option("--data", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--race-date", type=str, help="Race date as YYYY-MM-DD")
@click.option("--hrv", type=float, help="Current HRV RMSSD (ms)")
@click.option("--hrv-baseline", type=float, help="7-14 day HRV baseline (ms)")
@click.option("--rhr", type=float, help="Current resting HR (bpm)")
@click.option("--rhr-baseline", type=float, help="7-14 day RHR baseline (bpm)")
@click.option("--sleep", type=float, help="Last night sleep (hours)")
@click.option("--feel", type=int, help="Subjective feel 1-10")
def next(
    data: Path,
    race_date: str | None,
    hrv: float | None,
    hrv_baseline: float | None,
    rhr: float | None,
    rhr_baseline: float | None,
    sleep: float | None,
    feel: int | None,
):
    """Recommend next workout."""
    activities = _load_activities(data)
    as_of = datetime.now()

    race_dt = None
    if race_date:
        race_dt = datetime.strptime(race_date, "%Y-%m-%d")

    readiness = None
    if any(x is not None for x in (hrv, rhr, sleep, feel)):
        readiness = compute_readiness(
            activities,
            as_of,
            ReadinessInputs(
                hrv_rmssd=hrv,
                hrv_baseline=hrv_baseline,
                resting_hr=rhr,
                rhr_baseline=rhr_baseline,
                sleep_hours=sleep,
                subjective_score=feel,
            ),
        )

    rec = recommend_next_workout(activities, as_of, race_dt, readiness=readiness)

    console.print(f"\n[bold]Next workout: [cyan]{rec.kind.value.upper()}[/cyan][/bold]")
    console.print(f"  Reason: {rec.reason}")
    if rec.target_distance_km:
        console.print(f"  Distance: [yellow]{rec.target_distance_km:.1f} km[/yellow]")
    if rec.target_duration_min:
        console.print(f"  Duration: [yellow]{rec.target_duration_min:.0f} min[/yellow]")
    if rec.target_pace_s_per_km:
        console.print(f"  Target pace: [yellow]{_fmt_pace(rec.target_pace_s_per_km)}[/yellow]")
    if rec.notes:
        console.print(f"  Notes: {rec.notes}")
    if readiness is not None:
        console.print(
            f"  Readiness: [magenta]{readiness.score:.0f}/100 ({readiness.zone})[/magenta]"
        )
    console.print()


@cli.command()
@click.option("--data", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--weeks", type=int, default=12)
def progress(data: Path, weeks: int):
    """Show progression trend over recent weeks."""
    activities = _load_activities(data)
    history = compute_load_history(activities)

    cutoff_days = weeks * 7
    recent = history[-cutoff_days:] if len(history) > cutoff_days else history

    # Sample weekly
    table = Table(title=f"Progression over last {weeks} weeks")
    table.add_column("Week", style="dim")
    table.add_column("CTL (fitness)", justify="right")
    table.add_column("ATL (fatigue)", justify="right")
    table.add_column("TSB (form)", justify="right")

    for i in range(0, len(recent), 7):
        state = recent[i]
        tsb_color = "green" if state.tsb > 0 else "red"
        table.add_row(
            state.as_of.strftime("%Y-%m-%d"),
            f"{state.ctl:.1f}",
            f"{state.atl:.1f}",
            f"[{tsb_color}]{state.tsb:+.1f}[/{tsb_color}]",
        )

    console.print(table)


@cli.command()
@click.option(
    "--data",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Data directory (manual_log.csv will be created/appended)",
)
@click.option("--date", "date_str", type=str, help="YYYY-MM-DD (default: today)")
@click.option(
    "--type",
    "activity_type",
    type=click.Choice(["run", "ride", "swim", "strength", "walk"]),
    default="run",
    show_default=True,
)
@click.option("--distance", type=float, required=True, help="Distance in km")
@click.option("--duration", type=float, required=True, help="Duration in minutes")
@click.option("--avg-hr", type=float)
@click.option("--max-hr", type=float)
@click.option("--elevation", type=float, help="Elevation gain in meters")
@click.option("--name", type=str, default="", help="Workout name/notes")
def log(
    data: Path,
    date_str: str | None,
    activity_type: str,
    distance: float,
    duration: float,
    avg_hr: float | None,
    max_hr: float | None,
    elevation: float | None,
    name: str,
):
    """Log a manual activity to the data directory."""
    act_date = (
        datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
    )
    target = data / MANUAL_LOG_FILENAME
    append_manual_log(
        target,
        date=act_date,
        activity_type=activity_type,
        distance_km=distance,
        duration_min=duration,
        avg_hr=avg_hr,
        max_hr=max_hr,
        elevation_m=elevation,
        name=name,
    )
    console.print(
        f"[green]logged[/green] {activity_type} {distance:g} km in {duration:g} min "
        f"on [cyan]{act_date.strftime('%Y-%m-%d')}[/cyan] → [dim]{target}[/dim]"
    )


@cli.command()
@click.option("--data", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--hrv", type=float, help="Current HRV RMSSD (ms)")
@click.option("--hrv-baseline", type=float, help="HRV baseline (ms)")
@click.option("--rhr", type=float, help="Current resting HR (bpm)")
@click.option("--rhr-baseline", type=float, help="RHR baseline (bpm)")
@click.option("--sleep", type=float, help="Last night sleep (hours)")
@click.option("--feel", type=int, help="Subjective feel 1-10")
def readiness(
    data: Path,
    hrv: float | None,
    hrv_baseline: float | None,
    rhr: float | None,
    rhr_baseline: float | None,
    sleep: float | None,
    feel: int | None,
):
    """Compute composite readiness score."""
    activities = _load_activities(data)
    score = compute_readiness(
        activities,
        datetime.now(),
        ReadinessInputs(
            hrv_rmssd=hrv,
            hrv_baseline=hrv_baseline,
            resting_hr=rhr,
            rhr_baseline=rhr_baseline,
            sleep_hours=sleep,
            subjective_score=feel,
        ),
    )

    zone_color = {
        "ready": "green",
        "neutral": "yellow",
        "caution": "orange1",
        "recover": "red",
    }.get(score.zone, "white")

    console.print(
        f"\n[bold]Readiness: [{zone_color}]{score.score:.0f}/100 ({score.zone})[/{zone_color}][/bold]"
    )
    console.print(f"  Days since hard session: {score.days_since_hard}")
    if score.notes:
        console.print("  Signals:")
        for note in score.notes:
            console.print(f"    • {note}")
    console.print()


def main():
    cli()


if __name__ == "__main__":
    main()
