"""Command-line orchestration for the first real-data milestone."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .baseline import build_current_projections, evaluate_recency_baseline, write_baseline_report
from .features import build_modeling_table
from .ingest import ingest_all, load_source_config


def run_pipeline(*, refresh: bool = False) -> None:
    config_path = Path("configs/data_sources.json")
    raw_root = Path("data/raw")
    processed_root = Path("data/processed")
    config = load_source_config(config_path)
    ingest_all(config_path, raw_root, refresh=refresh)

    seasons = config["historical"]["seasons"]
    table = build_modeling_table(
        raw_root,
        seasons,
        processed_root / "modeling_table.csv",
    )
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
    parser.add_argument("command", choices=("all", "ingest", "features", "baseline"))
    parser.add_argument("--refresh", action="store_true", help="Redownload existing raw snapshots")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config_path = Path("configs/data_sources.json")
    raw_root = Path("data/raw")
    processed_root = Path("data/processed")
    config = load_source_config(config_path)
    seasons = config["historical"]["seasons"]

    if args.command == "all":
        run_pipeline(refresh=args.refresh)
        return
    if args.command == "ingest":
        manifest = ingest_all(config_path, raw_root, refresh=args.refresh)
        print(f"source files ready: {len(manifest['files'])}")
        return
    if args.command == "features":
        table = build_modeling_table(raw_root, seasons, processed_root / "modeling_table.csv")
        print(f"modeling rows: {len(table):,}")
        return

    table = pd.read_csv(processed_root / "modeling_table.csv", low_memory=False)
    metrics = evaluate_recency_baseline(table)
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
