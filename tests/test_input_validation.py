from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.input_validation import validate_excel_input


def test_validate_excel_input_rejects_non_xlsx_extension(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matriz.xls"
    matrix_path.write_bytes(b"test")

    result = validate_excel_input(matrix_path)

    assert not result.is_valid
    assert result.errors[0].title == "Formato de archivo no permitido"
    assert "xlsx" in result.errors[0].detail


def test_validate_excel_input_rejects_missing_file(tmp_path: Path) -> None:
    result = validate_excel_input(tmp_path / "matriz.xlsx")

    assert not result.is_valid
    assert result.errors[0].title == "Archivo Excel no encontrado"


def test_validate_excel_input_delegates_to_etl_validator(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matriz.xlsx"
    matrix_path.write_bytes(b"test")

    with patch(
        "app.services.input_validation.validate_matrix_structure",
        return_value=[],
    ) as mock_validate:
        result = validate_excel_input(matrix_path)

    assert result.is_valid
    mock_validate.assert_called_once_with(matrix_path, sheet_name="Asignaturas - RA")


def test_validate_excel_input_wraps_structural_errors(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matriz.xlsx"
    matrix_path.write_bytes(b"test")

    with patch(
        "app.services.input_validation.validate_matrix_structure",
        return_value=["Hoja 'Asignaturas - RA' no encontrada."],
    ):
        result = validate_excel_input(matrix_path)

    assert not result.is_valid
    assert result.errors[0].title == "La matriz no tiene la estructura esperada"
    assert result.errors[0].detail == "Hoja 'Asignaturas - RA' no encontrada."
    assert "Asignaturas - RA" in result.errors[0].recommendation
