# Example data

`sample_activities.csv` contains fake training data that mirrors the structure
of Strava's bulk export (`activities.csv`). Use it to test the CLI without
needing your own data:

```bash
trainopt analyze --data examples/sample_activities.csv
trainopt predict --data examples/sample_activities.csv --distance 21.0975
trainopt next --data examples/sample_activities.csv --race-date 2026-05-15
trainopt progress --data examples/sample_activities.csv --weeks 4
```

## Using your own data

1. Export from Strava: https://www.strava.com/athlete/delete_your_account (scroll
   down to "Download Request" - this gives you a bulk export ZIP).
2. Unzip somewhere local.
3. Run commands against `activities.csv` inside the export.

Your real data should live in `data/` which is gitignored. Nothing is ever
uploaded.
