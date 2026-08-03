"""Leakage-aware baseline ML training scaffold."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FEATURE_COLUMNS = (
    "minutes_last_3",
    "minutes_last_6",
    "minutes_last_12",
    "starts_last_6",
    "points_last_3",
    "points_last_6",
    "points_last_12",
    "goals_scored_last_6",
    "assists_last_6",
    "bonus_last_6",
    "expected_goals_last_6",
    "expected_assists_last_6",
    "team_goals_for_last_6",
    "team_goals_against_last_6",
)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    season: str
    cutoff_gameweek: int
    rows: int
    mean_absolute_error: float


def walk_forward_validate(
    table_path: str | Path,
    *,
    target: str = "points_next_6",
    minimum_train_gameweeks: int = 20,
) -> list[ValidationResult]:
    """Train only on rows strictly earlier than each validation Gameweek."""
    try:
        import pandas as pd
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error
    except ImportError as error:  # pragma: no cover
        raise RuntimeError('Install dependencies with: pip install -e ".[model]"') from error

    table = pd.read_csv(table_path).sort_values(["season", "gameweek", "player_id"])
    required = {"season", "gameweek", "player_id", target, *FEATURE_COLUMNS}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(f"Modeling table is missing columns: {sorted(missing)}")

    time_keys = table[["season", "gameweek"]].drop_duplicates().reset_index(drop=True)
    results: list[ValidationResult] = []
    for index in range(minimum_train_gameweeks, len(time_keys)):
        key = time_keys.iloc[index]
        earlier = (table["season"] < key["season"]) | (
            (table["season"] == key["season"]) & (table["gameweek"] < key["gameweek"])
        )
        current = (table["season"] == key["season"]) & (table["gameweek"] == key["gameweek"])
        train = table.loc[earlier].dropna(subset=[target])
        validation = table.loc[current].dropna(subset=[target])
        if train.empty or validation.empty:
            continue
        model = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_iter=250,
            max_leaf_nodes=20,
            l2_regularization=1.0,
            random_state=26,
        )
        model.fit(train[list(FEATURE_COLUMNS)], train[target])
        predictions = model.predict(validation[list(FEATURE_COLUMNS)])
        results.append(
            ValidationResult(
                season=str(key["season"]),
                cutoff_gameweek=int(key["gameweek"]),
                rows=len(validation),
                mean_absolute_error=float(mean_absolute_error(validation[target], predictions)),
            )
        )
    return results
