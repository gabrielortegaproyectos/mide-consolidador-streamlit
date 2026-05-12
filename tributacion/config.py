"""config.py — Constantes y parámetros centralizados del pipeline de tributación.

Todas las constantes que en los notebooks originales estaban hardcodeadas en
distintas celdas viven aquí. Para adaptar el pipeline a otra carrera basta
con sobreescribir los valores relevantes al llamar las funciones del paquete
(o subclasificar / monkeypatching en un script de configuración por carrera).
"""

import logging

from pathlib import Path

from tributacion.ciclo_catalog import resolve_ciclo_label, resolve_tipo_ciclo

# ---------------------------------------------------------------------------
# Matriz de tributación (NB01)
# ---------------------------------------------------------------------------

# Nombre de la hoja de cálculo que contiene la matriz de tributación.
DEFAULT_SHEET_NAME: str = "Asignaturas - RA"

# Títulos de área que identifican columnas de tributación válidas en la matriz.
# Todo lo demás (ej. "HABILIDADES TRANSVERSALES") se ignora.
AREA_TITLES: list[str] = [
    "ÁREA DE FORMACIÓN DISCIPLINAR",
    "ÁREA DE FORMACIÓN BÁSICA",
    "ÁREA DE FORMACIÓN GENERAL / EJE DE FORMACIÓN INTEGRAL",
    "MODELO EDUCATIVO INSTITUCIONAL",
]

# Valor que indica tributación activa en la celda de la matriz.
TRIBUTACION_VALUE: str = "1"

# Ciclo formativo.
# En el flujo actual se resuelve prioritariamente desde los catálogos manuales
# ``data/ciclos_manual/*.json``. Si no hay match, se conserva la heurística
# histórica por ``max_semestre`` como compatibilidad final.
CICLO_POR_DEFINIR: str = "POR DEFINIR"
CICLO_INICIAL: str = "CICLO INICIAL"
CICLO_INTERMEDIO: str = "CICLO INTERMEDIO"
CICLO_TITULACION: str = "CICLO DE TITULACIÓN"

logger = logging.getLogger(__name__)


def compute_ciclo(
    semestre: int,
    max_semestre: int,
    *,
    tipo_ciclo: str | None = None,
    carrera: str | None = None,
    matrix_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
) -> str:
    """Calcula el ciclo formativo según catálogo manual o heurística histórica.

    Args:
        semestre:      Número de semestre de la asignatura (1–12).
        max_semestre:  Máximo semestre encontrado en la carrera.
        tipo_ciclo:    Identificador de catálogo manual para la carrera.
        carrera:       Nombre de la carrera, usado para fallback de resolución.
        matrix_path:   Ruta de la matriz, usada para fallback de resolución.
        pdf_path:      Ruta del PDF, usada para fallback de resolución.

    Returns:
        Etiqueta del ciclo formativo.
    """
    resolved_tipo_ciclo = resolve_tipo_ciclo(
        {"TIPO_CICLO": tipo_ciclo or "", "CARRERA": carrera or ""},
        carrera=carrera,
        matrix_path=matrix_path,
        pdf_path=pdf_path,
    )
    if resolved_tipo_ciclo:
        ciclo_label = resolve_ciclo_label(semestre, resolved_tipo_ciclo)
        if ciclo_label is not None:
            return ciclo_label
        logger.warning(
            "Semestre %s no mapeado para tipo_ciclo '%s'; se devolverá '%s'.",
            semestre,
            resolved_tipo_ciclo,
            CICLO_POR_DEFINIR,
        )
        return CICLO_POR_DEFINIR

    if max_semestre <= 8:
        return CICLO_POR_DEFINIR
    # max_semestre >= 10
    if semestre <= 4:
        return CICLO_INICIAL
    if semestre <= 8:
        return CICLO_INTERMEDIO
    return CICLO_TITULACION

# Etiquetas cortas para la columna TRIBUTACIÓN a partir del título completo del área.
# Permite convertir "ÁREA DE FORMACIÓN DISCIPLINAR" → "DISCIPLINAR", etc.
AREA_SHORT_LABELS: dict[str, str] = {
    "ÁREA DE FORMACIÓN DISCIPLINAR":                        "DISCIPLINAR",
    "ÁREA DE FORMACIÓN BÁSICA":                             "BÁSICA",
    "ÁREA DE FORMACIÓN GENERAL / EJE DE FORMACIÓN INTEGRAL": "GENERAL / EJE DE FORMACIÓN INTEGRAL",
    "MODELO EDUCATIVO INSTITUCIONAL":                       "MODELO EDUCATIVO INSTITUCIONAL",
}

# N°AR base para las áreas no-DISCIPLINAR (BÁSICA, GENERAL/EJE, MEI).
# Sus índices se asignan como BASE + índice_0 dentro del área.
NON_DISCIPLINAR_NAR_BASES: dict[str, int] = {
    "ÁREA DE FORMACIÓN BÁSICA":                             100,
    "ÁREA DE FORMACIÓN GENERAL / EJE DE FORMACIÓN INTEGRAL": 200,
    "MODELO EDUCATIVO INSTITUCIONAL":                       300,
}

# ---------------------------------------------------------------------------
# Extracción de horas desde PDF (pdf_parser)
# ---------------------------------------------------------------------------

# Texto que identifica las páginas de distribución de horas en el PDF.
# La comparación se hace en minúsculas.
TARGET_TEXT: str = "distribución y cálculo de tipos de hora por semestre"

# Mapa de palabras ordinales en español → número de semestre.
SEMESTER_ORDINAL_MAP: dict[str, int] = {
    "primer": 1,
    "segundo": 2,
    "tercer": 3,
    "cuarto": 4,
    "quinto": 5,
    "sexto": 6,
    "séptimo": 7,
    "septimo": 7,
    "octavo": 8,
    "noveno": 9,
    "décimo": 10,
    "decimo": 10,
    "undécimo": 11,
    "undecimo": 11,
    "duodécimo": 12,
    "duodecimo": 12,
}

# Offsets de columna respecto a la posición de "SCT" en la fila de cabecera.
# Los PDFs de diferentes instituciones tienen entre 41 y 44 columnas totales,
# pero los grupos de horas siempre están anclados a SCT.
SCT_OFFSETS: dict[str, int] = {
    "sct": 0,
    "horas_docencia_directa": 1,
    "DD TEÓRICAS": 2,
    "DD TALLER": 5,
    "DD AYUDANTÍA": 8,
    "DD LABORATORIO": 11,
    "DD SIMULACIÓN": 14,
    "DD CAMPOS CLÍNICOS": 17,
    "DD SALIDAS A TERRENO": 20,
    "DD PRO COLABORATIVO": 23,
    "total_trabajo_autonomo": 26,
    # total_plan_estudio se detecta dinámicamente en build_col_map()
}

# Columnas del CSV que produce pdf_parser.parse_pdf().
CSV_COLUMNS: list[str] = [
    "fuente",
    "CARRERA",
    "semestre",
    "codigo_prerrequisito",
    "asignatura_prerrequisito",
    "codigo",
    "asignatura",
    "sct",
    "horas_docencia_directa",
    "DD TEÓRICAS",
    "DD AYUDANTÍA",
    "DD TALLER",
    "DD CAMPOS CLÍNICOS",
    "DD SIMULACIÓN",
    "DD LABORATORIO",
    "DD PRO COLABORATIVO",
    "DD SALIDAS A TERRENO",
    "total_trabajo_autonomo",
    "total_plan_estudio",
]

# ---------------------------------------------------------------------------
# Fusión de horas con el consolidado (merger)
# ---------------------------------------------------------------------------

# Mapeo: columna del DataFrame de horas (CSV) → columna objetivo en el Excel final.
# La llave es el nombre de columna en el DataFrame producido por parse_pdf().
# El valor es el nombre de columna en el consolidado de tributación.
MAPEO_CSV_A_EXCEL: dict[str, str] = {
    "asignatura_prerrequisito": "PRERREQUISITO",
    "codigo":                   "CÓDIGO DEL CURSO",
    "codigo_prerrequisito":     "CÓDIGO PRERREQUISITO",
    "sct":                      "N° DE CRÉDITOS",
    "total_plan_estudio":       "HORAS CR TOTALES",
    "horas_docencia_directa":   "HORAS DE DOCENCIA DIRECTA",
    "DD TEÓRICAS":              "DD TEÓRICAS",
    "DD AYUDANTÍA":             "DD AYUDANTÍA",
    "DD TALLER":                "DD TALLER",
    "DD CAMPOS CLÍNICOS":       "DD CAMPOS CLÍNICOS",
    "DD SIMULACIÓN":            "DD SIMULACIÓN",
    "DD LABORATORIO":           "DD LABORATORIO",
    "DD PRO COLABORATIVO":      "DD PRO COLABORATIVO",
    "DD SALIDAS A TERRENO":     "DD SALIDAS A TERRENO",
    "total_trabajo_autonomo":   "HORAS DE TRABAJO AUTÓNOMO",
}

# Columnas del Excel final que deben convertirse a tipo numérico después del join.
# PRERREQUISITO y CÓDIGO DEL CURSO son texto; el resto son horas/créditos.
NUMERIC_COLUMNS: list[str] = [
    "N° DE CRÉDITOS",
    "HORAS CR TOTALES",
    "HORAS DE DOCENCIA DIRECTA",
    "DD TEÓRICAS",
    "DD AYUDANTÍA",
    "DD TALLER",
    "DD CAMPOS CLÍNICOS",
    "DD SIMULACIÓN",
    "DD LABORATORIO",
    "DD PRO COLABORATIVO",
    "DD SALIDAS A TERRENO",
    "HORAS DE TRABAJO AUTÓNOMO",
]

# ---------------------------------------------------------------------------
# Esquema completo del Excel de salida (36 columnas)
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS: list[str] = [
    # ---- Identificación de la carrera (viene de plans_mapped.json) ----
    "GRADO",
    "FACULTAD",
    "ESCUELA",
    "CARRERA",
    # ---- Clasificación de tributación ----
    "TRIBUTACIÓN",
    "CICLO",
    "N°AR",
    "ÁMBITO DE REALIZACIÓN",
    "DESCRIPCIÓN AR",
    "N° RA",
    "NOMBRE RA",
    "DESCRIPCIÓN RA",
    "NIVEL DE LOGRO",
    "DESCRIPCIÓN DEL NIVEL DE LOGRO",
    # ---- Datos de la asignatura en la malla ----
    "ÁREA DE FORMACIÓN",
    "AÑO",
    "NIVEL O SEMESTRE",
    "CÓDIGO DEL CURSO",
    "ASIGNATURA",
    "CÓDIGO PRERREQUISITO",
    "PRERREQUISITO",
    # ---- Créditos y horas ----
    "N° DE CRÉDITOS",
    "HORAS CR TOTALES",
    "HORAS DE DOCENCIA DIRECTA",
    "DD TEÓRICAS",
    "DD AYUDANTÍA",
    "DD TALLER",
    "DD CAMPOS CLÍNICOS",
    "DD SIMULACIÓN",
    "DD LABORATORIO",
    "DD PRO COLABORATIVO",
    "DD SALIDAS A TERRENO",
    "HORAS DE TRABAJO AUTÓNOMO",
    # ---- Campos adicionales ----
    "MODALIDAD",
    "INDICADORES DE LOGRO POR ASIGNATURA",
    "PRODUCTOS DE APRENDIZAJE POR ASIGNATURA",
]

# ---------------------------------------------------------------------------
# Normalización canónica de NOMBRE RA
# ---------------------------------------------------------------------------

# Catálogo local versionado con los nombres canónicos de Resultados de
# Aprendizaje. El pipeline lo usa como fuente de verdad y lo va enriqueciendo
# a medida que se procesan carreras.
CANONICAL_RA_LOCAL_PATH: Path = Path("data/normalizacion_ra/nombres_ra_canonicos.csv")

# URL histórica del Google Sheet publicado como CSV. Se conserva solo como
# referencia externa; la normalización del pipeline ya no depende de la red.
CANONICAL_RA_URL: str = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTZaJfr_NcbR5vKW82gSFDSTcxM30yRxC8hALWB_QrCSubBX9aO95OeH-zQVfsOUqYuXA-TQPiIJoGX"
    "/pub?gid=482771756&single=true&output=csv"
)

# Umbral mínimo de similitud (0–1) para aceptar un match canónico.
# Variantes tipográficas menores (espacios, puntos) superan fácilmente 0.85.
CANONICAL_RA_THRESHOLD: float = 0.85

# ---------------------------------------------------------------------------
# Códigos oficiales de asignatura
# ---------------------------------------------------------------------------

# URL del Google Sheet publicado como CSV con los códigos oficiales por
# combinación de carrera y asignatura.
SUBJECT_CODES_URL: str = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQFUDzPrXAVamTbYn81ngIix58Lija4HIEhz0GtOGEp6hyyUnD_IatB2A2FY0LvFhBNN7vV6lvAR0kF"
    "/pub?gid=1386699334&single=true&output=csv"
)

# Catálogo local versionado en el repositorio.
SUBJECT_CODES_LOCAL_PATH: Path = Path("data/codigos/CODIGOS_MALLAS - Hoja1.csv")

# Alias manuales para asignaturas cuyo nombre en la matriz no coincide de forma
# exacta con el catálogo oficial de códigos. Puede incluir un semestre
# específico para desambiguar variantes A/B.
SUBJECT_CODES_ALIASES_PATH: Path = Path("data/codigos/CODIGOS_MALLAS_ALIASES.csv")

# Nombres de columnas esperadas en el catálogo oficial de asignaturas.
SUBJECT_CODES_CAREER_COLUMN: str = "nombre_carrera"
SUBJECT_CODES_SUBJECT_COLUMN: str = "Asignatura"
SUBJECT_CODES_CODE_COLUMN: str = "cod_ramo"
