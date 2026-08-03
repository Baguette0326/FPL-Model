# Data sources and leakage policy

## Historical Gameweek data

The pipeline downloads `merged_gw.csv` and `players_raw.csv` for 2022/23 through 2025/26 from the public [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League) historical dataset. Its files originate from FPL API snapshots and provide one row per player fixture plus a season-end player identity table.

The upstream repository stopped weekly updates after 2024/25 but still provides major start, January, and end-of-season snapshots. The 2025/26 end-of-season files are used here.

## Current 2026/27 data

The pipeline snapshots the official public FPL endpoints:

- `https://fantasy.premierleague.com/api/bootstrap-static/`
- `https://fantasy.premierleague.com/api/fixtures/`

These supply the current player pool, positions, availability, clubs, and all fixtures. Raw responses are timestamped and checksummed in `data/raw/manifest.json`.

## Leakage exclusions

- Same-Gameweek `xP` is excluded. The historical dataset warns that it may reflect post-match updates to FPL's `ep_this` field.
- All rolling player and team features are shifted by one Gameweek.
- Six-Gameweek targets use only later Gameweeks.
- Current status and fixture data are used only for future 2026/27 projections, never historical training rows.

## Storage policy

Downloaded raw files and generated modeling tables are intentionally ignored by Git because they are reproducible and relatively large. Source configuration, pipeline code, checksums generated locally, and compact evaluation reports remain auditable.
