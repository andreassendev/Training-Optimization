"""Render TriathlonProgram as Obsidian-friendly markdown."""

from __future__ import annotations

from training_optimization.programs.triathlon import TriathlonProgram, WeekPlan


_SPORT_EMOJI = {
    "swim": "🏊",
    "bike": "🚴",
    "run": "🏃",
    "strength": "🏋️",
    "brick": "🔁",
    "rest": "💤",
    "race": "🏁",
}


def _render_week(week: WeekPlan) -> str:
    lines = [
        f"## Uke {week.week_number} — {week.block.title()} ({week.start_date.isoformat()})",
        f"_{week.focus}_",
        "",
        f"**Total: {week.total_duration_min // 60}t {week.total_duration_min % 60}min**",
        "",
        "| Dag | Økt | Sport | Varighet | Intensitet | Notater |",
        "|-----|-----|-------|----------|------------|---------|",
    ]
    days = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"]
    for day, w in zip(days, week.workouts):
        emoji = _SPORT_EMOJI.get(w.sport, "")
        duration = "Hvile" if w.duration_min == 0 else f"{w.duration_min} min"
        lines.append(
            f"| {day} | {w.name} | {emoji} {w.sport} | {duration} | {w.intensity} | {w.notes} |"
        )
    return "\n".join(lines)


def render_program_markdown(program: TriathlonProgram) -> str:
    """Render full program as a single markdown document."""
    swim_km, bike_km, run_km = program.distance.distances
    total_weeks = len(program.weeks)

    header = f"""# Triatlon-program — {program.distance.value.title()}

**Race-dato:** {program.race_date.isoformat()}
**Start:** {program.start_date.isoformat()}
**Varighet:** {total_weeks} uker
**Distanser:** {swim_km} km svøm + {bike_km} km sykkel + {run_km} km løp

## Filosofi

- 2 kvalitetsøkter løping per uke (som har funket bra for deg)
- Mye sone 1-2 sykling for aerob base
- Svømming bygges gradvis (svakeste disiplin)
- Styrketrening 2x/uke - vedlikehold ikke vekst
- Plyometri integrert i styrkeøktene for løpsøkonomi
- Brick-økter (sykkel→løp direkte) er nøkkelen til triatlon

## Block-struktur

| Block | Fokus |
|-------|-------|
| **Base** ({sum(1 for w in program.weeks if w.block == "base")} uker) | Aerob kapasitet, teknikk, volum |
| **Build** ({sum(1 for w in program.weeks if w.block == "build")} uker) | Race-pace introduksjon, brick-økter |
| **Peak** ({sum(1 for w in program.weeks if w.block == "peak")} uker) | Race-spesifikk intensitet |
| **Taper** ({sum(1 for w in program.weeks if w.block == "taper")} uker) | Nedtrapping, friske bein |

---

"""
    week_blocks = "\n\n".join(_render_week(w) for w in program.weeks)

    footer = """

---

## Notater

- Juster ukentlig basert på `trainopt next` anbefalinger
- Skipp én økt i uka hvis du føler deg sliten - bedre å være underrent enn skadet
- Brick-økter er ikke valgfritt - kroppen MÅ lære å løpe på trette bein
- Carb-load fra 2-3 dager før race
- Test alt utstyr på trening, aldri debut på racedag

## Loggføring

Bruk daglig logg-mal: `Trening/Logg/{{dato}}.md`
"""

    return header + week_blocks + footer
