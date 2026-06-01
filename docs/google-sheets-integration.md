# Integracion con Google Sheets

## Objetivo

Definir el contrato de datos para publicar el consolidado generado por la app
Streamlit hacia Google Sheets sin concatenacion manual y sin alterar la
estructura actual del Excel consolidado.

## Alcance de este contrato

Este documento define:

- la Google Sheet maestra y la hoja destino principal;
- la Google Sheet separada para auditoria de publicaciones;
- la estructura esperada de `BASE_ESTRUCTURAL`;
- la clave funcional para detectar carreras nuevas o existentes;
- la semantica de `append` y `replace`;
- la politica ante columnas faltantes o sobrantes;
- los campos de trazabilidad que deben registrarse por publicacion.

Este documento define el contrato de datos y la configuracion segura necesaria
para preparar la integracion con Google Sheets. La lectura/escritura real, la
UI final de publicacion y las confirmaciones interactivas siguen fuera de
alcance.

## Configuracion vigente

```toml
[google_sheets]
base_spreadsheet_id = "1MBeZLGF_z37kbu32g-WiQ8Q0_ZyY9QGyGJY5tReIDdY"
base_worksheet_name = "BASE_ESTRUCTURAL"

log_spreadsheet_id = "1Zw6I3sxiM618TRnmP04d0016to_vjKXITvdOBc8z8Tg"
log_worksheet_name = "LOG_PUBLICACIONES"
```

## Configuracion segura en Streamlit

El repositorio ahora incluye:

- dependencias `gspread` y `google-auth`;
- un ejemplo seguro en `.streamlit/secrets.toml.example`;
- deteccion de integracion habilitada/deshabilitada desde `st.secrets`;
- construccion de credenciales de service account solo cuando los secrets
  existen.

### Secrets esperados

La estructura esperada en Streamlit es:

```toml
[google_sheets]
base_spreadsheet_id = "REEMPLAZAR_CON_SPREADSHEET_ID_BASE"
base_worksheet_name = "BASE_ESTRUCTURAL"
log_spreadsheet_id = "REEMPLAZAR_CON_SPREADSHEET_ID_LOG"
log_worksheet_name = "LOG_PUBLICACIONES"

[gcp_service_account]
type = "service_account"
project_id = "reemplazar-con-project-id"
private_key_id = "reemplazar-con-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nREEMPLAZAR_CON_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "reemplazar-con-service-account@proyecto.iam.gserviceaccount.com"
client_id = "reemplazar-con-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/reemplazar-con-service-account%40proyecto.iam.gserviceaccount.com"
```

### Pasos externos requeridos

1. Crear o reutilizar una service account en Google Cloud.
2. Habilitar **Google Sheets API**.
3. Habilitar **Google Drive API** para el acceso administrado por `gspread`.
4. Guardar el JSON y copiar sus campos a secrets locales o a Streamlit
   Community Cloud.
5. Compartir como **Editor** ambas Google Sheets con el `client_email` de la
   service account.

### Service account operativa del proyecto

Actualmente, la service account compartida para el proyecto es:

```text
mide-sheets-writer@mide-consolidador-sheets.iam.gserviceaccount.com
```

Debe mantenerse con permiso **Editor** en:

- `BASE_ESTRUCTURAL` (`1MBeZLGF_z37kbu32g-WiQ8Q0_ZyY9QGyGJY5tReIDdY`);
- `LOG_PUBLICACIONES` (`1Zw6I3sxiM618TRnmP04d0016to_vjKXITvdOBc8z8Tg`).

### Regla de seguridad

`.streamlit/secrets.toml` nunca debe subirse al repositorio. Solo se versiona
`.streamlit/secrets.toml.example` con placeholders.

## Estructura de hojas

### 1. Base maestra: `BASE_ESTRUCTURAL`

- Vive en la Google Sheet identificada por `base_spreadsheet_id`.
- Es la fuente online principal de la base estructural consolidada.
- Debe mantener **exactamente** la misma estructura del Excel consolidado que
  genera la app Streamlit.
- No debe incluir columnas tecnicas de publicacion dentro de esta hoja.

Columnas esperadas:

```text
GRADO
FACULTAD
ESCUELA
CARRERA
TRIBUTACIÓN
CICLO
N°AR
ÁMBITO DE REALIZACIÓN
DESCRIPCIÓN AR
N° RA
NOMBRE RA
DESCRIPCIÓN RA
NIVEL DE LOGRO
DESCRIPCIÓN DEL NIVEL DE LOGRO
ÁREA DE FORMACIÓN
AÑO
NIVEL O SEMESTRE
CÓDIGO DEL CURSO
ASIGNATURA
CÓDIGO PRERREQUISITO
PRERREQUISITO
N° DE CRÉDITOS
HORAS CR TOTALES
HORAS DE DOCENCIA DIRECTA
DD TEÓRICAS
DD AYUDANTÍA
DD TALLER
DD CAMPOS CLÍNICOS
DD SIMULACIÓN
DD LABORATORIO
DD PRO COLABORATIVO
DD SALIDAS A TERRENO
HORAS DE TRABAJO AUTÓNOMO
MODALIDAD
INDICADORES DE LOGRO POR ASIGNATURA
PRODUCTOS DE APRENDIZAJE POR ASIGNATURA
```

### 2. Auditoria: `LOG_PUBLICACIONES`

- Vive en una Google Sheet separada identificada por `log_spreadsheet_id`.
- Registra la trazabilidad de cada publicacion.
- No modifica ni extiende la estructura de `BASE_ESTRUCTURAL`.

Columnas sugeridas del log:

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
validation_status
warnings
result_status
error_message
```

## Clave funcional de carrera

La clave funcional para detectar si una carrera ya existe en la base online es:

```text
FACULTAD + CARRERA
```

### Regla de normalizacion

La comparacion no debe usar una normalizacion paralela o incompatible con el
ETL. La implementacion futura debe reutilizar o extraer una utilidad compatible
con `_norm_key` de `tributacion/ciclo_catalog.py`.

Como minimo, la normalizacion debe:

- convertir a minusculas;
- quitar tildes;
- compactar espacios internos;
- recortar espacios al inicio y al final.

### Casos bloqueantes

La publicacion debe bloquearse y pedir revision humana cuando:

- `FACULTAD` este vacia; o
- `CARRERA` este vacia.

## Reglas de escritura

### Cuando una publicacion es `append`

La publicacion es `append` solo cuando la clave funcional normalizada
`FACULTAD + CARRERA` **no existe** en `BASE_ESTRUCTURAL`.

En ese caso, la implementacion agrega las filas del nuevo consolidado al final
de la base maestra y registra la operacion en `LOG_PUBLICACIONES`.

### Cuando una publicacion es `replace`

La publicacion es `replace` cuando la clave funcional normalizada
`FACULTAD + CARRERA` **ya existe** en `BASE_ESTRUCTURAL`.

Reemplazar una carrera significa sobrescribir completamente el bloque de filas
existente para esa combinacion:

1. identificar todas las filas actuales de la carrera/facultad;
2. eliminar o reemplazar ese bloque completo;
3. escribir las filas nuevas del consolidado;
4. registrar la operacion en `LOG_PUBLICACIONES`.

No se define en esta etapa una publicacion con versiones historicas dentro de la
base maestra. La trazabilidad historica queda en el log de publicaciones.

## Politica de esquema y validacion previa

Antes de publicar, la app debe validar que el consolidado a publicar y
`BASE_ESTRUCTURAL` compartan exactamente el mismo esquema de columnas.

### Columnas faltantes

Si al consolidado le falta una o mas columnas esperadas de `BASE_ESTRUCTURAL`,
la publicacion se bloquea. No se deben crear columnas faltantes en linea ni
rellenar automaticos silenciosos.

### Columnas sobrantes

Si el consolidado trae columnas adicionales que no existen en
`BASE_ESTRUCTURAL`, la publicacion tambien se bloquea. No se deben publicar
columnas extra ni extender la hoja maestra sin actualizar antes el contrato.

### Regla general

Cualquier diferencia de esquema entre el consolidado y `BASE_ESTRUCTURAL`
requiere revision del ETL o actualizacion explicita del contrato de datos antes
habilitar publicacion online.

## Trazabilidad requerida

`BASE_ESTRUCTURAL` no almacena columnas tecnicas de trazabilidad. Esos datos se
registran por publicacion en `LOG_PUBLICACIONES`.

Campos de trazabilidad requeridos por operacion:

- `publication_id`: identificador unico de la publicacion.
- `run_id`: identificador de la corrida ETL origen.
- `published_at`: fecha/hora efectiva de publicacion.
- `operation_type`: `append` o `replace`.
- `base_spreadsheet_id`: destino de base maestra.
- `base_worksheet_name`: hoja destino de base maestra.
- `log_spreadsheet_id`: destino del log.
- `log_worksheet_name`: hoja destino del log.
- `facultad`: valor original publicado.
- `carrera`: valor original publicado.
- `career_key`: clave funcional normalizada usada para comparar.
- `rows_before`: filas existentes antes de publicar para esa clave.
- `rows_replaced`: filas eliminadas o sobrescritas.
- `rows_published`: filas escritas desde el consolidado.
- `pipeline_version`: version del pipeline o release aplicado.
- `source_pdf_name`: nombre del PDF origen.
- `source_matrix_name`: nombre de la matriz origen.
- `validation_status`: resultado de validaciones previas.
- `warnings`: advertencias relevantes de la corrida.
- `result_status`: resultado final de la publicacion.
- `error_message`: detalle si la publicacion falla.

## Flujo esperado de publicacion

1. Ejecutar ETL y obtener consolidado con metadatos ya resueltos.
2. Validar que `FACULTAD` y `CARRERA` existan en todas las filas a publicar.
3. Normalizar `FACULTAD + CARRERA` con logica compatible con `_norm_key`.
4. Comparar la clave contra `BASE_ESTRUCTURAL`.
5. Si no existe, preparar `append`.
6. Si existe, preparar `replace` del bloque completo.
7. Validar igualdad exacta de esquema entre consolidado y base maestra.
8. Ejecutar escritura en la base maestra.
9. Registrar el resultado en `LOG_PUBLICACIONES`.

## Fuera de alcance

Este contrato no cubre aun:

- lectura o escritura real en Google Sheets;
- UI de publicacion y confirmacion de reemplazo;
- pruebas de integracion con Google Sheets.

Hasta implementar esos puntos en issues posteriores, no se debe publicar nada
online sin respetar este contrato de datos.
