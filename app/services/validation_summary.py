from __future__ import annotations

import pandas as pd


def expected_excel_fields() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Campo": "Asignatura",
                "Origen": "Matriz Excel",
                "Uso": "Llave principal para cruzar tributacion con horas del PDF.",
            },
            {
                "Campo": "Area / AR / RA",
                "Origen": "Matriz Excel",
                "Uso": "Estructura de tributacion curricular y resultados de aprendizaje.",
            },
            {
                "Campo": "Nivel de logro",
                "Origen": "Matriz Excel",
                "Uso": "Medida curricular que se conserva en el consolidado final.",
            },
            {
                "Campo": "Semestre, creditos y horas",
                "Origen": "PDF plan de estudio",
                "Uso": "Datos academicos extraidos y validados contra la matriz.",
            },
            {
                "Campo": "Codigo de asignatura",
                "Origen": "Catalogos ETL",
                "Uso": "Enriquecimiento para trazabilidad y consumo posterior.",
            },
        ]
    )

