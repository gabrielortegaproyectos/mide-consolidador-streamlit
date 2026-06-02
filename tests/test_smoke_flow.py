from __future__ import annotations

import importlib
from pathlib import Path
from zipfile import ZipFile

from app.services.delivery_package import UploadedFileTrace, build_delivery_package
from app.services.validation_summary import READY, build_validation_summary
from app.ui.manual import render_manual_content


def test_streamlit_entrypoint_imports_without_running_server() -> None:
    import app.main as streamlit_app
    google_sheets_config = importlib.import_module(
        "app.services.google_sheets_config"
    )
    google_sheets_client = importlib.import_module(
        "app.services.google_sheets_client"
    )

    assert callable(streamlit_app.main)
    assert callable(render_manual_content)
    assert callable(google_sheets_config.get_google_sheets_settings)
    assert callable(google_sheets_client.load_master_sheet)


def test_public_artifact_fixture_builds_downloadable_package(
    tmp_path: Path,
    sample_etl_artifacts: dict[str, Path],
) -> None:
    summary = build_validation_summary(sample_etl_artifacts)
    artifacts = {
        key: {"name": path.name, "bytes": path.read_bytes()}
        for key, path in sample_etl_artifacts.items()
    }

    package = build_delivery_package(
        artifacts=artifacts,
        summary=summary,
        uploaded_files={
            "PDF plan de estudio": UploadedFileTrace(
                name="plan_fixture.pdf",
                sha256="a" * 64,
                size_bytes=1024,
            ),
            "Matriz Excel tributacion": UploadedFileTrace(
                name="matriz_fixture.xlsx",
                sha256="b" * 64,
                size_bytes=2048,
            ),
        },
        metadata={"Fuente de metadatos": "PDF, matriz y catalogos JSON"},
        pipeline_version="test-version",
        warnings=[],
    )
    zip_path = tmp_path / "mide_resultados.zip"
    zip_path.write_bytes(package.zip_bytes)

    assert summary.status == READY
    assert "Version ETL: test-version" in package.validation_summary_md
    assert "plan_fixture.pdf | sha256=" in package.validation_summary_md

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        assert "tributacion_final.xlsx" in names
        assert "tributacion_final_horas_pdf.csv" in names
        assert "tributacion_final_matching.csv" in names
        assert "tributacion_final_subject_codes_matching.csv" in names
        assert "resumen_validacion.md" in names
