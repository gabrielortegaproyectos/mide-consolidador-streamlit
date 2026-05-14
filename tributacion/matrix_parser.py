"""matrix_parser.py — Construcción del consolidado de tributación desde la Matriz Excel.

Lee la Matriz de Tributación (formato UBO) y genera un ``pd.DataFrame``
con una fila por cada par ``(asignatura, RA)`` donde la celda
de la matriz vale ``"1"``. Una misma asignatura puede tributar a muchos RA,
generando múltiples filas.

Flujo interno
-------------
1. Leer el Excel sin cabeceras (``header=None``) para preservar las 4 filas
   de encabezado de la matriz.
2. Aplicar ``ffill()`` horizontal a las filas de área, AR y RA para reconstruir
   los valores que el Excel tenía como celdas combinadas.
3. Identificar las columnas de tributación válidas (pertenecen a una de las
   áreas en :data:`~tributacion.config.AREA_TITLES`) excluyendo
   ``"HABILIDADES TRANSVERSALES"``.
4. Construir ``CURSOS_OBJETIVO`` leyendo dinámicamente la columna D desde la
   fila 7 en adelante.
5. Para cada curso, iterar las columnas válidas y emitir un registro cuando la
   celda vale ``"1"``.

Función pública principal
-------------------------
:func:`parse_matrix`
"""

import math
from pathlib import Path

import pandas as pd

from tributacion.ciclo_catalog import infer_tipo_ciclo_from_max_semestre, resolve_tipo_ciclo
from tributacion.config import (
    AREA_TITLES,
    DEFAULT_SHEET_NAME,
    NON_DISCIPLINAR_NAR_BASES,
    OUTPUT_COLUMNS,
    TRIBUTACION_VALUE,
    compute_ciclo,
)
from tributacion.text_utils import (
    is_habilidades_transversales,
    is_modelo_educativo_ar,
    norm_text,
    parse_ar_disciplinar,
    parse_level,
    parse_ra,
    parse_ra_num,
    roman_to_int,
    tributacion_short_label,
)


# ---------------------------------------------------------------------------
# Lectura y preparación de la matriz
# ---------------------------------------------------------------------------

def _load_raw_matrix(xlsx_path: Path, sheet_name: str) -> pd.DataFrame:
    """Carga la hoja de la Matriz de Tributación sin procesar.

    Args:
        xlsx_path:  Ruta al archivo Excel.
        sheet_name: Nombre de la hoja de cálculo.

    Returns:
        DataFrame con todas las celdas sin interpretar.
    """
    return pd.read_excel(str(xlsx_path), sheet_name=sheet_name, header=None)


def _build_header_rows(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Extrae y forward-rellena las 4 filas de cabecera de la matriz.

    La matriz tiene la siguiente estructura de cabeceras:
    - Fila 0: Título del bloque de área (4 grandes áreas, celdas combinadas).
    - Fila 1: Ámbito de Realización (``AR_N: título: desc``).
    - Fila 2: Resultado de Aprendizaje (``AR_N – RA_M: nombre: desc``).
    - Fila 3: Nivel de logro (``NIVEL: descripción``).

    Las celdas combinadas de Excel se leen como ``NaN`` en las columnas
    después de la primera; ``ffill()`` las restaura.

    Returns:
        Cuatro Series con los valores rellenados: ``(r_area, r_ar, r_ra, r_lvl)``.
    """
    r_area = df.iloc[0].ffill()
    r_ar   = df.iloc[1].ffill()
    r_ra   = df.iloc[2].ffill()
    r_lvl  = df.iloc[3].copy()
    return r_area, r_ar, r_ra, r_lvl


def _find_valid_columns(
    r_area: pd.Series,
    r_ra: pd.Series,
    df: pd.DataFrame,
) -> list[int]:
    """Identifica los índices de columna correspondientes a tributación activa.

    Una columna es válida si:
    1. Su área (``r_area``) es una de las 4 áreas en :data:`AREA_TITLES`.
    2. Su RA (``r_ra``) no es ``"HABILIDADES TRANSVERSALES"``.

    Args:
        r_area: Fila 0 forward-rellenada.
        r_ra:   Fila 2 forward-rellenada.
        df:     DataFrame completo (para conocer el rango de columnas).

    Returns:
        Lista de índices de columna válidos.
    """
    valid_cols: list[int] = []
    for col_idx in range(df.shape[1]):
        area_val = str(r_area.iloc[col_idx]).strip().upper()
        if area_val not in [a.upper() for a in AREA_TITLES]:
            continue
        # Ya no excluimos HABILIDADES TRANSVERSALES; se procesan como AR sin número.
        valid_cols.append(col_idx)
    return valid_cols


def _find_course_rows(df: pd.DataFrame) -> dict[str, int]:
    """Construye un mapa ``{nombre_asignatura → índice_fila}`` para todas las asignaturas.

    La columna C (índice 2) desde la fila 6 (índice 5) contiene los nombres
    de asignatura. Las 5 primeras filas (0-4) son cabeceras.
    Se ignoran las celdas vacías y se hace único usando el primer occurrence.

    Args:
        df: DataFrame de la matriz (sin cabeceras).

    Returns:
        Diccionario ordenado por orden de aparición en la hoja.
    """
    course_rows: dict[str, int] = {}
    for row_idx in range(5, df.shape[0]):   # row 5 = primera fila de datos
        val = df.iloc[row_idx, 2]           # col 2 (C) = nombre de asignatura
        if pd.isna(val) or str(val).strip() == "":
            continue
        name = str(val).strip()
        if name not in course_rows:
            course_rows[name] = row_idx
    return course_rows


# ---------------------------------------------------------------------------
# Construcción de registros
# ---------------------------------------------------------------------------

def _build_record(
    course_name: str,
    row_idx: int,
    col_idx: int,
    df: pd.DataFrame,
    r_area: pd.Series,
    r_ar: pd.Series,
    r_ra: pd.Series,
    r_lvl: pd.Series,
    meta: dict,
    max_semestre: int = 8,
    tipo_ciclo: str | None = None,
) -> dict:
    """Genera un dict con todos los campos de un registro de tributación.

    Args:
        course_name:     Nombre de la asignatura.
        row_idx:         Índice de fila de la asignatura en la matriz.
        col_idx:         Índice de la columna de tributación activa.
        df:              DataFrame completo de la matriz.
        r_area:          Fila 0 forward-rellenada.
        r_ar:            Fila 1 forward-rellenada.
        r_ra:            Fila 2 forward-rellenada.
        r_lvl:           Fila 3 (nivel de logro, sin ffill).
        meta:            Dict con GRADO, FACULTAD, ESCUELA, CARRERA.
        tipo_ciclo:      Tipo de ciclo ya resuelto para la carrera.

    Returns:
        Diccionario con las 36 columnas del Excel de salida.
    """
    area_title = str(r_area.iloc[col_idx]).strip()
    ar_text    = str(r_ar.iloc[col_idx]).strip()
    ra_text    = str(r_ra.iloc[col_idx]).strip()
    lvl_text   = str(r_lvl.iloc[col_idx]).strip()

    # ---- Detectar si la columna cae bajo HABILIDADES TRANSVERSALES
    #      o bajo un sub-área de MODELO EDUCATIVO (EJES / PERSPECTIVAS) ----
    is_hab_transv = is_habilidades_transversales(ra_text)
    is_modelo_edu = is_modelo_educativo_ar(ra_text)

    # ---- Tributación — etiqueta abreviada ----
    tributacion = tributacion_short_label(area_title)

    # ---- Ámbito de Realización y N°AR ----
    if is_hab_transv:
        # HABILIDADES TRANSVERSALES es un AR sin número.
        ambito  = "HABILIDADES TRANSVERSALES"
        n_ar    = 0
        desc_ar = ""
    elif is_modelo_edu:
        # EJES DEL MODELO / PERSPECTIVAS DEL DESARROLLO SOSTENIBLE
        # actúan como AR sin número y sin descripción.
        ambito  = ra_text
        n_ar    = ""
        desc_ar = ""
    elif "DISCIPLINAR" in area_title.upper():
        ambito, n_ar, desc_ar = parse_ar_disciplinar(ar_text)
    elif "BÁSICA" in area_title.upper():
        # Formación Básica no tiene AR.
        ambito  = "No tiene"
        n_ar    = ""
        desc_ar = "No tiene"
    else:
        ambito  = ""
        n_ar    = 0
        desc_ar = ""

    # ---- Resultado de Aprendizaje ----
    if is_hab_transv or is_modelo_edu:
        # La fila 4 (nivel) contiene el nombre del RA (sin número ni descripción).
        nombre_ra = lvl_text
        desc_ra   = ""
    else:
        nombre_ra, desc_ra = parse_ra(area_title, ra_text)

    # ---- N° RA: extraer de cualquier área (el patrón RA\d+ aparece en todas) ----
    if is_hab_transv or is_modelo_edu:
        n_ra = ""
    else:
        n_ra = parse_ra_num(ra_text)

    # ---- Nivel de logro ----
    if is_hab_transv or is_modelo_edu:
        nivel_logro = ""
        desc_nivel  = ""
    else:
        nivel_logro, desc_nivel = parse_level(lvl_text)

    # ---- Datos de la fila de asignatura (col A = \u00edndice 0, col B = \u00edndice 1) ----
    area_formacion = str(df.iloc[row_idx, 0]).strip() if df.shape[1] > 0 else ""
    semestre_str   = str(df.iloc[row_idx, 1]).strip() if df.shape[1] > 1 else ""

    try:
        semestre_num = roman_to_int(semestre_str)
    except ValueError:
        semestre_num = 0

    anio = math.ceil(semestre_num / 2) if semestre_num > 0 else 0

    return {
        # ---- Identificación de carrera ----
        "GRADO":                             meta.get("GRADO", "PREGRADO"),
        "FACULTAD":                          meta.get("FACULTAD", ""),
        "ESCUELA":                           meta.get("ESCUELA", ""),
        "CARRERA":                           meta.get("CARRERA", ""),
        # ---- Tributación ----
        "TRIBUTACIÓN":                       tributacion,
        "CICLO":                             compute_ciclo(
            semestre_num,
            max_semestre,
            tipo_ciclo=tipo_ciclo,
            carrera=meta.get("CARRERA", ""),
        ),
        "N°AR":                              n_ar,
        "ÁMBITO DE REALIZACIÓN":             ambito,
        "DESCRIPCIÓN AR":                    desc_ar,
        "N° RA":                             n_ra,
        "NOMBRE RA":                         nombre_ra,
        "DESCRIPCIÓN RA":                    desc_ra,
        "NIVEL DE LOGRO":                    nivel_logro,
        "DESCRIPCIÓN DEL NIVEL DE LOGRO":    desc_nivel,
        # ---- Asignatura ----
        "ÁREA DE FORMACIÓN":                 area_formacion,
        "AÑO":                               anio,
        "NIVEL O SEMESTRE":                  semestre_num,
        "CÓDIGO DEL CURSO":                  "",
        "ASIGNATURA":                        course_name,
        "CÓDIGO PRERREQUISITO":              "",
        "PRERREQUISITO":                     "",   # se completa en merger.py
        # ---- Horas (se completan en merger.py) ----
        "N° DE CRÉDITOS":                    "",
        "HORAS CR TOTALES":                  "",
        "HORAS DE DOCENCIA DIRECTA":         "",
        "DD TEÓRICAS":                       "",
        "DD AYUDANTÍA":                      "",
        "DD TALLER":                         "",
        "DD CAMPOS CLÍNICOS":                "",
        "DD SIMULACIÓN":                     "",
        "DD LABORATORIO":                    "",
        "DD PRO COLABORATIVO":               "",
        "DD SALIDAS A TERRENO":              "",
        "HORAS DE TRABAJO AUTÓNOMO":         "",
        # ---- Adicionales ----
        "MODALIDAD":                         "Presencial",
        "INDICADORES DE LOGRO POR ASIGNATURA":          "",
        "PRODUCTOS DE APRENDIZAJE POR ASIGNATURA":      "",
    }


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------

def _build_non_disc_ar_map(
    valid_cols: list[int],
    r_area: pd.Series,
    r_ar: pd.Series,
) -> dict[str, dict[str, int]]:
    """Pre-calcula el mapa N°AR para columnas de áreas no-DISCIPLINAR.

    Para cada área no-DISCIPLINAR, asigna un número secuencial comenzando desde
    la base definida en :data:`~tributacion.config.NON_DISCIPLINAR_NAR_BASES`.
    Columnas con el mismo texto de AR (celdas fusionadas) reciben el mismo número.

    Args:
        valid_cols: Índices de columna seleccionados como tributación activa.
        r_area:     Fila 0 forward-rellenada.
        r_ar:       Fila 1 forward-rellenada.

    Returns:
        ``{area_title: {ar_text: n_ar}}``
    """
    result: dict[str, dict[str, int]] = {}
    counters: dict[str, int] = {}
    for col_idx in valid_cols:
        area_title = str(r_area.iloc[col_idx]).strip()
        if "DISCIPLINAR" in area_title.upper():
            continue
        ar_text = str(r_ar.iloc[col_idx]).strip()
        if area_title not in result:
            result[area_title] = {}
            counters[area_title] = 0
        if ar_text not in result[area_title]:
            base = NON_DISCIPLINAR_NAR_BASES.get(area_title, 100)
            result[area_title][ar_text] = base + counters[area_title]
            counters[area_title] += 1
    return result


def parse_matrix(
    xlsx_path: Path,
    sheet_name: str = DEFAULT_SHEET_NAME,
    meta: dict | None = None,
) -> pd.DataFrame:
    """Lee la Matriz de Tributación y devuelve el consolidado inicial.

    Genera una fila por cada par ``(asignatura, RA tributado)`` donde
    la celda de la matriz vale ``"1"``. Una misma asignatura tributa
    normalmente a decenas de RA, por lo que el DataFrame resultante
    tiene muchas más filas que la cantidad de asignaturas de la carrera.
    Las columnas de horas quedan vacías para ser completadas por
    :func:`~tributacion.merger.merge_horas`.

    Args:
        xlsx_path:  Ruta al archivo Excel de la Matriz de Tributación.
        sheet_name: Nombre de la hoja (por defecto ``"Asignaturas - RA"``).
        meta:       Diccionario con ``GRADO``, ``FACULTAD``, ``ESCUELA`` y
                    ``CARRERA``. Si es ``None`` se usan cadenas vacías.

    Returns:
        DataFrame con las 36 columnas de :data:`~tributacion.config.OUTPUT_COLUMNS`
        y ``ASIGNATURA_norm`` adicional para el join.

    Raises:
        FileNotFoundError: Si ``xlsx_path`` no existe.
        ValueError:        Si la hoja ``sheet_name`` no existe en el archivo.

    Examples:
        >>> df = parse_matrix(Path("Matriz de Tributación Informática.xlsx"))
        >>> "ASIGNATURA" in df.columns
        True
        >>> len(df) > 0
        True
    """
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Excel no encontrado: {xlsx_path}")

    meta = meta or {}

    df = _load_raw_matrix(xlsx_path, sheet_name)
    r_area, r_ar, r_ra, r_lvl = _build_header_rows(df)
    valid_cols = _find_valid_columns(r_area, r_ra, df)
    course_rows = _find_course_rows(df)

    # Calcular el máximo semestre de la carrera para fallback histórico de CICLO.
    max_semestre = 0
    for row_idx in course_rows.values():
        sem_str = str(df.iloc[row_idx, 1]).strip() if df.shape[1] > 1 else ""
        try:
            sem = roman_to_int(sem_str)
            if sem > max_semestre:
                max_semestre = sem
        except ValueError:
            pass

    tipo_ciclo = resolve_tipo_ciclo(meta, carrera=meta.get("CARRERA", ""), matrix_path=xlsx_path)
    if tipo_ciclo is None:
        tipo_ciclo = infer_tipo_ciclo_from_max_semestre(max_semestre)

    records: list[dict] = []
    for course_name, row_idx in course_rows.items():
        for col_idx in valid_cols:
            cell_val = str(df.iloc[row_idx, col_idx]).strip()
            if cell_val == TRIBUTACION_VALUE:
                record = _build_record(
                    course_name, row_idx, col_idx,
                    df, r_area, r_ar, r_ra, r_lvl,
                    meta, max_semestre, tipo_ciclo,
                )
                records.append(record)

    if not records:
        df_out = pd.DataFrame(columns=OUTPUT_COLUMNS + ["ASIGNATURA_norm"])
        return df_out

    df_out = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    df_out["ASIGNATURA_norm"] = df_out["ASIGNATURA"].apply(norm_text)
    return df_out


def extract_matrix_courses(
    xlsx_path: Path,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> pd.DataFrame:
    """Extrae el catálogo de asignaturas de la matriz con estado de tributación.

    Devuelve una fila por asignatura (única por ``(semestre, asignatura_norm)``)
    indicando si la matriz tiene al menos una celda activa ``"1"`` para esa
    asignatura en columnas válidas de tributación.

    Args:
        xlsx_path:  Ruta al archivo Excel de la Matriz de Tributación.
        sheet_name: Nombre de la hoja (por defecto ``"Asignaturas - RA"``).

    Returns:
        DataFrame con columnas:
        ``NIVEL O SEMESTRE``, ``ASIGNATURA``, ``ASIGNATURA_norm``,
        ``TRIBUTA_EN_MATRIZ`` y ``N_TRIBUTACIONES``.
    """
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Excel no encontrado: {xlsx_path}")

    df = _load_raw_matrix(xlsx_path, sheet_name)
    r_area, r_ar, r_ra, r_lvl = _build_header_rows(df)
    valid_cols = _find_valid_columns(r_area, r_ra, df)
    course_rows = _find_course_rows(df)

    rows: list[dict] = []
    for course_name, row_idx in course_rows.items():
        sem_str = str(df.iloc[row_idx, 1]).strip() if df.shape[1] > 1 else ""
        area_formacion = str(df.iloc[row_idx, 0]).strip() if df.shape[1] > 0 else ""
        try:
            semestre_num = roman_to_int(sem_str)
        except ValueError:
            semestre_num = 0

        n_tributaciones = 0
        for col_idx in valid_cols:
            cell_val = str(df.iloc[row_idx, col_idx]).strip()
            if cell_val == TRIBUTACION_VALUE:
                n_tributaciones += 1

        rows.append(
            {
                "NIVEL O SEMESTRE": semestre_num,
                "AÑO": math.ceil(semestre_num / 2) if semestre_num > 0 else 0,
                "ASIGNATURA": course_name,
                "ÁREA DE FORMACIÓN": area_formacion,
                "ASIGNATURA_norm": norm_text(course_name),
                "TRIBUTA_EN_MATRIZ": n_tributaciones > 0,
                "N_TRIBUTACIONES": n_tributaciones,
            }
        )

    return pd.DataFrame(rows)
