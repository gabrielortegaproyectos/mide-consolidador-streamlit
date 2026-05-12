# MIDE Consolidador Streamlit

Aplicacion Streamlit para que usuarios autorizados carguen un PDF de plan de
estudio y una matriz Excel de tributacion curricular, ejecuten el pipeline ETL
MIDE y descarguen consolidados, diagnosticos y un resumen de validacion.

Este repositorio no reemplaza `mide-tributacion-curricular`. Para el despliegue
inicial en Streamlit Community Cloud incluye una instantanea vendorizada del
paquete `tributacion`, documentada en `docs/etl-vendor.md`, y concentra el
desarrollo propio en experiencia de usuario, manejo de archivos, validaciones,
trazabilidad y descarga de resultados.

## Estado

Bootstrap inicial. La app ya puede importar el contrato publico vendorizado del
ETL mediante `tributacion.pipeline.run_pipeline_result`; el siguiente hito es
conectar `app/services/pipeline_runner.py` con uploads temporales.

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
- `docs/etl-vendor.md`: decision de vendor controlado del ETL.
- `docs/operacion.md`: criterios operativos, privacidad y despliegue.
