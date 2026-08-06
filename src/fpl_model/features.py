"""Leakage-safe historical player and team feature construction."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

POSITION_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
ALLOWED_PLAYER_POSITIONS = frozenset(POSITION_MAP.values())

CORE_PLAYER_SUM_COLUMNS = (
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "bonus",
    "clean_sheets",
    "saves",
    "yellow_cards",
    "red_cards",
)
OPTIONAL_PLAYER_SUM_COLUMNS = ("expected_goals", "expected_assists")
PLAYER_SUM_COLUMNS = CORE_PLAYER_SUM_COLUMNS + ("starts",) + OPTIONAL_PLAYER_SUM_COLUMNS


def _deduplicate_player_fixtures(
    gameweeks: pd.DataFrame, season: str
) -> tuple[pd.DataFrame, int]:
    """Remove equivalent source duplicates and reject conflicting outcomes."""
    keys = ["GW", "element", "fixture"]
    duplicated = gameweeks.duplicated(keys, keep=False)
    if not duplicated.any():
        return gameweeks, 0

    candidates = [
        "was_home",
        "kickoff_time",
        "team_h_score",
        "team_a_score",
        "position",
        "team",
        *CORE_PLAYER_SUM_COLUMNS,
        "starts",
        *OPTIONAL_PLAYER_SUM_COLUMNS,
    ]
    critical = [column for column in candidates if column in gameweeks.columns]
    duplicate_rows = gameweeks.loc[duplicated]
    conflicts = duplicate_rows.groupby(keys, dropna=False)[critical].nunique(dropna=False)
    conflicting_keys = conflicts.index[conflicts.gt(1).any(axis=1)].tolist()
    if conflicting_keys:
        examples = conflicting_keys[:5]
        raise ValueError(
            f"{season} contains conflicting duplicate player-fixture rows: {examples}"
        )

    deduplicated = gameweeks.drop_duplicates(keys, keep="first").copy()
    return deduplicated, len(gameweeks) - len(deduplicated)


def _read_csv_compatible(path: str | Path) -> pd.DataFrame:
    """Read modern UTF-8 or legacy Windows-1252 historical snapshots."""
    try:
        return pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, low_memory=False, encoding="cp1252")


def _forward_sum(series: pd.Series, horizon: int) -> pd.Series:
    """Sum the event at the prediction cutoff and the remaining horizon events."""
    future = pd.concat([series.shift(-step) for step in range(horizon)], axis=1)
    return future.sum(axis=1, min_count=horizon)


def _complete_player_gameweeks(
    frame: pd.DataFrame, event_calendar: pd.DataFrame
) -> pd.DataFrame:
    completed: list[pd.DataFrame] = []
    for (_, _), player in frame.groupby(["season", "player_code"], sort=False):
        player = player.copy()
        player["_observed_player_event"] = 1
        first_event = int(player["event_sequence"].min())
        last_event = int(player["event_sequence"].max())
        registration_calendar = event_calendar.loc[
            event_calendar["event_sequence"].between(first_event, last_event)
        ]
        player = player.set_index("event_sequence").reindex(
            registration_calendar["event_sequence"]
        )
        player.index.name = "event_sequence"
        player = player.join(
            registration_calendar.set_index("event_sequence"), rsuffix="_calendar"
        )
        player["gameweek"] = player.pop("gameweek_calendar")
        player["disrupted_schedule"] = player.pop("disrupted_schedule_calendar")
        player = player.drop(columns="season_calendar")
        for column in (
            "season",
            "player_code",
            "name",
            "position",
            "team",
            "expected_stats_available",
            "has_expected_stats_source",
            "has_starts_source",
            "has_availability_source",
            "has_fixture_strength_source",
            "schema_era",
            "disrupted_schedule",
        ):
            player[column] = player[column].ffill().bfill()
        for column in CORE_PLAYER_SUM_COLUMNS:
            player[column] = pd.to_numeric(player[column], errors="coerce").fillna(0.0)
        player["starts"] = pd.to_numeric(player["starts"], errors="coerce")
        player.loc[player["has_starts_source"].eq(0), "starts"] = np.nan
        generated_start_zero = (
            player["_observed_player_event"].isna() & player["has_starts_source"].eq(1)
        )
        player.loc[generated_start_zero, "starts"] = 0.0
        for column in OPTIONAL_PLAYER_SUM_COLUMNS:
            player[column] = pd.to_numeric(player[column], errors="coerce")
            player.loc[player["has_expected_stats_source"].eq(0), column] = np.nan
            generated_zero = (
                player["_observed_player_event"].isna()
                & player["has_expected_stats_source"].eq(1)
            )
            player.loc[generated_zero, column] = 0.0
        player["player_event_observed"] = (
            player["_observed_player_event"].fillna(0).astype(int)
        )
        player = player.drop(columns="_observed_player_event")
        completed.append(player.reset_index())
    return pd.concat(completed, ignore_index=True)


def _event_calendar(gameweeks: pd.DataFrame, season: str) -> pd.DataFrame:
    """Map source Gameweek labels onto chronological FPL event periods.

    The 2019/20 archive renumbers the post-pause events as 39-47. Seasons whose
    labels stay within the normal 1-38 range retain those labels, including an
    entirely blank event such as 2022/23 GW7.
    """
    events = (
        gameweeks.groupby("GW", as_index=False)
        .agg(event_start_time=("kickoff_time", "min"), event_end_time=("kickoff_time", "max"))
        .rename(columns={"GW": "gameweek"})
    )
    events["gameweek"] = pd.to_numeric(events["gameweek"], errors="raise").astype(int)
    events["event_start_time"] = pd.to_datetime(events["event_start_time"], utc=True)
    events["event_end_time"] = pd.to_datetime(events["event_end_time"], utc=True)
    # Raw sources expose kickoff times, not final-whistle timestamps. Three hours
    # is a conservative availability proxy for the final fixture in an event.
    events["event_end_time"] = events["event_end_time"] + pd.Timedelta(hours=3)
    events = events.sort_values(["event_start_time", "gameweek"]).reset_index(drop=True)

    source_labels_are_standard = events["gameweek"].between(1, 38).all()
    if source_labels_are_standard:
        calendar = pd.DataFrame({"event_sequence": range(1, 39)})
        calendar["gameweek"] = calendar["event_sequence"]
        calendar = calendar.merge(events, on="gameweek", how="left", validate="one_to_one")
        # A blank event has no fixture timestamp. Place its cutoff between its
        # neighbours; it remains an explicit zero-fixture event in all targets.
        starts = calendar["event_start_time"].interpolate(method="linear")
        calendar["event_start_time"] = starts.bfill().ffill()
        calendar["event_end_time"] = calendar["event_end_time"].fillna(
            calendar["event_start_time"] + pd.Timedelta(hours=3)
        )
    else:
        calendar = events.copy()
        calendar["event_sequence"] = np.arange(1, len(calendar) + 1)

    calendar["season"] = season
    calendar["disrupted_schedule"] = int(
        not source_labels_are_standard or len(events) != 38
    )
    calendar["prediction_cutoff"] = calendar["event_start_time"]
    calendar["available_at"] = calendar["event_end_time"].shift(1)
    return calendar[
        [
            "season",
            "gameweek",
            "event_sequence",
            "prediction_cutoff",
            "available_at",
            "event_end_time",
            "disrupted_schedule",
        ]
    ]


def _season_frame(
    raw_root: Path, season: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    gameweeks = _read_csv_compatible(raw_root / season / "merged_gw.csv")
    players = _read_csv_compatible(raw_root / season / "players_raw.csv")
    required = {"GW", "element", "fixture", "was_home"}
    missing = required.difference(gameweeks.columns)
    if missing:
        raise ValueError(f"{season} gameweeks missing columns: {sorted(missing)}")
    if not {"id", "code"}.issubset(players.columns):
        raise ValueError(f"{season} players_raw.csv must include id and code")

    gameweeks, duplicate_rows_removed = _deduplicate_player_fixtures(
        gameweeks, season
    )
    selectable_players = players.loc[players["element_type"].isin(POSITION_MAP)].copy()
    gameweeks = gameweeks.loc[gameweeks["element"].isin(selectable_players["id"])].copy()

    id_map = selectable_players[
        ["id", "code", "element_type", "team", "web_name"]
    ].rename(
        columns={
            "id": "element",
            "code": "player_code",
            "element_type": "meta_element_type",
            "team": "meta_team",
            "web_name": "meta_name",
        }
    )
    frame = gameweeks.merge(id_map, on="element", how="left", validate="many_to_one")
    if frame["player_code"].isna().any():
        raise ValueError(f"{season} contains Gameweek rows without a stable player code")
    frame["season"] = season
    has_expected_stats = int(
        {"expected_goals", "expected_assists"}.issubset(gameweeks.columns)
    )
    frame["expected_stats_available"] = has_expected_stats
    frame["has_expected_stats_source"] = has_expected_stats
    has_starts = int("starts" in gameweeks.columns)
    frame["has_starts_source"] = has_starts
    frame["has_availability_source"] = 0
    frame["has_fixture_strength_source"] = 0
    frame["schema_era"] = "core_expected_stats" if has_expected_stats else "core"
    frame["gameweek"] = pd.to_numeric(frame["GW"], errors="raise").astype(int)
    calendar = _event_calendar(gameweeks, season)
    frame = frame.merge(
        calendar[["gameweek", "event_sequence", "disrupted_schedule"]],
        on="gameweek",
        how="left",
        validate="many_to_one",
    )
    if "name" not in frame.columns:
        frame["name"] = frame["meta_name"]
    frame["position"] = frame["meta_element_type"].map(POSITION_MAP)
    invalid_positions = sorted(
        frame.loc[~frame["position"].isin(ALLOWED_PLAYER_POSITIONS), "position"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    if invalid_positions or frame["position"].isna().any():
        raise ValueError(f"{season} contains unsupported player positions: {invalid_positions}")
    if "team" not in frame.columns:
        # Legacy Gameweek files omit the player's club. The end-of-season player
        # snapshot can be wrong for transferred players, so infer each fixture
        # side from the modal metadata team among all players on that side.
        frame["team"] = frame.groupby(["fixture", "was_home"])["meta_team"].transform(
            lambda values: values.mode().iloc[0]
        )
    if frame[["name", "position", "team"]].isna().any().any():
        raise ValueError(f"{season} contains rows without player name, position, or team")
    for column in CORE_PLAYER_SUM_COLUMNS:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    if "starts" not in frame.columns:
        frame["starts"] = np.nan
    frame["starts"] = pd.to_numeric(frame["starts"], errors="coerce")
    for column in OPTIONAL_PLAYER_SUM_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    player_week = (
        frame.groupby(
            ["season", "gameweek", "event_sequence", "player_code"], as_index=False
        )
        .agg(
            name=("name", "first"),
            position=("position", "first"),
            team=("team", "last"),
            expected_stats_available=("expected_stats_available", "max"),
            has_expected_stats_source=("has_expected_stats_source", "max"),
            has_starts_source=("has_starts_source", "max"),
            has_availability_source=("has_availability_source", "max"),
            has_fixture_strength_source=("has_fixture_strength_source", "max"),
            schema_era=("schema_era", "first"),
            disrupted_schedule=("disrupted_schedule", "max"),
            **{column: (column, "sum") for column in CORE_PLAYER_SUM_COLUMNS},
            starts=("starts", lambda values: values.sum(min_count=1)),
            **{
                column: (column, lambda values: values.sum(min_count=1))
                for column in OPTIONAL_PLAYER_SUM_COLUMNS
            },
        )
        .sort_values(["player_code", "event_sequence"])
    )

    team_match = frame[
        [
            "season",
            "gameweek",
            "event_sequence",
            "fixture",
            "team",
            "was_home",
            "team_h_score",
            "team_a_score",
        ]
    ].drop_duplicates(["season", "event_sequence", "fixture", "team"])
    # Legacy archives can list a postponed fixture in both its original and
    # eventual event. Only the completed occurrence supplies target exposure.
    team_match = team_match.loc[
        team_match["team_h_score"].notna() & team_match["team_a_score"].notna()
    ].copy()
    home_score = pd.to_numeric(team_match["team_h_score"], errors="coerce").fillna(0)
    away_score = pd.to_numeric(team_match["team_a_score"], errors="coerce").fillna(0)
    team_match["goals_for"] = np.where(team_match["was_home"], home_score, away_score)
    team_match["goals_against"] = np.where(team_match["was_home"], away_score, home_score)
    observed_team_week = team_match.groupby(
        ["season", "gameweek", "event_sequence", "team"], as_index=False
    ).agg(
        goals_for=("goals_for", "sum"),
        goals_against=("goals_against", "sum"),
        fixtures_next_1=("fixture", "nunique"),
    )
    team_keys = frame[["season", "team"]].drop_duplicates()
    team_week = (
        calendar[["season", "gameweek", "event_sequence"]]
        .merge(team_keys, on="season", how="inner", validate="many_to_many")
        .merge(
            observed_team_week,
            on=["season", "gameweek", "event_sequence", "team"],
            how="left",
            validate="one_to_one",
        )
        .sort_values(["team", "event_sequence"])
    )
    team_week["fixtures_next_1"] = team_week["fixtures_next_1"].fillna(0).astype(int)
    team_week["team_event_observed"] = team_week["fixtures_next_1"].gt(0).astype(int)
    team_week[["goals_for", "goals_against"]] = team_week[
        ["goals_for", "goals_against"]
    ].fillna(0.0)
    player_week.attrs["source_duplicate_player_fixture_rows_removed"] = (
        duplicate_rows_removed
    )
    return player_week, team_week, calendar


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
        player_week, team_week, calendar = _season_frame(raw_root, season)
        source_duplicates_removed = player_week.attrs.get(
            "source_duplicate_player_fixture_rows_removed", 0
        )
        player_seasons.append(_complete_player_gameweeks(player_week, calendar))
        player_seasons[-1].attrs["source_duplicate_player_fixture_rows_removed"] = (
            source_duplicates_removed
        )
        team_seasons.append(team_week)

    total_source_duplicates_removed = sum(
        frame.attrs.get("source_duplicate_player_fixture_rows_removed", 0)
        for frame in player_seasons
    )
    table = pd.concat(player_seasons, ignore_index=True)
    table["season"] = pd.Categorical(table["season"], categories=list(seasons), ordered=True)
    table = table.sort_values(["season", "player_code", "event_sequence"]).reset_index(drop=True)
    player_group = table.groupby(["season", "player_code"], observed=True, sort=False)

    for measure in ("points", "minutes"):
        source = "total_points" if measure == "points" else measure
        for window in (3, 6, 12):
            table[f"{measure}_last_{window}"] = player_group[source].transform(
                lambda values, window=window: values.shift(1).rolling(window, min_periods=1).sum()
            )
    for measure in (
        "starts",
        "goals_scored",
        "assists",
        "bonus",
        "expected_goals",
        "expected_assists",
    ):
        table[f"{measure}_last_6"] = player_group[measure].transform(
            lambda values: values.shift(1).rolling(6, min_periods=1).sum()
        )

    table["points_next_6"] = player_group["total_points"].transform(_forward_sum, horizon=6)
    table["minutes_next_6"] = player_group["minutes"].transform(_forward_sum, horizon=6)
    table["appearance_next_1"] = table["minutes"].gt(0).astype("Int64")
    table["start_next_1"] = table["starts"].gt(0).astype("Int64")
    table.loc[table["has_starts_source"].ne(1), "start_next_1"] = pd.NA
    table["minutes_next_1"] = table["minutes"]
    table["points_next_1"] = table["total_points"]
    table["target_1_observed_event"] = table["event_sequence"]
    table["target_6_observed_event"] = table["event_sequence"] + 5

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
                    "event_sequence",
                    "team",
                    "team_event_observed",
                    "fixtures_next_1",
                    "team_goals_for_last_6",
                    "team_goals_against_last_6",
                ]
            ]
        )
    team_features = pd.concat(team_frames, ignore_index=True)
    table["season"] = table["season"].astype(str)
    season_order = {season: index for index, season in enumerate(seasons)}
    table["season_recency"] = table["season"].map(
        lambda season: len(season_order) - 1 - season_order[season]
    )
    table = table.merge(
        team_features,
        on=["season", "gameweek", "event_sequence", "team"],
        how="left",
        validate="many_to_one",
    )
    common_features = [
        column
        for column in table.columns
        if "_last_" in column
        and not column.startswith(("expected_", "starts_"))
    ]
    table[common_features] = table[common_features].fillna(0.0)
    table.attrs["source_duplicate_player_fixture_rows_removed"] = (
        total_source_duplicates_removed
    )

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(output, index=False)
    return table
