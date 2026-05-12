"""merger.py — Fusión del consolidado de tributación con las horas extraídas del PDF.

Une el DataFrame producido por :func:`~tributacion.matrix_parser.parse_matrix`
con el DataFrame producido por :func:`~tributacion.pdf_parser.parse_pdf` usando
un left join por ``(semestre, asignatura_norm)``.

Si el join exacto deja filas sin horas, se intenta un join difuso (fuzzy)
por ``asignatura_norm`` dentro del mismo semestre, usando
:func:`~tributacion.text_utils.best_fuzzy_match`.

Después del join:
- Se mapean las 14 columnas del PDF a las columnas objetivo del Excel.
- Las columnas de horas se convierten a numérico.
- Las columnas temporales de join se eliminan.

Función pública principal
-------------------------
:func:`merge_horas`
"""

import logging
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from tributacion.config import (
    MAPEO_CSV_A_EXCEL,
    NUMERIC_COLUMNS,
    OUTPUT_COLUMNS,
    SUBJECT_CODES_ALIASES_PATH,
)
from tributacion.text_utils import best_fuzzy_match, norm_text

logger = logging.getLogger(__name__)

# Umbral de similitud para el join difuso dentro del mismo semestre (0–1).
FUZZY_THRESHOLD: float = 0.75

# Umbral más estricto para el fallback cross-semestre (se usa solo cuando el
# join exacto y el fuzzy dentro del mismo semestre fallan por completo).
CROSS_SEMESTER_THRESHOLD: float = 0.90

# Umbral mínimo para el fallback "alerta nombre diferente" (Fase 3).
# Matches a este nivel se aplican igual pero emiten una ALARMA visible:
# indica que el nombre del PDF y la matriz son distintos aunque similares.
ALERTA_NOMBRE_THRESHOLD: float = 0.65

# Umbral para completar ÁREA DE FORMACIÓN cuando falta y existen variaciones
# menores de nombre entre PDF y matriz.
AREA_FUZZY_THRESHOLD: float = 0.70

# Fallback difuso global de nombre (sin restringir semestre) para completar
# área cuando no hay coincidencia por semestre.
AREA_GLOBAL_FUZZY_THRESHOLD: float = 0.72

# Fallbacks controlados para casos donde la matriz sí declara el área en texto
# descriptivo, pero el catálogo tabular no la expone de forma directa.
MANUAL_AREA_FALLBACKS: dict[str, str] = {
    norm_text("Atención Primaria y Modelo de Salud Familiar I"): "Formación Práctica",
    norm_text("Atención Primaria y Modelo de Salud Familiar II"): "Formación Práctica",
    norm_text("Cuidados Neonatales I"): "Formación Práctica",
    norm_text("Cuidados Neonatales II"): "Formación Práctica",
    norm_text("Optativo de Certificación I"): "Formación Especializada",
    norm_text("Optativo de Certificación II"): "Formación Especializada",
    norm_text("Optativo de Certificación III"): "Formación Especializada",
}

INVALID_COURSE_CODES: set[str] = {
    "",
    "SIN CÓDIGO",
    "SIN CODIGO",
    "N/A",
    "NA",
    "NONE",
    "NULL",
}

_CAREER_EQUIVALENCES: dict[str, str] = {
    "ingenieria mecatronica": "ingenieria en mecatronica",
    "ingenieria civil en medio ambiente": "ingenieria civil en medio ambiente y sustentabilidad",
}

_OPTION_INCOMPATIBLE_SUBJECTS_BY_CARRERA: dict[str, set[str]] = {
    norm_text("Certificación Académica en Enfermería Adulto"): {
        norm_text("Enfermería en Salud Familiar"),
        norm_text("Intervención de Enfermería en Salud Comunitaria"),
    },
    norm_text("Certificación Académica en Enfermería Comunitaria"): {
        norm_text("Cuidados de Enfermería en Adulto Crítico"),
        norm_text("Cuidados de Enfermería en el Adulto Crítico"),
        norm_text("Enfermería en Unidades Quirúrgicas del Adulto"),
    },
}


def _base_carrera_for_alias(carrera: object) -> str:
    """Obtiene carrera base antes de sufijos de opcion academica."""
    value = "" if pd.isna(carrera) else str(carrera)
    value = value.replace("_", " ").strip()
    return value.split("-", 1)[0].strip()


def _career_norm_for_alias(carrera: object) -> str:
    """Normaliza carrera igual que el catalogo manual de alias."""
    base = _base_carrera_for_alias(carrera)
    norm = norm_text(base)
    if norm.startswith("tecnologia medica mencion "):
        return "tecnologia medica"
    return _CAREER_EQUIVALENCES.get(norm, norm)


def _normalize_semestre_key(value: object) -> str:
    """Normaliza semestre a clave comparable para alias manuales."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def _target_norms_from_alias(value: object) -> list[str]:
    """Genera variantes normalizadas de un alias objetivo."""
    text = str(value or "").strip()
    if not text:
        return []

    variants = [text]
    without_parenthetical = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    if without_parenthetical and without_parenthetical != text:
        variants.append(without_parenthetical)

    seen: set[str] = set()
    out: list[str] = []
    for variant in variants:
        norm = norm_text(variant)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _normalize_hours_alias_catalog(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el catalogo manual de alias para uso en merge de horas."""
    required = {"nombre_carrera", "Asignatura", "Asignatura_catalogo"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    alias = df.copy().fillna("")
    for col in ["nombre_carrera", "Asignatura", "Asignatura_catalogo", "semestre"]:
        if col not in alias.columns:
            alias[col] = ""
        alias[col] = alias[col].astype(str).str.strip()

    alias = alias.loc[
        (alias["nombre_carrera"] != "")
        & (alias["Asignatura"] != "")
        & (alias["Asignatura_catalogo"] != "")
    ].copy()
    if alias.empty:
        return pd.DataFrame()

    alias["_carrera_base_norm"] = alias["nombre_carrera"].apply(_career_norm_for_alias)
    alias["_asignatura_norm"] = alias["Asignatura"].apply(norm_text)
    alias["_semestre_norm"] = alias["semestre"].apply(_normalize_semestre_key)
    alias["_target_norms"] = alias["Asignatura_catalogo"].apply(_target_norms_from_alias)
    alias = alias[alias["_target_norms"].map(bool)].copy()
    if alias.empty:
        return pd.DataFrame()
    return alias


@lru_cache(maxsize=4)
def _load_hours_alias_catalog_cached(path_str: str) -> pd.DataFrame:
    path = Path(path_str)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo leer catalogo de alias de horas %s (%s).", path, exc)
        return pd.DataFrame()
    alias = _normalize_hours_alias_catalog(df)
    if not alias.empty:
        logger.info("Alias de horas cargados desde %s.", path)
    return alias


def _load_hours_alias_catalog(path: Path = SUBJECT_CODES_ALIASES_PATH) -> pd.DataFrame:
    """Carga alias manuales reutilizando el catalogo local de asignaturas."""
    return _load_hours_alias_catalog_cached(str(path))


def _manual_hours_alias_targets(carrera: object, asignatura: object) -> list[str]:
    """Alias de horas que dependen de la opcion academica activa."""
    carrera_text = "" if pd.isna(carrera) else str(carrera)
    carrera_norm = norm_text(carrera_text.replace("_", " "))
    asig_norm = norm_text(asignatura)
    targets: list[str] = []

    if "obstetricia y puericultura" in carrera_norm:
        if (
            "certificacion i en atencion primaria" in asig_norm
            or "certificacion i en atencion primaria y modelo de salud familiar competencias" in asig_norm
        ):
            if "cuidados neonatales" in carrera_norm:
                targets.append("Cuidados Neonatales I")
            elif "atencion primaria" in carrera_norm:
                targets.append("Atención Primaria y Modelo de Salud Familiar I")
        if (
            "certificacion ii en atencion primaria" in asig_norm
            or "certificacion ii en atencion primaria y modelo de salud familiar competencias" in asig_norm
        ):
            if "cuidados neonatales" in carrera_norm:
                targets.append("Cuidados Neonatales II")
            elif "atencion primaria" in carrera_norm:
                targets.append("Atención Primaria y Modelo de Salud Familiar II")

    if "trabajo social" in carrera_norm and "politicas publicas" in carrera_norm:
        if (
            "optativo de especializacion i" in asig_norm
            or "optativo de especializacion 1" in asig_norm
        ):
            targets.append("Optativo de Certificación I")
        if (
            "optativo de especializacion ii" in asig_norm
            or "optativo de especializacion 2" in asig_norm
        ):
            targets.append("Optativo de Certificación II")
        if (
            "optativo de especializacion iii" in asig_norm
            or "optativo de especializacion 3" in asig_norm
        ):
            targets.append("Optativo de Certificación III")

    return targets


def _copy_hour_values(
    df_merge: pd.DataFrame,
    idx: int,
    hora_row: pd.Series,
    src_dst: dict[str, str],
) -> None:
    """Copia columnas de horas sin pisar valores ya poblados."""
    for src_col, dst_col in src_dst.items():
        val = hora_row[src_col]
        dst_empty = (
            pd.isna(df_merge.at[idx, dst_col])
            or str(df_merge.at[idx, dst_col]).strip() in ("", "nan")
        )
        if dst_empty and pd.notna(val):
            df_merge.at[idx, dst_col] = val


def _filter_option_incompatible_rows(df_c: pd.DataFrame) -> pd.DataFrame:
    """Descarta asignaturas de la otra opcion academica antes del fuzzy."""
    if df_c.empty:
        return df_c
    required = {"CARRERA", "ASIGNATURA_norm"}
    if not required.issubset(df_c.columns):
        return df_c

    carreras_norm = (
        df_c["CARRERA"]
        .fillna("")
        .astype(str)
        .str.replace("_", " ", regex=False)
        .map(norm_text)
    )
    asignaturas_norm = df_c["ASIGNATURA_norm"].fillna("").astype(str)

    drop_mask = pd.Series(False, index=df_c.index)
    for option_norm, excluded_subjects in _OPTION_INCOMPATIBLE_SUBJECTS_BY_CARRERA.items():
        option_mask = carreras_norm.str.contains(option_norm, regex=False, na=False)
        if option_mask.any():
            drop_mask |= option_mask & asignaturas_norm.isin(excluded_subjects)

    if not drop_mask.any():
        return df_c

    logger.warning(
        "  ⚠ %d fila(s) descartadas por pertenecer a otra opción académica.",
        int(drop_mask.sum()),
    )
    return df_c.loc[~drop_mask].copy()


def _select_canonical_subject_name(names: pd.Series) -> str:
    """Selecciona un nombre canónico entre variantes para el mismo código.

    Criterios (en orden):
    1) mayor frecuencia,
    2) mayor número de tokens,
    3) menos uniones tipográficas (ej. ``deTitulación``),
    4) mayor longitud.
    """
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
    code_df = code_df[(code_df["code"] != "") & (~code_df["code"].isin(INVALID_COURSE_CODES)) & (code_df["name"] != "")]
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
        return out

    mask = codes.isin(canonical_by_code.keys())
    out.loc[mask, "ASIGNATURA"] = codes[mask].map(canonical_by_code)
    if "ASIGNATURA_norm" in out.columns:
        out.loc[mask, "ASIGNATURA_norm"] = out.loc[mask, "ASIGNATURA"].map(norm_text)

    return out


def _resolve_default_value(df: pd.DataFrame, column: str) -> str:
    """Obtiene un valor por defecto estable desde el DataFrame final base."""
    if column not in df.columns or df.empty:
        return ""
    series = df[column].dropna().astype(str).str.strip()
    series = series[series != ""]
    if series.empty:
        return ""
    return str(series.mode().iloc[0])


def _build_semester_ciclo_map(df: pd.DataFrame) -> dict[int, str]:
    """Construye un mapa ``semestre -> CICLO`` desde las filas disponibles."""
    if "NIVEL O SEMESTRE" not in df.columns or "CICLO" not in df.columns or df.empty:
        return {}
    sub = df[["NIVEL O SEMESTRE", "CICLO"]].copy()
    sub["NIVEL O SEMESTRE"] = pd.to_numeric(
        sub["NIVEL O SEMESTRE"], errors="coerce"
    ).fillna(0).astype(int)
    sub["CICLO"] = sub["CICLO"].fillna("").astype(str).str.strip()
    sub = sub[(sub["NIVEL O SEMESTRE"] > 0) & (sub["CICLO"] != "")]
    if sub.empty:
        return {}
    grouped = sub.groupby("NIVEL O SEMESTRE")["CICLO"].agg(lambda s: s.mode().iloc[0])
    return {int(k): str(v) for k, v in grouped.items()}


def _resolve_ciclo_for_semester(
    semester: int,
    semester_ciclo_map: dict[int, str],
    default_ciclo: str,
) -> str:
    """Resuelve etiqueta de ciclo para un semestre dado."""
    if semester <= 0:
        return default_ciclo
    ciclo = semester_ciclo_map.get(int(semester), "")
    if ciclo:
        return ciclo
    return default_ciclo


def _alias_fill(
    df_merge: pd.DataFrame,
    df_horas: pd.DataFrame,
    alias_catalog: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Rellena horas usando alias manuales de asignatura.

    Esta fase corre antes del fuzzy para casos donde la matriz y el PDF usan
    nombres intencionalmente distintos, como ``Lengua Extranjera I`` vs
    ``Inglés I`` o siglas como ``PI II TMB``.
    """
    if df_merge.empty or df_horas.empty:
        df_merge["_alias_pdf_norm"] = [""] * len(df_merge)
        return df_merge

    if alias_catalog is None:
        alias_catalog = _load_hours_alias_catalog()
    if alias_catalog is None:
        alias_catalog = pd.DataFrame()
    elif not alias_catalog.empty and "_target_norms" not in alias_catalog.columns:
        alias_catalog = _normalize_hours_alias_catalog(alias_catalog)

    h_unique = df_horas.drop_duplicates(subset=["semestre", "asignatura_norm"]).copy()
    h_unique["semestre"] = pd.to_numeric(h_unique["semestre"], errors="coerce").fillna(0).astype(int)
    h_unique["asignatura_norm"] = h_unique["asignatura_norm"].astype(str)
    h_lookup = {
        (int(r["semestre"]), str(r["asignatura_norm"])): r
        for _, r in h_unique.iterrows()
    }

    src_dst = {src: dst for src, dst in MAPEO_CSV_A_EXCEL.items() if src in df_horas.columns}
    alias_pdf_norms: list[str] = [""] * len(df_merge)
    n_alias = 0

    for idx in df_merge.index:
        loc = df_merge.index.get_loc(idx)
        already_matched = not (
            pd.isna(df_merge.at[idx, "N° DE CRÉDITOS"])
            or str(df_merge.at[idx, "N° DE CRÉDITOS"]).strip() in ("", "nan")
        )
        if already_matched:
            continue

        carrera = df_merge.at[idx, "CARRERA"] if "CARRERA" in df_merge.columns else ""
        asig = df_merge.at[idx, "ASIGNATURA"] if "ASIGNATURA" in df_merge.columns else ""
        asig_norm = str(df_merge.at[idx, "ASIGNATURA_norm"])
        sem = int(df_merge.at[idx, "_semestre_int"]) if pd.notna(df_merge.at[idx, "_semestre_int"]) else 0
        sem_norm = _normalize_semestre_key(sem)

        target_norms: list[str] = []
        for target in _manual_hours_alias_targets(carrera, asig):
            target_norms.extend(_target_norms_from_alias(target))

        if not alias_catalog.empty:
            career_norm = _career_norm_for_alias(carrera)
            candidates = alias_catalog[
                (alias_catalog["_carrera_base_norm"] == career_norm)
                & (alias_catalog["_asignatura_norm"] == asig_norm)
                & (
                    (alias_catalog["_semestre_norm"] == "")
                    | (alias_catalog["_semestre_norm"] == sem_norm)
                )
            ]
            for norms in candidates["_target_norms"].tolist():
                target_norms.extend(norms)

        seen: set[str] = set()
        for target_norm in target_norms:
            if not target_norm or target_norm in seen:
                continue
            seen.add(target_norm)
            hora_row = h_lookup.get((sem, target_norm))
            if hora_row is None:
                continue
            _copy_hour_values(df_merge, idx, hora_row, src_dst)
            df_merge.at[idx, "_match_state"] = "MATCH_ALIAS"
            alias_pdf_norms[loc] = f"{sem}::{target_norm}"
            n_alias += 1
            break

    df_merge["_alias_pdf_norm"] = alias_pdf_norms
    if n_alias:
        logger.info("  → %d filas rellenadas por alias de asignatura", n_alias)
    return df_merge


def _fuzzy_fill(
    df_merge: pd.DataFrame,
    df_horas: pd.DataFrame,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> pd.DataFrame:
    """Rellena filas sin horas usando coincidencia difusa.

    **Fase 1 — mismo semestre:** para cada fila cuyo ``N° DE CRÉDITOS`` sigue
    vacío tras el join exacto, busca en ``df_horas`` (dentro del mismo semestre)
    el nombre más parecido a ``fuzzy_threshold``.

    **Fase 2 — cross-semestre:** si la fase 1 no encuentra match, busca en
    *todos* los semestres del PDF con umbral :data:`CROSS_SEMESTER_THRESHOLD`
    (más estricto: 0.90).  Cuando hay match cross-semestre se emite un
    ``WARNING`` indicando la discrepancia.

    **Fase 3 — alerta nombre diferente:** si las fases 1 y 2 fallan, reintenta
    con umbral :data:`ALERTA_NOMBRE_THRESHOLD` (0.60) en todos los semestres.
    Aun así se aplica el match pero emite una **ALARMA** visible indicando que
    los nombres son muy distintos y deben verificarse manualmente.
        df_horas:        DataFrame de horas (salida de ``parse_pdf``).
        fuzzy_threshold: Umbral para el join dentro del mismo semestre.

    Returns:
        ``df_merge`` con huecos rellenados y columnas temporales
        ``_fuzzy_score`` y ``_pdf_semestre`` añadidas.
    """
    # Índice auxiliar: semestre → lista de (asignatura_norm, df_idx)
    sem_to_candidates: dict[int, list[tuple[str, int]]] = {}
    # Lista plana para búsqueda cross-semestre: (asignatura_norm, df_idx, semestre)
    all_candidates: list[tuple[str, int, int]] = []
    for i, row in df_horas.iterrows():
        sem = int(row["semestre"]) if pd.notna(row["semestre"]) else 0
        sem_to_candidates.setdefault(sem, []).append((row["asignatura_norm"], int(i)))  # type: ignore[arg-type]
        all_candidates.append((row["asignatura_norm"], int(i), sem))

    # Mapeo de columnas fuente → destino para copiar
    src_dst = {src: dst for src, dst in MAPEO_CSV_A_EXCEL.items() if src in df_horas.columns}

    fuzzy_scores: list[float] = [0.0] * len(df_merge)
    fuzzy_types: list[str] = [""] * len(df_merge)
    pdf_sem_overrides: list[int | None] = [None] * len(df_merge)
    # Tracks the (semestre, asignatura_norm) of the PDF subject consumed by each
    # fuzzy match.  This is used by _append_pdf_only_rows to avoid re-adding
    # subjects that were already matched via fuzzy join.
    fuzzy_pdf_norm_list: list[str] = [""] * len(df_merge)

    for idx in df_merge.index:

        mat_sem = int(df_merge.at[idx, "_semestre_int"]) if pd.notna(df_merge.at[idx, "_semestre_int"]) else 0
        query = str(df_merge.at[idx, "ASIGNATURA_norm"])
        asig_display = str(df_merge.at[idx, "ASIGNATURA"]) if "ASIGNATURA" in df_merge.columns else query
        loc = df_merge.index.get_loc(idx)

        # --- Fase 1: mismo semestre -------------------------------------------
        same_sem_candidates = sem_to_candidates.get(mat_sem, [])
        if same_sem_candidates:
            candidate_names = [c[0] for c in same_sem_candidates]
            best_name, score = best_fuzzy_match(query, candidate_names, threshold=fuzzy_threshold)
            if best_name is not None:
                hora_idx = next(c[1] for c in same_sem_candidates if c[0] == best_name)
                hora_row = df_horas.loc[hora_idx]
                logger.debug(
                    "Fuzzy match (score=%.2f): '%s' → '%s' (semestre %d)",
                    score, query, best_name, mat_sem,
                )
                fuzzy_scores[loc] = score
                fuzzy_types[loc] = "MATCH_FUZZY"
                fuzzy_pdf_norm_list[loc] = f"{mat_sem}::{best_name}"
                _copy_hour_values(df_merge, idx, hora_row, src_dst)
                continue

        # --- Fase 2: cross-semestre (umbral más estricto) ---------------------
        all_names = [c[0] for c in all_candidates]
        best_cross, score_cross = best_fuzzy_match(query, all_names, threshold=CROSS_SEMESTER_THRESHOLD)
        if best_cross is not None:
            match_entry = next(c for c in all_candidates if c[0] == best_cross)
            hora_idx_cross, pdf_sem = match_entry[1], match_entry[2]
            hora_row_cross = df_horas.loc[hora_idx_cross]
            logger.warning(
                "  ⚠ SEMESTRE DISCREPANTE — '%s': matriz=sem%d / PDF=sem%d "
                "(score=%.2f). Se usará el semestre del PDF.",
                asig_display, mat_sem, pdf_sem, score_cross,
            )
            fuzzy_scores[loc] = score_cross
            fuzzy_types[loc] = "MATCH_CROSS_SEMESTRE"
            pdf_sem_overrides[loc] = pdf_sem
            fuzzy_pdf_norm_list[loc] = f"{pdf_sem}::{best_cross}"
            _copy_hour_values(df_merge, idx, hora_row_cross, src_dst)
            continue

        # --- Fase 3: alerta nombre diferente (umbral bajo) -------------------
        best_alert, score_alert = best_fuzzy_match(
            query, all_names, threshold=ALERTA_NOMBRE_THRESHOLD
        )
        if best_alert is not None:
            alert_entry = next(c for c in all_candidates if c[0] == best_alert)
            hora_idx_alert, pdf_sem_alert = alert_entry[1], alert_entry[2]
            hora_row_alert = df_horas.loc[hora_idx_alert]
            logger.warning(
                "  🚨 ALERTA NOMBRE DIFERENTE — '%s' (sem%d en matriz) apareada con "
                "'%s' (sem%d en PDF, score=%.2f). "
                "Son los más similares disponibles; verificar si corresponden a la misma asignatura.",
                asig_display, mat_sem,
                str(df_horas.loc[hora_idx_alert, "asignatura"]), pdf_sem_alert, score_alert,
            )
            fuzzy_scores[loc] = score_alert
            fuzzy_types[loc] = "MATCH_ALERTA_NOMBRE"
            fuzzy_pdf_norm_list[loc] = f"{pdf_sem_alert}::{best_alert}"
            _copy_hour_values(df_merge, idx, hora_row_alert, src_dst)

    df_merge["_fuzzy_score"] = fuzzy_scores
    df_merge["_fuzzy_match_type"] = fuzzy_types
    df_merge["_pdf_semestre"] = pd.array(pdf_sem_overrides, dtype="object")
    df_merge["_fuzzy_pdf_norm"] = fuzzy_pdf_norm_list
    return df_merge


def _append_pdf_only_rows(df_merge: pd.DataFrame, df_h: pd.DataFrame) -> pd.DataFrame:
    """Agrega filas para asignaturas presentes en PDF pero ausentes en matriz.

    La detección se hace por clave ``(semestre, asignatura_norm)``.
    Cada asignatura sólo-PDF se agrega una vez con estado
    ``SIN_TRIBUTACION_EN_MATRIZ`` para mantener trazabilidad.
    """
    if df_h.empty:
        return df_merge

    matrix_keys = {
        (int(sem), str(asig_norm))
        for sem, asig_norm in df_merge[["_semestre_int", "ASIGNATURA_norm"]]
        .dropna()
        .drop_duplicates()
        .itertuples(index=False, name=None)
    }

    if not matrix_keys and df_merge.empty:
        matrix_keys = set()

    # Build the set of PDF subjects already consumed by alias/fuzzy matching.
    # Format stored in *_pdf_norm is "semestre::asignatura_norm".
    # This prevents re-adding a PDF subject that was matched (even fuzzily) to
    # a matrix subject with a slightly different normalised name.
    consumed_pdf_keys: set[tuple[int, str]] = set()
    for marker_col in ["_alias_pdf_norm", "_fuzzy_pdf_norm"]:
        if marker_col not in df_merge.columns:
            continue
        for entry in df_merge[marker_col].dropna():
            entry_str = str(entry).strip()
            if "::" not in entry_str:
                continue
            sem_str, norm_str = entry_str.split("::", 1)
            try:
                consumed_pdf_keys.add((int(sem_str), norm_str))
            except ValueError:
                pass

    df_h_unique = df_h.drop_duplicates(subset=["semestre", "asignatura_norm"])
    missing_pdf = df_h_unique[
        ~df_h_unique.apply(
            lambda row: (
                (int(row["semestre"]), str(row["asignatura_norm"])) in matrix_keys
                or (int(row["semestre"]), str(row["asignatura_norm"])) in consumed_pdf_keys
            ),
            axis=1,
        )
    ]

    if missing_pdf.empty:
        return df_merge

    src_dst = {src: dst for src, dst in MAPEO_CSV_A_EXCEL.items() if src in df_h.columns}
    semester_ciclo_map = _build_semester_ciclo_map(df_merge)
    default_ciclo = _resolve_default_value(df_merge, "CICLO")
    defaults = {
        "GRADO": _resolve_default_value(df_merge, "GRADO"),
        "FACULTAD": _resolve_default_value(df_merge, "FACULTAD"),
        "ESCUELA": _resolve_default_value(df_merge, "ESCUELA"),
        "CARRERA": _resolve_default_value(df_merge, "CARRERA"),
        "MODALIDAD": _resolve_default_value(df_merge, "MODALIDAD") or "Presencial",
    }

    new_rows: list[dict] = []
    for _, row in missing_pdf.iterrows():
        sem = int(row["semestre"])
        new_row = {col: pd.NA for col in df_merge.columns}
        for meta_col, default_value in defaults.items():
            if meta_col in new_row:
                if meta_col == "CARRERA":
                    new_row[meta_col] = default_value
                else:
                    new_row[meta_col] = row.get(meta_col, default_value) or default_value
        if "NIVEL O SEMESTRE" in new_row:
            new_row["NIVEL O SEMESTRE"] = sem
        if "AÑO" in new_row:
            new_row["AÑO"] = (sem + 1) // 2 if sem > 0 else 0
        if "CICLO" in new_row:
            new_row["CICLO"] = _resolve_ciclo_for_semester(
                sem,
                semester_ciclo_map,
                default_ciclo,
            )
        if "ASIGNATURA" in new_row:
            new_row["ASIGNATURA"] = row.get("asignatura", "")
        if "ASIGNATURA_norm" in new_row:
            new_row["ASIGNATURA_norm"] = row.get("asignatura_norm", "")
        if "_semestre_int" in new_row:
            new_row["_semestre_int"] = sem
        if "_match_state" in new_row:
            new_row["_match_state"] = "SIN_TRIBUTACION"

        for src_col, dst_col in src_dst.items():
            if dst_col in new_row:
                new_row[dst_col] = row.get(src_col, pd.NA)

        new_rows.append(new_row)

    if not new_rows:
        return df_merge

    logger.warning(
        "  ⚠ %d asignatura(s) presentes en PDF no existen en matriz y se agregarán al consolidado.",
        len(new_rows),
    )
    return pd.concat([df_merge, pd.DataFrame(new_rows)], ignore_index=True)


def _append_matrix_no_tributacion_rows(
    df_merge: pd.DataFrame,
    df_h: pd.DataFrame,
    matrix_courses: pd.DataFrame,
) -> pd.DataFrame:
    """Agrega filas de matriz sin tributación para la opción académica actual.

    Para evitar mezclar opciones, solo agrega filas cuyo ``(semestre,
    asignatura_norm)`` exista en ``df_h`` (subset de horas ya filtrado por
    opción en ``run_batch``).
    """
    required = {
        "NIVEL O SEMESTRE",
        "AÑO",
        "ASIGNATURA",
        "ASIGNATURA_norm",
        "TRIBUTA_EN_MATRIZ",
        "ÁREA DE FORMACIÓN",
    }
    if matrix_courses.empty or not required.issubset(matrix_courses.columns):
        return df_merge
    if df_h.empty:
        return df_merge

    df_mc = matrix_courses.copy()
    df_mc["NIVEL O SEMESTRE"] = pd.to_numeric(
        df_mc["NIVEL O SEMESTRE"], errors="coerce"
    ).fillna(0).astype(int)
    df_mc["ASIGNATURA_norm"] = df_mc["ASIGNATURA_norm"].astype(str)
    df_mc = df_mc[df_mc["TRIBUTA_EN_MATRIZ"] == False]  # noqa: E712
    if df_mc.empty:
        return df_merge

    horas_keys = set(
        zip(
            pd.to_numeric(df_h["semestre"], errors="coerce").fillna(0).astype(int),
            df_h["asignatura_norm"].astype(str),
        )
    )
    if not horas_keys:
        return df_merge

    existing_keys = set(
        zip(
            pd.to_numeric(df_merge["NIVEL O SEMESTRE"], errors="coerce").fillna(0).astype(int),
            df_merge["ASIGNATURA_norm"].astype(str),
        )
    )

    src_dst = {src: dst for src, dst in MAPEO_CSV_A_EXCEL.items() if src in df_h.columns}
    h_unique = df_h.drop_duplicates(subset=["semestre", "asignatura_norm"]).copy()
    h_unique["semestre"] = pd.to_numeric(h_unique["semestre"], errors="coerce").fillna(0).astype(int)
    h_lookup = {
        (int(r["semestre"]), str(r["asignatura_norm"])): r
        for _, r in h_unique.iterrows()
    }
    semester_ciclo_map = _build_semester_ciclo_map(df_merge)
    default_ciclo = _resolve_default_value(df_merge, "CICLO")

    defaults = {
        "GRADO": _resolve_default_value(df_merge, "GRADO"),
        "FACULTAD": _resolve_default_value(df_merge, "FACULTAD"),
        "ESCUELA": _resolve_default_value(df_merge, "ESCUELA"),
        "CARRERA": _resolve_default_value(df_merge, "CARRERA"),
        "MODALIDAD": _resolve_default_value(df_merge, "MODALIDAD") or "Presencial",
    }

    new_rows: list[dict] = []
    for _, row in df_mc.iterrows():
        key = (int(row["NIVEL O SEMESTRE"]), str(row["ASIGNATURA_norm"]))
        if key not in horas_keys:
            continue
        if key in existing_keys:
            continue

        new_row = {col: pd.NA for col in df_merge.columns}
        for meta_col, default_value in defaults.items():
            if meta_col in new_row:
                new_row[meta_col] = default_value
        if "NIVEL O SEMESTRE" in new_row:
            new_row["NIVEL O SEMESTRE"] = key[0]
        if "AÑO" in new_row:
            year_value = row.get("AÑO", pd.NA)
            if pd.isna(year_value):
                year_value = (key[0] + 1) // 2 if key[0] > 0 else 0
            new_row["AÑO"] = year_value
        if "CICLO" in new_row:
            new_row["CICLO"] = _resolve_ciclo_for_semester(
                key[0],
                semester_ciclo_map,
                default_ciclo,
            )
        if "ASIGNATURA" in new_row:
            new_row["ASIGNATURA"] = row.get("ASIGNATURA", "")
        if "ÁREA DE FORMACIÓN" in new_row:
            new_row["ÁREA DE FORMACIÓN"] = row.get("ÁREA DE FORMACIÓN", "")
        if "ASIGNATURA_norm" in new_row:
            new_row["ASIGNATURA_norm"] = key[1]
        if "_semestre_int" in new_row:
            new_row["_semestre_int"] = key[0]
        if "_match_state" in new_row:
            new_row["_match_state"] = "SIN_TRIBUTACION"

        hora_row = h_lookup.get(key)
        if hora_row is not None:
            for src_col, dst_col in src_dst.items():
                if dst_col in new_row:
                    new_row[dst_col] = hora_row.get(src_col, pd.NA)

        new_rows.append(new_row)

    if not new_rows:
        return df_merge

    logger.warning(
        "  ⚠ %d asignatura(s) de matriz sin tributación se agregaron para la opción actual.",
        len(new_rows),
    )
    return pd.concat([df_merge, pd.DataFrame(new_rows)], ignore_index=True)


def _fill_missing_area_formacion(
    df_merge: pd.DataFrame,
    matrix_courses: pd.DataFrame,
    fuzzy_threshold: float = AREA_FUZZY_THRESHOLD,
) -> pd.DataFrame:
    """Completa ``ÁREA DE FORMACIÓN`` faltante desde catálogo de matriz.

    Estrategia de completado (en orden):
    1) Match exacto por ``(semestre, ASIGNATURA_norm)``.
    2) Match exacto por ``ASIGNATURA_norm`` ignorando semestre.
    3) Match difuso dentro del mismo semestre.

    Esta función permite cubrir variaciones leves de nombre entre la malla del
    PDF y la matriz (por ejemplo, espacios o palabras intermedias).
    """
    if df_merge.empty:
        return df_merge
    if "ÁREA DE FORMACIÓN" not in df_merge.columns:
        return df_merge

    required = {"NIVEL O SEMESTRE", "ASIGNATURA_norm", "ÁREA DE FORMACIÓN"}
    if matrix_courses.empty or not required.issubset(matrix_courses.columns):
        return df_merge

    df_mc = matrix_courses.copy()
    df_mc["NIVEL O SEMESTRE"] = pd.to_numeric(
        df_mc["NIVEL O SEMESTRE"], errors="coerce"
    ).fillna(0).astype(int)
    df_mc["ASIGNATURA_norm"] = df_mc["ASIGNATURA_norm"].fillna("").astype(str)
    df_mc["ÁREA DE FORMACIÓN"] = df_mc["ÁREA DE FORMACIÓN"].fillna("").astype(str).str.strip()
    df_mc = df_mc[df_mc["ÁREA DE FORMACIÓN"] != ""]
    if df_mc.empty:
        return df_merge

    exact_by_sem = (
        df_mc[["NIVEL O SEMESTRE", "ASIGNATURA_norm", "ÁREA DE FORMACIÓN"]]
        .drop_duplicates()
        .set_index(["NIVEL O SEMESTRE", "ASIGNATURA_norm"])["ÁREA DE FORMACIÓN"]
        .to_dict()
    )
    exact_by_name = (
        df_mc.groupby("ASIGNATURA_norm")["ÁREA DE FORMACIÓN"]
        .agg(lambda s: s.mode().iloc[0])
        .to_dict()
    )
    all_candidate_names = list(exact_by_name.keys())

    sem_to_candidates: dict[int, list[tuple[str, str]]] = {}
    for sem, asig_norm, area in df_mc[
        ["NIVEL O SEMESTRE", "ASIGNATURA_norm", "ÁREA DE FORMACIÓN"]
    ].drop_duplicates().itertuples(index=False, name=None):
        sem_to_candidates.setdefault(int(sem), []).append((str(asig_norm), str(area)))

    mask_missing = (
        df_merge["ÁREA DE FORMACIÓN"].isna()
        | (df_merge["ÁREA DE FORMACIÓN"].astype(str).str.strip() == "")
    )
    if not mask_missing.any():
        return df_merge

    for idx in df_merge.index[mask_missing]:
        sem = int(pd.to_numeric(df_merge.at[idx, "NIVEL O SEMESTRE"], errors="coerce") or 0)
        asig_norm = str(df_merge.at[idx, "ASIGNATURA_norm"] or "")
        if asig_norm == "":
            continue

        area = exact_by_sem.get((sem, asig_norm), "")
        if not area:
            area = exact_by_name.get(asig_norm, "")

        if not area:
            candidates = sem_to_candidates.get(sem, [])
            if candidates:
                candidate_names = [n for n, _ in candidates]
                best_name, score = best_fuzzy_match(
                    asig_norm,
                    candidate_names,
                    threshold=fuzzy_threshold,
                )
                if best_name is not None:
                    area = next((a for n, a in candidates if n == best_name), "")
                    logger.debug(
                        "Área formación fuzzy (score=%.2f): '%s' -> '%s' (sem=%d)",
                        score,
                        asig_norm,
                        best_name,
                        sem,
                    )

        if not area and all_candidate_names:
            best_name_global, score_global = best_fuzzy_match(
                asig_norm,
                all_candidate_names,
                threshold=AREA_GLOBAL_FUZZY_THRESHOLD,
            )
            if best_name_global is not None:
                area = exact_by_name.get(best_name_global, "")
                logger.debug(
                    "Área formación fuzzy global (score=%.2f): '%s' -> '%s'",
                    score_global,
                    asig_norm,
                    best_name_global,
                )

        if not area:
            area = MANUAL_AREA_FALLBACKS.get(asig_norm, "")

        if area:
            df_merge.at[idx, "ÁREA DE FORMACIÓN"] = area

    return df_merge


def merge_horas(
    df_consolidado: pd.DataFrame,
    df_horas: pd.DataFrame,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    matching_path: Path | None = None,
    include_pdf_only: bool = False,
    matrix_courses: pd.DataFrame | None = None,
    hours_alias_catalog: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Une el consolidado de tributación con las horas del PDF.

    Realiza un left join para preservar todos los registros de tributación.
    Si el join exacto deja filas sin "N° DE CRÉDITOS", se intenta un join
    difuso por nombre de asignatura dentro del mismo semestre.

    Estrategia de join:
    - Clave exacta: ``(NIVEL O SEMESTRE, ASIGNATURA_norm)``.
    - Clave difusa: ``best_fuzzy_match`` sobre ``asignatura_norm`` dentro del
      mismo semestre, con umbral ``fuzzy_threshold``.

    Después del join:
    1. Mapeado de columnas PDF → columnas Excel (:data:`~tributacion.config.MAPEO_CSV_A_EXCEL`).
    2. Conversión a numérico (:data:`~tributacion.config.NUMERIC_COLUMNS`).
    3. Limpieza de columnas temporales.

    Args:
        df_consolidado:  Salida de :func:`~tributacion.matrix_parser.parse_matrix`.
        df_horas:        Salida de :func:`~tributacion.pdf_parser.parse_pdf`.
        fuzzy_threshold: Umbral de similitud para el join difuso (0–1).
        include_pdf_only:
            Si es ``True``, agrega filas para asignaturas presentes en el PDF
            que no existan en la matriz (por ``(semestre, asignatura_norm)``)
            con ``ESTADO_MATCH_HORAS = SIN_TRIBUTACION``.
        matrix_courses:
            Catálogo de asignaturas de matriz (salida de
            ``extract_matrix_courses``) para distinguir correctamente
            asignaturas sin tributación y evitar falsos "solo PDF".
        hours_alias_catalog:
            Catálogo opcional de alias de asignaturas para parear nombres de
            matriz contra nombres equivalentes del PDF antes del fuzzy.

    Returns:
        DataFrame con las 36 columnas de :data:`~tributacion.config.OUTPUT_COLUMNS`.

    Examples:
        >>> df_final = merge_horas(df_consolidado, df_horas)
        >>> list(df_final.columns) == OUTPUT_COLUMNS
        True
    """
    # --- Preparar df_horas ---------------------------------------------------
    df_h = df_horas.copy()
    if "asignatura_norm" not in df_h.columns:
        df_h["asignatura_norm"] = df_h["asignatura"].apply(norm_text)
    df_h["semestre"] = pd.to_numeric(df_h["semestre"], errors="coerce").astype("Int64")

    # --- Preparar df_consolidado ---------------------------------------------
    df_c = df_consolidado.copy()
    if "ASIGNATURA_norm" not in df_c.columns:
        df_c["ASIGNATURA_norm"] = df_c["ASIGNATURA"].apply(norm_text)
    df_c["_semestre_int"] = pd.to_numeric(
        df_c["NIVEL O SEMESTRE"], errors="coerce"
    ).astype("Int64")
    df_c = _filter_option_incompatible_rows(df_c)

    # --- Join exacto ---------------------------------------------------------
    df_merge = df_c.merge(
        df_h,
        how="left",
        left_on=["_semestre_int", "ASIGNATURA_norm"],
        right_on=["semestre", "asignatura_norm"],
        suffixes=("", "_pdf"),
        indicator="_merge_match",
    )
    df_merge["_match_state"] = "SIN_MATCH"
    df_merge.loc[df_merge["_merge_match"] == "both", "_match_state"] = "MATCH_EXACTO"

    # --- Mapear columnas PDF → columnas Excel --------------------------------
    for src_col, dst_col in MAPEO_CSV_A_EXCEL.items():
        # Después del merge con suffixes=("", "_pdf"), las columnas de horas
        # que existen en ambos DataFrames quedan duplicadas: la del consolidado
        # mantiene su nombre (vacía) y la del PDF recibe el sufijo "_pdf"
        # (con los valores reales).  Priorizamos la versión "_pdf".
        pdf_col = f"{src_col}_pdf"
        actual_src = pdf_col if pdf_col in df_merge.columns else src_col
        if actual_src in df_merge.columns:
            mask = df_merge[dst_col].isna() | (df_merge[dst_col].astype(str).str.strip() == "")
            df_merge.loc[mask, dst_col] = df_merge.loc[mask, actual_src]

    df_merge = _alias_fill(df_merge, df_h, alias_catalog=hours_alias_catalog)

    # --- Join difuso para filas sin horas ------------------------------------
    unmatched = df_merge["N° DE CRÉDITOS"].isna() | (
        df_merge["N° DE CRÉDITOS"].astype(str).str.strip().isin(["", "nan"])
    )
    n_unmatched = unmatched.sum()
    if n_unmatched > 0 and len(df_h) > 0:
        logger.info("  → %d filas sin match exacto; intentando join difuso...", n_unmatched)
        df_merge = _fuzzy_fill(df_merge, df_h, fuzzy_threshold)
        filled = df_merge.get("_fuzzy_score", pd.Series(dtype=float))
        n_fuzzy = (filled > 0).sum()
        logger.info("  → %d filas rellenadas por join difuso", n_fuzzy)
        mask_fuzzy = (
            df_merge["_match_state"].eq("SIN_MATCH")
            & df_merge.get("_fuzzy_match_type", "").astype(str).ne("")
        )
        df_merge.loc[mask_fuzzy, "_match_state"] = df_merge.loc[mask_fuzzy, "_fuzzy_match_type"]

    if include_pdf_only:
        if matrix_courses is not None and not matrix_courses.empty:
            df_mc = matrix_courses.copy()
            df_mc["NIVEL O SEMESTRE"] = pd.to_numeric(
                df_mc["NIVEL O SEMESTRE"], errors="coerce"
            ).fillna(0).astype(int)
            df_mc["ASIGNATURA_norm"] = df_mc["ASIGNATURA_norm"].astype(str)
            matrix_all_keys = set(
                zip(df_mc["NIVEL O SEMESTRE"], df_mc["ASIGNATURA_norm"])
            )

            if matrix_all_keys:
                horas_unique = df_h.drop_duplicates(subset=["semestre", "asignatura_norm"]).copy()
                horas_unique["semestre"] = pd.to_numeric(
                    horas_unique["semestre"], errors="coerce"
                ).fillna(0).astype(int)
                horas_unique["asignatura_norm"] = horas_unique["asignatura_norm"].astype(str)
                mask_pdf_only = ~horas_unique.apply(
                    lambda r: (int(r["semestre"]), str(r["asignatura_norm"])) in matrix_all_keys,
                    axis=1,
                )
                pdf_only_df_h = horas_unique.loc[mask_pdf_only].copy()
            else:
                pdf_only_df_h = df_h
        else:
            pdf_only_df_h = df_h

        df_merge = _append_pdf_only_rows(df_merge, pdf_only_df_h)

        if matrix_courses is not None and not matrix_courses.empty:
            df_merge = _append_matrix_no_tributacion_rows(df_merge, df_h, matrix_courses)

        # _match_state se mantiene interno para decidir agregados SIN_TRIBUTACION,
        # pero no forma parte del esquema final exportado.

    if matrix_courses is not None and not matrix_courses.empty:
        df_merge = _fill_missing_area_formacion(df_merge, matrix_courses)

    df_merge = _harmonize_subject_names_by_course_code(df_merge)

    # --- Aplicar overrides de semestre del PDF (cross-semestre) --------------
    if "_pdf_semestre" in df_merge.columns:
        mask_override = df_merge["_pdf_semestre"].notna()
        if mask_override.any():
            df_merge.loc[mask_override, "NIVEL O SEMESTRE"] = (
                df_merge.loc[mask_override, "_pdf_semestre"].astype(int)
            )
            if "AÑO" in df_merge.columns:
                df_merge.loc[mask_override, "AÑO"] = (
                    (pd.to_numeric(
                        df_merge.loc[mask_override, "NIVEL O SEMESTRE"],
                        errors="coerce",
                    ).fillna(0).astype(int) + 1) // 2
                )
            if "CICLO" in df_merge.columns:
                ciclo_map = _build_semester_ciclo_map(df_merge.loc[~mask_override])
                default_ciclo = _resolve_default_value(df_merge, "CICLO")
                sems = pd.to_numeric(
                    df_merge.loc[mask_override, "NIVEL O SEMESTRE"],
                    errors="coerce",
                ).fillna(0).astype(int)
                df_merge.loc[mask_override, "CICLO"] = sems.apply(
                    lambda sem: _resolve_ciclo_for_semester(int(sem), ciclo_map, default_ciclo)
                )
            n_overrides = mask_override.sum()
            logger.info(
                "  → %d asignatura(s) con semestre corregido al valor del PDF.",
                n_overrides,
            )

    # --- Generar Excel de pareamiento para depuración -------------------------
    if matching_path is not None:
        # Construir un registro por asignatura única del consolidado
        asig_unique = df_merge.drop_duplicates(subset=["ASIGNATURA"])[
            ["ASIGNATURA", "ASIGNATURA_norm", "NIVEL O SEMESTRE"]
        ].copy()
        asig_unique = asig_unique.rename(columns={
            "ASIGNATURA": "ASIGNATURA_MATRIZ",
            "ASIGNATURA_norm": "ASIGNATURA_MATRIZ_NORM",
            "NIVEL O SEMESTRE": "SEMESTRE_MATRIZ",
        })

        # Para cada asignatura, buscar si hubo match exacto, fuzzy o cross-semestre
        match_records = []
        for _, row in asig_unique.iterrows():
            mat_name = row["ASIGNATURA_MATRIZ"]
            mat_norm = row["ASIGNATURA_MATRIZ_NORM"]
            sem = row["SEMESTRE_MATRIZ"]
            pdf_sem: int | None = None

            # Buscar match exacto en horas (mismo semestre)
            exact = df_h[
                (df_h["semestre"] == sem) & (df_h["asignatura_norm"] == mat_norm)
            ]
            if len(exact) > 0:
                pdf_name = exact.iloc[0]["asignatura"]
                match_type = "EXACTO"
                score = 1.0
            else:
                # Intentar fuzzy mismo semestre
                candidates_sem = df_h[df_h["semestre"] == sem]
                if len(candidates_sem) > 0:
                    cand_names = candidates_sem["asignatura_norm"].tolist()
                    best_name, score = best_fuzzy_match(mat_norm, cand_names, threshold=fuzzy_threshold)
                else:
                    best_name, score = None, 0.0

                if best_name is not None:
                    pdf_row = candidates_sem[candidates_sem["asignatura_norm"] == best_name].iloc[0]
                    pdf_name = pdf_row["asignatura"]
                    match_type = "FUZZY"
                else:
                    # Fallback cross-semestre
                    all_norms = df_h["asignatura_norm"].tolist()
                    best_cross, score_cross = best_fuzzy_match(
                        mat_norm, all_norms, threshold=CROSS_SEMESTER_THRESHOLD
                    )
                    if best_cross is not None:
                        cross_row = df_h[df_h["asignatura_norm"] == best_cross].iloc[0]
                        pdf_name = cross_row["asignatura"]
                        pdf_sem = int(cross_row["semestre"])
                        match_type = "CROSS_SEMESTRE"
                        score = score_cross
                    else:
                        # Fase 3: alerta nombre diferente
                        all_norms = df_h["asignatura_norm"].tolist()
                        best_alert, score_alert = best_fuzzy_match(
                            mat_norm, all_norms, threshold=ALERTA_NOMBRE_THRESHOLD
                        )
                        if best_alert is not None:
                            alert_row = df_h[
                                df_h["asignatura_norm"] == best_alert
                            ].iloc[0]
                            pdf_name = alert_row["asignatura"]
                            pdf_sem = int(alert_row["semestre"])
                            match_type = "ALERTA_NOMBRE"
                            score = score_alert
                        else:
                            pdf_name = ""
                            match_type = "SIN MATCH"
                            score = 0.0

            match_records.append({
                "SEMESTRE": sem,
                "SEMESTRE_PDF": pdf_sem if pdf_sem is not None else sem if match_type != "SIN MATCH" else "",
                "ASIGNATURA_MATRIZ": mat_name,
                "ASIGNATURA_PDF": pdf_name,
                "TIPO_MATCH": match_type,
                "SCORE": round(score, 3),
            })

        df_matching = pd.DataFrame(match_records)
        df_matching = df_matching.sort_values(["SEMESTRE", "ASIGNATURA_MATRIZ"])
        df_matching = df_matching[["SEMESTRE", "SEMESTRE_PDF", "ASIGNATURA_MATRIZ", "ASIGNATURA_PDF", "TIPO_MATCH", "SCORE"]]
        matching_path.parent.mkdir(parents=True, exist_ok=True)
        df_matching.to_csv(str(matching_path), index=False, encoding="utf-8-sig")
        logger.info("  → CSV de pareamiento guardado en: %s", matching_path)

    # --- Convertir columnas numéricas ----------------------------------------
    for col in NUMERIC_COLUMNS:
        if col in df_merge.columns:
            df_merge[col] = pd.to_numeric(df_merge[col], errors="coerce")

    # --- Limpiar columnas temporales -----------------------------------------
    cols_to_drop = [
        "_semestre_int",
        "_merge_match",
        "_match_state",
        "_fuzzy_score",
        "_fuzzy_match_type",
        "_pdf_semestre",
        "_fuzzy_pdf_norm",
        "_alias_pdf_norm",
        "ASIGNATURA_norm",
        "asignatura_norm",
        "semestre",
        "asignatura",
        "fuente",
        "codigo_prerrequisito",
        "codigo",
        "CARRERA_pdf",
    ]
    # También eliminar las columnas con sufijo _pdf generadas por el merge
    cols_to_drop += [c for c in df_merge.columns if c.endswith("_pdf")]
    cols_to_drop = [c for c in cols_to_drop if c in df_merge.columns]
    df_merge = df_merge.drop(columns=cols_to_drop)

    # --- Reordenar según esquema final ---------------------------------------
    final_cols = [c for c in OUTPUT_COLUMNS if c in df_merge.columns]
    df_final = df_merge[final_cols].copy()

    return df_final
