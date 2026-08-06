"""Phase ML-1: leakage-safe appearance, start, and expected-minutes models."""

from __future__ import annotations

import json
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .modeling import COMMON_FEATURE_COLUMNS

POSITIONS = ("GK", "DEF", "MID", "FWD")
ROLLING_FEATURES = (
    "appearances_last_3",
    "appearances_last_6",
    "appearances_last_12",
    "history_events_last_6",
    "fixtures_last_6",
    "minutes_per_fixture_last_6",
    "recent_minutes_baseline",
)
PHASE1_FEATURE_COLUMNS = (
    *COMMON_FEATURE_COLUMNS,
    *ROLLING_FEATURES,
    "fixtures_next_1",
    *(f"position_{position}" for position in POSITIONS),
)


@dataclass(frozen=True, slots=True)
class Phase1Metrics:
    holdout_season: str
    rows: int
    appearance_brier: float
    appearance_baseline_brier: float
    start_brier: float
    start_baseline_brier: float
    expected_minutes_mae: float
    minutes_baseline_mae: float
    appearance_rate: float
    start_rate: float


@dataclass(slots=True)
class SigmoidCalibrator:
    intercept: float = 0.0
    slope: float = 1.0

    def fit(self, probabilities: np.ndarray, labels: np.ndarray) -> SigmoidCalibrator:
        from sklearn.linear_model import LogisticRegression

        probabilities = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
        labels = np.asarray(labels, dtype=int)
        if np.unique(labels).size < 2:
            return self
        logits = np.log(probabilities / (1 - probabilities)).reshape(-1, 1)
        model = LogisticRegression(C=1e6, max_iter=500, random_state=26)
        model.fit(logits, labels)
        self.intercept = float(model.intercept_[0])
        self.slope = float(model.coef_[0, 0])
        return self

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        probabilities = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
        logits = np.log(probabilities / (1 - probabilities))
        calibrated_logits = self.intercept + self.slope * logits
        return 1 / (1 + np.exp(-np.clip(calibrated_logits, -30, 30)))


def prepare_phase1_table(table: pd.DataFrame) -> pd.DataFrame:
    """Add only cutoff-safe rolling features needed by the first models."""
    required = {
        "season",
        "event_sequence",
        "player_code",
        "position",
        "minutes",
        "starts",
        "has_starts_source",
        "appearance_next_1",
        "start_next_1",
        "minutes_next_1",
        "fixtures_next_1",
        *COMMON_FEATURE_COLUMNS,
    }
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(f"Phase ML-1 table is missing columns: {sorted(missing)}")
    invalid_positions = sorted(set(table["position"].dropna()) - set(POSITIONS))
    if invalid_positions:
        raise ValueError(f"Unsupported player positions: {invalid_positions}")

    result = table.sort_values(
        ["season", "player_code", "event_sequence"]
    ).copy()
    groups = result.groupby(["season", "player_code"], sort=False)
    appeared = result["minutes"].gt(0).astype(float)
    for window in (3, 6, 12):
        result[f"appearances_last_{window}"] = groups["minutes"].transform(
            lambda values, size=window: values.gt(0)
            .astype(float)
            .shift(1)
            .rolling(size, min_periods=1)
            .sum()
        ).fillna(0.0)
    result["history_events_last_6"] = groups["minutes"].transform(
        lambda values: values.shift(1).rolling(6, min_periods=1).count()
    ).fillna(0.0)
    result["fixtures_last_6"] = groups["fixtures_next_1"].transform(
        lambda values: values.shift(1).rolling(6, min_periods=1).sum()
    ).fillna(0.0)
    result["minutes_per_fixture_last_6"] = (
        result["minutes_last_6"] / result["fixtures_last_6"].replace(0, np.nan)
    ).fillna(0.0)
    result["recent_minutes_baseline"] = (
        result["minutes_per_fixture_last_6"] * result["fixtures_next_1"]
    ).clip(lower=0, upper=90 * result["fixtures_next_1"])
    for position in POSITIONS:
        result[f"position_{position}"] = result["position"].eq(position).astype(int)
    # Keep the construction visibly tied to the past, never the current label.
    assert not appeared.equals(result["appearances_last_6"])
    return result


def _history_rows(
    table: pd.DataFrame, validation_season: str, history_seasons: int = 5
) -> pd.DataFrame:
    order = table["season"].astype(str).drop_duplicates().tolist()
    validation_index = order.index(validation_season)
    first = max(0, validation_index - history_seasons)
    allowed = set(order[first:validation_index])
    return table.loc[table["season"].astype(str).isin(allowed)].copy()


def _classifier() -> Any:
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=160,
        max_leaf_nodes=20,
        l2_regularization=1.0,
        random_state=26,
    )


def _fit_residual_minutes_model(train: pd.DataFrame) -> Any:
    """Fit systematic corrections to the strong recent-minutes baseline."""
    scheduled = train.loc[train["fixtures_next_1"].gt(0)]
    model = _regressor()
    model.fit(
        scheduled[list(PHASE1_FEATURE_COLUMNS)],
        scheduled["minutes_next_1"] - scheduled["recent_minutes_baseline"],
    )
    return model


def _predict_residual_minutes(model: Any, table: pd.DataFrame) -> np.ndarray:
    """Return baseline-anchored predictions within event fixture capacity."""
    prediction = table["recent_minutes_baseline"].to_numpy(dtype=float).copy()
    scheduled = table["fixtures_next_1"].gt(0).to_numpy()
    prediction[scheduled] += model.predict(
        table.loc[scheduled, list(PHASE1_FEATURE_COLUMNS)]
    )
    return np.clip(
        prediction,
        0,
        90 * table["fixtures_next_1"].to_numpy(dtype=float),
    )


def _regressor() -> Any:
    from sklearn.ensemble import HistGradientBoostingRegressor

    return HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_iter=140,
        max_leaf_nodes=20,
        l2_regularization=1.0,
        loss="absolute_error",
        random_state=26,
    )


def _fit_calibrator(
    table: pd.DataFrame,
    *,
    calibration_season: str,
    target: str,
    starts_only: bool = False,
) -> SigmoidCalibrator:
    train = _history_rows(table, calibration_season)
    calibration = table.loc[table["season"].eq(calibration_season)].copy()
    if starts_only:
        train = train.loc[train["has_starts_source"].eq(1)]
        calibration = calibration.loc[calibration["has_starts_source"].eq(1)]
    train = train.dropna(subset=[target])
    calibration = calibration.dropna(subset=[target])
    model = _classifier()
    model.fit(train[list(PHASE1_FEATURE_COLUMNS)], train[target].astype(int))
    raw = model.predict_proba(calibration[list(PHASE1_FEATURE_COLUMNS)])[:, 1]
    return SigmoidCalibrator().fit(raw, calibration[target].to_numpy())


def run_phase1_backtest(
    table_path: str | Path,
    *,
    holdout_season: str = "2025-26",
    calibration_season: str = "2024-25",
    output_report: str | Path | None = None,
    output_json: str | Path | None = None,
    artifact_path: str | Path | None = None,
) -> Phase1Metrics:
    """Fit on pre-holdout seasons and evaluate once on the final holdout."""
    from joblib import dump
    from sklearn.metrics import brier_score_loss, mean_absolute_error

    table = prepare_phase1_table(pd.read_csv(table_path, low_memory=False))
    train = _history_rows(table, holdout_season)
    holdout = table.loc[table["season"].eq(holdout_season)].copy()

    appearance_calibrator = _fit_calibrator(
        table, calibration_season=calibration_season, target="appearance_next_1"
    )
    appearance_model = _classifier()
    appearance_model.fit(
        train[list(PHASE1_FEATURE_COLUMNS)], train["appearance_next_1"].astype(int)
    )
    appearance_probability = appearance_calibrator.predict(
        appearance_model.predict_proba(holdout[list(PHASE1_FEATURE_COLUMNS)])[:, 1]
    )

    start_train = train.loc[train["has_starts_source"].eq(1)].dropna(
        subset=["start_next_1"]
    )
    start_holdout = holdout.loc[holdout["has_starts_source"].eq(1)].dropna(
        subset=["start_next_1"]
    )
    start_calibrator = _fit_calibrator(
        table,
        calibration_season=calibration_season,
        target="start_next_1",
        starts_only=True,
    )
    start_model = _classifier()
    start_model.fit(
        start_train[list(PHASE1_FEATURE_COLUMNS)], start_train["start_next_1"].astype(int)
    )
    start_probability_raw = start_calibrator.predict(
        start_model.predict_proba(start_holdout[list(PHASE1_FEATURE_COLUMNS)])[:, 1]
    )
    holdout_appearance_by_index = pd.Series(appearance_probability, index=holdout.index)
    start_probability = np.minimum(
        start_probability_raw,
        holdout_appearance_by_index.loc[start_holdout.index].to_numpy(),
    )

    minutes_model = _fit_residual_minutes_model(train)
    expected_minutes = _predict_residual_minutes(minutes_model, holdout)

    appearance_baseline = (
        (holdout["appearances_last_6"] + 1)
        / (holdout["history_events_last_6"] + 2)
    ).clip(0, 1)
    start_baseline = (
        holdout.loc[start_holdout.index, "starts_last_6"].fillna(0) + 1
    ) / (holdout.loc[start_holdout.index, "history_events_last_6"] + 2)
    minutes_baseline = holdout["recent_minutes_baseline"]

    metrics = Phase1Metrics(
        holdout_season=holdout_season,
        rows=len(holdout),
        appearance_brier=float(
            brier_score_loss(holdout["appearance_next_1"], appearance_probability)
        ),
        appearance_baseline_brier=float(
            brier_score_loss(holdout["appearance_next_1"], appearance_baseline)
        ),
        start_brier=float(
            brier_score_loss(start_holdout["start_next_1"], start_probability)
        ),
        start_baseline_brier=float(
            brier_score_loss(start_holdout["start_next_1"], start_baseline.clip(0, 1))
        ),
        expected_minutes_mae=float(
            mean_absolute_error(holdout["minutes_next_1"], expected_minutes)
        ),
        minutes_baseline_mae=float(
            mean_absolute_error(holdout["minutes_next_1"], minutes_baseline)
        ),
        appearance_rate=float(holdout["appearance_next_1"].mean()),
        start_rate=float(start_holdout["start_next_1"].mean()),
    )

    digest = hashlib.sha256()
    with Path(table_path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    payload = {
        "metrics": asdict(metrics),
        "promotion": {
            "appearance": metrics.appearance_brier < metrics.appearance_baseline_brier,
            "start": metrics.start_brier < metrics.start_baseline_brier,
            "minutes": metrics.expected_minutes_mae < metrics.minutes_baseline_mae,
        },
        "features": list(PHASE1_FEATURE_COLUMNS),
        "table_sha256": digest.hexdigest(),
        "history_seasons": 5,
        "calibration_season": calibration_season,
        "seed": 26,
    }
    if output_json is not None:
        destination = Path(output_json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if output_report is not None:
        destination = Path(output_report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(_render_report(metrics), encoding="utf-8")
    if artifact_path is not None:
        destination = Path(artifact_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        dump(
            {
                **payload,
                "appearance_model": appearance_model,
                "appearance_calibrator": appearance_calibrator,
                "start_model": start_model,
                "start_calibrator": start_calibrator,
                "minutes_model": minutes_model,
            },
            destination,
        )
    return metrics


def _render_report(metrics: Phase1Metrics) -> str:
    return f"""# Phase ML-1 minutes backtest

The 2025/26 season was held out from training and calibration. Lower scores are better.

| Measure | Model | Baseline |
|---|---:|---:|
| Appearance Brier score | {metrics.appearance_brier:.4f} | {metrics.appearance_baseline_brier:.4f} |
| Start Brier score | {metrics.start_brier:.4f} | {metrics.start_baseline_brier:.4f} |
| Expected-minutes MAE | {metrics.expected_minutes_mae:.3f} | {metrics.minutes_baseline_mae:.3f} |

Rows: {metrics.rows:,}. Appearance rate: {metrics.appearance_rate:.3f}. Start rate: {metrics.start_rate:.3f}.
"""
