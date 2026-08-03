# FPL Draft Model

A machine-learning and decision-support project for a **four-manager Fantasy Premier League Draft league** in the 2026/27 season.

The project is deliberately split into two problems:

1. **Project player points** from historical performance, minutes, role, team strength, and upcoming fixtures.
2. **Make the best live draft decision** after every selection, accounting for unavailable players, positional scarcity, squad constraints, and the picks before your next turn.

This is for the official FPL Draft format, not the salary-cap version of FPL. A Draft squad has 15 unique players: 2 goalkeepers, 5 defenders, 5 midfielders, and 3 forwards. There is no player budget and no captain.

## What is included

- A detailed implementation roadmap in [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)
- A weekly waiver, free-agent, breakout, and trade plan in [`docs/WEEKLY_MANAGER.md`](docs/WEEKLY_MANAGER.md)
- Confirmed league settings and opponent-behavior assumptions in [`docs/LEAGUE_STRATEGY.md`](docs/LEAGUE_STRATEGY.md)
- A pure-Python live draft board and recommendation engine
- A starter same-position weekly add/drop recommendation engine
- A walk-forward ML training scaffold that avoids random train/test leakage
- Synthetic example projections so the draft assistant can be tried immediately
- Unit tests for player removal, roster constraints, and recommendation updates
- A data dictionary specifying the future historical dataset

## Quick start

The live draft prototype uses only the Python standard library:

```powershell
python -m unittest discover -s tests -v
$env:PYTHONPATH = "src"
python -m fpl_model.cli recommend --projections data/sample/player_projections.csv --taken "Sample Forward A"
```

Build the real historical table and preliminary 2026/27 baseline rankings:

```powershell
python -m pip install -e ".[model,dev]"
$env:PYTHONPATH = "src"
python -m fpl_model.pipeline all
```

This downloads four historical seasons and current official FPL snapshots. Generated raw and processed data stay outside Git; checksums are recorded in `data/raw/manifest.json`.

## Draft-day workflow

1. Generate updated projections shortly before the draft.
2. Start the assistant with all players available.
3. Record every manager's selection as it happens.
4. Ask for recommendations before each of your picks.
5. Select a player, record the pick, and recalculate.

The initial recommendation score combines projected points with value over a replacement-level player and a small positional-scarcity adjustment. Later versions will add opponent-pick simulations and probability that a target remains available at your next pick.

## After the draft

The project will refresh 1-, 3-, 6-Gameweek, and rest-of-season projections each week. It will identify role and performance trends, rank waiver/free-agent add-drop pairs, surface high-upside sleepers, and evaluate trades. Official FPL Draft has no Wildcard chip, so this repository uses “wildcard pick” only to mean a speculative breakout target.

## Important modeling principle

Do not optimize only for last season's total points. That mostly rewards players who stayed healthy and started all year. The useful target is future value under uncertainty: projected points over a defined horizon, probability of playing, and an uncertainty range. All training and validation must respect time order.

## Status

This repository is an auditable starter, not yet a production-quality prediction model. Synthetic rows under `data/sample/` are only for exercising the draft engine and must never be treated as real forecasts.

## License

MIT
