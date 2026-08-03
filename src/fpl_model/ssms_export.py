"""Create a SQL Server/SSMS-friendly copy of the modeling table."""

from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path


def normalize_team_identifier(value: str) -> str:
    """Return a non-empty text identifier so SSMS never infers a numeric team column."""
    text = value.strip()
    if not text:
        return "team_unknown"
    if text.startswith(("team_id_", "team_name_", "team_unknown")):
        return text
    try:
        number = float(text)
    except ValueError:
        return f"team_name_{text}"
    if math.isfinite(number) and number.is_integer():
        return f"team_id_{int(number)}"
    return f"team_id_{text}"


def export_ssms_csv(source_path: str | Path, output_path: str | Path) -> int:
    """Normalize a CSV for SSMS using UTF-8 BOM, CRLF, and a textual team field."""
    source = Path(source_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    rows_written = 0

    with source.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.reader(input_file)
        header = next(reader)
        if "team" not in header:
            raise ValueError("Modeling table is missing the team column")
        team_index = header.index("team")

        with temporary.open("w", encoding="utf-8-sig", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\r\n")
            writer.writerow(header)
            for line_number, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    raise ValueError(
                        f"Row {line_number} has {len(row)} fields; expected {len(header)}"
                    )
                row[team_index] = normalize_team_identifier(row[team_index])
                writer.writerow(row)
                rows_written += 1

    os.replace(temporary, output)
    return rows_written


def main() -> None:
    parser = argparse.ArgumentParser(description="Make modeling_table.csv SSMS-friendly")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()
    destination = args.output or args.source
    rows = export_ssms_csv(args.source, destination)
    print(f"SSMS-compatible rows written: {rows:,}")
    print(f"output: {destination}")


if __name__ == "__main__":
    main()
