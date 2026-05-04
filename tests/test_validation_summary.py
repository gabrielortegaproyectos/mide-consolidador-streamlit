from app.services.validation_summary import expected_excel_fields


def test_expected_excel_fields_documents_core_fields():
    fields = expected_excel_fields()

    assert {"Campo", "Origen", "Uso"}.issubset(fields.columns)
    assert "Asignatura" in fields["Campo"].to_list()
    assert not fields.empty

