"""Transparent preseason rankings for the official four-manager FPL Draft."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .baseline import POSITION_MAP, _fixture_difficulty

STATUS_SEASON_FACTOR = {"a": 1.0, "d": 0.96, "i": 0.88, "s": 0.97, "u": 0.75, "n": 0.70}
STATUS_FIRST6_FACTOR = {"a": 1.0, "d": 0.88, "i": 0.70, "s": 0.78, "u": 0.55, "n": 0.50}
REPLACEMENT_RANK = {"GK": 9, "DEF": 21, "MID": 21, "FWD": 13}


def _historical_lookup(raw_root: Path, seasons: list[str]) -> pd.DataFrame:
    frames = []
    for recency, season in enumerate(reversed(seasons)):
        path = raw_root / season / "players_raw.csv"
        frame = pd.read_csv(
            path,
            usecols=["code", "total_points", "minutes", "element_type", "team_code"],
            low_memory=False,
        )
        frame["prior_season"] = season
        frame["seasons_ago"] = recency + 1
        frames.append(frame)
    history = pd.concat(frames, ignore_index=True)
    history = history.sort_values(["code", "seasons_ago"]).drop_duplicates("code")
    return history


def build_preseason_rankings(
    bootstrap_path: str | Path,
    fixtures_path: str | Path,
    raw_root: str | Path,
    historical_seasons: list[str],
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    with Path(bootstrap_path).open(encoding="utf-8") as handle:
        bootstrap = json.load(handle)
    with Path(fixtures_path).open(encoding="utf-8") as handle:
        fixtures = json.load(handle)
    current = pd.DataFrame(bootstrap["elements"])
    current = current.loc[current.get("can_select", True).fillna(True)].copy()
    if "removed" in current:
        current = current.loc[~current["removed"].fillna(False)].copy()
    teams = pd.DataFrame(bootstrap["teams"])[["id", "name", "code"]].rename(
        columns={"id": "team", "name": "team_name", "code": "current_team_code"}
    )
    current = current.merge(teams, on="team", validate="many_to_one")
    current["position"] = current["element_type"].map(POSITION_MAP)
    current["name"] = (
        current["first_name"].fillna("").str.strip()
        + " "
        + current["second_name"].fillna("").str.strip()
    ).str.strip()

    raw_root = Path(raw_root)
    history = _historical_lookup(raw_root, historical_seasons)
    latest = pd.read_csv(raw_root / historical_seasons[-1] / "players_raw.csv")
    latest["position"] = latest["element_type"].map(POSITION_MAP)
    established = latest.loc[latest["minutes"].ge(900)].copy()
    established["points_per90"] = established["total_points"] * 90 / established["minutes"]
    position_p90 = established.groupby("position")["points_per90"].median().to_dict()
    position_minutes = established.groupby("position")["minutes"].median().to_dict()
    prior_team_codes = set(latest["team_code"].dropna().astype(int))

    current = current.merge(history, on="code", how="left", suffixes=("", "_prior"))
    current["prior_points"] = current["total_points_prior"]
    current["prior_minutes"] = current["minutes_prior"]
    current["position_prior_p90"] = current["position"].map(position_p90)
    current["position_prior_minutes"] = current["position"].map(position_minutes)
    has_history = current["prior_minutes"].notna()
    prior_p90 = current["prior_points"] * 90 / current["prior_minutes"].replace(0, np.nan)
    weight = current["prior_minutes"].fillna(0) / (current["prior_minutes"].fillna(0) + 900)
    current["shrunk_points_per90"] = (
        weight * prior_p90.fillna(current["position_prior_p90"])
        + (1 - weight) * current["position_prior_p90"]
    )
    current["cost_percentile"] = current.groupby("position")["now_cost"].rank(pct=True)
    history_minutes = (
        0.8 * current["prior_minutes"].fillna(0)
        + 0.2 * current["position_prior_minutes"]
    )
    new_minutes = current["position_prior_minutes"] * (0.55 + 0.55 * current["cost_percentile"])
    recency_discount = np.power(0.72, (current["seasons_ago"].fillna(1) - 1).clip(lower=0))
    current["expected_minutes_season"] = np.where(
        has_history, history_minutes * recency_discount, new_minutes
    ).clip(0, 3420)
    current["promoted_team"] = ~current["current_team_code"].isin(prior_team_codes)
    current["new_to_history"] = ~has_history
    current["season_status_factor"] = current["status"].map(STATUS_SEASON_FACTOR).fillna(0.85)
    current["first6_status_factor"] = current["status"].map(STATUS_FIRST6_FACTOR).fillna(0.75)
    current["projected_points"] = (
        current["shrunk_points_per90"]
        * current["expected_minutes_season"]
        / 90
        * current["season_status_factor"]
    ).clip(lower=0)

    difficulty = _fixture_difficulty(fixtures)
    current["fixture_difficulty_next6"] = current["team"].map(difficulty).fillna(3.0)
    fixture_multiplier = 1 + (3 - current["fixture_difficulty_next6"]) * 0.035
    current["projected_points_next_6"] = (
        current["projected_points"] / 38 * 6 * fixture_multiplier
        * current["first6_status_factor"] / current["season_status_factor"].replace(0, np.nan)
    ).fillna(0).clip(lower=0)
    current["reliability"] = (
        np.minimum(current["prior_minutes"].fillna(0) / 1800, 1)
        * current["first6_status_factor"]
    ).clip(0, 1)
    current["uncertainty"] = (
        current["projected_points"]
        * (0.16 + 0.18 * current["new_to_history"] + 0.10 * current["promoted_team"]
           + 0.12 * current["status"].ne("a"))
    ).clip(lower=10)
    current["manual_review"] = (
        current["new_to_history"]
        | current["promoted_team"]
        | current["status"].ne("a")
        | current["prior_minutes"].fillna(0).lt(900)
    )
    current["projection_method"] = np.select(
        [current["seasons_ago"].eq(1), has_history],
        ["2025/26 empirical-Bayes rate and minutes", "older PL history with recency discount"],
        default="position and official-cost prior; manual review",
    )

    for position, replacement_rank in REPLACEMENT_RANK.items():
        mask = current["position"].eq(position)
        ordered = current.loc[mask, "projected_points"].sort_values(ascending=False)
        replacement = ordered.iloc[min(replacement_rank - 1, len(ordered) - 1)]
        current.loc[mask, "replacement_points"] = replacement
    current["value_over_replacement"] = current["projected_points"] - current["replacement_points"]
    current = current.sort_values(
        ["projected_points", "reliability"], ascending=[False, False]
    ).reset_index(drop=True)
    current.insert(0, "overall_rank", np.arange(1, len(current) + 1))
    output = current[
        [
            "overall_rank", "name", "position", "projected_points", "uncertainty",
            "id", "code", "team_name", "status", "news", "prior_season",
            "prior_points", "prior_minutes", "expected_minutes_season",
            "projected_points_next_6", "reliability", "fixture_difficulty_next6",
            "replacement_points", "value_over_replacement", "projection_method",
            "promoted_team", "new_to_history", "manual_review",
        ]
    ].rename(columns={"id": "player_id"})
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        output.to_csv(destination, index=False, float_format="%.4f")
    return output
