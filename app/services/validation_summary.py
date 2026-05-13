from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError


READY = "listo_para_descargar"
READY_WITH_WARNINGS = "descargar_con_advertencias"
NEEDS_REVIEW = "requiere_revision"


@dataclass(frozen=True)
class ValidationSummary:
    status: str
    total_rows: int = 0
    total_columns: int = 0
    main_columns: list[str] = field(default_factory=list)
    match_counts: dict[str, int] = field(default_factory=dict)
    code_counts: dict[str, int] = field(default_factory=dict)
    match_rate: float | None = None
    problematic_subjects: pd.DataFrame = field(default_factory=pd.DataFrame)
    warnings: list[str] = field(default_factory=list)


def expected_excel_fields() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Campo": "Asignatura",
                "Origen": "Matriz Excel",
                "Uso": "Llave principal para cruzar tributacion con horas del PDF.",
            },
            {
                "Campo": "Area / AR / RA",
                "Origen": "Matriz Excel",
                "Uso": "Estructura de tributacion curricular y resultados de aprendizaje.",
            },
            {
                "Campo": "Nivel de logro",
                "Origen": "Matriz Excel",
                "Uso": "Medida curricular que se conserva en el consolidado final.",
            },
            {
                "Campo": "Semestre, creditos y horas",
                "Origen": "PDF plan de estudio",
                "Uso": "Datos academicos extraidos y validados contra la matriz.",
            },
            {
                "Campo": "Codigo de asignatura",
                "Origen": "Catalogos ETL",
                "Uso": "Enriquecimiento para trazabilidad y consumo posterior.",
            },
        ]
    )


def build_validation_summary(artifacts: dict[str, Path]) -> ValidationSummary:
    """Construye un resumen de validacion desde artefactos diagnosticos ETL."""
    warnings: list[str] = []

    consolidated = _read_optional_excel(artifacts.get("consolidated_excel"))
    matching = _read_optional_csv(artifacts.get("matching_matriz_pdf_csv"))
    codes = _read_optional_csv(artifacts.get("matching_codigos_csv"))

    if matching is None:
        warnings.append("No se encontro diagnostico de matching matriz/PDF.")
    if codes is None:
        warnings.append("No se encontro diagnostico de codigos de asignatura.")

    match_counts = _value_counts(matching, "TIPO_MATCH")
    code_counts = _value_counts(codes, "ESTADO_CODIGO")
    match_rate = _match_rate(match_counts)
    problematic = _problematic_subjects(matching, codes)
    status = _status_for_summary(match_counts, code_counts, warnings)

    return ValidationSummary(
        status=status,
        total_rows=0 if consolidated is None else int(len(consolidated)),
        total_columns=0 if consolidated is None else int(len(consolidated.columns)),
        main_columns=_main_columns(consolidated),
        match_counts=match_counts,
        code_counts=code_counts,
        match_rate=match_rate,
        problematic_subjects=problematic,
        warnings=warnings,
    )


def _read_optional_csv(path: Path | None) -> pd.DataFrame | None:
    if path is None or not Path(path).exists():
        return None
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except EmptyDataError:
        return pd.DataFrame()


def _read_optional_excel(path: Path | None) -> pd.DataFrame | None:
    if path is None or not Path(path).exists():
        return None
    return pd.read_excel(path)


def _value_counts(df: pd.DataFrame | None, column: str) -> dict[str, int]:
    if df is None or column not in df.columns:
        return {}
    counts = df[column].fillna("").astype(str).str.strip().value_counts()
    return {str(key): int(value) for key, value in counts.items() if str(key)}


def _main_columns(df: pd.DataFrame | None) -> list[str]:
    if df is None:
        return []
    expected = expected_excel_fields()["Campo"].to_list()
    present_expected = [column for column in expected if column in df.columns]
    extra = [column for column in df.columns if column not in present_expected]
    return [*present_expected, *extra][:12]


def _match_rate(match_counts: dict[str, int]) -> float | None:
    total = sum(match_counts.values())
    if total == 0:
        return None
    matched = sum(
        count
        for state, count in match_counts.items()
        if state.upper() != "SIN MATCH"
    )
    return matched / total


def _problematic_subjects(
    matching: pd.DataFrame | None,
    codes: pd.DataFrame | None,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    if matching is not None and {"ASIGNATURA_MATRIZ", "TIPO_MATCH"}.issubset(matching.columns):
        problem_mask = matching["TIPO_MATCH"].astype(str).str.upper().isin(
            {"SIN MATCH", "CROSS_SEMESTRE"}
        )
        for _, row in matching.loc[problem_mask].iterrows():
            rows.append(
                {
                    "Asignatura": str(row.get("ASIGNATURA_MATRIZ", "")),
                    "Problema": str(row.get("TIPO_MATCH", "")),
                    "Detalle": _matching_detail(row),
                }
            )

    if codes is not None and {"ASIGNATURA", "ESTADO_CODIGO"}.issubset(codes.columns):
        problem_mask = codes["ESTADO_CODIGO"].astype(str).str.upper().isin(
            {"SIN_MATCH", "AMBIGUO", "SIN_CATALOGO"}
        )
        for _, row in codes.loc[problem_mask].iterrows():
            rows.append(
                {
                    "Asignatura": str(row.get("ASIGNATURA", "")),
                    "Problema": str(row.get("ESTADO_CODIGO", "")),
                    "Detalle": str(row.get("CODIGO_OFICIAL", "")),
                }
            )

    return pd.DataFrame(rows, columns=["Asignatura", "Problema", "Detalle"])


def _matching_detail(row: pd.Series) -> str:
    pdf_subject = str(row.get("ASIGNATURA_PDF", ""))
    sem_matrix = str(row.get("SEMESTRE", ""))
    sem_pdf = str(row.get("SEMESTRE_PDF", ""))
    score = str(row.get("SCORE", ""))
    parts = []
    if pdf_subject:
        parts.append(f"PDF: {pdf_subject}")
    if sem_matrix or sem_pdf:
        parts.append(f"Semestre matriz/PDF: {sem_matrix}/{sem_pdf}")
    if score:
        parts.append(f"Score: {score}")
    return " | ".join(parts)


def _status_for_summary(
    match_counts: dict[str, int],
    code_counts: dict[str, int],
    warnings: list[str],
) -> str:
    if _has_blocking_match_issue(match_counts):
        return NEEDS_REVIEW
    if _has_warning_match_issue(match_counts) or _has_code_issue(code_counts) or warnings:
        return READY_WITH_WARNINGS
    return READY


def _has_blocking_match_issue(match_counts: dict[str, int]) -> bool:
    return int(match_counts.get("SIN MATCH", 0)) > 0


def _has_warning_match_issue(match_counts: dict[str, int]) -> bool:
    return int(match_counts.get("CROSS_SEMESTRE", 0)) > 0


def _has_code_issue(code_counts: dict[str, int]) -> bool:
    return any(
        int(code_counts.get(state, 0)) > 0
        for state in ["SIN_MATCH", "AMBIGUO", "SIN_CATALOGO"]
    )

