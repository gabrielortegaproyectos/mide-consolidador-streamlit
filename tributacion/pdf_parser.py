"""pdf_parser.py — Extracción de horas desde un PDF de plan de estudio.

Convierte las páginas de "Distribución y cálculo de tipos de hora por semestre"
de un PDF en un ``pd.DataFrame`` sin escribir archivos intermedios en disco.

Flujo interno
-------------
1. Abrir el PDF con PyMuPDF.
2. Filtrar páginas que contienen :data:`~tributacion.config.TARGET_TEXT`.
3. En cada página: localizar la tabla principal, detectar semestre y construir
   el mapa de columnas anclado a la posición de ``"SCT"``.
4. Extraer filas de datos, fusionando nombres de asignatura partidos en dos
   filas físicas.
5. Retornar todas las filas como un ``pd.DataFrame`` con las columnas definidas
   en :data:`~tributacion.config.CSV_COLUMNS`.

Función pública principal
-------------------------
:func:`parse_pdf`
"""

import re
from pathlib import Path

import pandas as pd
import pymupdf

from tributacion.config import CSV_COLUMNS, SCT_OFFSETS, TARGET_TEXT
from tributacion.text_utils import detect_option_from_rows, detect_semester_from_rows, norm_text

# Palabras que indican que una fila NO es continuación de asignatura
_CONTINUATION_SKIP: frozenset[str] = frozenset([
    "semestre", "total", "n°", "sct", "horas", "código", "codigo",
    "asignatura", "plan de", "prerequisito",
])


# ---------------------------------------------------------------------------
# Utilidades de celda
# ---------------------------------------------------------------------------

def _cell(row: list, idx: int | None) -> str:
    """Devuelve el contenido de ``row[idx]`` como cadena limpia.

    Retorna cadena vacía si el índice es ``None``, negativo o fuera de rango.
    Los saltos de línea se reemplazan por espacios.
    """
    if idx is None or idx < 0 or idx >= len(row):
        return ""
    return str(row[idx] or "").replace("\n", " ").strip()


def _cell_in_span(row: list, start: int | None, span: int = 3) -> str:
    """Devuelve el primer valor no vacío dentro del rango [start, start+span).

    Útil cuando pdfplumber puede colocar el contenido de una celda fusionada
    en cualquier sub-columna del span en lugar de siempre en ``start``.
    Retorna cadena vacía si ninguna sub-columna tiene valor.
    """
    if start is None or start < 0:
        return ""
    for offset in range(span):
        val = _cell(row, start + offset)
        if val:
            return val
    return ""


# ---------------------------------------------------------------------------
# Localización de cabecera y construcción del mapa de columnas
# ---------------------------------------------------------------------------

def find_header_row(rows: list[list]) -> tuple[int, list]:
    """Localiza la fila de encabezado de la tabla de distribución de horas.

    Busca la fila que contenga simultáneamente ``'SCT'`` y ``'N°'``,
    que identifican inequívocamente el encabezado.

    Args:
        rows: Filas extraídas con ``Table.extract()`` de PyMuPDF.

    Returns:
        Tupla ``(índice, fila_encabezado)``; ``(-1, [])`` si no se encuentra.
    """
    for i, row in enumerate(rows):
        texts = [str(c or "").strip() for c in row]
        if "SCT" in texts and "N°" in texts:
            return i, row
    return -1, []


def build_col_map(header_row: list) -> dict[str, int]:
    """Construye el mapa ``campo → índice_columna`` anclado a la posición de ``'SCT'``.

    El número de columnas en los PDFs varía (41-44) porque la columna
    "Asignatura" abarca distintas sub-columnas. Al anclar en ``'SCT'`` el
    mapa es robusto ante esa variación.

    Detección especial:
    - ``total_plan_estudio``: busca la subcadena ``'plan de estu'`` entre las
      cabeceras y usa el índice tres posiciones antes.
    - ``asignatura``: busca el primer encabezado que contiene ``'asignatura'``
      pero no ``'prerrequisito'``; cae en ``col_n + 2`` si no se encuentra.
    - ``codigo``: busca el primer encabezado que contiene ``'código'`` o
      ``'codigo'`` pero no ``'prerrequisito'``; cae en ``col_n + 1`` si no se
      encuentra.
    - ``numero``, ``codigo_prerrequisito``, ``asignatura_prerrequisito``:
      calculados a partir de la posición de ``'N°'``.

    Args:
        header_row: Fila de encabezado de la tabla.

    Returns:
        Diccionario ``{campo: índice}``; dict vacío si no se encuentra ``'SCT'``.
    """
    texts = [str(c or "").strip() for c in header_row]

    try:
        col_sct = texts.index("SCT")
    except ValueError:
        return {}

    col_map: dict[str, int] = {}

    # Campos con offset fijo respecto a SCT
    for field, offset in SCT_OFFSETS.items():
        col_map[field] = col_sct + offset

    # horas_docencia_directa: dinámico por cabecera real.
    # Algunos PDFs insertan sub-columnas vacías entre SCT y la etiqueta de
    # "Docencia Directa", por lo que el valor ya no cae en sct + 1.
    for j, t in enumerate(texts):
        tl = t.lower()
        if "docencia" in tl and "directa" in tl:
            col_map["horas_docencia_directa"] = j
            break

    # Campos posicionales respecto a N°
    try:
        col_n = texts.index("N°")
    except ValueError:
        col_n = 3
    col_map["numero"] = col_n

    # "Código" y "Asignatura" se detectan dinámicamente buscando su texto en la
    # cabecera, porque PyMuPDF puede introducir sub-columnas adicionales que
    # desplazan los índices respecto a N°.  Se excluyen las columnas de
    # prerrequisito para no confundirlas con las columnas principales.
    col_asig = col_n + 2   # fallback si no se encuentra en la cabecera
    col_cod = col_n + 1    # fallback si no se encuentra en la cabecera
    for j, t in enumerate(texts):
        tl = t.lower()
        if "prerrequisito" in tl:
            continue
        if ("código" in tl or "codigo" in tl) and col_cod == col_n + 1:
            col_cod = j
        if "asignatura" in tl and col_asig == col_n + 2:
            col_asig = j
    col_map["codigo"] = col_cod
    col_map["asignatura"] = col_asig

    # Prerrequisitos: detectar dinámicamente a partir de la cabecera.
    # "Código Prerrequisito" siempre está en col 0.
    # "Asignatura Prerrequisito" puede estar en col 1 o col 2 según el PDF;
    # se busca la cabecera que contenga "prerrequisito" excluyendo col 0.
    col_map["codigo_prerrequisito"] = 0
    col_asig_prereq = 1          # fallback conservador
    for j, t in enumerate(texts):
        if j == 0:
            continue              # ya asignado a codigo_prerrequisito
        if "prerrequisito" in t.lower():
            col_asig_prereq = j
            break
    # Si la columna detectada coincide con N°, el encabezado de
    # "Asignatura Prerrequisito" no existe como columna separada y no hay
    # prerrequisitos en esta página; se usa col 1 como fallback seguro.
    if col_asig_prereq == col_n:
        col_asig_prereq = 1
    col_map["asignatura_prerrequisito"] = col_asig_prereq

    # total_trabajo_autonomo: dinámico por cabecera real.
    # En algunos PDFs el valor queda una columna antes del bloque "Total Horas
    # Cronológicas Trabajo Autónomo", por lo que se ancla al texto extraído y
    # no solo al offset respecto de SCT.
    idx_total_horas = None
    idx_trabajo_autonomo = None
    for j, t in enumerate(texts):
        tl = t.lower()
        if idx_total_horas is None and "total horas" in tl:
            idx_total_horas = j
        if idx_trabajo_autonomo is None and "trabajo" in tl and (
            "autónomo" in tl or "autonomo" in tl
        ):
            idx_trabajo_autonomo = j
    if idx_trabajo_autonomo is not None:
        col_map["total_trabajo_autonomo"] = max(0, idx_trabajo_autonomo - 3)
    elif idx_total_horas is not None:
        col_map["total_trabajo_autonomo"] = max(0, idx_total_horas - 1)

    # total_plan_estudio: dinámico por subcadena.
    # En algunos PDFs PyMuPDF extrae el encabezado con las palabras invertidas
    # (ej. "Estudio Plan de" en vez de "Plan de Estudio"), por lo que también
    # se busca la combinación "plan" + "estudio" en la misma celda.
    for j, t in enumerate(texts):
        tl = t.lower()
        if "plan de estu" in tl or ("plan" in tl and "estudio" in tl):
            col_map["total_plan_estudio"] = j - 3
            break
    else:
        col_map["total_plan_estudio"] = len(header_row) - 2

    return col_map


# ---------------------------------------------------------------------------
# Extracción del nombre de carrera
# ---------------------------------------------------------------------------

def extract_carrera(pdf_stem: str) -> str:
    """Extrae el nombre de la carrera a partir del stem del archivo PDF.

    Busca la subcadena ``"Plan de Estudio(s)"`` en el nombre y captura
    todo lo que viene después, descartando las últimas dos palabras
    (mes y año, ej. ``"JULIO 2025"``).

    Args:
        pdf_stem: Nombre del PDF sin extensión.

    Returns:
        Nombre de la carrera en mayúsculas, o ``pdf_stem.upper()`` si no
        se reconoce el patrón.

    Examples:
        >>> extract_carrera("Plan de Estudios Informática Julio 2025")
        'INFORMÁTICA'
    """
    m = re.search(r"plan\s+de\s+estudios?\s+(.*)", pdf_stem, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        parts = name.rsplit(None, 2)
        if len(parts) == 3:
            name = parts[0]
        return name.strip().upper()
    return pdf_stem.upper()


# ---------------------------------------------------------------------------
# Extracción de filas de la tabla
# ---------------------------------------------------------------------------

def _extract_asignatura(row: list, base_col: int) -> str:
    """Extrae el nombre completo de asignatura de una fila.

    En algunos PDFs el nombre ocupa dos celdas contiguas (``base_col`` y
    ``base_col + 1``). Se concatenan salvo que la segunda sea numérica.
    """
    a = _cell(row, base_col)
    b = _cell(row, base_col + 1)
    if b and not b.isdigit():
        return (a + " " + b).strip()
    return a


def _extract_prereq_asignatura(row: list, base_col: int) -> str:
    """Extrae el nombre del prerrequisito de una fila.

    Funciona como :func:`_extract_asignatura`: el nombre puede ocupar
    dos celdas contiguas (``base_col`` y ``base_col + 1``) cuando el texto
    es largo y el motor de extracción lo reparte en sub-columnas.
    """
    a = _cell(row, base_col)
    b = _cell(row, base_col + 1)
    if b and not b.isdigit():
        return (a + " " + b).strip()
    return a


def _is_data_row(row: list, col_n: int) -> bool:
    """Retorna ``True`` si la fila corresponde a una asignatura numerada.

    Una fila de datos válida tiene en la columna ``N°`` un entero positivo.
    """
    try:
        val = _cell(row, col_n).strip()
        return val.isdigit() and int(val) > 0
    except (ValueError, IndexError):
        return False


def _is_continuation_row(
    row: list,
    col_n: int,
    col_asig: int,
    col_sct: int,
    col_prereq_asig: int | None = None,
) -> tuple[bool, str, str]:
    """Detecta si la fila es la continuación del nombre de la asignatura anterior.

    Una fila de continuación tiene ``N°`` y ``SCT`` vacíos, pero contiene
    texto en la columna de asignatura **o** en la columna de prerrequisito
    que no es una palabra reservada de encabezado.

    Returns:
        Tupla ``(True, asig_extra, prereq_extra)`` si es continuación;
        ``(False, '', '')`` en caso contrario.
    """
    if _cell(row, col_n).strip():
        return False, "", ""
    if _cell_in_span(row, col_sct, span=3).strip():
        return False, "", ""
    asig_extra = _extract_asignatura(row, col_asig).strip()
    prereq_extra = (
        _extract_prereq_asignatura(row, col_prereq_asig).strip()
        if col_prereq_asig is not None
        else ""
    )
    if not asig_extra and not prereq_extra:
        return False, "", ""
    # Only test asig_extra against skip keywords — prereq text may legitimately
    # contain words like "semestre" (e.g. "aprobadas...de primer a octavo semestre")
    # which would incorrectly block a valid asignatura continuation row.
    if any(kw in asig_extra.lower() for kw in _CONTINUATION_SKIP):
        return False, "", ""
    return True, asig_extra, prereq_extra


def extract_table_rows(
    table_rows: list[list],
    col_map: dict[str, int],
    fuente: str,
    carrera: str,
    semestre: int,
    option_label: str | None = None,
) -> list[dict]:
    """Extrae todas las filas de datos de una tabla PyMuPDF ya procesada.

    Las filas de datos (``N°`` positivo) generan un registro nuevo.
    Las filas de continuación de asignatura se fusionan con el registro anterior.

    Args:
        table_rows:   Lista de listas de ``Table.extract()``.
        col_map:      Mapa ``campo → índice`` de :func:`build_col_map`.
        fuente:       Nombre del PDF (sin extensión).
        carrera:      Nombre de la carrera.
        semestre:     Número de semestre (1–12).
        option_label: Etiqueta de la opción académica detectada en el encabezado
                      de la tabla (e.g. ``'Certificación Académica en Enfermería
                      Comunitaria'``), o ``None`` si la tabla no pertenece a
                      ninguna opción.

    Returns:
        Lista de dicts con los campos de :data:`~tributacion.config.CSV_COLUMNS`
        más la clave interna ``'_opcion'``.
    """
    col_n = col_map.get("numero", 3)
    col_asig = col_map.get("asignatura", 5)
    col_sct = col_map.get("sct", 0)
    col_prereq_asig = col_map.get("asignatura_prerrequisito")

    records: list[dict] = []
    for row in table_rows:
        if _is_data_row(row, col_n):
            record = {
                "fuente":                   fuente,
                "CARRERA":                  carrera.upper(),
                "semestre":                 semestre,
                "_opcion":                  option_label,
                "codigo_prerrequisito":     _cell(row, col_map.get("codigo_prerrequisito")),
                "asignatura_prerrequisito": _extract_prereq_asignatura(
                    row, col_map.get("asignatura_prerrequisito", 2),
                ),
                "codigo":                   _cell(row, col_map.get("codigo")),
                "asignatura":               _extract_asignatura(row, col_asig),
                "sct":                      _cell_in_span(row, col_map.get("sct"), span=3),
                "horas_docencia_directa":   _cell_in_span(row, col_map.get("horas_docencia_directa"), span=3),
                "DD TEÓRICAS":              _cell_in_span(row, col_map.get("DD TEÓRICAS"), span=3),
                "DD AYUDANTÍA":             _cell_in_span(row, col_map.get("DD AYUDANTÍA"), span=3),
                "DD TALLER":                _cell_in_span(row, col_map.get("DD TALLER"), span=3),
                "DD CAMPOS CLÍNICOS":       _cell_in_span(row, col_map.get("DD CAMPOS CLÍNICOS"), span=3),
                "DD SIMULACIÓN":            _cell_in_span(row, col_map.get("DD SIMULACIÓN"), span=3),
                "DD LABORATORIO":           _cell_in_span(row, col_map.get("DD LABORATORIO"), span=3),
                "DD PRO COLABORATIVO":      _cell_in_span(row, col_map.get("DD PRO COLABORATIVO"), span=3),
                "DD SALIDAS A TERRENO":     _cell_in_span(row, col_map.get("DD SALIDAS A TERRENO"), span=3),
                "total_trabajo_autonomo":   _cell_in_span(row, col_map.get("total_trabajo_autonomo"), span=4),
                "total_plan_estudio":       _cell_in_span(row, col_map.get("total_plan_estudio"), span=4),
            }
            records.append(record)
        elif records:
            is_cont, asig_extra, prereq_extra = _is_continuation_row(
                row, col_n, col_asig, col_sct, col_prereq_asig,
            )
            if is_cont:
                if asig_extra:
                    records[-1]["asignatura"] = (
                        records[-1]["asignatura"] + " " + asig_extra
                    ).strip()
                if prereq_extra:
                    records[-1]["asignatura_prerrequisito"] = (
                        records[-1]["asignatura_prerrequisito"] + " " + prereq_extra
                    ).strip()

    return records


# ---------------------------------------------------------------------------
# División por opción académica
# ---------------------------------------------------------------------------

def _split_by_option(
    df: pd.DataFrame,
) -> list[tuple[str | None, pd.DataFrame]]:
    """Divide el DataFrame por etiqueta de opción académica.

    Si el PDF contiene variantes de semestres (p. ej. dos versiones del
    Noveno Semestre bajo distintas Opciones), este función produce un
    sub-DataFrame por cada etiqueta de opción, combinando las filas base
    (sin etiqueta, i.e. semestres 1–8 en el caso Enfermería) con las filas
    propias de cada variante.

    Args:
        df: DataFrame devuelto por :func:`parse_pdf`, que incluye la columna
            interna ``'_opcion'``.

    Returns:
        Lista de tuplas ``(etiqueta, sub_DataFrame)`` donde el sub-DataFrame
        tiene la columna ``'_opcion'`` eliminada.  Si no se detectan múltiples
        opciones devuelve ``[(None, df_sin_opcion)]``.
    """
    if "_opcion" not in df.columns:
        return [(None, df)]

    option_values = (
        df.loc[df["_opcion"].notna(), "_opcion"]
        .dropna()
        .unique()
        .tolist()
    )

    if len(option_values) <= 1:
        # Sin variantes reales: descartar la columna temporal y retornar todo
        return [(None, df.drop(columns=["_opcion"]))]

    # Filas compartidas: semestres sin etiqueta de opción (ej. semestres 1–8)
    base_df = df[df["_opcion"].isna()].drop(columns=["_opcion"]).copy()

    result: list[tuple[str | None, pd.DataFrame]] = []
    for label in sorted(option_values):
        variant_df = df[df["_opcion"] == label].drop(columns=["_opcion"]).copy()
        combined = pd.concat([base_df, variant_df], ignore_index=True)
        # Recalcular asignatura_norm para las filas combinadas
        combined["asignatura_norm"] = combined["asignatura"].apply(norm_text)
        result.append((label, combined))

    return result


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------

def parse_pdf(pdf_path: Path) -> pd.DataFrame:
    """Lee un PDF de plan de estudio y devuelve un DataFrame con las horas de cada asignatura.

    Filtra las páginas que contienen el texto de distribución de horas, extrae
    la tabla principal de cada una y devuelve todos los registros como un
    ``pd.DataFrame``. No escribe ningún archivo en disco.

    Args:
        pdf_path: Ruta al PDF del plan de estudio.

    Returns:
        DataFrame con columnas :data:`~tributacion.config.CSV_COLUMNS` y una fila
        por asignatura por semestre. Puede estar vacío si el PDF no contiene
        páginas de distribución de horas o no se detecta tabla válida.

    Raises:
        FileNotFoundError: Si ``pdf_path`` no existe.
        RuntimeError: Si PyMuPDF no puede abrir el archivo.

    Examples:
        >>> df = parse_pdf(Path("Plan de Estudios Informática Julio 2025.pdf"))
        >>> df.columns.tolist()[:3]
        ['fuente', 'CARRERA', 'semestre']
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    doc = pymupdf.open(str(pdf_path))
    fuente = pdf_path.stem
    carrera = extract_carrera(fuente)
    all_records: list[dict] = []

    for page in doc:
        page_text = page.get_text()
        if TARGET_TEXT not in page_text.lower():
            continue

        tab_finder = page.find_tables()
        if not tab_finder or not tab_finder.tables:
            continue

        # Tabla más grande por número de filas = tabla principal de distribución
        main_table = max(tab_finder.tables, key=lambda t: len(t.extract()))
        rows = main_table.extract()

        semestre = detect_semester_from_rows(rows)
        option_label = detect_option_from_rows(rows)
        hidx, header_row = find_header_row(rows)
        if hidx == -1:
            continue

        col_map = build_col_map(header_row)
        if not col_map:
            continue

        records = extract_table_rows(
            rows, col_map, fuente, carrera, semestre, option_label=option_label
        )
        all_records.extend(records)

    doc.close()

    if not all_records:
        return pd.DataFrame(columns=CSV_COLUMNS)

    # Include _opcion as an internal column so callers can use _split_by_option()
    df = pd.DataFrame(all_records, columns=CSV_COLUMNS + ["_opcion"])
    # Normalizar nombre de asignatura para el join posterior
    df["asignatura_norm"] = df["asignatura"].apply(norm_text)
    return df
