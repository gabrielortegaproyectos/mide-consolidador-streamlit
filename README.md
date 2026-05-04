# MIDE Consolidador Streamlit

Aplicacion Streamlit para que usuarios autorizados carguen un PDF de plan de
estudio y una matriz Excel de tributacion curricular, ejecuten el pipeline ETL
MIDE y descarguen consolidados, diagnosticos y un resumen de validacion.

Este repositorio no reemplaza `mide-tributacion-curricular`. La app debe
consumir el ETL como dependencia estable y concentrarse en experiencia de
usuario, manejo de archivos, validaciones, trazabilidad y descarga de
resultados.

## Estado

Bootstrap inicial. El siguiente hito es estabilizar el contrato publico del ETL
para poder llamar `tributacion.pipeline.run_pipeline` desde archivos cargados en
la interfaz.

## Flujo MVP

1. Cargar PDF de plan de estudio.
2. Cargar matriz Excel de tributacion.
3. Ingresar metadatos minimos de la carrera.
4. Validar formato de insumos.
5. Ejecutar pipeline ETL MIDE.
6. Revisar resumen de validacion y alertas.
7. Descargar ZIP con Excel final, CSV diagnosticos y `resumen_validacion.md`.

## Instalacion local

```bash
uv sync
uv run streamlit run app/main.py
```

Fallback con `pip`:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
streamlit run app/main.py
```

## Tests

```bash
uv run --group dev pytest
```

## Documentacion

- `docs/roadmap.md`: ruta de implementacion y backlog inicial.
- `docs/arquitectura.md`: separacion entre app y ETL.
- `docs/operacion.md`: criterios operativos, privacidad y despliegue.
