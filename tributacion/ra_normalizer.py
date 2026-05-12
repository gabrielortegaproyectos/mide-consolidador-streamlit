"""ra_normalizer.py — Normalización de NOMBRE RA contra catálogo local.

Usa un catálogo local persistente de Resultados de Aprendizaje y, mediante
fuzzy matching, reemplaza variantes tipográficas por su forma canónica. El
catálogo se actualiza con nuevos RA a medida que se procesan carreras, por lo
que el pipeline no depende de conectividad externa.

Funciones públicas
------------------
:func:`load_canonical_nombres`
    Carga y devuelve la lista canónica de NOMBRE RA desde un CSV local.
:func:`save_canonical_nombres`
    Persiste la lista canónica local de NOMBRE RA.
:func:`normalize_nombre_ra`
    Normaliza un NOMBRE RA individual contra la lista canónica.
:func:`normalize_df_nombre_ra`
    Aplica la normalización a la columna entera de un DataFrame.
:func:`normalize_df_nombre_ra_with_local_catalog`
    Normaliza el DataFrame usando el catálogo local y agrega nuevos RA.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from tributacion.config import CANONICAL_RA_LOCAL_PATH, CANONICAL_RA_THRESHOLD
from tributacion.text_utils import best_fuzzy_match

logger = logging.getLogger(__name__)

_COLUMN = "NOMBRE RA"
_DISCIPLINAR_RA_PATTERN = re.compile(
    r"AR\s*_?\s*(\d+)\s*[\-–—]?\s*R\.?\s*A\.?\s*(\d+)",
    re.IGNORECASE,
)


def _pre_norm_ra(text: str) -> str:
    """Normalización leve de puntuación específica para nombres de RA.

    Añade un espacio después de ``.`` o ``-`` cuando van pegados a una letra,
    y colapsa espacios múltiples. Esto permite que variantes como
    ``E.Compromiso`` y ``E. Compromiso`` tengan el mismo score fuzzy.
    """
    # Prefijo típico de RA: "E - Compromiso" / "E-Compromiso" -> "E. Compromiso"
    text = re.sub(r"^([A-Za-záéíóúÁÉÍÓÚüÜñÑ])\s*-\s*", r"\1. ", text)
    # Espacio tras punto pegado a letra: "E.Compromiso" → "E. Compromiso"
    text = re.sub(r"\.(?=[A-Za-záéíóúÁÉÍÓÚüÜñÑ])", ". ", text)
    # Espacio tras guión pegado a letra: "E-Compromiso" → "E- Compromiso"
    text = re.sub(r"-(?=[A-Za-záéíóúÁÉÍÓÚüÜñÑ])", "- ", text)
    # Colapsa espacios múltiples
    return re.sub(r"\s+", " ", text).strip()


def _normalize_disciplinar_ra_name(name: str) -> str | None:
    """Canoniza nombres disciplinares tipo ``AR_x - RAy`` si aplican.

    Acepta variantes comunes de puntuación y separación como
    ``AR_4 - R.A.10`` o ``AR4–RA10`` y devuelve siempre ``AR_4 - RA10``.
    Si el texto no representa un RA disciplinar, devuelve ``None``.
    """
    match = _DISCIPLINAR_RA_PATTERN.search(name)
    if match is None:
        return None
    ar_num = int(match.group(1))
    ra_num = int(match.group(2))
    return f"AR_{ar_num} - RA{ra_num}"


def _clean_nombres(values: Iterable[object]) -> list[str]:
    """Normaliza una secuencia de nombres preservando orden y removiendo vacíos."""
    nombres: list[str] = []
    seen: set[str] = set()
    for value in values:
        if pd.isna(value):
            continue
        nombre = str(value).strip()
        if not nombre or nombre in seen:
            continue
        seen.add(nombre)
        nombres.append(nombre)
    return nombres


def load_canonical_nombres(path: str | Path = CANONICAL_RA_LOCAL_PATH) -> list[str]:
    """Carga la lista canónica de NOMBRE RA desde un CSV local.

    Parameters
    ----------
    path:
        Ruta local del catálogo CSV. Por defecto usa
        :data:`tributacion.config.CANONICAL_RA_LOCAL_PATH`.

    Returns
    -------
    list[str]
        Lista de nombres canónicos deduplicados y sin vacíos.
        Devuelve ``[]`` si el archivo no existe o no puede leerse. En ese caso
        el pipeline continuará y podrá inicializar el catálogo al procesar la
        carrera actual.
    """
    path = Path(path)
    if not path.exists():
        logger.info(
            "ra_normalizer: el catálogo local %s aún no existe; "
            "se inicializará con la corrida actual si aparecen RA nuevos.",
            path,
        )
        return []

    try:
        df = pd.read_csv(path, dtype=str)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ra_normalizer: no se pudo cargar la lista canónica desde %s (%s).",
            path,
            exc,
        )
        return []

    if _COLUMN not in df.columns:
        logger.warning(
            "ra_normalizer: la columna '%s' no se encontró en %s. "
            "Columnas disponibles: %s. Se omite normalización.",
            _COLUMN,
            path,
            list(df.columns),
        )
        return []

    nombres = _clean_nombres(df[_COLUMN].tolist())
    logger.info(
        "ra_normalizer: %d nombres canónicos cargados desde %s.",
        len(nombres),
        path,
    )
    return nombres


def save_canonical_nombres(
    nombres: Iterable[object],
    path: str | Path = CANONICAL_RA_LOCAL_PATH,
) -> list[str]:
    """Guarda la lista canónica de NOMBRE RA en el catálogo local."""
    path = Path(path)
    canonical = _clean_nombres(nombres)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({_COLUMN: canonical}).to_csv(path, index=False, encoding="utf-8-sig")
    logger.info(
        "ra_normalizer: catálogo local actualizado en %s con %d nombre(s).",
        path,
        len(canonical),
    )
    return canonical


def normalize_nombre_ra(
    name: str,
    canonical: list[str],
    threshold: float = CANONICAL_RA_THRESHOLD,
) -> str:
    """Normaliza un NOMBRE RA individual contra la lista canónica.

    Compara *name* con cada entrada de *canonical* usando
    :func:`tributacion.text_utils.best_fuzzy_match` (token_sort_ratio sobre
    cadenas sin tildes). Si el score supera *threshold* devuelve el nombre
    canónico; de lo contrario devuelve *name* intacto y emite una advertencia.

    Parameters
    ----------
    name:
        Nombre tal como aparece en el Excel de la carrera.
    canonical:
        Lista devuelta por :func:`load_canonical_nombres`.
    threshold:
        Umbral de similitud (0–1). Por defecto
        :data:`tributacion.config.CANONICAL_RA_THRESHOLD`.

    Returns
    -------
    str
        Nombre canónico si el match supera el umbral, *name* en caso contrario.
    """
    disciplinar_name = _normalize_disciplinar_ra_name(name)
    if disciplinar_name is not None:
        return disciplinar_name

    if not canonical:
        return name

    name_pre = _pre_norm_ra(name)
    best, score = best_fuzzy_match(name_pre, canonical, threshold=threshold)
    if best is not None:
        if best != name:
            logger.debug(
                "ra_normalizer: '%s' → '%s' (score=%.2f)",
                name,
                best,
                score,
            )
        return best

    logger.warning(
        "ra_normalizer: NOMBRE RA sin match canónico (score máx < %.2f): '%s'. "
        "Se conserva el valor original.",
        threshold,
        name,
    )
    return name


def normalize_df_nombre_ra(
    df: pd.DataFrame,
    canonical: list[str],
    threshold: float = CANONICAL_RA_THRESHOLD,
) -> pd.DataFrame:
    """Aplica :func:`normalize_nombre_ra` a la columna NOMBRE RA de un DataFrame.

    Modifica una *copia* del DataFrame; el original no se altera.

    Parameters
    ----------
    df:
        DataFrame con columna ``"NOMBRE RA"``.
    canonical:
        Lista devuelta por :func:`load_canonical_nombres`.
    threshold:
        Umbral de similitud. Por defecto
        :data:`tributacion.config.CANONICAL_RA_THRESHOLD`.

    Returns
    -------
    pd.DataFrame
        DataFrame con la columna ``"NOMBRE RA"`` normalizada.
    """
    if not canonical or _COLUMN not in df.columns:
        return df

    df = df.copy()
    df[_COLUMN] = df[_COLUMN].apply(
        lambda x: normalize_nombre_ra(str(x), canonical, threshold=threshold)
    )
    return df


def _normalize_df_ra_value(value: object, mapping: dict[str, str]) -> object:
    """Aplica un mapping de RA preservando vacíos y nulos."""
    if pd.isna(value):
        return value
    nombre = str(value).strip()
    if not nombre:
        return nombre
    return mapping.get(nombre, nombre)


def normalize_df_nombre_ra_with_local_catalog(
    df: pd.DataFrame,
    catalog_path: str | Path = CANONICAL_RA_LOCAL_PATH,
    threshold: float = CANONICAL_RA_THRESHOLD,
) -> pd.DataFrame:
    """Normaliza NOMBRE RA usando el catálogo local y lo enriquece si hace falta.

    El flujo es:

    1. Cargar el catálogo local actual.
    2. Intentar normalizar los RA del DataFrame contra ese catálogo.
    3. Si aparece un RA sin match, agregarlo al catálogo local para futuras
       corridas.

    Esto permite que el catálogo crezca de manera incremental sin depender de
    una hoja remota.
    """
    if _COLUMN not in df.columns:
        return df

    df = df.copy()
    canonical = load_canonical_nombres(catalog_path)
    known = list(canonical)
    known_set = set(known)
    mapping: dict[str, str] = {}
    nuevos = 0

    for nombre in _clean_nombres(df[_COLUMN].tolist()):
        normalized = normalize_nombre_ra(nombre, known, threshold=threshold)
        mapping[nombre] = normalized
        if normalized == nombre and nombre not in known_set:
            known.append(nombre)
            known_set.add(nombre)
            nuevos += 1

    df[_COLUMN] = df[_COLUMN].apply(lambda value: _normalize_df_ra_value(value, mapping))

    path = Path(catalog_path)
    if nuevos:
        logger.info(
            "ra_normalizer: %d nombre(s) RA nuevos agregados al catálogo local %s.",
            nuevos,
            path,
        )
    if nuevos or (mapping and not path.exists()):
        save_canonical_nombres(known, path)

    return df
