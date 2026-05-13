from __future__ import annotations

import re


MAX_UPLOAD_BYTES = 50 * 1024 * 1024

_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s'\"]+")
_POSIX_PATH_RE = re.compile(r"(?<!\w)/(?:[^\s/'\"]+/)+[^\s'\"]+")


def upload_size_error(filename: str, size_bytes: int) -> str | None:
    if size_bytes <= MAX_UPLOAD_BYTES:
        return None
    return (
        f"`{filename}` supera el limite de {_format_bytes(MAX_UPLOAD_BYTES)}. "
        "Usa un archivo mas liviano o revisa si contiene hojas, imagenes o anexos "
        "que no son necesarios para la corrida."
    )


def public_error_message(message: str) -> str:
    cleaned = _WINDOWS_PATH_RE.sub("[ruta local omitida]", message)
    cleaned = _POSIX_PATH_RE.sub("[ruta local omitida]", cleaned)
    if "[ruta local omitida]" in cleaned:
        return (
            "No fue posible procesar los insumos. Revisa formato, hoja esperada y "
            "contenido de los archivos cargados."
        )
    return cleaned


def generic_processing_error() -> str:
    return (
        "No fue posible completar la corrida. Revisa los insumos y vuelve a intentar. "
        "Si el problema se repite, conserva el resumen de validacion y reporta el caso."
    )


def _format_bytes(size_bytes: int) -> str:
    mib = size_bytes / (1024 * 1024)
    return f"{mib:.0f} MB"
