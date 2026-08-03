"""Reproducible downloads for historical and current FPL data."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_source_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _download(url: str, destination: Path, *, refresh: bool) -> dict[str, Any]:
    if destination.exists() and not refresh:
        payload = destination.read_bytes()
        return {
            "url": url,
            "path": destination.as_posix(),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "downloaded": False,
        }

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "fpl-draft-model/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)
    return {
        "url": url,
        "path": destination.as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "downloaded": True,
    }


def ingest_all(
    config_path: str | Path = "configs/data_sources.json",
    raw_root: str | Path = "data/raw",
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Download configured sources and write a checksum manifest."""
    config = load_source_config(config_path)
    raw_root = Path(raw_root)
    files: list[dict[str, Any]] = []

    historical = config["historical"]
    for season in historical["seasons"]:
        season_root = raw_root / season
        files.append(
            _download(
                historical["gameweeks_url"].format(season=season),
                season_root / "merged_gw.csv",
                refresh=refresh,
            )
        )
        files.append(
            _download(
                historical["players_url"].format(season=season),
                season_root / "players_raw.csv",
                refresh=refresh,
            )
        )

    current = config["current"]
    current_root = raw_root / current["season"]
    files.append(
        _download(
            current["bootstrap_url"],
            current_root / "bootstrap-static.json",
            refresh=refresh,
        )
    )
    files.append(
        _download(
            current["fixtures_url"],
            current_root / "fixtures.json",
            refresh=refresh,
        )
    )

    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": str(config_path),
        "files": files,
    }
    raw_root.mkdir(parents=True, exist_ok=True)
    with (raw_root / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest
