from __future__ import annotations

from app.services.privacy import (
    MAX_UPLOAD_BYTES,
    generic_processing_error,
    public_error_message,
    upload_size_error,
)


def test_upload_size_error_blocks_large_files() -> None:
    assert upload_size_error("matriz.xlsx", MAX_UPLOAD_BYTES) is None

    message = upload_size_error("matriz.xlsx", MAX_UPLOAD_BYTES + 1)

    assert message is not None
    assert "matriz.xlsx" in message
    assert "50 MB" in message


def test_public_error_message_hides_local_paths() -> None:
    message = public_error_message(
        "No existe C:\\Users\\lenovo\\Documents\\privado\\plan.pdf"
    )

    assert "C:\\Users" not in message
    assert "privado" not in message
    assert "No fue posible procesar" in message


def test_generic_processing_error_is_actionable_without_technical_details() -> None:
    message = generic_processing_error()

    assert "Traceback" not in message
    assert "Revisa los insumos" in message
