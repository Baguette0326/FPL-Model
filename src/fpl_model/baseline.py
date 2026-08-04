"""Transparent baseline evaluation and current-season projections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

POSITION_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def evaluate_recency_baseline(table: pd.DataFrame) -> pd.DataFrame:
    """Evaluate 'the next six resemble the previous six' by season."""
    valid = table.dropna(subset=["points_next_6"]).copy()
    time_column = "event_sequence" if "event_sequence" in valid.columns else "gameweek"
    valid = valid[(valid[time_column] >= 6) & (valid["minutes_last_6"] >= 180)]
    valid["prediction"] = valid["points_last_6"].clip(lower=0)
    rows: list[dict[str, Any]] = []
    for season, group in valid.groupby("season", sort=True):
        error = group["prediction"] - group["points_next_6"]
        rows.append(
            {
                "season": season,
                "rows": len(group),
                "mae": float(error.abs().mean()),
                "rmse": float(np.sqrt(np.mean(np.square(error)))),
                "spearman": float(
                    group["prediction"].rank(method="average").corr(
                        group["points_next_6"].rank(method="average")
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def _fixture_difficulty(fixtures: list[dict[str, Any]]) -> dict[int, float]:
    difficulties: dict[int, list[float]] = {}
    for fixture in fixtures:
        event = fixture.get("event")
        if event is None or int(event) > 6:
            continue
        difficulties.setdefault(int(fixture["team_h"]), []).append(
            float(fixture["team_h_difficulty"])
        )
        difficulties.setdefault(int(fixture["team_a"]), []).append(
            float(fixture["team_a_difficulty"])
        )
    return {
        team_id: float(np.mean(team_difficulties))
        for team_id, team_difficulties in difficulties.items()
    }


def build_current_projections(
    bootstrap_path: str | Path,
    fixtures_path: str | Path,
    previous_players_path: str | Path,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Create an auditable 2026/27 preseason baseline from 2025/26 totals."""
    with Path(bootstrap_path).open(encoding="utf-8") as handle:
        bootstrap = json.load(handle)
    with Path(fixtures_path).open(encoding="utf-8") as handle:
        fixtures = json.load(handle)

    current = pd.DataFrame(bootstrap["elements"])
    if "can_select" in current.columns:
        current = current[current["can_select"].fillna(True)].copy()
    if "removed" in current.columns:
        current = current[~current["removed"].fillna(False)].copy()
    teams = pd.DataFrame(bootstrap["teams"])[["id", "name"]].rename(
        columns={"id": "team", "name": "team_name"}
    )
    previous = pd.read_csv(previous_players_path, low_memory=False)[
        ["code", "total_points", "minutes"]
    ].rename(
        columns={
            "total_points": "prior_total_points",
            "minutes": "prior_minutes",
        }
    )
    current = current.merge(previous, on="code", how="left", validate="one_to_one")
    current = current.merge(teams, on="team", how="left", validate="many_to_one")
    current["position"] = current["element_type"].map(POSITION_MAP)
    current["name"] = (
        current["first_name"].fillna("").str.strip()
        + " "
        + current["second_name"].fillna("").str.strip()
    ).str.strip()
    duplicates = current["name"].duplicated(keep=False)
    current.loc[duplicates, "name"] = (
        current.loc[duplicates, "name"] + " [" + current.loc[duplicates, "code"].astype(str) + "]"
    )

    established = current["prior_minutes"].fillna(0) >= 900
    position_medians = (
        current.loc[established]
        .groupby("position")["prior_total_points"]
        .median()
        .to_dict()
    )
    current["position_prior"] = current["position"].map(position_medians).fillna(60.0)
    has_history = current["prior_total_points"].notna()
    current["base_points"] = np.where(
        has_history,
        0.8 * current["prior_total_points"].fillna(0) + 0.2 * current["position_prior"],
        0.65 * current["position_prior"],
    )

    difficulty = _fixture_difficulty(fixtures)
    current["fixture_difficulty_next6"] = current["team"].map(difficulty).fillna(3.0)
    current["fixture_multiplier"] = 1.0 + (3.0 - current["fixture_difficulty_next6"]) * 0.04
    temporary_status_factor = current["status"].map(
        {"a": 1.0, "d": 0.94, "i": 0.88, "s": 0.90, "u": 0.82, "n": 0.75}
    ).fillna(0.90)
    current["projected_points"] = (
        current["base_points"] * current["fixture_multiplier"] * temporary_status_factor
    ).clip(lower=0)

    low_minutes = (current["prior_minutes"].fillna(0) < 900).astype(float)
    new_player = (~has_history).astype(float)
    unavailable = (current["status"] != "a").astype(float)
    current["uncertainty"] = (
        current["projected_points"] * (0.15 + 0.10 * low_minutes + 0.15 * new_player + 0.08 * unavailable)
    ).clip(lower=8.0)
    current["projection_method"] = np.where(
        has_history,
        "prior-season points with positional shrinkage",
        "position prior for new player",
    )
    output = current[
        [
            "name",
            "position",
            "projected_points",
            "uncertainty",
            "id",
            "code",
            "team_name",
            "status",
            "prior_total_points",
            "prior_minutes",
            "fixture_difficulty_next6",
            "projection_method",
        ]
    ].rename(columns={"id": "player_id"})
    output = output.sort_values("projected_points", ascending=False).reset_index(drop=True)
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        output.to_csv(destination, index=False, float_format="%.3f")
    return output


def write_baseline_report(
    metrics: pd.DataFrame,
    projections: pd.DataFrame,
    destination: str | Path,
) -> None:
    lines = [
        "# Baseline report",
        "",
        "This report is generated from real historical FPL data. The model is deliberately simple: the evaluation predicts that the next six Gameweeks resemble the previous six for players with at least 180 minutes in the prior six, while the preseason ranking regresses 2025/26 totals toward positional priors and applies a small opening-fixture adjustment.",
        "",
        "## Walk-forward recency baseline",
        "",
        "| Season | Rows | MAE | RMSE | Spearman rank correlation |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in metrics.itertuples(index=False):
        lines.append(
            f"| {row.season} | {row.rows:,} | {row.mae:.3f} | {row.rmse:.3f} | {row.spearman:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Top 20 preliminary 2026/27 projections",
            "",
            "These are baseline estimates, not final draft recommendations. Transfers, injuries, expected minutes, promoted players, and model uncertainty still require further work.",
            "",
            "| Rank | Player | Pos | Club | Projected points | Uncertainty | Prior minutes | First-6 FDR |",
            "|---:|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for rank, row in enumerate(projections.head(20).itertuples(index=False), start=1):
        prior_minutes = 0 if pd.isna(row.prior_minutes) else int(row.prior_minutes)
        lines.append(
            f"| {rank} | {row.name} | {row.position} | {row.team_name} | "
            f"{row.projected_points:.1f} | {row.uncertainty:.1f} | {prior_minutes:,} | "
            f"{row.fixture_difficulty_next6:.2f} |"
        )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
