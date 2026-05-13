from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def collect_artifacts(output_dir: Path) -> dict[str, Path]:
    """Return known ETL artifacts from an output directory."""
    if not output_dir.exists():
        return {}

    return {
        path.name: path
        for path in output_dir.iterdir()
        if path.suffix.lower() in {".xlsx", ".csv", ".md"}
    }


def build_artifacts_zip(artifacts: dict[str, Path]) -> bytes:
    """Build an in-memory ZIP with generated ETL artifacts."""
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for artifact in artifacts.values():
            path = Path(artifact)
            if path.exists() and path.is_file():
                archive.write(path, arcname=path.name)
    return buffer.getvalue()

