from __future__ import annotations

import unicodedata

import pandas as pd

from tributacion.config import DEFAULT_SHEET_NAME, OUTPUT_COLUMNS


def expected_excel_fields() -> pd.DataFrame:
    """Return the user-facing description of fields produced by the ETL."""
    descriptions = _output_column_descriptions()
    return pd.DataFrame(
        [
            {
                "Campo": column,
                "Grupo": _field_group(column),
                "Origen": _field_origin(column),
                "Uso": descriptions.get(
                    _field_key(column),
                    "Campo conservado en el consolidado final.",
                ),
            }
            for column in OUTPUT_COLUMNS
        ]
    )


def input_requirements() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Insumo": "PDF de plan de estudio",
                "Que revisar": "Debe contener la tabla de distribucion de horas por semestre.",
            },
            {
                "Insumo": "Matriz Excel de tributacion",
                "Que revisar": f"Debe incluir la hoja `{DEFAULT_SHEET_NAME}` con asignaturas y RA.",
            },
        ]
    )


def diagnostic_outputs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Archivo": "tributacion_final.xlsx",
                "Uso": "Consolidado principal que se revisa, descarga y luego se agrega al Excel online maestro.",
            },
        ]
    )


def operational_steps() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Paso": "1. Cargar insumos",
                "Que hacer": "Subir el PDF del plan de estudio y la matriz Excel de tributacion de una carrera.",
            },
            {
                "Paso": "2. Procesar carrera",
                "Que hacer": "Usar el boton de procesamiento. La app valida la matriz antes de ejecutar el ETL.",
            },
            {
                "Paso": "3. Revisar validacion",
                "Que hacer": "Si hay errores, corregir la matriz indicada y volver a procesar. Si aparece el check, continuar.",
            },
            {
                "Paso": "4. Leer resumen de carrera",
                "Que hacer": "Revisar carrera detectada, semestres, asignaturas, ciclos y observaciones importantes.",
            },
            {
                "Paso": "5. Corroborar preview",
                "Que hacer": "Revisar algunas filas del consolidado: carrera, semestre, asignatura, ciclo, RA, creditos y horas.",
            },
            {
                "Paso": "6. Descargar consolidado",
                "Que hacer": "Descargar el Excel consolidado generado para esa carrera.",
            },
            {
                "Paso": "7. Agregar al Excel online",
                "Que hacer": "Abrir el Excel online maestro, pegar o concatenar las filas del consolidado y verificar que las columnas coincidan.",
            },
        ]
    )


def warning_guide() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Advertencia": "SIN MATCH",
                "Que hacer": "Revisar nombre y semestre de la asignatura en PDF y matriz.",
            },
            {
                "Advertencia": "CROSS_SEMESTRE",
                "Que hacer": "Confirmar si la asignatura existe en otro semestre del PDF.",
            },
            {
                "Advertencia": "SIN_MATCH en codigos",
                "Que hacer": "Revisar catalogo de codigos o alias de asignatura.",
            },
            {
                "Advertencia": "AMBIGUO",
                "Que hacer": "Resolver manualmente cuando hay mas de un codigo posible.",
            },
            {
                "Advertencia": "Diagnostico faltante",
                "Que hacer": "Revisar el seguimiento experto para decidir si falta evidencia tecnica.",
            },
            {
                "Advertencia": "Seguimiento experto",
                "Que hacer": "Usarlo como log tecnico cuando se necesite revisar matching, codigos o columnas.",
            },
        ]
    )


def file_policy_notes() -> list[str]:
    return [
        "La app procesa una carrera por vez.",
        "Los archivos cargados se escriben en carpetas temporales durante la corrida.",
        "El resultado se conserva en memoria solo para permitir la descarga en la sesion.",
        "No se deben subir insumos privados al repositorio Git.",
    ]


def _field_group(column: str) -> str:
    key = _field_key(column)
    if key in {"GRADO", "FACULTAD", "ESCUELA", "CARRERA"}:
        return "Identificacion"
    if key in {
        "TRIBUTACION",
        "CICLO",
        "NAR",
        "AMBITO DE REALIZACION",
        "DESCRIPCION AR",
        "N RA",
        "NOMBRE RA",
        "DESCRIPCION RA",
        "NIVEL DE LOGRO",
        "DESCRIPCION DEL NIVEL DE LOGRO",
        "AREA DE FORMACION",
    }:
        return "Tributacion"
    if key in {
        "ANO",
        "NIVEL O SEMESTRE",
        "CODIGO DEL CURSO",
        "ASIGNATURA",
        "CODIGO PRERREQUISITO",
        "PRERREQUISITO",
    }:
        return "Asignatura"
    if "HORAS" in key or key.startswith("DD ") or key == "N DE CREDITOS":
        return "Creditos y horas"
    return "Campos adicionales"


def _field_origin(column: str) -> str:
    key = _field_key(column)
    if key in {
        "N DE CREDITOS",
        "HORAS CR TOTALES",
        "HORAS DE DOCENCIA DIRECTA",
        "DD TEORICAS",
        "DD AYUDANTIA",
        "DD TALLER",
        "DD CAMPOS CLINICOS",
        "DD SIMULACION",
        "DD LABORATORIO",
        "DD PRO COLABORATIVO",
        "DD SALIDAS A TERRENO",
        "HORAS DE TRABAJO AUTONOMO",
        "CODIGO DEL CURSO",
        "CODIGO PRERREQUISITO",
        "PRERREQUISITO",
    }:
        return "PDF plan de estudio"
    if key in {"GRADO", "FACULTAD", "ESCUELA", "CARRERA"}:
        return "PDF, matriz o catalogos JSON"
    return "Matriz Excel"


def _output_column_descriptions() -> dict[str, str]:
    return {
        "ASIGNATURA": "Nombre usado para cruzar matriz, PDF y catalogos.",
        "NIVEL O SEMESTRE": "Semestre de la asignatura en la malla.",
        "TRIBUTACION": "Area abreviada donde la asignatura tributa.",
        "CICLO": "Ciclo curricular inferido desde la duracion de la carrera y catalogos JSON.",
        "NAR": "Numero de ambito de realizacion asociado.",
        "AMBITO DE REALIZACION": "Ambito curricular asociado al RA.",
        "N RA": "Numero de resultado de aprendizaje.",
        "NOMBRE RA": "Nombre canonico del resultado de aprendizaje.",
        "DESCRIPCION RA": "Descripcion del resultado de aprendizaje.",
        "NIVEL DE LOGRO": "Nivel declarado en la matriz para ese cruce asignatura-RA.",
        "N DE CREDITOS": "Creditos SCT extraidos desde el PDF.",
        "HORAS CR TOTALES": "Total de horas del plan extraidas desde el PDF.",
        "HORAS DE DOCENCIA DIRECTA": "Horas de docencia directa extraidas desde el PDF.",
        "HORAS DE TRABAJO AUTONOMO": "Horas de trabajo autonomo extraidas desde el PDF.",
        "CODIGO DEL CURSO": "Codigo oficial enriquecido desde PDF o catalogos.",
    }


def _field_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_value.upper().replace("°", "").split())
