"""Leakage-safe historical player and team feature construction."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PLAYER_SUM_COLUMNS = (
    "total_points",
    "minutes",
    "starts",
    "goals_scored",
    "assists",
    "bonus",
    "expected_goals",
    "expected_assists",
    "clean_sheets",
    "saves",
    "yellow_cards",
    "red_cards",
)


def _forward_sum(series: pd.Series, horizon: int) -> pd.Series:
    future = pd.concat([series.shift(-step) for step in range(1, horizon + 1)], axis=1)
    return future.sum(axis=1, min_count=horizon)


def _complete_player_gameweeks(frame: pd.DataFrame, maximum_gameweek: int) -> pd.DataFrame:
    completed: list[pd.DataFrame] = []
    for (_, _), player in frame.groupby(["season", "player_code"], sort=False):
        player = player.set_index("gameweek").reindex(range(1, maximum_gameweek + 1))
        player.index.name = "gameweek"
        for column in ("season", "player_code", "name", "position", "team"):
            player[column] = player[column].ffill().bfill()
        for column in PLAYER_SUM_COLUMNS:
            player[column] = pd.to_numeric(player[column], errors="coerce").fillna(0.0)
        completed.append(player.reset_index())
    return pd.concat(completed, ignore_index=True)


def _season_frame(raw_root: Path, season: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    gameweeks = pd.read_csv(raw_root / season / "merged_gw.csv", low_memory=False)
    players = pd.read_csv(raw_root / season / "players_raw.csv", low_memory=False)
    required = {"GW", "element", "name", "position", "team", "fixture", "was_home"}
    missing = required.difference(gameweeks.columns)
    if missing:
        raise ValueError(f"{season} gameweeks missing columns: {sorted(missing)}")
    if not {"id", "code"}.issubset(players.columns):
        raise ValueError(f"{season} players_raw.csv must include id and code")

    id_map = players[["id", "code"]].rename(columns={"id": "element", "code": "player_code"})
    frame = gameweeks.merge(id_map, on="element", how="left", validate="many_to_one")
    if frame["player_code"].isna().any():
        raise ValueError(f"{season} contains Gameweek rows without a stable player code")
    frame["season"] = season
    frame["gameweek"] = pd.to_numeric(frame["GW"], errors="raise").astype(int)
    for column in PLAYER_SUM_COLUMNS:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    player_week = (
        frame.groupby(["season", "gameweek", "player_code"], as_index=False)
        .agg(
            name=("name", "first"),
            position=("position", "first"),
            team=("team", "last"),
            **{column: (column, "sum") for column in PLAYER_SUM_COLUMNS},
        )
        .sort_values(["player_code", "gameweek"])
    )

    team_match = frame[
        ["season", "gameweek", "fixture", "team", "was_home", "team_h_score", "team_a_score"]
    ].drop_duplicates(["season", "fixture", "team"])
    home_score = pd.to_numeric(team_match["team_h_score"], errors="coerce").fillna(0)
    away_score = pd.to_numeric(team_match["team_a_score"], errors="coerce").fillna(0)
    team_match["goals_for"] = np.where(team_match["was_home"], home_score, away_score)
    team_match["goals_against"] = np.where(team_match["was_home"], away_score, home_score)
    team_week = (
        team_match.groupby(["season", "gameweek", "team"], as_index=False)[
            ["goals_for", "goals_against"]
        ]
        .sum()
        .sort_values(["team", "gameweek"])
    )
    return player_week, team_week


def build_modeling_table(
    raw_root: str | Path,
    seasons: Iterable[str],
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Build one row per player/Gameweek using only pre-deadline history."""
    raw_root = Path(raw_root)
    player_seasons: list[pd.DataFrame] = []
    team_seasons: list[pd.DataFrame] = []
    for season in seasons:
        player_week, team_week = _season_frame(raw_root, season)
        maximum_gameweek = max(int(player_week["gameweek"].max()), 38)
        player_seasons.append(_complete_player_gameweeks(player_week, maximum_gameweek))
        team_seasons.append(team_week)

    table = pd.concat(player_seasons, ignore_index=True)
    table["season"] = pd.Categorical(table["season"], categories=list(seasons), ordered=True)
    table = table.sort_values(["season", "player_code", "gameweek"]).reset_index(drop=True)
    player_group = table.groupby(["season", "player_code"], observed=True, sort=False)

    for measure in ("points", "minutes"):
        source = "total_points" if measure == "points" else measure
        for window in (3, 6, 12):
            table[f"{measure}_last_{window}"] = player_group[source].transform(
                lambda values, window=window: values.shift(1).rolling(window, min_periods=1).sum()
            )
    for measure in ("starts", "goals_scored", "assists", "bonus", "expected_goals", "expected_assists"):
        table[f"{measure}_last_6"] = player_group[measure].transform(
            lambda values: values.shift(1).rolling(6, min_periods=1).sum()
        )

    table["points_next_6"] = player_group["total_points"].transform(_forward_sum, horizon=6)
    table["minutes_next_6"] = player_group["minutes"].transform(_forward_sum, horizon=6)

    team_frames: list[pd.DataFrame] = []
    for team_week in team_seasons:
        team_week = team_week.copy()
        team_group = team_week.groupby(["season", "team"], sort=False)
        team_week["team_goals_for_last_6"] = team_group["goals_for"].transform(
            lambda values: values.shift(1).rolling(6, min_periods=1).sum()
        )
        team_week["team_goals_against_last_6"] = team_group["goals_against"].transform(
            lambda values: values.shift(1).rolling(6, min_periods=1).sum()
        )
        team_frames.append(
            team_week[
                [
                    "season",
                    "gameweek",
                    "team",
                    "team_goals_for_last_6",
                    "team_goals_against_last_6",
                ]
            ]
        )
    team_features = pd.concat(team_frames, ignore_index=True)
    table["season"] = table["season"].astype(str)
    table = table.merge(
        team_features,
        on=["season", "gameweek", "team"],
        how="left",
        validate="many_to_one",
    )
    feature_columns = [column for column in table.columns if "_last_" in column]
    table[feature_columns] = table[feature_columns].fillna(0.0)

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(output, index=False)
    return table
