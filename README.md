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

MVP funcional. La app carga insumos, valida la matriz, ejecuta el ETL
vendorizado, muestra resumen de validacion y genera un ZIP auditable con
consolidado, diagnosticos y `resumen_validacion.md`.

## Flujo MVP

1. Cargar PDF de plan de estudio.
2. Cargar matriz Excel de tributacion.
3. Validar formato de insumos.
4. Ejecutar pipeline ETL MIDE.
5. Revisar resumen de validacion y alertas.
6. Descargar ZIP con Excel final, CSV diagnosticos y `resumen_validacion.md`.

Los metadatos administrativos y el ciclo curricular se resuelven desde el PDF,
la matriz y los catalogos JSON versionados; el usuario no debe ingresarlos en la
interfaz.

El manual de campos, insumos, salidas y advertencias vive en una pestaña
superior dentro de la misma pantalla de Streamlit.

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
uv run --group dev ruff check app tests tributacion
uv run python -c "import app.main; print('app import ok')"
```

## Privacidad operativa

La decision vigente es no persistir archivos en servidor: uploads y artefactos
se procesan en temporales, el ZIP se arma en memoria y la auditoria queda en el
paquete descargado por el usuario. Ver `docs/operacion.md`.

## Despliegue

El destino de MVP es Streamlit Community Cloud con acceso privado/restringido.
La app se despliega desde `main` usando `app/main.py` y no requiere secretos para
instalar el ETL vendorizado.

URL de MVP: <https://mide-etl.streamlit.app/>

El despliegue gratuito operativo usa el repo
`gabrielortegaproyectos/mide-consolidador-streamlit`. Ver
`docs/despliegue.md`.

## Documentacion

- `docs/roadmap.md`: ruta de implementacion y backlog inicial.
- `docs/arquitectura.md`: separacion entre app y ETL.
- `docs/etl-vendor.md`: decision de vendor controlado del ETL.
- `docs/despliegue.md`: decision de despliegue y acceso para el MVP.
- `docs/operacion.md`: criterios operativos, privacidad y despliegue.
- `docs/qa.md`: smoke tests, fixtures publicos y checklist manual autorizado.
- `docs/branding.md`: logo autorizado, paleta y reglas visuales basicas.
- `docs/cierre-mvp.md`: criterios cumplidos, limitaciones y cierre del MVP.
