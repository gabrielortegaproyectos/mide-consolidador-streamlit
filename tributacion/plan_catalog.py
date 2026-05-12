"""plan_catalog.py — Carga compartida del catálogo de planes activos.

Centraliza la lectura de ``data/data_primary/plans_mapped.json`` para que
los scripts de procesamiento y la suite de validación estructural usen
la misma fuente de verdad.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tributacion.ciclo_catalog import resolve_tipo_ciclo

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLANS_MAPPED_PATH = REPO_ROOT / "data" / "data_primary" / "plans_mapped.json"


@dataclass(frozen=True)
class MatrixVariant:
    """Variante de matriz asociada a una opción académica del PDF."""

    label: str
    matrix_rel_path: str
    matrix_path: Path


@dataclass(frozen=True)
class PlanCatalogEntry:
    """Entrada tipada del catálogo de planes activos."""

    grado: str
    facultad: str
    escuela: str
    carrera: str
    pdf_rel_path: str
    pdf_path: Path
    matrix_rel_path: str
    matrix_path: Path | None
    tipo_ciclo: str | None = None
    matrix_variants: tuple[MatrixVariant, ...] = ()

    def meta(self, carrera: str | None = None) -> dict[str, str]:
        """Construye el bloque ``meta`` esperado por el pipeline."""
        return {
            "GRADO": self.grado,
            "FACULTAD": self.facultad,
            "ESCUELA": self.escuela,
            "CARRERA": carrera or self.carrera,
            "TIPO_CICLO": self.tipo_ciclo or "",
        }


def resolve_repo_path(path_str: str, repo_root: Path | None = None) -> Path:
    """Resuelve una ruta relativa al repositorio a una ruta absoluta."""
    root = (repo_root or REPO_ROOT).resolve()
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _parse_variants(raw_variants: list[dict[str, Any]], repo_root: Path) -> tuple[MatrixVariant, ...]:
    variants: list[MatrixVariant] = []
    for raw_variant in raw_variants:
        matrix_rel_path = str(raw_variant.get("matrix_path", "")).strip()
        if not matrix_rel_path:
            continue
        variants.append(
            MatrixVariant(
                label=str(raw_variant.get("label", "")).strip(),
                matrix_rel_path=matrix_rel_path,
                matrix_path=resolve_repo_path(matrix_rel_path, repo_root),
            )
        )
    return tuple(variants)


def load_plan_catalog(
    plans_path: Path | None = None,
    repo_root: Path | None = None,
) -> list[PlanCatalogEntry]:
    """Carga el catálogo activo de planes desde ``plans_mapped.json``."""
    root = (repo_root or REPO_ROOT).resolve()
    if plans_path is None:
        catalog_path = resolve_repo_path("data/data_primary/plans_mapped.json", root)
    else:
        catalog_path = resolve_repo_path(str(plans_path), root)

    with catalog_path.open(encoding="utf-8") as fh:
        raw_plans: list[dict[str, Any]] = json.load(fh)

    plans: list[PlanCatalogEntry] = []
    for raw_plan in raw_plans:
        pdf_rel_path = str(raw_plan.get("pdf_path", "")).strip()
        matrix_rel_path = str(raw_plan.get("matrix_path", "")).strip()
        matrix_path = resolve_repo_path(matrix_rel_path, root) if matrix_rel_path else None
        pdf_path = resolve_repo_path(pdf_rel_path, root)
        tipo_ciclo = resolve_tipo_ciclo(
            carrera=str(raw_plan.get("CARRERA", "")).strip(),
            matrix_path=matrix_path,
            pdf_path=pdf_path,
            repo_root=root,
        )

        plans.append(
            PlanCatalogEntry(
                grado=str(raw_plan.get("GRADO", "PREGRADO")).strip(),
                facultad=str(raw_plan.get("FACULTAD", "")).strip(),
                escuela=str(raw_plan.get("ESCUELA", "")).strip(),
                carrera=str(raw_plan.get("CARRERA", "")).strip(),
                pdf_rel_path=pdf_rel_path,
                pdf_path=pdf_path,
                matrix_rel_path=matrix_rel_path,
                matrix_path=matrix_path,
                tipo_ciclo=tipo_ciclo,
                matrix_variants=_parse_variants(raw_plan.get("matrix_variants") or [], root),
            )
        )

    return plans


__all__ = [
    "DEFAULT_PLANS_MAPPED_PATH",
    "MatrixVariant",
    "PlanCatalogEntry",
    "REPO_ROOT",
    "load_plan_catalog",
    "resolve_repo_path",
]
