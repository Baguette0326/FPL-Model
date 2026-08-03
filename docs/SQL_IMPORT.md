# Importing processed CSVs into a SQL editor

Clone or download the repository, then import the three files under `data/processed/` using UTF-8 encoding and the first row as column names.

## Recommended table names

| CSV | SQL table |
|---|---|
| `modeling_table.csv` | `player_gameweeks` |
| `2026-27_baseline_projections.csv` | `player_projections_2026_27` |
| `baseline_metrics.csv` | `baseline_metrics` |

## DBeaver, DataGrip, TablePlus, or similar

1. Create or open a SQLite/PostgreSQL database.
2. Choose the editor's **Import Data** or **Import CSV** action.
3. Select a CSV from `data/processed/`.
4. Use UTF-8, comma delimiter, double-quote text quoting, and header row enabled.
5. Allow type detection, then verify identifiers and Gameweeks are integers while points, minutes, expected statistics, and probabilities are numeric.
6. Repeat for the other two CSVs using the table names above.

## Quick verification queries

```sql
SELECT season, COUNT(*) AS rows, COUNT(DISTINCT player_code) AS players
FROM player_gameweeks
GROUP BY season
ORDER BY season;

SELECT name, position, team_name, projected_points, uncertainty
FROM player_projections_2026_27
ORDER BY projected_points DESC
LIMIT 20;

SELECT *
FROM baseline_metrics
ORDER BY season;
```

## Important interpretation notes

- `expected_stats_available = 0` means the historical source did not contain xG/xA; the zero expected-stat values in those rows must not be interpreted as observed zero performance.
- `modeling_table.csv` contains future targets for offline model training. Do not use target columns as live prediction inputs.
- `2026-27_baseline_projections.csv` is the file intended for the current draft assistant, but it remains a preliminary baseline until the ML workstream promotes a validated model.
