from __future__ import annotations

from app.services.message_catalog import (
    MESSAGE_CATALOG,
    message_for_code,
    message_for_excel_issue,
)


def test_catalog_contains_minimum_issue_7_cases() -> None:
    expected_codes = {
        "excel.sheet_missing",
        "excel.columns_missing",
        "excel.headers_invalid",
        "pdf.unreadable",
        "matching.subjects_missing",
        "codes.no_match",
        "matching.semester_ambiguous",
        "excel.unsupported_format",
    }

    assert expected_codes.issubset(MESSAGE_CATALOG)


def test_messages_have_user_facing_action() -> None:
    for template in MESSAGE_CATALOG.values():
        message = template.render(technical_detail="detalle")
        assert message.code
        assert message.title
        assert message.explanation
        assert message.action
        assert message.technical_detail == "detalle"


def test_message_for_code_falls_back_to_generic_structure_error() -> None:
    message = message_for_code("unknown.code")

    assert message.code == "excel.structure_invalid"


def test_message_for_excel_issue_classifies_sheet_missing() -> None:
    message = message_for_excel_issue("Hoja 'Asignaturas - RA' no encontrada.")

    assert message.code == "excel.sheet_missing"
    assert "Asignaturas - RA" in message.action
    assert message.technical_detail == "Hoja 'Asignaturas - RA' no encontrada."


def test_message_for_excel_issue_classifies_unreadable_file() -> None:
    message = message_for_excel_issue("No se pudo abrir el Excel: File is not a zip file")

    assert message.code == "excel.unreadable"
    assert "Excel" in message.title


def test_message_for_excel_issue_classifies_tributation_missing() -> None:
    message = message_for_excel_issue("No se encontraron valores de tributacion activos.")

    assert message.code == "excel.tributation_missing"
