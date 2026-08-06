"""Phase ML-2 first challenger: baseline-anchored one-event points forecasts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .minutes_model import PHASE1_FEATURE_COLUMNS, _history_rows, prepare_phase1_table

POINTS_FEATURE_COLUMNS = (*PHASE1_FEATURE_COLUMNS, "recent_points_baseline")


@dataclass(frozen=True, slots=True)
class PointsFoldMetrics:
    season: str
    rows: int
    model_mae: float
    baseline_mae: float
    model_spearman: float
    baseline_spearman: float
    reliable_rows: int
    reliable_model_mae: float
    reliable_baseline_mae: float
    reliable_model_spearman: float
    reliable_baseline_spearman: float


def prepare_points_table(table: pd.DataFrame) -> pd.DataFrame:
    result = prepare_phase1_table(table)
    result["recent_points_baseline"] = (
        result["points_last_6"]
        / result["fixtures_last_6"].replace(0, np.nan)
        * result["fixtures_next_1"]
    ).fillna(0.0).clip(lower=0)
    return result


def _points_regressor(loss: str) -> Any:
    from sklearn.ensemble import HistGradientBoostingRegressor

    return HistGradientBoostingRegressor(
        loss=loss,
        learning_rate=0.05,
        max_iter=140,
        max_leaf_nodes=8,
        min_samples_leaf=100,
        l2_regularization=2.0,
        random_state=26,
    )


def _fit_points_model(train: pd.DataFrame, *, loss: str) -> Any:
    scheduled = train.loc[train["fixtures_next_1"].gt(0)]
    model = _points_regressor(loss)
    model.fit(
        scheduled[list(POINTS_FEATURE_COLUMNS)],
        scheduled["points_next_1"] - scheduled["recent_points_baseline"],
    )
    return model


def _predict_points(model: Any, table: pd.DataFrame) -> np.ndarray:
    prediction = table["recent_points_baseline"].to_numpy(dtype=float).copy()
    scheduled = table["fixtures_next_1"].gt(0).to_numpy()
    prediction[scheduled] += model.predict(
        table.loc[scheduled, list(POINTS_FEATURE_COLUMNS)]
    )
    prediction[~scheduled] = 0.0
    return prediction


def _fold(
    table: pd.DataFrame, season: str, *, loss: str
) -> tuple[PointsFoldMetrics, Any]:
    from sklearn.metrics import mean_absolute_error

    train = _history_rows(table, season)
    validation = table.loc[table["season"].eq(season)].copy()
    model = _fit_points_model(train, loss=loss)
    prediction = _predict_points(model, validation)
    baseline = validation["recent_points_baseline"].to_numpy()
    actual = validation["points_next_1"].to_numpy()
    reliable = validation["recent_minutes_baseline"].ge(45).to_numpy()
    metrics = PointsFoldMetrics(
        season=season,
        rows=len(validation),
        model_mae=float(mean_absolute_error(actual, prediction)),
        baseline_mae=float(mean_absolute_error(actual, baseline)),
        model_spearman=float(pd.Series(prediction).corr(pd.Series(actual), method="spearman")),
        baseline_spearman=float(pd.Series(baseline).corr(pd.Series(actual), method="spearman")),
        reliable_rows=int(reliable.sum()),
        reliable_model_mae=float(mean_absolute_error(actual[reliable], prediction[reliable])),
        reliable_baseline_mae=float(mean_absolute_error(actual[reliable], baseline[reliable])),
        reliable_model_spearman=float(
            pd.Series(prediction[reliable]).corr(pd.Series(actual[reliable]), method="spearman")
        ),
        reliable_baseline_spearman=float(
            pd.Series(baseline[reliable]).corr(pd.Series(actual[reliable]), method="spearman")
        ),
    )
    return metrics, model


def run_points_backtest(
    table_path: str | Path,
    *,
    output_report: str | Path | None = None,
    output_json: str | Path | None = None,
    artifact_path: str | Path | None = None,
) -> list[PointsFoldMetrics]:
    from joblib import dump

    table = prepare_points_table(pd.read_csv(table_path, low_memory=False))
    development: dict[str, PointsFoldMetrics] = {}
    for loss in ("squared_error", "absolute_error"):
        metrics, _ = _fold(table, "2023-24", loss=loss)
        development[loss] = metrics
    selected_loss = min(development, key=lambda loss: development[loss].model_mae)
    folds = [development[selected_loss]]
    confirmation, _ = _fold(table, "2024-25", loss=selected_loss)
    final, final_model = _fold(table, "2025-26", loss=selected_loss)
    folds.extend([confirmation, final])
    prefinal_pass = all(
        fold.model_mae < fold.baseline_mae
        and fold.reliable_model_mae < fold.reliable_baseline_mae
        for fold in folds
        if fold.season != "2025-26"
    )
    final_pass = (
        folds[-1].model_mae < folds[-1].baseline_mae
        and folds[-1].reliable_model_mae < folds[-1].reliable_baseline_mae
    )
    payload = {
        "folds": [asdict(fold) for fold in folds],
        "promotion": prefinal_pass and final_pass,
        "selection_excludes": "2025-26",
        "development_candidates": {
            loss: asdict(metrics) for loss, metrics in development.items()
        },
        "selected_loss": selected_loss,
        "features": list(POINTS_FEATURE_COLUMNS),
        "seed": 26,
    }
    if output_json is not None:
        destination = Path(output_json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if output_report is not None:
        lines = [
            "# Phase ML-2 one-event points challenger",
            "",
            f"The {selected_loss} loss was selected on 2023/24 and confirmed on 2024/25 before the 2025/26 evaluation.",
            "",
            "| Season | Model MAE | Baseline MAE | Model Spearman | Baseline Spearman |",
            "|---|---:|---:|---:|---:|",
        ]
        for fold in folds:
            lines.append(
                f"| {fold.season} | {fold.model_mae:.3f} | {fold.baseline_mae:.3f} | "
                f"{fold.model_spearman:.3f} | {fold.baseline_spearman:.3f} |"
            )
        lines.extend(
            [
                "",
                "## Reliable-player cohort (recent expected minutes >= 45)",
                "",
                "| Season | Rows | Model MAE | Baseline MAE | Model Spearman | Baseline Spearman |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for fold in folds:
            lines.append(
                f"| {fold.season} | {fold.reliable_rows:,} | {fold.reliable_model_mae:.3f} | "
                f"{fold.reliable_baseline_mae:.3f} | {fold.reliable_model_spearman:.3f} | "
                f"{fold.reliable_baseline_spearman:.3f} |"
            )
        lines.extend(["", f"Promotion: **{'yes' if payload['promotion'] else 'no'}**.", ""])
        destination = Path(output_report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("\n".join(lines), encoding="utf-8")
    if artifact_path is not None and final_model is not None:
        destination = Path(artifact_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        dump({**payload, "model": final_model}, destination)
    return folds
