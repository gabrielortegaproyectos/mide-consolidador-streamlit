from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from app.services.delivery_package import (
    UploadedFileTrace,
    build_delivery_package,
    trace_file,
)
from app.services.validation_summary import READY_WITH_WARNINGS, ValidationSummary


def test_trace_file_records_name_hash_and_size(tmp_path: Path) -> None:
    upload = tmp_path / "matriz.xlsx"
    upload.write_bytes(b"excel")

    trace = trace_file(upload)

    assert trace.name == "matriz.xlsx"
    assert trace.size_bytes == 5
    assert len(trace.sha256) == 64


def test_build_delivery_package_includes_artifacts_and_markdown(tmp_path: Path) -> None:
    summary = ValidationSummary(
        status=READY_WITH_WARNINGS,
        total_rows=10,
        total_columns=36,
        match_counts={"EXACTO": 8, "SIN MATCH": 2},
        code_counts={"MATCH_OK": 9, "SIN_MATCH": 1},
        match_rate=0.8,
        warnings=["No se encontro diagnostico complementario."],
    )

    package = build_delivery_package(
        artifacts={
            "consolidated_excel": {
                "name": "tributacion_final.xlsx",
                "bytes": b"xlsx",
            },
            "matching_matriz_pdf_csv": {
                "name": "tributacion_final_matching.csv",
                "bytes": b"TIPO_MATCH\nEXACTO\n",
            },
            "existing_summary": {
                "name": "resumen_validacion.md",
                "bytes": b"old summary",
            },
        },
        summary=summary,
        uploaded_files={
            "PDF plan de estudio": UploadedFileTrace(
                name="plan.pdf",
                sha256="a" * 64,
                size_bytes=123,
            )
        },
        metadata={"Fuente de metadatos": "PDF, matriz y catalogos JSON"},
        pipeline_version="abc123",
        warnings=["Advertencia del ETL."],
        generated_at=datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc),
    )
    zip_path = tmp_path / "mide_resultados.zip"
    zip_path.write_bytes(package.zip_bytes)

    assert "Version ETL: abc123" in package.validation_summary_md
    assert "Fecha/hora de corrida: 2026-05-13T12:00:00+00:00" in package.validation_summary_md
    assert "Metadatos de ejecucion" in package.validation_summary_md
    assert "Fuente de metadatos: PDF, matriz y catalogos JSON" in package.validation_summary_md
    assert "plan.pdf | sha256=" in package.validation_summary_md
    assert "Advertencia del ETL." in package.validation_summary_md

    with ZipFile(zip_path) as archive:
        assert sorted(archive.namelist()) == [
            "resumen_validacion.md",
            "tributacion_final.xlsx",
            "tributacion_final_matching.csv",
        ]
        assert archive.read("resumen_validacion.md").decode("utf-8") == (
            package.validation_summary_md
        )
