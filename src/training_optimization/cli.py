"""Command-line interface for training optimization."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from training_optimization.models.fitness_state import compute_fitness_state
from training_optimization.models.training_load import (
    compute_load_history,
    current_load_state,
)
from training_optimization.optimizers.race_predictor import predict_race
from training_optimization.optimizers.workout_recommender import recommend_next_workout
from training_optimization.parsers.strava_export import parse_strava_export

console = Console()


def _load_activities(data_path: Path):
    csv_file = data_path / "activities.csv" if data_path.is_dir() else data_path
    if not csv_file.exists():
        raise click.ClickException(f"Could not find activities.csv at {csv_file}")
    return parse_strava_export(csv_file)


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
def next(data: Path, race_date: str | None):
    """Recommend next workout."""
    activities = _load_activities(data)
    as_of = datetime.now()

    race_dt = None
    if race_date:
        race_dt = datetime.strptime(race_date, "%Y-%m-%d")

    rec = recommend_next_workout(activities, as_of, race_dt)

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


def main():
    cli()


if __name__ == "__main__":
    main()
