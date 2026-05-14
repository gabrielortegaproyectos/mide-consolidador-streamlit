from __future__ import annotations

from app.services.manual import (
    diagnostic_outputs,
    expected_excel_fields,
    file_policy_notes,
    input_requirements,
    operational_steps,
    warning_guide,
)
from tributacion.config import OUTPUT_COLUMNS


def test_expected_excel_fields_follow_etl_output_contract() -> None:
    fields = expected_excel_fields()

    assert fields["Campo"].to_list() == OUTPUT_COLUMNS
    assert set(fields["Grupo"]) >= {
        "Identificacion",
        "Tributacion",
        "Asignatura",
        "Creditos y horas",
    }
    assert fields.loc[fields["Campo"] == "ASIGNATURA", "Uso"].item().startswith(
        "Nombre usado"
    )


def test_manual_tables_cover_issue_topics() -> None:
    inputs = input_requirements()
    diagnostics = diagnostic_outputs()
    steps = operational_steps()
    warnings = warning_guide()
    policy = file_policy_notes()

    assert "PDF de plan de estudio" in inputs["Insumo"].to_list()
    assert inputs["Que revisar"].str.contains("Asignaturas - RA", regex=False).any()
    assert diagnostics["Archivo"].to_list() == ["tributacion_final.xlsx"]
    assert steps["Que hacer"].str.contains("Excel online maestro", regex=False).any()
    assert warnings["Advertencia"].str.contains("SIN MATCH", regex=False).any()
    assert any("temporales" in note for note in policy)
