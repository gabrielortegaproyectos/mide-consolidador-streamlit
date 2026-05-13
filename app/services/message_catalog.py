from __future__ import annotations

from dataclasses import dataclass

from tributacion.config import DEFAULT_SHEET_NAME


@dataclass(frozen=True)
class UserMessage:
    code: str
    title: str
    explanation: str
    action: str
    technical_detail: str | None = None


@dataclass(frozen=True)
class MessageTemplate:
    code: str
    title: str
    explanation: str
    action: str

    def render(self, *, technical_detail: str | None = None) -> UserMessage:
        return UserMessage(
            code=self.code,
            title=self.title,
            explanation=self.explanation,
            action=self.action,
            technical_detail=technical_detail,
        )


MESSAGE_CATALOG: dict[str, MessageTemplate] = {
    "excel.unsupported_format": MessageTemplate(
        code="excel.unsupported_format",
        title="El archivo de matriz no tiene el formato esperado",
        explanation=(
            "La app necesita una matriz Excel en formato .xlsx para revisar sus "
            "hojas, cabeceras y celdas de tributacion."
        ),
        action="Guarda o exporta la matriz como .xlsx y vuelve a cargarla.",
    ),
    "excel.file_missing": MessageTemplate(
        code="excel.file_missing",
        title="No se encontro el archivo de matriz",
        explanation=(
            "La validacion no pudo acceder al archivo temporal de la matriz "
            "cargada."
        ),
        action="Vuelve a cargar la matriz Excel y ejecuta la validacion otra vez.",
    ),
    "excel.sheet_missing": MessageTemplate(
        code="excel.sheet_missing",
        title="La matriz no tiene la hoja esperada",
        explanation=(
            "El ETL busca una hoja con un nombre especifico para leer la "
            "estructura de asignaturas, AR, RA y niveles de logro."
        ),
        action=f"Revisa que exista una hoja llamada exactamente '{DEFAULT_SHEET_NAME}'.",
    ),
    "excel.unreadable": MessageTemplate(
        code="excel.unreadable",
        title="No se pudo abrir la matriz Excel",
        explanation=(
            "El archivo no pudo leerse como Excel. Puede estar corrupto, "
            "protegido o guardado en un formato incompatible."
        ),
        action="Abre el archivo en Excel, guardalo nuevamente como .xlsx y vuelve a cargarlo.",
    ),
    "excel.headers_invalid": MessageTemplate(
        code="excel.headers_invalid",
        title="La matriz tiene cabeceras incompletas o desplazadas",
        explanation=(
            "Las filas y columnas de cabecera no coinciden con la estructura "
            "que el ETL necesita para identificar areas, AR, RA y niveles."
        ),
        action="Revisa que la matriz conserve las cabeceras originales y sus celdas fusionadas.",
    ),
    "excel.columns_missing": MessageTemplate(
        code="excel.columns_missing",
        title="La matriz no tiene las filas o columnas suficientes",
        explanation=(
            "La hoja parece estar vacia, cortada o no corresponde a una matriz "
            "de tributacion curricular compatible."
        ),
        action="Verifica que cargaste la matriz correcta y que contiene cabeceras y asignaturas.",
    ),
    "excel.tributation_missing": MessageTemplate(
        code="excel.tributation_missing",
        title="La matriz no tiene tributacion reconocible",
        explanation=(
            "No se encontraron marcas de tributacion con el valor esperado por "
            "el ETL en las celdas de asignaturas."
        ),
        action="Confirma que las celdas de tributacion usan el valor esperado, normalmente 1.",
    ),
    "excel.structure_invalid": MessageTemplate(
        code="excel.structure_invalid",
        title="La matriz no tiene la estructura esperada",
        explanation=(
            "La validacion encontro un problema estructural que puede impedir "
            "que el pipeline genere un consolidado confiable."
        ),
        action="Corrige la matriz y vuelve a validar antes de ejecutar el pipeline.",
    ),
    "pdf.unreadable": MessageTemplate(
        code="pdf.unreadable",
        title="No se pudo leer el PDF de plan de estudio",
        explanation=(
            "El PDF no parece tener una estructura tabular compatible o no se "
            "puede procesar correctamente."
        ),
        action="Revisa que el archivo sea el plan de estudio oficial y que no sea una imagen escaneada sin texto.",
    ),
    "matching.subjects_missing": MessageTemplate(
        code="matching.subjects_missing",
        title="Hay asignaturas de la matriz que no aparecen en el PDF",
        explanation=(
            "El cruce entre matriz y plan de estudio no encontro algunas "
            "asignaturas, por lo que sus horas o creditos pueden quedar incompletos."
        ),
        action="Revisa nombres de asignaturas, tildes, abreviaturas y versiones del plan/matriz.",
    ),
    "codes.no_match": MessageTemplate(
        code="codes.no_match",
        title="Hay asignaturas sin codigo oficial",
        explanation=(
            "El catalogo de codigos no encontro un match unico para algunas "
            "asignaturas."
        ),
        action="Revisa si falta un alias o si el nombre de asignatura difiere del catalogo.",
    ),
    "matching.semester_ambiguous": MessageTemplate(
        code="matching.semester_ambiguous",
        title="Hay diferencias de semestre o nombres ambiguos",
        explanation=(
            "El ETL detecto posibles diferencias entre la matriz y el PDF al "
            "comparar asignaturas o semestres."
        ),
        action="Revisa el diagnostico de matching y confirma la version correcta de los insumos.",
    ),
}


def message_for_code(code: str, *, technical_detail: str | None = None) -> UserMessage:
    template = MESSAGE_CATALOG.get(code, MESSAGE_CATALOG["excel.structure_invalid"])
    return template.render(technical_detail=technical_detail)


def message_for_excel_issue(issue: str) -> UserMessage:
    lowered = _strip_accents(issue.lower())
    if "hoja" in lowered and "no encontrada" in lowered:
        return message_for_code("excel.sheet_missing", technical_detail=issue)
    if "no se pudo abrir" in lowered:
        return message_for_code("excel.unreadable", technical_detail=issue)
    if "fila" in lowered and "columna" in lowered:
        return message_for_code("excel.columns_missing", technical_detail=issue)
    if "tributacion" in lowered:
        return message_for_code("excel.tributation_missing", technical_detail=issue)
    if "cabecera" in lowered or "area" in lowered or "ar" in lowered or "ra" in lowered:
        return message_for_code("excel.headers_invalid", technical_detail=issue)
    return message_for_code("excel.structure_invalid", technical_detail=issue)


def _strip_accents(value: str) -> str:
    return (
        value.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
