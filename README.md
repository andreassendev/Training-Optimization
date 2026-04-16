# Training Optimization

Personal training optimization engine focused on **progression** - not just tracking workouts, but understanding whether each session actually makes you faster.

## Core idea

Most training apps log what you did. This tool answers: **"What should I do next to progress fastest?"**

It does this by:
1. Measuring your current fitness from recent data (not just volume - actual aerobic capacity)
2. Tracking progression over time via efficiency metrics
3. Recommending the next workout type based on what gives the best marginal fitness gain

## Philosophy

Built for a specific training approach (quality over volume):
- 2 quality runs per week (1 long, 1 interval/tempo)
- Zone 1 cycling as aerobic base builder
- Strength training for durability
- Swimming as active recovery

If you train differently, the recommendations won't fit.

## Key metrics tracked

- **Efficiency Factor (EF)** — pace per heartbeat. Rising EF = fitness improving at same effort.
- **Aerobic decoupling** — HR drift on long runs. Lower = better aerobic base.
- **Training load (CTL/ATL/TSB)** — Banister impulse-response model.
- **VDOT estimate** — Jack Daniels' race equivalency metric.
- **Readiness score** — composite of HRV, RHR, days since hard session.

## Structure

```
src/
├── parsers/        # .fit.gz and CSV parsing
├── models/         # Fitness state, training load, readiness
├── optimizers/     # Workout recommender, race predictor, taper
└── cli.py          # Command-line interface

data/               # Your data - gitignored
examples/           # Sample fake data for testing
tests/              # Unit tests
```

## Usage

```bash
# Analyze current fitness from Strava export
trainopt analyze --data data/export.zip

# Predict race time for given distance
trainopt predict --distance 21.1

# Get workout recommendation for tomorrow
trainopt next --race-date 2026-05-15

# Track progression over last 12 weeks
trainopt progress --weeks 12
```

## Privacy

Your training data stays local:
- `data/` is gitignored
- No cloud uploads
- No account required
- Set `TRAINING_DATA_PATH` env var to point to your data folder
