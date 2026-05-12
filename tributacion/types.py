"""Tipos publicos para integrar el pipeline desde otras aplicaciones."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class PipelineArtifacts:
    """Rutas de los artefactos generados por una ejecucion del ETL."""

    consolidated_excel: Path
    horas_pdf_csv: Path
    matching_matriz_pdf_csv: Path
    matching_codigos_csv: Path
    validation_summary: Path | None = None


@dataclass(frozen=True)
class PipelineResult:
    """Resultado tipado para consumo programatico del ETL."""

    dataframe: pd.DataFrame
    artifacts: PipelineArtifacts
    warnings: list[str] = field(default_factory=list)
    pipeline_version: str = "unknown"
