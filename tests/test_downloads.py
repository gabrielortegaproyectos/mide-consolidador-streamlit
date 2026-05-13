from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from app.services.downloads import build_artifacts_zip, collect_artifacts


def test_collect_artifacts_returns_known_generated_files(tmp_path: Path) -> None:
    (tmp_path / "tributacion_final.xlsx").write_bytes(b"xlsx")
    (tmp_path / "diagnostico.csv").write_text("a,b\n1,2\n")
    (tmp_path / "resumen_validacion.md").write_text("# Resumen\n")
    (tmp_path / "debug.log").write_text("ignore")

    artifacts = collect_artifacts(tmp_path)

    assert set(artifacts) == {
        "tributacion_final.xlsx",
        "diagnostico.csv",
        "resumen_validacion.md",
    }


def test_build_artifacts_zip_includes_existing_artifacts(tmp_path: Path) -> None:
    consolidated = tmp_path / "tributacion_final.xlsx"
    matching = tmp_path / "tributacion_final_matching.csv"
    missing = tmp_path / "missing.csv"
    consolidated.write_bytes(b"xlsx")
    matching.write_text("estado,cantidad\nEXACTO,1\n")

    zip_bytes = build_artifacts_zip(
        {
            "consolidated_excel": consolidated,
            "matching_matriz_pdf_csv": matching,
            "missing": missing,
        }
    )
    zip_path = tmp_path / "resultados.zip"
    zip_path.write_bytes(zip_bytes)

    with ZipFile(zip_path) as archive:
        assert sorted(archive.namelist()) == [
            "tributacion_final.xlsx",
            "tributacion_final_matching.csv",
        ]
