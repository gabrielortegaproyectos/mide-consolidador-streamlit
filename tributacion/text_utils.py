"""text_utils.py — Funciones puras de manipulación de texto.

Todas las funciones de este módulo son stateless y no tienen dependencias
externas más allá de la biblioteca estándar. Pueden usarse y testearse de
forma aislada sin cargar pandas ni pymupdf.
"""

import re
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz

from tributacion.config import AREA_SHORT_LABELS, SEMESTER_ORDINAL_MAP


# ---------------------------------------------------------------------------
# Conversión de numerales romanos
# ---------------------------------------------------------------------------

_ROMAN_VALUES: dict[str, int] = {
    "I": 1, "V": 5, "X": 10, "L": 50,
    "C": 100, "D": 500, "M": 1000,
}


def roman_to_int(roman: str) -> int:
    """Convierte un numeral romano a su equivalente entero.

    Soporta los valores 1–12 usados para numerar semestres (I–XII).

    Args:
        roman: Cadena con el numeral romano, ej. ``'VIII'``.

    Returns:
        Entero correspondiente, ej. ``8``.

    Raises:
        ValueError: Si ``roman`` contiene caracteres no romanos o está vacío.

    Examples:
        >>> roman_to_int("IV")
        4
        >>> roman_to_int("IX")
        9
    """
    roman = roman.strip().upper()
    if not roman or not all(c in _ROMAN_VALUES for c in roman):
        raise ValueError(f"Numeral romano inválido: {roman!r}")

    result = 0
    prev = 0
    for ch in reversed(roman):
        val = _ROMAN_VALUES[ch]
        if val < prev:
            result -= val
        else:
            result += val
        prev = val
    return result


# ---------------------------------------------------------------------------
# Normalización de texto para joins
# ---------------------------------------------------------------------------

def norm_text(s: str) -> str:
    """Normaliza una cadena para comparaciones tolerantes a tildes y mayúsculas.

    Convierte a minúsculas, elimina tildes / diacríticos (NFD → ASCII) y
    colapsa espacios internos múltiples en uno solo.

    También expande abreviaturas curriculares frecuentes para mejorar el
    matching entre la matriz y el PDF. Actualmente:
    - ``APS`` → ``atencion primaria de salud``

    Args:
        s: Cadena de entrada.

    Returns:
        Cadena normalizada, ej. ``'álgebra  I'`` → ``'algebra i'``.

    Examples:
        >>> norm_text("Álgebra  I")
        'algebra i'
        >>> norm_text("SÉPTIMO")
        'septimo'
    """
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\baps\b", "atencion primaria de salud", s)
    return s


# ---------------------------------------------------------------------------
# Conversión segura a entero
# ---------------------------------------------------------------------------

def safe_int(x: object) -> int | None:
    """Convierte ``x`` a entero sólo si es una cadena de dígitos puros.

    No lanza excepciones: devuelve ``None`` si la conversión no es posible.

    Args:
        x: Valor a convertir (normalmente una celda de tabla o celda Excel).

    Returns:
        Entero si ``x`` es convertible; ``None`` en cualquier otro caso.

    Examples:
        >>> safe_int("42")
        42
        >>> safe_int("3.5") is None
        True
        >>> safe_int("") is None
        True
    """
    try:
        val = str(x).strip()
        return int(val) if re.match(r"^\d+$", val) else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Detección de semestre desde texto de página PDF
# ---------------------------------------------------------------------------

def detect_semester_from_text(text: str) -> int:
    """Infiere el número de semestre a partir de texto libre de una página PDF.

    Busca cualquier token ordinal del mapa :data:`~tributacion.config.SEMESTER_ORDINAL_MAP`
    seguido (en la misma celda o línea) de la palabra "semestre".

    Args:
        text: Texto extraído de la página o encabezado de tabla.

    Returns:
        Número de semestre (1–12), o ``0`` si no se detecta.

    Examples:
        >>> detect_semester_from_text("Distribución Primer Semestre 2025")
        1
        >>> detect_semester_from_text("nada relevante")
        0
    """
    text_lower = text.lower()
    for key, num in SEMESTER_ORDINAL_MAP.items():
        if key in text_lower and "semestre" in text_lower:
            return num
    return 0


def detect_semester_from_rows(rows: list[list]) -> int:
    """Infiere el número de semestre escaneando las primeras 5 filas de la tabla.

    Aplica :func:`detect_semester_from_text` a cada celda de las primeras 5 filas.

    Args:
        rows: Lista de listas devuelta por ``Table.extract()`` de PyMuPDF.

    Returns:
        Número de semestre (1–12), o ``0`` si no se detecta.
    """
    for row in rows[:5]:
        for cell in row:
            result = detect_semester_from_text(str(cell or ""))
            if result:
                return result
    return 0


# ---------------------------------------------------------------------------
# Detección de etiqueta de opción académica (ej. "Opción A: ...")
# ---------------------------------------------------------------------------

def extract_option_label(text: str) -> str | None:
    """Extrae la etiqueta de opción académica contenida en paréntesis.

    Busca el patrón ``(Opción X: <etiqueta>)`` en el texto y retorna
    ``<etiqueta>``.  Acepta tanto ``Opción`` (con tilde) como ``Opcion``
    (sin tilde) y cualquier letra mayúscula como discriminador de opción.

    Args:
        text: Texto de una celda de encabezado de tabla PDF.

    Returns:
        Texto de la etiqueta, e.g.
        ``'Certificación Académica en Enfermería Comunitaria'``; o ``None``
        si el patrón no está presente.

    Examples:
        >>> extract_option_label(
        ...     "Noveno Semestre (Opción A: Certificación Académica en Enfermería Comunitaria)"
        ... )
        'Certificación Académica en Enfermería Comunitaria'
        >>> extract_option_label("Primer Semestre") is None
        True
    """
    m = re.search(r"\(Opci[oó]n\s+[A-Z]:\s*(.+?)\)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def detect_option_from_rows(rows: list[list]) -> str | None:
    """Detecta la etiqueta de opción académica escaneando las primeras 5 filas.

    Aplica :func:`extract_option_label` a cada celda de las primeras 5 filas y
    retorna la primera coincidencia encontrada.

    Args:
        rows: Lista de listas devuelta por ``Table.extract()`` de PyMuPDF.

    Returns:
        La etiqueta de opción, e.g.
        ``'Certificación Académica en Enfermería Comunitaria'``; o ``None``
        si no se detecta ninguna.
    """
    for row in rows[:5]:
        for cell in row:
            result = extract_option_label(str(cell or ""))
            if result is not None:
                return result
    return None


# ---------------------------------------------------------------------------
# Inferencia de semestre desde nombre de archivo
# ---------------------------------------------------------------------------

def get_semester_from_filename(path: Path) -> int | None:
    """Infiere el número de semestre a partir del nombre de un archivo .md o .csv.

    Primero intenta extraer dígitos directamente del stem (ej. ``'semestre_3.md'``
    → ``3``). Si no los encuentra, prueba con palabras ordinales del mapa de
    configuración (ej. ``'Séptimo Semestre.md'`` → ``7``).

    Args:
        path: Ruta al archivo de semestre.

    Returns:
        Número de semestre (1–12) o ``None`` si no se puede determinar.

    Examples:
        >>> from pathlib import Path
        >>> get_semester_from_filename(Path("Cuarto Semestre.md"))
        4
        >>> get_semester_from_filename(Path("semestre_7.csv"))
        7
    """
    stem = path.stem

    # Intento 1: dígitos explícitos en el nombre
    digits = re.findall(r"\d+", stem)
    if digits:
        return int(digits[0])

    # Intento 2: palabras ordinales
    stem_norm = norm_text(stem)
    for key, num in SEMESTER_ORDINAL_MAP.items():
        # norm_text ya eliminó tildes, comparar igualmente sin tildes
        if norm_text(key) in stem_norm:
            return num

    return None


# ---------------------------------------------------------------------------
# Parseo de textos de la matriz de tributación (NB01)
# ---------------------------------------------------------------------------

def parse_ar_disciplinar(text: str) -> tuple[str, int, str]:
    """Extrae los componentes de una celda de Ámbito de Realización (Disciplinar).

    El formato esperado es ``"AR_N: Título: Descripción"``.

    Args:
        text: Contenido de la celda de AR de la fila 1 de la matriz.

    Returns:
        Tupla ``(ambito, n_ar, desc_ar)``.  Si el formato no coincide
        retorna ``(text, 0, '')``.

    Examples:
        >>> parse_ar_disciplinar("AR_2: Gestión: Administra recursos TI")
        ('Gestión', 2, 'Administra recursos TI')
    """
    parts = str(text).split(":", 2)
    # AR_N → extraer entero N del primer segmento
    m = re.search(r"\d+", parts[0])
    n_ar = int(m.group()) if m else 0
    if len(parts) >= 3:
        # Formato completo: "AR_N: Título: Descripción"
        ambito  = parts[1].strip()
        desc_ar = parts[2].strip()
    elif len(parts) == 2:
        # Solo un separador: "AR_N: Descripción larga"
        # No se puede distinguir título de descripción → ÁMBITO vacío,
        # todo el texto va a DESCRIPCIÓN AR.
        ambito  = ""
        desc_ar = parts[1].strip()
    else:
        return str(text).strip(), 0, ""
    return ambito, n_ar, desc_ar


def parse_ra(area_title: str, text: str) -> tuple[str, str]:
    """Extrae nombre y descripción del Resultado de Aprendizaje.

    Para el área Disciplinar el separador es el primer ``:``;
    para las demás áreas es el segundo ``:``.

    Args:
        area_title: Título del área de tributación (ver ``AREA_TITLES``).
        text: Contenido de la celda RA (fila 2 de la matriz).

    Returns:
        Tupla ``(nombre_ra, descripcion_ra)``.
    """
    text = str(text)
    if "DISCIPLINAR" in area_title.upper():
        parsed = _parse_disciplinar_ra_header(text)
        if parsed is not None:
            return parsed["nombre_ra"], parsed["descripcion_ra"]
        idx = text.find(":")
        if idx == -1:
            return text.strip(), ""
        return text[:idx].strip(), text[idx + 1:].strip()
    else:
        first = text.find(":")
        if first == -1:
            return text.strip(), ""
        second = text.find(":", first + 1)
        if second == -1:
            return text[:first].strip(), text[first + 1:].strip()
        return text[:second].strip(), text[second + 1:].strip()


def _normalize_level_label(level: str) -> str:
    """Canonicaliza la etiqueta de nivel de logro.

    Normaliza mayúsculas/minúsculas y tildes para converger en tres valores
    canónicos: ``INICIAL``, ``INTERMEDIO`` y ``AVANZADO``.
    La variante ``titulación``/``titulacion`` se considera equivalente a
    ``AVANZADO``.
    """
    normalized = norm_text(level)
    canonical_map = {
        "inicial": "INICIAL",
        "intermedio": "INTERMEDIO",
        "avanzado": "AVANZADO",
        "titulacion": "AVANZADO",
    }
    return canonical_map.get(normalized, level.strip())


def parse_level(text: str) -> tuple[str, str]:
    """Extrae nivel de logro y su descripción de una celda de nivel (fila 3).

    El formato esperado es ``"N. INICIAL: descripción..."``.
    Se elimina el prefijo ``"N."`` y se devuelve la etiqueta canonicalizada
    del nivel (``INICIAL``, ``INTERMEDIO`` o ``AVANZADO``). La variante
    ``titulación`` se normaliza como ``AVANZADO``.

    Args:
        text: Contenido de la celda de nivel de logro.

    Returns:
        Tupla ``(nivel_logro, descripcion_nivel)``.

    Examples:
        >>> parse_level("N. INICIAL: Reconoce conceptos básicos")
        ('INICIAL', 'Reconoce conceptos básicos')
        >>> parse_level("N. AVANZADO: Diseña estrategias integrales")
        ('AVANZADO', 'Diseña estrategias integrales')
    """
    text = str(text)
    idx = text.find(":")
    if idx == -1:
        level = text.strip()
    else:
        level = text[:idx].strip()
    # Eliminar prefijo "N." / "N " si existe
    import re
    level = re.sub(r"^N\.\s*", "", level, flags=re.IGNORECASE).strip()
    desc = text[idx + 1:].strip() if idx != -1 else ""
    return _normalize_level_label(level), desc


def is_habilidades_transversales(ra_cell: str) -> bool:
    """Determina si una celda RA corresponde a la columna de Habilidades Transversales.

    Esas columnas se excluyen del consolidado de tributación.

    Args:
        ra_cell: Valor de la celda en la fila de RA (fila 2, con ffill aplicado).

    Returns:
        ``True`` si la celda es exactamente "HABILIDADES TRANSVERSALES".
    """
    return str(ra_cell).strip().upper() == "HABILIDADES TRANSVERSALES"


# Etiquetas de la fila 3 (RA) que bajo MODELO EDUCATIVO INSTITUCIONAL actúan como
# AR sin número, con las celdas de la fila 4 como RA sin número.
_MODELO_EDUCATIVO_AR_LABELS: frozenset[str] = frozenset([
    "EJES DEL MODELO",
    "PERSPECTIVAS DEL DESARROLLO SOSTENIBLE",
])


def is_modelo_educativo_ar(ra_cell: str) -> bool:
    """Determina si una celda RA pertenece a un sub-área de MODELO EDUCATIVO.

    Bajo el área *MODELO EDUCATIVO INSTITUCIONAL*, las etiquetas
    ``EJES DEL MODELO`` y ``PERSPECTIVAS DEL DESARROLLO SOSTENIBLE`` funcionan
    como Ámbitos de Realización (AR) sin número, y las celdas de la fila 4
    contienen los nombres de RA (sin número ni descripción).

    Args:
        ra_cell: Valor de la celda en la fila de RA (fila 2, con ffill aplicado).

    Returns:
        ``True`` si la celda coincide con una de las etiquetas de MODELO EDUCATIVO.
    """
    return str(ra_cell).strip().upper() in _MODELO_EDUCATIVO_AR_LABELS


# ---------------------------------------------------------------------------
# Etiqueta corta de tributación
# ---------------------------------------------------------------------------

def tributacion_short_label(area_title: str) -> str:
    """Devuelve la etiqueta abreviada de tributación a partir del título del área.

    Consulta :data:`~tributacion.config.AREA_SHORT_LABELS`; si no hay
    coincidencia exacta, devuelve ``area_title`` tal cual.

    Args:
        area_title: Título completo del área (celda de la fila 0 de la matriz).

    Returns:
        Etiqueta abreviada, e.g. ``"ÁREA DE FORMACIÓN DISCIPLINAR"`` → ``"DISCIPLINAR"``.

    Examples:
        >>> tributacion_short_label("ÁREA DE FORMACIÓN DISCIPLINAR")
        'DISCIPLINAR'
        >>> tributacion_short_label("MODELO EDUCATIVO INSTITUCIONAL")
        'MODELO EDUCATIVO INSTITUCIONAL'
    """
    return AREA_SHORT_LABELS.get(area_title.strip(), area_title.strip())


# ---------------------------------------------------------------------------
# Extracción del número de RA desde texto de celda
# ---------------------------------------------------------------------------

_DISCIPLINAR_RA_PATTERN = re.compile(
    r"^\s*AR_?(\d+)\s*[–—-]\s*RA\s*(\d+)\s*:\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def _parse_disciplinar_ra_header(ra_text: str) -> dict[str, object] | None:
    """Parsea y canoniza un encabezado RA disciplinar.

    Acepta variantes como ``AR_4-RA10: ...``, ``AR4 – RA11: ...`` y
    ``AR_2– RA5: ...``. Si el encabezado coincide, devuelve el nombre RA
    canonizado como ``AR_<n> - RA<m>`` y la descripción posterior al ``:``.
    """
    text = str(ra_text).strip()
    match = _DISCIPLINAR_RA_PATTERN.match(text)
    if match is None:
        return None

    ar_num = int(match.group(1))
    ra_num = int(match.group(2))
    descripcion_ra = match.group(3).strip()
    return {
        "ar_num": ar_num,
        "ra_num": ra_num,
        "nombre_ra": f"AR_{ar_num} - RA{ra_num}",
        "descripcion_ra": descripcion_ra,
    }


def parse_ra_num(ra_text: str) -> int:
    """Extrae el número global de Resultado de Aprendizaje de una celda RA disciplinar.

    El formato esperado es ``"AR_x – RAy: nombre: desc"`` (acepta guiones largos
    y cortos). Retorna ``y`` como entero.

    Para columnas no-DISCIPLINAR el pipeline pasa directamente 0, por lo que
    esta función sólo se llama para columnas bajo "ÁREA DE FORMACIÓN DISCIPLINAR".

    Args:
        ra_text: Contenido de la celda RA (fila 2 de la matriz, con ffill).

    Returns:
        Número ``y`` extraído, o ``0`` si el patrón no coincide.

    Examples:
        >>> parse_ra_num("AR_1 – RA3: Gestión de Datos: Administra bases de datos")
        3
        >>> parse_ra_num("AR_2 - RA12: Redes: Configura redes")
        12
    """
    parsed = _parse_disciplinar_ra_header(ra_text)
    return int(parsed["ra_num"]) if parsed is not None else 0


# ---------------------------------------------------------------------------
# Coincidencia difusa (fuzzy matching)
# ---------------------------------------------------------------------------

def fuzzy_match_score(s1: str, s2: str) -> float:
    """Calcula el puntaje de similitud entre dos cadenas normalizadas.

    Usa :func:`rapidfuzz.fuzz.token_sort_ratio` (0–100) y lo normaliza a [0, 1].
    ``token_sort_ratio`` es robusto ante reordenamiento de palabras, ideal para
    nombres de asignaturas que pueden diferir en orden de palabras.

    Args:
        s1: Primera cadena.
        s2: Segunda cadena.

    Returns:
        Similitud en el rango ``[0.0, 1.0]``.

    Examples:
        >>> fuzzy_match_score("álgebra lineal", "Álgebra Lineal")
        1.0
        >>> fuzzy_match_score("calculo i", "cálculo I") >= 0.9
        True
    """
    n1 = norm_text(s1)
    n2 = norm_text(s2)
    return fuzz.token_sort_ratio(n1, n2) / 100.0


def best_fuzzy_match(
    query: str,
    candidates: list[str],
    threshold: float = 0.75,
) -> tuple[str | None, float]:
    """Encuentra la mejor coincidencia difusa para ``query`` en ``candidates``.

    Itera sobre los candidatos y devuelve el de mayor similitud si supera
    ``threshold``. En caso de empate devuelve el primero encontrado.

    Args:
        query:      Cadena a buscar.
        candidates: Lista de cadenas contra las cuales comparar.
        threshold:  Umbral mínimo de similitud (0–1).
                    Por defecto ``0.75`` (75 %).

    Returns:
        Tupla ``(mejor_candidato, puntaje)``; ``(None, 0.0)`` si no hay coincidencia.

    Examples:
        >>> best_fuzzy_match("calculo diferencial", ["Cálculo Diferencial", "Física"])
        ('Cálculo Diferencial', 1.0)
    """
    best_candidate: str | None = None
    best_score: float = 0.0
    for c in candidates:
        score = fuzzy_match_score(query, c)
        if score > best_score:
            best_score = score
            best_candidate = c
    if best_score >= threshold:
        return best_candidate, best_score
    return None, 0.0
