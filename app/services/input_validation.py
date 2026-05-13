from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tributacion.config import DEFAULT_SHEET_NAME
from tributacion.matrix_validator import validate_matrix_structure


ALLOWED_MATRIX_SUFFIXES = {".xlsx"}


@dataclass(frozen=True)
class ValidationMessage:
    title: str
    detail: str
    recommendation: str | None = None


@dataclass(frozen=True)
class InputValidationResult:
    is_valid: bool
    errors: list[ValidationMessage] = field(default_factory=list)
    warnings: list[ValidationMessage] = field(default_factory=list)


def validate_excel_input(
    matrix_path: Path,
    *,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> InputValidationResult:
    """Valida una matriz Excel antes de ejecutar el pipeline completo."""
    matrix_path = Path(matrix_path)
    errors: list[ValidationMessage] = []

    if matrix_path.suffix.lower() not in ALLOWED_MATRIX_SUFFIXES:
        errors.append(
            ValidationMessage(
                title="Formato de archivo no permitido",
                detail=(
                    "La matriz debe estar en formato .xlsx para poder leer sus "
                    "hojas y cabeceras."
                ),
                recommendation="Exporta o guarda la matriz como archivo .xlsx.",
            )
        )
        return InputValidationResult(is_valid=False, errors=errors)

    if not matrix_path.exists():
        errors.append(
            ValidationMessage(
                title="Archivo Excel no encontrado",
                detail=f"No se encontro el archivo: {matrix_path}",
                recommendation="Vuelve a cargar la matriz Excel antes de validar.",
            )
        )
        return InputValidationResult(is_valid=False, errors=errors)

    structural_issues = validate_matrix_structure(matrix_path, sheet_name=sheet_name)
    errors.extend(_structural_issue_to_message(issue) for issue in structural_issues)

    return InputValidationResult(is_valid=not errors, errors=errors)


def _structural_issue_to_message(issue: str) -> ValidationMessage:
    recommendation = _recommendation_for_issue(issue)
    return ValidationMessage(
        title="La matriz no tiene la estructura esperada",
        detail=issue,
        recommendation=recommendation,
    )


def _recommendation_for_issue(issue: str) -> str:
    lowered = issue.lower()
    if "hoja" in lowered and "no encontrada" in lowered:
        return f"Revisa que exista una hoja llamada exactamente '{DEFAULT_SHEET_NAME}'."
    if "no se pudo abrir" in lowered:
        return "Verifica que el archivo no este corrupto, protegido o abierto de forma incompatible."
    if "fila" in lowered or "columna" in lowered or "cabecera" in lowered:
        return "Revisa que la matriz mantenga las cabeceras originales de areas, AR, RA y niveles."
    if "tributacion" in lowered or "tributacion" in _strip_accents(lowered):
        return "Confirma que las celdas de tributacion usen el valor esperado por el ETL."
    return "Corrige la matriz y vuelve a validar antes de ejecutar el pipeline."


def _strip_accents(value: str) -> str:
    return (
        value.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
