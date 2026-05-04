from __future__ import annotations

from pathlib import Path


def collect_artifacts(output_dir: Path) -> dict[str, Path]:
    """Return known ETL artifacts from an output directory."""
    if not output_dir.exists():
        return {}

    return {
        path.name: path
        for path in output_dir.iterdir()
        if path.suffix.lower() in {".xlsx", ".csv", ".md"}
    }

