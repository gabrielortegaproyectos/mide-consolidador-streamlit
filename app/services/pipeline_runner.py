from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineInputs:
    pdf_path: Path
    matrix_path: Path
    career: str
    faculty: str | None = None
    school: str | None = None
    degree: str | None = None
    cycle_type: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    output_dir: Path
    artifacts: dict[str, Path]
    warnings: list[str]


def run_uploaded_pipeline(inputs: PipelineInputs) -> PipelineResult:
    """Run the ETL from uploaded files once the public ETL contract is stable."""
    raise NotImplementedError(
        "Pending ETL contract: call tributacion.pipeline.run_pipeline here."
    )

