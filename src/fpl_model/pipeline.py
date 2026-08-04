"""Command-line orchestration for the first real-data milestone."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .baseline import build_current_projections, evaluate_recency_baseline, write_baseline_report
from .features import build_modeling_table
from .ingest import ingest_all, load_source_config
from .modeling import audit_modeling_table
from .storage import initialize_database

LEGACY_MODELING_TABLE = Path("data/processed/modeling_table.csv")
ML_V2_MODELING_TABLE = Path("data/processed/modeling_table_ml_v2.csv")
ML_V2_AUDIT_REPORT = Path("reports/ml_v2_data_audit.json")


def build_ml_v2_table(raw_root: Path, seasons: list[str]) -> pd.DataFrame:
    """Build, audit, and publish v2 without touching the legacy table."""
    table = build_modeling_table(raw_root, seasons)
    audit = audit_modeling_table(table)
    audit.raise_for_violations()

    ML_V2_MODELING_TABLE.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(ML_V2_MODELING_TABLE, index=False)
    ML_V2_AUDIT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ML_V2_AUDIT_REPORT.write_text(
        json.dumps(
            {
                "table": str(ML_V2_MODELING_TABLE),
                "rows": audit.rows,
                "passed": audit.passed,
                "violations": audit.violations,
                "seasons": seasons,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return table


def run_pipeline(*, refresh: bool = False) -> None:
    config_path = Path("configs/data_sources.json")
    raw_root = Path("data/raw")
    processed_root = Path("data/processed")
    config = load_source_config(config_path)
    ingest_all(config_path, raw_root, refresh=refresh)

    seasons = config["historical"]["seasons"]
    table = build_ml_v2_table(raw_root, seasons)
    metrics = evaluate_recency_baseline(table)
    metrics.to_csv(processed_root / "baseline_metrics.csv", index=False, float_format="%.6f")

    current_season = config["current"]["season"]
    projections = build_current_projections(
        raw_root / current_season / "bootstrap-static.json",
        raw_root / current_season / "fixtures.json",
        raw_root / seasons[-1] / "players_raw.csv",
        processed_root / f"{current_season}_baseline_projections.csv",
    )
    write_baseline_report(metrics, projections, "reports/baseline_report.md")
    print(f"modeling rows: {len(table):,}")
    print(f"current players ranked: {len(projections):,}")
    print("report: reports/baseline_report.md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build FPL historical data and baseline rankings")
    parser.add_argument(
        "command", choices=("all", "ingest", "features", "baseline", "init-db")
    )
    parser.add_argument("--refresh", action="store_true", help="Redownload existing raw snapshots")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config_path = Path("configs/data_sources.json")
    raw_root = Path("data/raw")
    processed_root = Path("data/processed")
    config = load_source_config(config_path)
    seasons = config["historical"]["seasons"]

    if args.command == "init-db":
        initialize_database("data/league.sqlite3")
        print("database: data/league.sqlite3")
        return
    if args.command == "all":
        run_pipeline(refresh=args.refresh)
        return
    if args.command == "ingest":
        manifest = ingest_all(config_path, raw_root, refresh=args.refresh)
        print(f"source files ready: {len(manifest['files'])}")
        return
    if args.command == "features":
        table = build_ml_v2_table(raw_root, seasons)
        print(f"modeling rows: {len(table):,}")
        print(f"modeling table: {ML_V2_MODELING_TABLE}")
        print(f"leakage audit: {ML_V2_AUDIT_REPORT}")
        return

    modeling_path = (
        ML_V2_MODELING_TABLE if ML_V2_MODELING_TABLE.exists() else LEGACY_MODELING_TABLE
    )
    table = pd.read_csv(modeling_path, low_memory=False)
    metrics = evaluate_recency_baseline(table)
    metrics.to_csv(
        processed_root / "baseline_metrics.csv", index=False, float_format="%.6f"
    )
    current_season = config["current"]["season"]
    projections = build_current_projections(
        raw_root / current_season / "bootstrap-static.json",
        raw_root / current_season / "fixtures.json",
        raw_root / seasons[-1] / "players_raw.csv",
        processed_root / f"{current_season}_baseline_projections.csv",
    )
    write_baseline_report(metrics, projections, "reports/baseline_report.md")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
