"""ciclo_catalog.py — Resolución de ciclos curriculares desde catálogos manuales.

Centraliza la lectura de:

- ``data/ciclos_manual/ciclos_manual.json`` para resolver ``tipo_ciclo`` por
  carrera o por rutas de archivos.
- ``data/ciclos_manual/ciclos_semestres.json`` para mapear
  ``(tipo_ciclo, semestre) -> etiqueta final de CICLO``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


_PACKAGE_PATH = Path(__file__).resolve()
REPO_ROOT = (
    _PACKAGE_PATH.parents[1]
    if (_PACKAGE_PATH.parents[1] / "data").exists()
    else _PACKAGE_PATH.parents[2]
)
DEFAULT_CICLOS_MANUAL_PATH = REPO_ROOT / "data" / "ciclos_manual" / "ciclos_manual.json"
DEFAULT_CICLOS_SEMESTRES_PATH = REPO_ROOT / "data" / "ciclos_manual" / "ciclos_semestres.json"


def _repo_root(repo_root: Path | None = None) -> Path:
    return (repo_root or REPO_ROOT).resolve()


def _resolve_repo_path(path_value: str | Path, repo_root: Path | None = None) -> Path:
    root = _repo_root(repo_root)
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _norm_key(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


@dataclass(frozen=True)
class CycleManualIndex:
    """Índices de lookup para resolver ``tipo_ciclo``."""

    by_carrera_norm: dict[str, str]
    by_matrix_path: dict[str, str]
    by_pdf_path: dict[str, str]
    meta_by_carrera_norm: dict[str, dict[str, str]]
    meta_by_matrix_path: dict[str, dict[str, str]]
    meta_by_pdf_path: dict[str, dict[str, str]]


def _manual_catalog_path(repo_root: Path | None = None) -> Path:
    return _repo_root(repo_root) / "data" / "ciclos_manual" / "ciclos_manual.json"


def _semestres_catalog_path(repo_root: Path | None = None) -> Path:
    return _repo_root(repo_root) / "data" / "ciclos_manual" / "ciclos_semestres.json"


@lru_cache(maxsize=None)
def _load_manual_cycle_index_cached(repo_root_str: str) -> CycleManualIndex:
    root = Path(repo_root_str)
    path = _manual_catalog_path(root)
    if not path.exists():
        return CycleManualIndex(
            by_carrera_norm={},
            by_matrix_path={},
            by_pdf_path={},
            meta_by_carrera_norm={},
            meta_by_matrix_path={},
            meta_by_pdf_path={},
        )

    with path.open(encoding="utf-8") as fh:
        raw_entries: list[dict[str, Any]] = json.load(fh)

    by_carrera_norm: dict[str, str] = {}
    by_matrix_path: dict[str, str] = {}
    by_pdf_path: dict[str, str] = {}
    meta_by_carrera_norm: dict[str, dict[str, str]] = {}
    meta_by_matrix_path: dict[str, dict[str, str]] = {}
    meta_by_pdf_path: dict[str, dict[str, str]] = {}

    for entry in raw_entries:
        tipo_ciclo = str(entry.get("tipo_ciclo", "")).strip()
        if not tipo_ciclo:
            continue
        entry_meta = {
            key: str(entry.get(key, "")).strip()
            for key in ("GRADO", "FACULTAD", "ESCUELA", "CARRERA", "TIPO_CICLO")
            if str(entry.get(key, "")).strip()
        }
        entry_meta.setdefault("TIPO_CICLO", tipo_ciclo)

        carrera = str(entry.get("CARRERA", "")).strip()
        if carrera:
            carrera_key = _norm_key(carrera)
            by_carrera_norm.setdefault(carrera_key, tipo_ciclo)
            meta_by_carrera_norm.setdefault(carrera_key, entry_meta)

        matrix_path = str(entry.get("matrix_path", "")).strip()
        if matrix_path:
            resolved_matrix_path = str(_resolve_repo_path(matrix_path, root))
            by_matrix_path.setdefault(resolved_matrix_path, tipo_ciclo)
            meta_by_matrix_path.setdefault(resolved_matrix_path, entry_meta)

        pdf_path = str(entry.get("pdf_path", "")).strip()
        if pdf_path:
            resolved_pdf_path = str(_resolve_repo_path(pdf_path, root))
            by_pdf_path.setdefault(resolved_pdf_path, tipo_ciclo)
            meta_by_pdf_path.setdefault(resolved_pdf_path, entry_meta)

    return CycleManualIndex(
        by_carrera_norm=by_carrera_norm,
        by_matrix_path=by_matrix_path,
        by_pdf_path=by_pdf_path,
        meta_by_carrera_norm=meta_by_carrera_norm,
        meta_by_matrix_path=meta_by_matrix_path,
        meta_by_pdf_path=meta_by_pdf_path,
    )


def load_manual_cycle_index(repo_root: Path | None = None) -> CycleManualIndex:
    """Carga el índice manual de ``tipo_ciclo`` para el repositorio indicado."""
    return _load_manual_cycle_index_cached(str(_repo_root(repo_root)))


@lru_cache(maxsize=None)
def _load_semester_cycle_map_cached(repo_root_str: str) -> dict[str, dict[int, str]]:
    root = Path(repo_root_str)
    path = _semestres_catalog_path(root)
    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as fh:
        raw_catalog = json.load(fh)

    result: dict[str, dict[int, str]] = {}
    for entry in raw_catalog.get("tipos_ciclo", []):
        tipo_ciclo = str(entry.get("tipo_ciclo", "")).strip()
        if not tipo_ciclo:
            continue

        semesters: dict[int, str] = {}
        for semester_key, label in (entry.get("semestres") or {}).items():
            try:
                semesters[int(semester_key)] = str(label).strip()
            except (TypeError, ValueError):
                continue
        result[tipo_ciclo] = semesters

    return result


def load_semester_cycle_map(repo_root: Path | None = None) -> dict[str, dict[int, str]]:
    """Carga el mapa ``tipo_ciclo -> semestre -> etiqueta``."""
    return _load_semester_cycle_map_cached(str(_repo_root(repo_root)))


def resolve_tipo_ciclo(
    meta: dict[str, Any] | None = None,
    *,
    carrera: str | None = None,
    matrix_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    repo_root: Path | None = None,
) -> str | None:
    """Resuelve ``tipo_ciclo`` desde meta, carrera o rutas de archivos."""
    if meta:
        explicit_tipo = str(meta.get("TIPO_CICLO", "")).strip()
        if explicit_tipo:
            return explicit_tipo
        if carrera is None:
            carrera = str(meta.get("CARRERA", "")).strip() or None

    index = load_manual_cycle_index(repo_root)

    if carrera:
        tipo = index.by_carrera_norm.get(_norm_key(carrera))
        if tipo:
            return tipo

    if matrix_path:
        tipo = index.by_matrix_path.get(str(_resolve_repo_path(matrix_path, repo_root)))
        if tipo:
            return tipo

    if pdf_path:
        tipo = index.by_pdf_path.get(str(_resolve_repo_path(pdf_path, repo_root)))
        if tipo:
            return tipo

    return None


def infer_tipo_ciclo_from_max_semestre(
    max_semestre: int,
    *,
    repo_root: Path | None = None,
) -> str | None:
    """Infiere ``tipo_ciclo`` desde la duracion total detectada en la matriz."""
    duration_map = {
        8: "8_SEM_Licenciatura_super_titulacion",
        9: "9_SEM_Licenciatura_Titulacion",
        10: "10_SEM_Licenciatura_Titulacion",
    }
    tipo_ciclo = duration_map.get(int(max_semestre or 0))
    if tipo_ciclo and tipo_ciclo in load_semester_cycle_map(repo_root):
        return tipo_ciclo
    return None


def resolve_ciclo_label(
    semestre: int,
    tipo_ciclo: str,
    *,
    repo_root: Path | None = None,
) -> str | None:
    """Resuelve la etiqueta final de ``CICLO`` para un semestre dado."""
    if not tipo_ciclo:
        return None
    return load_semester_cycle_map(repo_root).get(tipo_ciclo, {}).get(int(semestre))


def enrich_meta_from_manual_catalog(
    meta: dict[str, Any] | None = None,
    *,
    carrera: str | None = None,
    matrix_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Completa metadatos faltantes desde ``ciclos_manual.json``."""
    meta_out = dict(meta or {})
    index = load_manual_cycle_index(repo_root)
    catalog_meta: dict[str, str] | None = None

    carrera_value = carrera or str(meta_out.get("CARRERA", "")).strip()
    if carrera_value:
        catalog_meta = index.meta_by_carrera_norm.get(_norm_key(carrera_value))

    if catalog_meta is None and matrix_path:
        catalog_meta = index.meta_by_matrix_path.get(
            str(_resolve_repo_path(matrix_path, repo_root))
        )

    if catalog_meta is None and pdf_path:
        catalog_meta = index.meta_by_pdf_path.get(
            str(_resolve_repo_path(pdf_path, repo_root))
        )

    if catalog_meta:
        for key, value in catalog_meta.items():
            if value and not str(meta_out.get(key, "")).strip():
                meta_out[key] = value
    return meta_out


def enrich_meta_with_tipo_ciclo(
    meta: dict[str, Any] | None = None,
    *,
    carrera: str | None = None,
    matrix_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Retorna ``meta`` enriquecido con ``TIPO_CICLO`` cuando se puede resolver."""
    meta_out = enrich_meta_from_manual_catalog(
        meta,
        carrera=carrera,
        matrix_path=matrix_path,
        pdf_path=pdf_path,
        repo_root=repo_root,
    )
    tipo_ciclo = resolve_tipo_ciclo(
        meta_out,
        carrera=carrera,
        matrix_path=matrix_path,
        pdf_path=pdf_path,
        repo_root=repo_root,
    )
    if tipo_ciclo:
        meta_out["TIPO_CICLO"] = tipo_ciclo
    return meta_out


def clear_cycle_catalog_cache() -> None:
    """Limpia caches internos. Útil en tests con catálogos temporales."""
    _load_manual_cycle_index_cached.cache_clear()
    _load_semester_cycle_map_cached.cache_clear()


__all__ = [
    "DEFAULT_CICLOS_MANUAL_PATH",
    "DEFAULT_CICLOS_SEMESTRES_PATH",
    "clear_cycle_catalog_cache",
    "enrich_meta_from_manual_catalog",
    "enrich_meta_with_tipo_ciclo",
    "infer_tipo_ciclo_from_max_semestre",
    "load_manual_cycle_index",
    "load_semester_cycle_map",
    "resolve_ciclo_label",
    "resolve_tipo_ciclo",
]
