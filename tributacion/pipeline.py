"""pipeline.py — Orquestador del pipeline completo de tributación curricular.

Encadena las tres etapas del proceso en una sola llamada:

1. :func:`~tributacion.pdf_parser.parse_pdf`
   → extrae las horas de cada asignatura desde el PDF del plan de estudio.
2. :func:`~tributacion.matrix_parser.parse_matrix`
   → construye el consolidado de tributación desde la Matriz Excel.
3. :func:`~tributacion.merger.merge_horas`
   → une ambos DataFrames y completa las columnas de horas y códigos.

El resultado se escribe en ``output_xlsx``.

Función pública principal
-------------------------
:func:`run_pipeline`
"""

import logging
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal, overload

import pandas as pd

from tributacion.ciclo_catalog import enrich_meta_with_tipo_ciclo
from tributacion.exceptions import PipelineInputFileError
from tributacion.matrix_parser import extract_matrix_courses, parse_matrix
from tributacion.merger import merge_horas
from tributacion.pdf_parser import parse_pdf
from tributacion.ra_normalizer import normalize_df_nombre_ra_with_local_catalog
from tributacion.subject_code_enricher import apply_subject_codes
from tributacion.types import PipelineArtifacts, PipelineResult

logger = logging.getLogger(__name__)


def get_pipeline_version() -> str:
    """Retorna la version instalada del paquete ETL."""
    try:
        return version("tributacion")
    except PackageNotFoundError:
        return "unknown"


def _build_result(
    df_final: pd.DataFrame,
    output_xlsx: Path,
    horas_pdf_csv: Path,
    matching_matriz_pdf_csv: Path,
    matching_codigos_csv: Path,
) -> PipelineResult:
    """Construye el resultado publico del pipeline."""
    return PipelineResult(
        dataframe=df_final,
        artifacts=PipelineArtifacts(
            consolidated_excel=output_xlsx,
            horas_pdf_csv=horas_pdf_csv,
            matching_matriz_pdf_csv=matching_matriz_pdf_csv,
            matching_codigos_csv=matching_codigos_csv,
        ),
        pipeline_version=get_pipeline_version(),
    )


def _first_non_empty(series: pd.Series) -> str:
    for value in series.dropna():
        text = str(value).strip()
        if text:
            return text
    return ""


@overload
def run_pipeline(
    pdf_path: Path,
    matrix_xlsx: Path,
    output_xlsx: Path,
    sheet_name: str = "Asignaturas - RA",
    meta: dict | None = None,
    *,
    return_result: Literal[False] = False,
) -> pd.DataFrame: ...


@overload
def run_pipeline(
    pdf_path: Path,
    matrix_xlsx: Path,
    output_xlsx: Path,
    sheet_name: str = "Asignaturas - RA",
    meta: dict | None = None,
    *,
    return_result: Literal[True],
) -> PipelineResult: ...


def run_pipeline(
    pdf_path: Path,
    matrix_xlsx: Path,
    output_xlsx: Path,
    sheet_name: str = "Asignaturas - RA",
    meta: dict | None = None,
    *,
    return_result: bool = False,
) -> pd.DataFrame | PipelineResult:
    """Ejecuta el pipeline completo de tributación curricular.

    Toma un PDF de plan de estudio y un Excel de Matriz de Tributación,
    los procesa y escribe el Excel final con las 36 columnas de tributación
    enriquecido con las horas de cada asignatura.

    Args:
        pdf_path:    Ruta al PDF del plan de estudio de la carrera.
        matrix_xlsx: Ruta al Excel de la Matriz de Tributación.
        output_xlsx: Ruta de destino para el Excel de salida. Se crean
                     los directorios padre si no existen.
        sheet_name:  Nombre de la hoja en la Matriz de Tributación.
                     Por defecto ``"Asignaturas - RA"``.
        meta:        Diccionario con ``GRADO``, ``FACULTAD``, ``ESCUELA`` y
                     ``CARRERA`` de la carrera. Si es ``None`` se usan cadenas vacías.

    Returns:
        DataFrame con el resultado final (mismo contenido que ``output_xlsx``)
        por defecto. Si ``return_result=True``, retorna ``PipelineResult`` con
        DataFrame, version y rutas de artefactos para consumo desde apps.

    Raises:
        PipelineInputFileError: Si ``pdf_path`` o ``matrix_xlsx`` no existen.

    Examples:
        >>> df = run_pipeline(
        ...     pdf_path=Path("Plan de Estudios Informática.pdf"),
        ...     matrix_xlsx=Path("Matriz de Tributación.xlsx"),
        ...     output_xlsx=Path("data/output/tributacion_final.xlsx"),
        ...     meta={"GRADO": "PREGRADO", "FACULTAD": "INGENIERÍA, CIENCIA Y TECNOLOGÍA",
        ...           "ESCUELA": "INGENIERÍA EN INFORMÁTICA", "CARRERA": "INGENIERÍA EN INFORMÁTICA"},
        ... )
        >>> len(df.columns)
        36
    """
    pdf_path    = Path(pdf_path)
    matrix_xlsx = Path(matrix_xlsx)
    output_xlsx = Path(output_xlsx)

    # --- Validación de archivos de entrada ----------------------------------
    if not pdf_path.exists():
        raise PipelineInputFileError(f"PDF no encontrado: {pdf_path}")
    if not matrix_xlsx.exists():
        raise PipelineInputFileError(f"Matriz Excel no encontrada: {matrix_xlsx}")

    meta = dict(meta or {})

    # --- Etapa 1: Extraer horas del PDF -------------------------------------
    logger.info("Etapa 1/3 — Extrayendo horas del PDF: %s", pdf_path.name)
    df_horas = parse_pdf(pdf_path)
    # Drop internal _opcion column if present (used by _split_by_option in run_batch)
    df_horas = df_horas.drop(columns=["_opcion"], errors="ignore")
    logger.info("  → %d filas de asignaturas extraídas del PDF", len(df_horas))

    if not str(meta.get("CARRERA", "")).strip() and "CARRERA" in df_horas.columns:
        carrera = _first_non_empty(df_horas["CARRERA"])
        if carrera:
            meta["CARRERA"] = carrera
    meta = enrich_meta_with_tipo_ciclo(meta, matrix_path=matrix_xlsx, pdf_path=pdf_path)

    # Guardar CSV intermedio para trazabilidad
    csv_path = output_xlsx.parent / f"{output_xlsx.stem}_horas_pdf.csv"
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    df_horas.to_csv(str(csv_path), index=False, encoding="utf-8-sig")
    logger.info("  → CSV intermedio guardado en: %s", csv_path)

    # --- Etapa 2: Construir consolidado desde la matriz ---------------------
    logger.info(
        "Etapa 2/3 — Construyendo consolidado desde la Matriz: %s (hoja: %s)",
        matrix_xlsx.name,
        sheet_name,
    )
    df_consolidado = parse_matrix(matrix_xlsx, sheet_name, meta=meta)
    logger.info("  → %d registros de tributación generados", len(df_consolidado))
    df_matrix_courses = extract_matrix_courses(matrix_xlsx, sheet_name)

    # --- Normalización canónica de NOMBRE RA --------------------------------
    df_consolidado = normalize_df_nombre_ra_with_local_catalog(df_consolidado)

    # --- Etapa 3: Fusionar horas con el consolidado -------------------------
    logger.info("Etapa 3/3 — Fusionando horas con el consolidado de tributación")
    matching_path = output_xlsx.parent / f"{output_xlsx.stem}_matching.csv"
    df_final = merge_horas(
        df_consolidado,
        df_horas,
        matching_path=matching_path,
        include_pdf_only=True,
        matrix_courses=df_matrix_courses,
    )

    matched = df_final["N° DE CRÉDITOS"].notna().sum()
    logger.info(
        "  → %d/%d filas con horas completadas (%.0f%%)",
        matched,
        len(df_final),
        100 * matched / len(df_final) if len(df_final) else 0,
    )

    # --- Capa final: códigos oficiales de asignatura ------------------------
    codes_matching_path = output_xlsx.parent / f"{output_xlsx.stem}_subject_codes_matching.csv"
    df_final = apply_subject_codes(df_final, matching_path=codes_matching_path)

    # --- Escritura del Excel de salida --------------------------------------
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_excel(str(output_xlsx), index=False)
    logger.info("Excel de salida escrito en: %s", output_xlsx)

    result = _build_result(
        df_final=df_final,
        output_xlsx=output_xlsx,
        horas_pdf_csv=csv_path,
        matching_matriz_pdf_csv=matching_path,
        matching_codigos_csv=codes_matching_path,
    )
    if return_result:
        return result
    return result.dataframe


def run_pipeline_result(
    pdf_path: Path,
    matrix_xlsx: Path,
    output_xlsx: Path,
    sheet_name: str = "Asignaturas - RA",
    meta: dict | None = None,
) -> PipelineResult:
    """Ejecuta el pipeline y retorna siempre un resultado tipado.

    Esta entrada es la recomendada para aplicaciones como Streamlit porque
    expone las rutas de salida sin depender de convenciones internas.
    """
    return run_pipeline(
        pdf_path=pdf_path,
        matrix_xlsx=matrix_xlsx,
        output_xlsx=output_xlsx,
        sheet_name=sheet_name,
        meta=meta,
        return_result=True,
    )


def run_pipeline_from_df(
    df_horas: pd.DataFrame,
    matrix_xlsx: Path,
    output_xlsx: Path,
    sheet_name: str = "Asignaturas - RA",
    meta: dict | None = None,
    *,
    return_result: bool = False,
) -> pd.DataFrame | PipelineResult:
    """Ejecuta las etapas 2 y 3 del pipeline usando un DataFrame de horas ya extraido.

    Equivalente a :func:`run_pipeline` pero la etapa 1 (``parse_pdf``) ya fue
    realizada externamente.  Se usa en el modo de variantes académicas cuando
    el mismo PDF se divide en múltiples carreras mediante
    :func:`~tributacion.pdf_parser._split_by_option`.

    Args:
        df_horas:    DataFrame de horas (salida de ``parse_pdf`` ya filtrado por
                     variante, sin la columna ``'_opcion'``).
        matrix_xlsx: Ruta al Excel de la Matriz de Tributación.
        output_xlsx: Ruta de destino para el Excel de salida.
        sheet_name:  Nombre de la hoja en la Matriz de Tributación.
        meta:        Diccionario con ``GRADO``, ``FACULTAD``, ``ESCUELA`` y
                     ``CARRERA``.  Si es ``None`` se usan cadenas vacías.

    Returns:
        DataFrame con el resultado final.

    Raises:
        FileNotFoundError: Si ``matrix_xlsx`` no existe.
    """
    matrix_xlsx = Path(matrix_xlsx)
    output_xlsx = Path(output_xlsx)

    if not matrix_xlsx.exists():
        raise PipelineInputFileError(f"Matriz Excel no encontrada: {matrix_xlsx}")

    meta = enrich_meta_with_tipo_ciclo(meta, matrix_path=matrix_xlsx)

    # Strip internal column if caller forgot
    df_horas = df_horas.drop(columns=["_opcion"], errors="ignore")

    # --- Etapa 2: Consolidado desde la matriz --------------------------------
    logger.info(
        "Etapa 2/3 — Construyendo consolidado desde la Matriz: %s (hoja: %s)",
        matrix_xlsx.name,
        sheet_name,
    )
    df_consolidado = parse_matrix(matrix_xlsx, sheet_name, meta=meta)
    logger.info("  → %d registros de tributación generados", len(df_consolidado))
    df_matrix_courses = extract_matrix_courses(matrix_xlsx, sheet_name)

    # --- Normalización canónica de NOMBRE RA --------------------------------
    df_consolidado = normalize_df_nombre_ra_with_local_catalog(df_consolidado)

    # --- Etapa 3: Guardar CSV intermedio y fusionar --------------------------
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    csv_path = output_xlsx.parent / f"{output_xlsx.stem}_horas_pdf.csv"
    df_horas.to_csv(str(csv_path), index=False, encoding="utf-8-sig")
    logger.info("  → CSV intermedio guardado en: %s", csv_path)

    logger.info("Etapa 3/3 — Fusionando horas con el consolidado de tributación")
    matching_path = output_xlsx.parent / f"{output_xlsx.stem}_matching.csv"
    df_final = merge_horas(
        df_consolidado,
        df_horas,
        matching_path=matching_path,
        include_pdf_only=True,
        matrix_courses=df_matrix_courses,
    )

    matched = df_final["N° DE CRÉDITOS"].notna().sum()
    logger.info(
        "  → %d/%d filas con horas completadas (%.0f%%)",
        matched,
        len(df_final),
        100 * matched / len(df_final) if len(df_final) else 0,
    )

    codes_matching_path = output_xlsx.parent / f"{output_xlsx.stem}_subject_codes_matching.csv"
    df_final = apply_subject_codes(df_final, matching_path=codes_matching_path)

    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_excel(str(output_xlsx), index=False)
    logger.info("Excel de salida escrito en: %s", output_xlsx)

    result = _build_result(
        df_final=df_final,
        output_xlsx=output_xlsx,
        horas_pdf_csv=csv_path,
        matching_matriz_pdf_csv=matching_path,
        matching_codigos_csv=codes_matching_path,
    )
    if return_result:
        return result
    return result.dataframe
