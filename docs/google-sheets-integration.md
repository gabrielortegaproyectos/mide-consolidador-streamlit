# Integracion con Google Sheets

## Objetivo

Documentar como se configura y opera la integracion online con Google Sheets,
distinguiendo claramente:

- la base maestra `BASE_ESTRUCTURAL`, que recibe solo el consolidado;
- el log `LOG_PUBLICACIONES`, que guarda la auditoria de cada intento de
  publicacion;
- la revision humana obligatoria antes de modificar la base maestra.

## Componentes de la integracion

### `BASE_ESTRUCTURAL`

- Es la hoja maestra online.
- Debe conservar solo las columnas del consolidado.
- No debe recibir columnas tecnicas ni metadatos de publicacion.

### `LOG_PUBLICACIONES`

- Es la hoja de auditoria.
- Registra que operacion se ejecuto, cuando, sobre que carrera/facultad y con
  que resultado.
- Permite reconstruir la trazabilidad operativa sin contaminar
  `BASE_ESTRUCTURAL`.

### Service account

- La app usa una **service account** para acceder a Google Sheets.
- Las credenciales reales viven en Streamlit Community Cloud o en un entorno
  local autorizado.
- El JSON de credenciales y `.streamlit/secrets.toml` **no deben versionarse**.

## Configuracion de secretos

### Donde viven los secretos reales

- Produccion: en los secrets de Streamlit Community Cloud.
- Local autorizado: en `.streamlit/secrets.toml`, fuera de Git.
- Repositorio: solo debe incluir `.streamlit/secrets.toml.example` con
  placeholders.

### Estructura esperada

```toml
[google_sheets]
base_spreadsheet_id = "REEMPLAZAR_CON_ID_BASE"
base_worksheet_name = "BASE_ESTRUCTURAL"
log_spreadsheet_id = "REEMPLAZAR_CON_ID_LOG"
log_worksheet_name = "LOG_PUBLICACIONES"

[gcp_service_account]
type = "service_account"
project_id = "reemplazar-con-project-id"
private_key_id = "reemplazar-con-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nREEMPLAZAR\n-----END PRIVATE KEY-----\n"
client_email = "reemplazar-con-service-account@proyecto.iam.gserviceaccount.com"
client_id = "reemplazar-con-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/reemplazar"
```

No incluir valores privados ni credenciales reales en documentacion,
commits, capturas ni issues.

## Compartir las Google Sheets con la service account

La integracion no funcionara aunque los secrets existan si las hojas no estan
compartidas con la service account correcta.

Pasos:

1. Identificar el `client_email` de la service account configurada.
2. Abrir la Google Sheet de `BASE_ESTRUCTURAL`.
3. Compartirla con ese `client_email` con permiso **Editor**.
4. Repetir el mismo paso para la Google Sheet de `LOG_PUBLICACIONES`.
5. Verificar que los nombres de hoja coincidan exactamente con los configurados
   en secrets.

## Comportamiento operativo de la app

- Si faltan secrets obligatorios, la publicacion online se deshabilita.
- En ese caso, la descarga local sigue funcionando.
- Si la integracion esta habilitada, la app consulta `BASE_ESTRUCTURAL`, clasifica
  el caso y exige una decision manual: `append`, `replace` o `cancel`.
- Si la decision es `replace`, la app exige escribir exactamente `REEMPLAZAR`
  antes de publicar.

## Semantica de escritura

### Append

`append` agrega una carrera nueva cuando la clave `FACULTAD + CARRERA` no existe
previamente en `BASE_ESTRUCTURAL`.

### Replace

`replace` elimina el bloque existente de esa misma clave y escribe el nuevo
bloque completo.

### Cancel

`cancel` no escribe en Google Sheets. Solo deja constancia en la interfaz de que
la publicacion fue cancelada por el usuario.

## Reglas de revision humana

No se debe publicar online si ocurre cualquiera de estas condiciones:

- `FACULTAD` esta vacia;
- `CARRERA` esta vacia;
- existe posible duplicado o conflicto de facultad;
- hay advertencias del pipeline que no fueron revisadas;
- el operador no tiene certeza de que la accion sugerida coincide con el caso
  real.

## Contrato de datos

### `BASE_ESTRUCTURAL`

- Debe compartir exactamente el mismo esquema del Excel consolidado.
- Si faltan columnas o aparecen columnas sobrantes, la publicacion debe
  bloquearse.
- La hoja no debe incluir campos tecnicos como `publication_id`, `warnings` o
  `error_message`.

### `LOG_PUBLICACIONES`

La auditoria usa estos campos:

```text
publication_id
run_id
published_at
operation_type
base_spreadsheet_id
base_worksheet_name
log_spreadsheet_id
log_worksheet_name
facultad
carrera
career_key
rows_before
rows_replaced
rows_published
pipeline_version
source_pdf_name
source_matrix_name
source_pdf_trace
source_matrix_trace
validation_status
warnings
result_status
error_message
```

Con estos campos se puede saber:

- que operacion se ejecuto;
- cuando se ejecuto;
- sobre que carrera y facultad;
- cuantas filas se publicaron;
- cuantas filas se reemplazaron;
- que version del pipeline intervino;
- si hubo advertencias o errores.

## Recuperacion y reversibilidad

### Que si permite el log

`LOG_PUBLICACIONES` permite identificar el intento o publicacion y entender su
impacto operativo.

### Que no reemplaza el log

El log no sustituye un respaldo del Excel consolidado. Para recuperar contenido
se necesita el archivo descargado localmente o una corrida valida equivalente.

### Recuperacion recomendada

1. Buscar el `publication_id` o la fecha en `LOG_PUBLICACIONES`.
2. Confirmar `operation_type`, `rows_published`, `rows_replaced` y
   `result_status`.
3. Revisar `error_message` y `warnings` si existieron observaciones.
4. Verificar manualmente el estado final de `BASE_ESTRUCTURAL`.
5. Si se necesita revertir, volver a publicar una version correcta mediante el
   flujo normal y con revision humana completa.

## Resolucion de problemas

### La integracion online no aparece

- Verificar que existan las secciones `google_sheets` y `gcp_service_account` en
  secrets.
- Confirmar que no falten claves obligatorias.
- Si faltan secrets, la app debe seguir permitiendo la descarga local.

### Faltan secrets

- Completar los valores en Streamlit Community Cloud o en un
  `.streamlit/secrets.toml` local autorizado.
- No subir el archivo al repositorio.

### La app no puede acceder a Google Sheets

- Verificar que ambas Sheets esten compartidas con la service account como
  **Editor**.
- Revisar que los spreadsheet IDs y worksheet names coincidan con la
  configuracion.
- Confirmar que Google Sheets API y Google Drive API esten habilitadas para esa
  service account.

### La carrera o facultad aparece vacia

- No publicar.
- Corregir insumos y repetir el ETL.
- Si el problema persiste, escalar antes de tocar la base maestra.

### La app detecta posible duplicado

- Tratar el caso como revision manual obligatoria.
- Comparar carrera, facultad y filas actuales.
- Si no hay certeza, elegir `cancel`.

### Google Sheets falla durante la publicacion

- Revisar el resumen post-publicacion.
- Consultar `LOG_PUBLICACIONES` para confirmar si la auditoria quedo escrita.
- Verificar manualmente `BASE_ESTRUCTURAL` antes de reintentar.

### La publicacion fue cancelada

- No hubo modificacion online.
- Ajustar insumos o decision operativa y volver a intentar solo cuando la
  revision este completa.

### Error de dependencias en Streamlit Cloud o `uv.lock`

- Si el deploy falla antes de levantar la app, el problema es de build y no de
  Google Sheets.
- Revisar dependencias declaradas y artefactos de lock antes de tocar secrets o
  permisos de las hojas.

## Prueba con Sheet sandbox

Toda prueba real debe hacerse primero con copias sandbox de `BASE_ESTRUCTURAL` y
`LOG_PUBLICACIONES`.

- Configurar secrets apuntando a esas copias.
- Compartir las sandbox con la misma service account como **Editor**.
- Probar al menos `append`, `replace` y `cancel`.
- Confirmar que `LOG_PUBLICACIONES` registre la operacion correcta.
- Confirmar que `BASE_ESTRUCTURAL` no reciba columnas tecnicas.

La guia paso a paso de QA manual vive en `docs/qa.md`.
