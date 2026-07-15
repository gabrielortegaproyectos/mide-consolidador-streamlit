# MIDE Consolidador Streamlit

Aplicacion Streamlit para que usuarios autorizados carguen un PDF de plan de
estudio y una matriz Excel de tributacion curricular, ejecuten el pipeline ETL
MIDE, revisen una previsualizacion y descarguen el consolidado de la carrera.

Este repositorio no reemplaza `mide-tributacion-curricular`. Para el despliegue
inicial en Streamlit Community Cloud incluye una instantanea vendorizada del
paquete `tributacion`, documentada en `docs/etl-vendor.md`, y concentra el
desarrollo propio en experiencia de usuario, manejo de archivos, validaciones,
trazabilidad y descarga de resultados.

## Estado

MVP funcional. La app carga insumos, valida la matriz dentro del procesamiento,
ejecuta el ETL vendorizado, muestra resumen de validacion, previsualiza algunas
filas del consolidado y permite distinguir entre descarga local segura y
publicacion online en Google Sheets con revision humana explicita.

## Flujo operativo resumido

1. Cargar PDF de plan de estudio.
2. Cargar matriz Excel de tributacion.
3. Ejecutar pipeline ETL MIDE. La validacion de insumos ocurre dentro de este paso.
4. Revisar el check de validacion, resumen, alertas y previsualizacion.
5. Descargar el consolidado Excel si se necesita respaldo o revision local.
6. Si la integracion online esta habilitada, completar la revision humana.
7. Elegir `append`, `replace` o `cancel` segun la deteccion en `BASE_ESTRUCTURAL`.
8. Publicar online solo cuando `CARRERA`, `FACULTAD` y advertencias ya fueron revisadas.

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

## Acceso restringido

La app queda bloqueada hasta ingresar una contraseña compartida. El
mecanismo:

- lee la contraseña esperada desde Streamlit Secrets (`[auth].password`),
  sin valor por defecto;
- no renderiza encabezado, pestañas, manual, integraciones ni panel de
  carga hasta autenticar la sesión;
- mantiene el acceso solo durante la sesión activa del navegador;
- ofrece una acción `Cerrar sesión` que vuelve a bloquear la app;
- se bloquea de forma segura si el secreto no está configurado.

Configuracion, verificacion y rotacion del secreto en
`docs/despliegue.md`.

## Privacidad operativa

La decision vigente es no persistir archivos en servidor: uploads y artefactos
se procesan en temporales y la descarga principal queda disponible en memoria
solo durante la sesion. Ver `docs/operacion.md`.

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
- `docs/operacion.md`: protocolo operativo, descarga local, publicacion online, revision humana y recuperacion.
- `docs/google-sheets-integration.md`: secretos, service account, contrato de `BASE_ESTRUCTURAL` y `LOG_PUBLICACIONES`, y troubleshooting.
- `docs/qa.md`: smoke tests, sandbox para publicacion online y checklist manual autorizado.
- `docs/branding.md`: logo autorizado, paleta y reglas visuales basicas.
- `docs/cierre-mvp.md`: criterios cumplidos, limitaciones y cierre del MVP.
