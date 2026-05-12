from __future__ import annotations

from pathlib import Path

from tributacion.pipeline import run_pipeline_result
from tributacion.types import PipelineArtifacts, PipelineResult


def test_vendored_etl_contract_is_importable() -> None:
    """La app debe importar el contrato ETL sin acceder a otro repo privado."""
    assert callable(run_pipeline_result)
    assert PipelineArtifacts is not None
    assert PipelineResult is not None


def test_vendored_lightweight_catalogs_exist() -> None:
    """Los catalogos livianos requeridos por el ETL viajan con la app."""
    root = Path(__file__).resolve().parents[1]

    assert (root / "data" / "ciclos_manual" / "ciclos_manual.json").exists()
    assert (root / "data" / "ciclos_manual" / "ciclos_semestres.json").exists()
    assert (root / "data" / "codigos" / "CODIGOS_MALLAS - Hoja1.csv").exists()
    assert (root / "data" / "codigos" / "CODIGOS_MALLAS_ALIASES.csv").exists()
    assert (
        root / "data" / "normalizacion_ra" / "nombres_ra_canonicos.csv"
    ).exists()
