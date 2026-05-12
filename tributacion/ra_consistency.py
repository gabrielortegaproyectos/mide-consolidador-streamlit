"""ra_consistency.py — Validación de consistencia entre ``N° RA`` y ``NOMBRE RA``.

Este módulo valida que, para filas disciplinares donde ``NOMBRE RA`` tiene
formato ``AR_x - RAy``, el número ``y`` coincida con la columna ``N° RA``.
"""

from __future__ import annotations

import re

import pandas as pd

_DISCIPLINAR_RA_PATTERN = re.compile(
    r"AR\s*_?\s*(\d+)\s*[\-–—]?\s*R\.?\s*A\.?\s*(\d+)",
    flags=re.IGNORECASE,
)


def extract_disciplinar_ra_number(nombre_ra: object) -> int | None:
    """Extrae el número de RA desde ``NOMBRE RA`` disciplinar.

    Acepta variantes comunes como ``AR_1 - RA3``, ``AR_1–RA3``
    o ``AR_4 - R.A.10``.
    """
    text = str(nombre_ra or "").strip()
    if not text:
        return None
    match = _DISCIPLINAR_RA_PATTERN.search(text)
    if match is None:
        return None
    return int(match.group(2))


def _to_int(value: object) -> int | None:
    """Convierte un valor escalar a entero si es posible, si no ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def build_disciplinar_ra_check_frame(
    df: pd.DataFrame,
    nra_column: str = "N° RA",
    nombre_ra_column: str = "NOMBRE RA",
) -> pd.DataFrame:
    """Construye un DataFrame auxiliar con campos de validación RA.

    Retorna una copia con columnas auxiliares:
    - ``_nra_num``: entero parseado desde ``N° RA``
    - ``_nombre_ra_num``: entero parseado desde ``NOMBRE RA`` disciplinar
    - ``_is_comparable_disciplinar``: fila comparable para este chequeo
    """
    if nra_column not in df.columns:
        raise ValueError(f"No existe la columna '{nra_column}' en el DataFrame.")
    if nombre_ra_column not in df.columns:
        raise ValueError(f"No existe la columna '{nombre_ra_column}' en el DataFrame.")

    work_df = df.copy()
    work_df["_nra_num"] = work_df[nra_column].apply(_to_int)
    work_df["_nombre_ra_num"] = work_df[nombre_ra_column].apply(extract_disciplinar_ra_number)
    work_df["_is_comparable_disciplinar"] = (
        work_df["_nra_num"].notna()
        & work_df["_nombre_ra_num"].notna()
        & (work_df["_nra_num"] > 0)
    )
    return work_df


def find_disciplinar_ra_mismatches(
    df: pd.DataFrame,
    nra_column: str = "N° RA",
    nombre_ra_column: str = "NOMBRE RA",
) -> pd.DataFrame:
    """Retorna las filas donde ``N° RA`` difiere del número en ``NOMBRE RA``.

    Solo evalúa filas disciplinares comparables (``AR_x - RAy`` y ``N° RA > 0``).
    """
    work_df = build_disciplinar_ra_check_frame(
        df,
        nra_column=nra_column,
        nombre_ra_column=nombre_ra_column,
    )
    mismatches_mask = (
        work_df["_is_comparable_disciplinar"]
        & (work_df["_nra_num"] != work_df["_nombre_ra_num"])
    )
    return work_df.loc[mismatches_mask].copy()
