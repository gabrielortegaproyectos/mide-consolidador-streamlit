from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from app.services.delivery_package import UploadedFileTrace, build_delivery_package
from app.services.validation_summary import READY, build_validation_summary


def test_streamlit_entrypoint_imports_without_running_server() -> None:
    import app.main as streamlit_app

    assert callable(streamlit_app.main)
    assert callable(streamlit_app.render_manual)


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
        metadata={"Carrera": "Ingenieria", "Tipo de ciclo": "Semestral"},
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
