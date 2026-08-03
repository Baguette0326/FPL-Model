"""CSV input/output helpers for projections."""

from __future__ import annotations

import csv
from pathlib import Path

from .draft import PlayerProjection


def load_projections(path: str | Path) -> list[PlayerProjection]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        required = {"name", "position", "projected_points", "uncertainty"}
        if rows.fieldnames is None or not required.issubset(rows.fieldnames):
            missing = required.difference(rows.fieldnames or [])
            raise ValueError(f"Projection CSV is missing columns: {sorted(missing)}")
        return [
            PlayerProjection(
                name=row["name"],
                position=row["position"].upper(),
                projected_points=float(row["projected_points"]),
                uncertainty=float(row["uncertainty"]),
            )
            for row in rows
        ]
