"""Leakage-safe temporal validation and baseline model comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMMON_FEATURE_COLUMNS = (
    "minutes_last_3",
    "minutes_last_6",
    "minutes_last_12",
    "points_last_3",
    "points_last_6",
    "points_last_12",
    "goals_scored_last_6",
    "assists_last_6",
    "bonus_last_6",
    "team_goals_for_last_6",
    "team_goals_against_last_6",
)
MODERN_FEATURE_COLUMNS = COMMON_FEATURE_COLUMNS + (
    "starts_last_6",
    "expected_goals_last_6",
    "expected_assists_last_6",
)
FEATURE_SETS = {
    "common": COMMON_FEATURE_COLUMNS,
    "modern": MODERN_FEATURE_COLUMNS,
}
# Kept as a compatibility alias for callers of the original scaffold.
FEATURE_COLUMNS = MODERN_FEATURE_COLUMNS


@dataclass(frozen=True, slots=True)
class ValidationResult:
    season: str
    cutoff_gameweek: int
    cutoff_event_sequence: int
    rows: int
    mean_absolute_error: float
    spearman_rank_correlation: float
    target: str
    feature_set: str
    history_strategy: str


@dataclass(frozen=True, slots=True)
class LeakageAudit:
    rows: int
    violations: dict[str, int]

    @property
    def passed(self) -> bool:
        return not any(self.violations.values())

    def raise_for_violations(self) -> None:
        if not self.passed:
            failures = {name: count for name, count in self.violations.items() if count}
            raise ValueError(f"Leakage audit failed: {failures}")


def infer_target_horizon(target: str) -> int:
    """Return the number of future event periods contained in a target."""
    suffix = target.rsplit("_", maxsplit=1)[-1]
    if suffix not in {"1", "6"}:
        raise ValueError(f"Cannot infer target horizon from {target!r}")
    return int(suffix)


def purged_training_mask(
    table: Any,
    *,
    validation_season: str,
    validation_event_sequence: int,
    horizon: int,
    embargo_events: int = 0,
    season_order: list[str] | None = None,
) -> Any:
    """Select labels fully observed before a validation prediction cutoff.

    For a six-event target validated at event ``t``, the latest eligible origin
    is ``t - 6``: its outcomes end at ``t - 1``. Earlier seasons are fully
    eligible; later seasons never are.
    """
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    if embargo_events < 0:
        raise ValueError("embargo_events cannot be negative")

    season = table["season"].astype(str)
    if season_order is None:
        if "_season_order" in table.columns:
            season_indices = table["_season_order"]
            matching = table.loc[season.eq(str(validation_season)), "_season_order"]
            if matching.empty:
                raise ValueError(f"Unknown validation season {validation_season!r}")
            validation_season_index = int(matching.iloc[0])
        else:
            season_order = season.drop_duplicates().tolist()
    if season_order is not None:
        order = {str(value): index for index, value in enumerate(season_order)}
        if str(validation_season) not in order:
            raise ValueError(f"Unknown validation season {validation_season!r}")
        season_indices = season.map(order)
        if season_indices.isna().any():
            unknown = sorted(season.loc[season_indices.isna()].unique().tolist())
            raise ValueError(f"Season order is missing seasons: {unknown}")
        validation_season_index = order[str(validation_season)]

    earlier_season = season_indices.lt(validation_season_index)
    same_season = season_indices.eq(validation_season_index)
    observed_event = table["event_sequence"] + horizon - 1 + embargo_events
    return earlier_season | (
        same_season & observed_event.lt(int(validation_event_sequence))
    )


def audit_modeling_table(table: Any) -> LeakageAudit:
    """Recompute timing-sensitive fields and fail closed on inconsistencies."""
    import numpy as np
    import pandas as pd

    required = {
        "season",
        "gameweek",
        "event_sequence",
        "player_code",
        "position",
        "player_event_observed",
        "team_event_observed",
        "available_at",
        "prediction_cutoff",
        "total_points",
        "minutes",
        "fixtures_next_1",
        "starts",
        "has_starts_source",
        "points_next_1",
        "minutes_next_1",
        "points_next_6",
        "minutes_next_6",
        "appearance_next_1",
        "start_next_1",
        "target_1_observed_event",
        "target_6_observed_event",
    }
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(f"Modeling table is missing audit columns: {sorted(missing)}")

    ordered = table.sort_values(["season", "player_code", "event_sequence"]).copy()
    player_group = ordered.groupby(["season", "player_code"], sort=False)

    def mismatch_count(actual: Any, expected: Any) -> int:
        actual_numeric = pd.to_numeric(actual, errors="coerce").astype(float)
        expected_numeric = pd.to_numeric(expected, errors="coerce").astype(float)
        both_missing = actual_numeric.isna() & expected_numeric.isna()
        both_present = actual_numeric.notna() & expected_numeric.notna()
        equal = pd.Series(False, index=actual_numeric.index)
        equal.loc[both_present] = np.isclose(
            actual_numeric.loc[both_present],
            expected_numeric.loc[both_present],
            rtol=1e-9,
            atol=1e-9,
        )
        return int((~(both_missing | equal)).sum())

    expected_points_1 = ordered["total_points"]
    expected_minutes_1 = ordered["minutes"]
    expected_appearance = pd.to_numeric(ordered["minutes"], errors="coerce").gt(0).astype(float)
    expected_starts = pd.to_numeric(ordered["starts"], errors="coerce").gt(0).astype(float)
    expected_starts.loc[ordered["has_starts_source"].ne(1)] = np.nan

    def forward_sum_including_current(values: Any, horizon: int) -> Any:
        future = pd.concat(
            [values.shift(-step) for step in range(horizon)], axis=1
        )
        return future.sum(axis=1, min_count=horizon)

    expected_points_6 = player_group["total_points"].transform(
        forward_sum_including_current, horizon=6
    )
    expected_minutes_6 = player_group["minutes"].transform(
        forward_sum_including_current, horizon=6
    )

    rolling_sources = {
        "points": "total_points",
        "minutes": "minutes",
        "starts": "starts",
        "goals_scored": "goals_scored",
        "assists": "assists",
        "bonus": "bonus",
        "expected_goals": "expected_goals",
        "expected_assists": "expected_assists",
    }
    rolling_mismatches = 0
    for feature_stem, source in rolling_sources.items():
        if source not in ordered.columns:
            continue
        for window in (3, 6, 12):
            feature = f"{feature_stem}_last_{window}"
            if feature not in ordered.columns:
                continue
            expected = player_group[source].transform(
                lambda values, size=window: values.shift(1).rolling(
                    size, min_periods=1
                ).sum()
            )
            if feature_stem in {
                "points",
                "minutes",
                "goals_scored",
                "assists",
                "bonus",
            }:
                expected = expected.fillna(0.0)
            rolling_mismatches += mismatch_count(ordered[feature], expected)

    prediction_cutoff = pd.to_datetime(
        ordered["prediction_cutoff"], utc=True, errors="coerce", format="mixed"
    )
    available_at = pd.to_datetime(
        ordered["available_at"], utc=True, errors="coerce", format="mixed"
    )
    invalid_prediction_cutoff = ordered["prediction_cutoff"].notna() & prediction_cutoff.isna()
    invalid_available_at = ordered["available_at"].notna() & available_at.isna()
    available = available_at.notna()

    first_observed = player_group["player_event_observed"].nth(0)
    last_observed = player_group["player_event_observed"].nth(-1)
    registration_bound_violations = int(first_observed.ne(1).sum() + last_observed.ne(1).sum())
    fixtures = pd.to_numeric(ordered["fixtures_next_1"], errors="coerce")
    minutes = pd.to_numeric(ordered["minutes"], errors="coerce")
    starts = pd.to_numeric(ordered["starts"], errors="coerce")
    invalid_fixture_count = fixtures.isna() | fixtures.lt(0) | fixtures.mod(1).ne(0)
    activity_without_fixture = fixtures.eq(0) & (
        minutes.gt(0) | starts.fillna(0).gt(0) | ordered["appearance_next_1"].eq(1)
    )

    violations = {
        "duplicate_player_events": int(
            ordered.duplicated(["season", "event_sequence", "player_code"]).sum()
        ),
        "invalid_timestamps": int(invalid_prediction_cutoff.sum() + invalid_available_at.sum()),
        "feature_timestamp_at_or_after_cutoff": int(
            (available & prediction_cutoff.notna() & (available_at >= prediction_cutoff)).sum()
        ),
        "invalid_player_event_observed": int(
            (~ordered["player_event_observed"].isin([0, 1, False, True])).sum()
        ),
        "invalid_player_position": int(
            (~ordered["position"].isin(["GK", "DEF", "MID", "FWD"])).sum()
        ),
        "invalid_fixture_count": int(invalid_fixture_count.sum()),
        "minutes_exceed_fixture_capacity": int((minutes > 90 * fixtures).sum()),
        "starts_exceed_fixture_capacity": int(
            (ordered["has_starts_source"].eq(1) & (starts > fixtures)).sum()
        ),
        "activity_without_fixture": int(activity_without_fixture.sum()),
        "incorrect_team_event_observed": int(
            ordered["team_event_observed"].astype(int).ne(fixtures.gt(0).astype(int)).sum()
        ),
        "unobserved_registration_bounds": registration_bound_violations,
        "incorrect_points_next_1": mismatch_count(ordered["points_next_1"], expected_points_1),
        "incorrect_minutes_next_1": mismatch_count(
            ordered["minutes_next_1"], expected_minutes_1
        ),
        "incorrect_appearance_next_1": mismatch_count(
            ordered["appearance_next_1"], expected_appearance
        ),
        "incorrect_start_next_1": mismatch_count(ordered["start_next_1"], expected_starts),
        "incorrect_points_next_6": mismatch_count(ordered["points_next_6"], expected_points_6),
        "incorrect_minutes_next_6": mismatch_count(
            ordered["minutes_next_6"], expected_minutes_6
        ),
        "rolling_feature_mismatch": rolling_mismatches,
        "incorrect_one_event_observation_index": int(
            ordered["target_1_observed_event"].ne(ordered["event_sequence"]).sum()
        ),
        "incorrect_six_event_observation_index": int(
            ordered["target_6_observed_event"].ne(ordered["event_sequence"] + 5).sum()
        ),
        "start_without_appearance": int(
            (
                ordered["start_next_1"].fillna(0).astype(float)
                > ordered["appearance_next_1"].fillna(0).astype(float)
            ).sum()
        ),
    }
    return LeakageAudit(rows=len(table), violations=violations)


def _history_mask_and_weights(
    train: Any,
    *,
    validation_season: str,
    season_order: list[str],
    history_seasons: int | None,
    half_life_seasons: float | None,
) -> tuple[Any, Any | None, str]:
    import numpy as np

    validation_index = season_order.index(validation_season)
    train_indices = train["season"].astype(str).map(season_order.index)
    mask = train_indices.le(validation_index)
    strategy = "all_history"
    if history_seasons is not None:
        first_index = max(0, validation_index - history_seasons + 1)
        mask &= train_indices.ge(first_index)
        strategy = f"last_{history_seasons}_seasons"

    weights = None
    if half_life_seasons is not None:
        distances = validation_index - train_indices
        weights = np.power(0.5, distances / half_life_seasons)
        strategy = f"half_life_{half_life_seasons:g}_seasons"
    return mask, weights, strategy


def walk_forward_validate(
    table_path: str | Path,
    *,
    target: str = "points_next_6",
    minimum_train_gameweeks: int = 20,
    feature_set: str = "common",
    history_seasons: int | None = None,
    half_life_seasons: float | None = None,
    embargo_events: int = 0,
) -> list[ValidationResult]:
    """Run purged rolling-origin validation over chronological event periods."""
    try:
        import pandas as pd
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error
    except ImportError as error:  # pragma: no cover
        raise RuntimeError('Install dependencies with: pip install -e ".[model]"') from error

    if feature_set not in FEATURE_SETS:
        raise ValueError(f"Unknown feature set {feature_set!r}; choose from {sorted(FEATURE_SETS)}")
    if history_seasons is not None and half_life_seasons is not None:
        raise ValueError("Choose a fixed history window or a half-life, not both")

    table = pd.read_csv(table_path, low_memory=False)
    if "event_sequence" not in table.columns:
        raise ValueError("Rebuild the modeling table: event_sequence is required")
    features = FEATURE_SETS[feature_set]
    identity = "player_code" if "player_code" in table.columns else "player_id"
    required = {"season", "gameweek", "event_sequence", identity, target, *features}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(f"Modeling table is missing columns: {sorted(missing)}")

    table["season"] = table["season"].astype(str)
    season_order = table["season"].drop_duplicates().tolist()
    table["_season_order"] = table["season"].map(season_order.index)
    table = table.sort_values(["_season_order", "event_sequence", identity])
    time_keys = table[["season", "gameweek", "event_sequence"]].drop_duplicates()
    horizon = infer_target_horizon(target)

    results: list[ValidationResult] = []
    for index in range(minimum_train_gameweeks, len(time_keys)):
        key = time_keys.iloc[index]
        train_mask = purged_training_mask(
            table,
            validation_season=str(key["season"]),
            validation_event_sequence=int(key["event_sequence"]),
            horizon=horizon,
            embargo_events=embargo_events,
            season_order=season_order,
        )
        current = table["season"].eq(str(key["season"])) & table["event_sequence"].eq(
            int(key["event_sequence"])
        )
        train = table.loc[train_mask].dropna(subset=[target])
        validation = table.loc[current].dropna(subset=[target])
        if feature_set == "modern":
            train = train.loc[
                train["has_expected_stats_source"].eq(1)
                & train["has_starts_source"].eq(1)
            ]
            validation = validation.loc[
                validation["has_expected_stats_source"].eq(1)
                & validation["has_starts_source"].eq(1)
            ]
        history_mask, weights, strategy = _history_mask_and_weights(
            train,
            validation_season=str(key["season"]),
            season_order=season_order,
            history_seasons=history_seasons,
            half_life_seasons=half_life_seasons,
        )
        train = train.loc[history_mask]
        if weights is not None:
            weights = weights.loc[history_mask]
        if train.empty or validation.empty:
            continue

        model = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_iter=250,
            max_leaf_nodes=20,
            l2_regularization=1.0,
            random_state=26,
        )
        model.fit(train[list(features)], train[target], sample_weight=weights)
        predictions = model.predict(validation[list(features)])
        rank_correlation = pd.Series(predictions).corr(
            validation[target].reset_index(drop=True), method="spearman"
        )
        results.append(
            ValidationResult(
                season=str(key["season"]),
                cutoff_gameweek=int(key["gameweek"]),
                cutoff_event_sequence=int(key["event_sequence"]),
                rows=len(validation),
                mean_absolute_error=float(mean_absolute_error(validation[target], predictions)),
                spearman_rank_correlation=float(rank_correlation),
                target=target,
                feature_set=feature_set,
                history_strategy=strategy,
            )
        )
    return results


def compare_recency_strategies(
    table_path: str | Path,
    *,
    target: str = "points_next_6",
    feature_set: str = "common",
    minimum_train_gameweeks: int = 20,
) -> dict[str, list[ValidationResult]]:
    """Evaluate all-history, fixed-window, and exponential-decay challengers."""
    configurations = {
        "all_history": {},
        **{f"last_{years}_seasons": {"history_seasons": years} for years in (3, 5, 7)},
        **{
            f"half_life_{years}_seasons": {"half_life_seasons": float(years)}
            for years in (2, 3, 5)
        },
    }
    return {
        name: walk_forward_validate(
            table_path,
            target=target,
            feature_set=feature_set,
            minimum_train_gameweeks=minimum_train_gameweeks,
            **configuration,
        )
        for name, configuration in configurations.items()
    }
