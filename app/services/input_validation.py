from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tributacion.config import DEFAULT_SHEET_NAME
from tributacion.matrix_validator import validate_matrix_structure

from app.services.message_catalog import (
    UserMessage,
    message_for_code,
    message_for_excel_issue,
)


ALLOWED_MATRIX_SUFFIXES = {".xlsx"}


@dataclass(frozen=True)
class InputValidationResult:
    is_valid: bool
    errors: list[UserMessage] = field(default_factory=list)
    warnings: list[UserMessage] = field(default_factory=list)


def validate_excel_input(
    matrix_path: Path,
    *,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> InputValidationResult:
    """Valida una matriz Excel antes de ejecutar el pipeline completo."""
    matrix_path = Path(matrix_path)
    errors: list[UserMessage] = []

    if matrix_path.suffix.lower() not in ALLOWED_MATRIX_SUFFIXES:
        errors.append(message_for_code("excel.unsupported_format"))
        return InputValidationResult(is_valid=False, errors=errors)

    if not matrix_path.exists():
        errors.append(
            message_for_code(
                "excel.file_missing",
                technical_detail=f"No se encontro el archivo: {matrix_path}",
            )
        )
        return InputValidationResult(is_valid=False, errors=errors)

    structural_issues = validate_matrix_structure(matrix_path, sheet_name=sheet_name)
    errors.extend(message_for_excel_issue(issue) for issue in structural_issues)

    return InputValidationResult(is_valid=not errors, errors=errors)
