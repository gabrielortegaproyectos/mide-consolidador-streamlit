"""subject_code_enricher.py — Enriquecimiento final con códigos oficiales.

Descarga el catálogo oficial publicado en Google Sheets y usa la combinación
``(carrera_base, asignatura)`` para poblar la columna ``"CÓDIGO DEL CURSO"``
del DataFrame final del pipeline.

Reglas:
- El código oficial sobrescribe cualquier valor previo.
- Si no hay match único, ``"CÓDIGO DEL CURSO"`` queda vacío.
- Si el catálogo remoto no está disponible, se intenta reutilizar un catálogo
  local construido desde corridas anteriores.
- Si no existe ni catálogo remoto ni local, el pipeline preserva cualquier
  código que ya venga desde el PDF en vez de borrarlo.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from tributacion.config import (
    SUBJECT_CODES_ALIASES_PATH,
    SUBJECT_CODES_CAREER_COLUMN,
    SUBJECT_CODES_CODE_COLUMN,
    SUBJECT_CODES_LOCAL_PATH,
    SUBJECT_CODES_SUBJECT_COLUMN,
    SUBJECT_CODES_URL,
)
from tributacion.text_utils import norm_text

logger = logging.getLogger(__name__)

MISSING_CODE_PLACEHOLDER = "sin código"


_CAREER_EQUIVALENCES: dict[str, str] = {
    "ingenieria mecatronica": "ingenieria en mecatronica",
    "ingenieria civil en medio ambiente": "ingenieria civil en medio ambiente y sustentabilidad",
}


_INVALID_COURSE_CODES: set[str] = {
    "",
    "SIN CÓDIGO",
    "SIN CODIGO",
    "N/A",
    "NA",
    "NONE",
    "NULL",
    MISSING_CODE_PLACEHOLDER.upper(),
}


_MANUAL_CANONICAL_BY_CODE: dict[str, str] = {
    "O1EA35409": "Optativo de Especialización I",
    "O1EB35409": "Optativo de Especialización I",
    "O2EA35409": "Optativo de Especialización II",
    "O2EB35409": "Optativo de Especialización II",
    "O3EA35409": "Optativo de Especialización III",
    "O3EB35409": "Optativo de Especialización III",
}


_ENFERMERIA_OPTION_CANONICAL_BY_CODE: dict[str, dict[str, str]] = {
    "CERTIFICACIÓN_ACADÉMICA_EN_ENFERMERÍA_ADULTO": {},
    "CERTIFICACIÓN_ACADÉMICA_EN_ENFERMERÍA_COMUNITARIA": {},
}


_ENFERMERIA_OPTION_EXCLUDE_CODES: dict[str, set[str]] = {
    "CERTIFICACIÓN_ACADÉMICA_EN_ENFERMERÍA_ADULTO": {"IEC21409"},
    "CERTIFICACIÓN_ACADÉMICA_EN_ENFERMERÍA_COMUNITARIA": {"CEA21409", "EUQ21409"},
}


def _select_canonical_subject_name(names: pd.Series) -> str:
    """Selecciona un nombre canónico entre variantes para el mismo código."""
    cleaned = names.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    if cleaned.empty:
        return ""

    counts = cleaned.value_counts()

    def _camel_glue_count(value: str) -> int:
        return len(re.findall(r"[a-záéíóúñ][A-ZÁÉÍÓÚÑ]", value))

    ranked = sorted(
        counts.index.tolist(),
        key=lambda value: (
            -int(counts[value]),
            -len(value.split()),
            _camel_glue_count(value),
            -len(value),
            value,
        ),
    )
    return ranked[0]


def _harmonize_subject_names_by_course_code(df: pd.DataFrame) -> pd.DataFrame:
    """Unifica ``ASIGNATURA`` cuando un mismo código aparece con variantes."""
    if "CÓDIGO DEL CURSO" not in df.columns or "ASIGNATURA" not in df.columns:
        return df

    out = df.copy()
    codes = out["CÓDIGO DEL CURSO"].fillna("").astype(str).str.strip().str.upper()
    names = out["ASIGNATURA"].fillna("").astype(str).str.strip()

    code_df = pd.DataFrame({"code": codes, "name": names})
    code_df = code_df[
        (code_df["code"] != "")
        & (~code_df["code"].isin(_INVALID_COURSE_CODES))
        & (code_df["name"] != "")
    ]
    if code_df.empty:
        return out

    canonical_by_code: dict[str, str] = {}
    for code, group in code_df.groupby("code"):
        if group["name"].nunique() <= 1:
            continue
        canonical = _select_canonical_subject_name(group["name"])
        if canonical:
            canonical_by_code[code] = canonical

    if not canonical_by_code:
        canonical_by_code = {}

    canonical_by_code.update(_MANUAL_CANONICAL_BY_CODE)

    if not canonical_by_code:
        return out

    mask = codes.isin(canonical_by_code.keys())
    out.loc[mask, "ASIGNATURA"] = codes[mask].map(canonical_by_code)

    if "CARRERA" in out.columns:
        carreras = out["CARRERA"].fillna("").astype(str).str.upper()
        for option_name, code_map in _ENFERMERIA_OPTION_CANONICAL_BY_CODE.items():
            option_mask = carreras.str.contains(option_name, regex=False, na=False)
            if not option_mask.any():
                continue
            for code, canonical_name in code_map.items():
                code_mask = option_mask & codes.eq(code)
                if code_mask.any():
                    out.loc[code_mask, "ASIGNATURA"] = canonical_name

        if "N° DE CRÉDITOS" in out.columns:
            for option_name, excluded_codes in _ENFERMERIA_OPTION_EXCLUDE_CODES.items():
                option_mask = carreras.str.contains(option_name, regex=False, na=False)
                if not option_mask.any() or not excluded_codes:
                    continue
                exclude_mask = option_mask & codes.isin(excluded_codes)
                if exclude_mask.any():
                    out.loc[exclude_mask, "N° DE CRÉDITOS"] = pd.NA

    return out


def _base_carrera(carrera: object) -> str:
    """Obtiene la carrera base antes de cualquier sufijo de variante."""
    value = str(carrera or "").replace("_", " ").strip()
    return value.split("-", 1)[0].strip()


def _career_norm_for_codes(carrera: object) -> str:
    """Normaliza la carrera para lookup en el catálogo de códigos."""
    base = _base_carrera(carrera)
    norm = norm_text(base)
    if norm.startswith("tecnologia medica mencion "):
        return "tecnologia medica"
    return _CAREER_EQUIVALENCES.get(norm, norm)


def _empty_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una copia con la columna oficial vacía."""
    df = df.copy()
    if "CÓDIGO DEL CURSO" in df.columns:
        df["CÓDIGO DEL CURSO"] = ""
    return df


def _normalize_semestre_key(value: object) -> str:
    """Normaliza el semestre a una clave estable para lookups manuales."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def _normalize_catalog(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza un catálogo al esquema interno estándar."""
    catalog = df[
        [
            "nombre_carrera",
            "Asignatura",
            "cod_ramo",
        ]
    ].copy()
    catalog = catalog.fillna("")
    for col in ["nombre_carrera", "Asignatura", "cod_ramo"]:
        catalog[col] = catalog[col].astype(str).str.strip()
    catalog = catalog.loc[
        (catalog["nombre_carrera"] != "")
        & (catalog["Asignatura"] != "")
        & (catalog["cod_ramo"] != "")
    ].copy()
    if catalog.empty:
        return pd.DataFrame()

    catalog["_carrera_base_norm"] = catalog["nombre_carrera"].apply(norm_text)
    catalog["_asignatura_norm"] = catalog["Asignatura"].apply(norm_text)
    return catalog


def _normalize_alias_catalog(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el catálogo manual de alias de asignaturas."""
    required = {
        SUBJECT_CODES_CAREER_COLUMN,
        SUBJECT_CODES_SUBJECT_COLUMN,
        SUBJECT_CODES_CODE_COLUMN,
    }
    missing = required.difference(df.columns)
    if missing:
        logger.warning(
            "subject_code_enricher: el catálogo manual de alias no tiene las columnas requeridas: %s.",
            sorted(missing),
        )
        return pd.DataFrame()

    alias = df.copy().fillna("")
    for col in list(required) + ["semestre"]:
        if col not in alias.columns:
            alias[col] = ""
        alias[col] = alias[col].astype(str).str.strip()

    alias = alias.loc[
        (alias[SUBJECT_CODES_CAREER_COLUMN] != "")
        & (alias[SUBJECT_CODES_SUBJECT_COLUMN] != "")
        & (alias[SUBJECT_CODES_CODE_COLUMN] != "")
    ].copy()
    if alias.empty:
        return pd.DataFrame()

    alias["_carrera_base_norm"] = alias[SUBJECT_CODES_CAREER_COLUMN].apply(_career_norm_for_codes)
    alias["_asignatura_norm"] = alias[SUBJECT_CODES_SUBJECT_COLUMN].apply(norm_text)
    alias["_semestre_norm"] = alias["semestre"].apply(_normalize_semestre_key)
    return alias


def _group_code_candidates(df: pd.DataFrame, keys: list[str], match_state: str) -> pd.DataFrame:
    """Agrupa candidatos de código y detecta ambigüedad."""
    if df.empty:
        return pd.DataFrame(columns=[*keys, "_cod_ramo_lookup", "_codigo_estado_lookup"])

    grouped = (
        df.groupby(keys, dropna=False)
        .agg(
            codigos=("cod_ramo", lambda s: sorted({str(v).strip() for v in s if str(v).strip()})),
        )
        .reset_index()
    )
    grouped["_cod_ramo_lookup"] = grouped["codigos"].apply(
        lambda codes: codes[0] if len(codes) == 1 else ""
    )
    grouped["_codigo_estado_lookup"] = grouped["codigos"].apply(
        lambda codes: match_state if len(codes) == 1 else "AMBIGUO"
    )
    return grouped.drop(columns=["codigos"])


def _load_local_subject_codes_cache(root: Path = Path("data/output")) -> pd.DataFrame:
    """Construye un catálogo local desde diagnósticos previos con MATCH_OK."""
    files = sorted(root.rglob("*subject_codes_matching.csv"))
    rows: list[pd.DataFrame] = []
    for path in files:
        try:
            df = pd.read_csv(path, dtype=str)
        except Exception:  # noqa: BLE001
            continue
        required = {"CARRERA_BASE", "ASIGNATURA", "CODIGO_OFICIAL", "ESTADO_CODIGO"}
        if not required.issubset(df.columns):
            continue
        sub = df.loc[df["ESTADO_CODIGO"].astype(str).str.strip().isin({"MATCH_OK", "MATCH_ALIAS"}), [
            "CARRERA_BASE",
            "ASIGNATURA",
            "CODIGO_OFICIAL",
        ]].copy()
        if sub.empty:
            continue
        sub = sub.rename(
            columns={
                "CARRERA_BASE": "nombre_carrera",
                "ASIGNATURA": "Asignatura",
                "CODIGO_OFICIAL": "cod_ramo",
            }
        )
        rows.append(sub)

    if not rows:
        return pd.DataFrame()

    catalog = pd.concat(rows, ignore_index=True).drop_duplicates()
    catalog = _normalize_catalog(catalog)
    if catalog.empty:
        return pd.DataFrame()

    logger.info(
        "subject_code_enricher: catálogo local cargado desde %d archivo(s) de data/output/.",
        len(files),
    )
    return catalog


def _load_subject_code_aliases(path: Path = SUBJECT_CODES_ALIASES_PATH) -> pd.DataFrame:
    """Carga alias manuales de asignaturas para lookup de códigos."""
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "subject_code_enricher: no se pudo leer el catálogo manual de alias %s (%s).",
            path,
            exc,
        )
        return pd.DataFrame()

    alias = _normalize_alias_catalog(df)
    if not alias.empty:
        logger.info("subject_code_enricher: alias manuales cargados desde %s.", path)
    return alias


def _load_subject_codes_local_file(path: Path = SUBJECT_CODES_LOCAL_PATH) -> pd.DataFrame:
    """Carga el catálogo local de códigos versionado en el repositorio."""
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "subject_code_enricher: no se pudo leer el catálogo local %s (%s).",
            path,
            exc,
        )
        return pd.DataFrame()

    required = {
        SUBJECT_CODES_CAREER_COLUMN,
        SUBJECT_CODES_SUBJECT_COLUMN,
        SUBJECT_CODES_CODE_COLUMN,
    }
    missing = required.difference(df.columns)
    if missing:
        logger.warning(
            "subject_code_enricher: el catálogo local %s no tiene las columnas requeridas: %s.",
            path,
            sorted(missing),
        )
        return pd.DataFrame()

    catalog = df.rename(
        columns={
            SUBJECT_CODES_CAREER_COLUMN: "nombre_carrera",
            SUBJECT_CODES_SUBJECT_COLUMN: "Asignatura",
            SUBJECT_CODES_CODE_COLUMN: "cod_ramo",
        }
    )
    catalog = _normalize_catalog(catalog)
    if not catalog.empty:
        logger.info("subject_code_enricher: catálogo local cargado desde %s.", path)
    return catalog


def load_subject_codes_catalog(url: str = SUBJECT_CODES_URL) -> pd.DataFrame:
    """Descarga el catálogo oficial de códigos de asignatura.

    Returns un DataFrame normalizado con las columnas:
    ``_carrera_base_norm``, ``_asignatura_norm``, ``cod_ramo``.
    Si la descarga falla o faltan columnas requeridas, devuelve un DataFrame vacío.
    """
    required = {
        SUBJECT_CODES_CAREER_COLUMN,
        SUBJECT_CODES_SUBJECT_COLUMN,
        SUBJECT_CODES_CODE_COLUMN,
    }
    local_catalog = _load_subject_codes_local_file()
    if not local_catalog.empty:
        return local_catalog

    try:
        df = pd.read_csv(url, dtype=str)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "subject_code_enricher: no se pudo cargar el catálogo desde %s (%s). "
            "Se intentará usar caché local.",
            url,
            exc,
        )
        return _load_local_subject_codes_cache()

    missing = required.difference(df.columns)
    if missing:
        logger.warning(
            "subject_code_enricher: faltan columnas requeridas en el catálogo %s. "
            "Faltantes: %s. Se intentará usar caché local.",
            url,
            sorted(missing),
        )
        return _load_local_subject_codes_cache()

    catalog = df.rename(
        columns={
            SUBJECT_CODES_CAREER_COLUMN: "nombre_carrera",
            SUBJECT_CODES_SUBJECT_COLUMN: "Asignatura",
            SUBJECT_CODES_CODE_COLUMN: "cod_ramo",
        }
    )
    catalog = _normalize_catalog(catalog)
    if catalog.empty:
        logger.warning(
            "subject_code_enricher: el catálogo descargado no contiene filas válidas. "
            "Se intentará usar caché local."
        )
        return _load_local_subject_codes_cache()

    return catalog


def apply_subject_codes(
    df_final: pd.DataFrame,
    catalog: pd.DataFrame | None = None,
    matching_path: Path | None = None,
) -> pd.DataFrame:
    """Sobrescribe ``CÓDIGO DEL CURSO`` con el código oficial por carrera+asignatura."""
    df_out = df_final.copy()
    if "CÓDIGO DEL CURSO" not in df_out.columns:
        df_out["CÓDIGO DEL CURSO"] = ""
    existing_codes = df_out["CÓDIGO DEL CURSO"].fillna("").astype(str)
    if df_out.empty:
        return df_out

    carrera_series = (
        df_out["CARRERA"]
        if "CARRERA" in df_out.columns
        else pd.Series([""] * len(df_out), index=df_out.index)
    )
    asignatura_series = (
        df_out["ASIGNATURA"]
        if "ASIGNATURA" in df_out.columns
        else pd.Series([""] * len(df_out), index=df_out.index)
    )
    semestre_series = (
        df_out["NIVEL O SEMESTRE"]
        if "NIVEL O SEMESTRE" in df_out.columns
        else pd.Series([""] * len(df_out), index=df_out.index)
    )

    df_out["_carrera_base"] = carrera_series.apply(_base_carrera)
    df_out["_carrera_base_norm"] = carrera_series.apply(_career_norm_for_codes)
    df_out["_asignatura_norm"] = asignatura_series.apply(norm_text)
    df_out["_semestre_norm"] = semestre_series.apply(_normalize_semestre_key)

    if catalog is None:
        catalog = load_subject_codes_catalog()

    if catalog.empty:
        mask_existing = existing_codes.str.strip() != ""
        df_out.loc[mask_existing, "CÓDIGO DEL CURSO"] = existing_codes.loc[mask_existing]
        df_out["_codigo_estado"] = "SIN_CATALOGO"
        df_out.loc[mask_existing, "_codigo_estado"] = "PRESERVADO_EXISTENTE"
        df_out["_cod_ramo_oficial"] = ""
    else:
        df_out["CÓDIGO DEL CURSO"] = ""
        grouped = _group_code_candidates(
            catalog,
            ["_carrera_base_norm", "_asignatura_norm"],
            "MATCH_OK",
        )

        df_out = df_out.merge(
            grouped,
            how="left",
            on=["_carrera_base_norm", "_asignatura_norm"],
        )
        df_out = df_out.rename(
            columns={
                "_cod_ramo_lookup": "_cod_ramo_oficial",
                "_codigo_estado_lookup": "_codigo_estado",
            }
        )
        df_out["_codigo_estado"] = df_out["_codigo_estado"].fillna("SIN_MATCH")
        df_out["_cod_ramo_oficial"] = df_out["_cod_ramo_oficial"].fillna("")

    alias_catalog = _load_subject_code_aliases()
    if not alias_catalog.empty:
        specific_aliases = _group_code_candidates(
            alias_catalog.loc[alias_catalog["_semestre_norm"] != ""].copy(),
            ["_carrera_base_norm", "_asignatura_norm", "_semestre_norm"],
            "MATCH_ALIAS",
        ).rename(
            columns={
                "_cod_ramo_lookup": "_cod_ramo_alias_specific",
                "_codigo_estado_lookup": "_codigo_estado_alias_specific",
            }
        )
        generic_aliases = _group_code_candidates(
            alias_catalog.loc[alias_catalog["_semestre_norm"] == ""].copy(),
            ["_carrera_base_norm", "_asignatura_norm"],
            "MATCH_ALIAS",
        ).rename(
            columns={
                "_cod_ramo_lookup": "_cod_ramo_alias_generic",
                "_codigo_estado_lookup": "_codigo_estado_alias_generic",
            }
        )

        if not specific_aliases.empty:
            df_out = df_out.merge(
                specific_aliases,
                how="left",
                on=["_carrera_base_norm", "_asignatura_norm", "_semestre_norm"],
            )
        else:
            df_out["_cod_ramo_alias_specific"] = ""
            df_out["_codigo_estado_alias_specific"] = ""

        if not generic_aliases.empty:
            df_out = df_out.merge(
                generic_aliases,
                how="left",
                on=["_carrera_base_norm", "_asignatura_norm"],
            )
        else:
            df_out["_cod_ramo_alias_generic"] = ""
            df_out["_codigo_estado_alias_generic"] = ""

        for col in [
            "_cod_ramo_alias_specific",
            "_codigo_estado_alias_specific",
            "_cod_ramo_alias_generic",
            "_codigo_estado_alias_generic",
        ]:
            df_out[col] = df_out[col].fillna("")

        mask_specific = df_out["_codigo_estado"].isin({"SIN_MATCH", "AMBIGUO", "SIN_CATALOGO"}) & (
            df_out["_codigo_estado_alias_specific"] == "MATCH_ALIAS"
        )
        df_out.loc[mask_specific, "CÓDIGO DEL CURSO"] = df_out.loc[mask_specific, "_cod_ramo_alias_specific"]
        df_out.loc[mask_specific, "_cod_ramo_oficial"] = df_out.loc[mask_specific, "_cod_ramo_alias_specific"]
        df_out.loc[mask_specific, "_codigo_estado"] = "MATCH_ALIAS"

        mask_generic = df_out["_codigo_estado"].isin({"SIN_MATCH", "AMBIGUO", "SIN_CATALOGO"}) & (
            df_out["_codigo_estado_alias_generic"] == "MATCH_ALIAS"
        )
        df_out.loc[mask_generic, "CÓDIGO DEL CURSO"] = df_out.loc[mask_generic, "_cod_ramo_alias_generic"]
        df_out.loc[mask_generic, "_cod_ramo_oficial"] = df_out.loc[mask_generic, "_cod_ramo_alias_generic"]
        df_out.loc[mask_generic, "_codigo_estado"] = "MATCH_ALIAS"

    mask_ok = df_out["_codigo_estado"].isin({"MATCH_OK", "MATCH_ALIAS"})
    df_out.loc[mask_ok, "CÓDIGO DEL CURSO"] = df_out.loc[mask_ok, "_cod_ramo_oficial"]

    mask_missing_code = df_out["_codigo_estado"].isin({"SIN_MATCH", "AMBIGUO", "SIN_CATALOGO"})
    df_out.loc[mask_missing_code, "CÓDIGO DEL CURSO"] = MISSING_CODE_PLACEHOLDER

    n_ok = int((df_out["_codigo_estado"] == "MATCH_OK").sum())
    n_alias = int((df_out["_codigo_estado"] == "MATCH_ALIAS").sum())
    n_missing = int((df_out["_codigo_estado"] == "SIN_MATCH").sum())
    n_ambiguous = int((df_out["_codigo_estado"] == "AMBIGUO").sum())
    n_no_catalog = int((df_out["_codigo_estado"] == "SIN_CATALOGO").sum())
    n_preserved = int((df_out["_codigo_estado"] == "PRESERVADO_EXISTENTE").sum())

    logger.info(
        "Etapa final — códigos oficiales: %d match(es), %d alias(es), %d sin match, %d ambiguo(s), %d sin catálogo, %d preservado(s).",
        n_ok,
        n_alias,
        n_missing,
        n_ambiguous,
        n_no_catalog,
        n_preserved,
    )

    if n_missing > 0:
        logger.warning(
            "subject_code_enricher: %d fila(s) quedaron sin código oficial.", n_missing
        )
    if n_ambiguous > 0:
        logger.warning(
            "subject_code_enricher: %d fila(s) tienen match ambiguo en el catálogo.", n_ambiguous
        )
    if n_no_catalog > 0:
        logger.warning(
            "subject_code_enricher: catálogo no disponible; %d fila(s) quedaron sin código oficial.",
            n_no_catalog,
        )
    if n_preserved > 0:
        logger.info(
            "subject_code_enricher: %d fila(s) conservaron el código ya presente en el DataFrame.",
            n_preserved,
        )

    if matching_path is not None:
        diag = df_out[
            [
                "CARRERA",
                "_carrera_base",
                "ASIGNATURA",
                "CÓDIGO DEL CURSO",
                "_codigo_estado",
            ]
        ].copy()
        diag = diag.rename(
            columns={
                "_carrera_base": "CARRERA_BASE",
                "CÓDIGO DEL CURSO": "CODIGO_OFICIAL",
                "_codigo_estado": "ESTADO_CODIGO",
            }
        )
        matching_path.parent.mkdir(parents=True, exist_ok=True)
        diag.to_csv(str(matching_path), index=False, encoding="utf-8-sig")
        logger.info("  → CSV de códigos oficiales guardado en: %s", matching_path)

    df_out = df_out.drop(
        columns=[
            "_carrera_base",
            "_carrera_base_norm",
            "_asignatura_norm",
            "_semestre_norm",
            "_cod_ramo_oficial",
            "_codigo_estado",
            "_cod_ramo_alias_specific",
            "_codigo_estado_alias_specific",
            "_cod_ramo_alias_generic",
            "_codigo_estado_alias_generic",
        ],
        errors="ignore",
    )
    df_out = _harmonize_subject_names_by_course_code(df_out)
    return df_out
