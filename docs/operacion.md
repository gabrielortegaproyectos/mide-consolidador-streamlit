# Operacion

## Objetivo

Este documento explica el flujo operativo completo para:

- generar el consolidado desde PDF + matriz Excel;
- descargar el Excel localmente sin tocar Google Sheets;
- publicar online en `BASE_ESTRUCTURAL` solo despues de una revision humana
  explicita;
- consultar `LOG_PUBLICACIONES` para trazabilidad y recuperacion operativa.

## Descarga local vs actualizacion online

### Descarga local

- Descarga el Excel generado en la sesion actual.
- **No modifica Google Sheets**.
- Es la opcion segura para respaldo manual, revision externa o recuperacion.

### Actualizacion online

- Escribe filas en `BASE_ESTRUCTURAL`.
- Registra trazabilidad en `LOG_PUBLICACIONES`.
- Requiere secretos configurados y revision humana completa.
- **No debe ejecutarse sin revisar antes `CARRERA` y `FACULTAD`.**

## Protocolo paso a paso de publicacion online

1. Cargar el PDF del plan de estudio.
2. Cargar la matriz Excel de tributacion.
3. Ejecutar el ETL desde la app.
4. Revisar el resumen de validacion de la carrera.
5. Revisar la previsualizacion del consolidado.
6. Descargar el Excel local si se necesita respaldo manual antes de publicar.
7. Ir a la seccion **Publicacion online en Google Sheets**.
8. Confirmar que `CARRERA` y `FACULTAD` detectadas son correctas.
9. Revisar las advertencias del pipeline; si no se entienden o no cuadran con los
   insumos, detenerse.
10. Revisar la deteccion en `BASE_ESTRUCTURAL`.
11. Elegir una accion:
    - **append**: agregar como nueva carrera;
    - **replace**: reemplazar la carrera existente;
    - **cancel**: no publicar nada.
12. Si la accion es `replace`, escribir exactamente `REEMPLAZAR` para habilitar la
    operacion.
13. Ejecutar la publicacion online.
14. Revisar el resumen post-publicacion y, si hace falta trazabilidad adicional,
    consultar `LOG_PUBLICACIONES`.

## Checklist de revision humana

No publicar online hasta poder marcar todo lo siguiente:

- [ ] La carrera detectada corresponde al PDF y a la matriz cargados.
- [ ] La facultad detectada es correcta.
- [ ] La previsualizacion del consolidado tiene sentido.
- [ ] Las advertencias fueron revisadas.
- [ ] La accion append/replace/cancel corresponde al caso real.
- [ ] En caso de replace, se entiende que se sobrescribira el bloque existente.
- [ ] El Excel local fue descargado si se necesita respaldo previo.

## Definiciones operativas

### Append

Agregar una carrera nueva a `BASE_ESTRUCTURAL` cuando la clave `FACULTAD +
CARRERA` no existe en la base online.

### Replace

Reemplazar completamente el bloque de filas ya existente para la misma clave
`FACULTAD + CARRERA`.

### Cancel

No publicar nada online ni modificar Google Sheets.

## Cuando publicar, reemplazar o cancelar

### Publicar con `append`

Usar `append` cuando la deteccion online indica **Nueva carrera** y no existe una
coincidencia valida en `BASE_ESTRUCTURAL`.

### Publicar con `replace`

Usar `replace` solo cuando la deteccion online confirma que la misma carrera ya
existe y se desea sobrescribir por completo su bloque actual.

Antes de confirmar `replace`:

- revisar cuantas filas actuales se reemplazaran;
- revisar cuantas filas nuevas se publicaran;
- confirmar que el Excel local ya fue descargado si se necesita respaldo.

### Cancelar

Cancelar cuando ocurra cualquiera de estos casos:

- `CARRERA` o `FACULTAD` estan vacias o mal detectadas;
- existe posible duplicado o conflicto de facultad;
- hay advertencias del pipeline no resueltas;
- no se entiende el impacto del reemplazo;
- Google Sheets devuelve un error o no hay certeza de si la publicacion es
  segura.

## Que hacer si carrera o facultad estan mal detectadas

1. No publicar online.
2. Descargar el Excel local solo si sirve para revision interna.
3. Revisar que el PDF y la matriz correspondan a la misma carrera.
4. Verificar encabezados, hoja esperada y consistencia de los insumos.
5. Ejecutar nuevamente el ETL con insumos corregidos.
6. Si el problema persiste, escalar la revision antes de tocar la base maestra.

## Que hacer si hay advertencias del pipeline

- Abrir y leer la seccion **Advertencias del pipeline**.
- Verificar si la advertencia afecta metadata, conteos o consistencia del
  consolidado.
- Si la advertencia no puede explicarse con seguridad, elegir `cancel`.
- Publicar solo cuando las advertencias hayan sido revisadas y aceptadas
  explicitamente.

## Resultado post-publicacion

Despues de publicar, la app muestra un resumen con al menos:

- tipo de operacion;
- facultad y carrera afectadas;
- filas publicadas;
- filas reemplazadas;
- `publication_id` si existe;
- mensaje de error u observacion si aplica.

Si el resultado indica `cancelled`, `blocked`, `failed`,
`published_without_audit` o `failed_without_audit`, detenerse y revisar el caso
antes de reintentar.

## Reversibilidad y recuperacion

### Regla base

`LOG_PUBLICACIONES` ayuda a reconstruir **que se intento o que se publico**, pero
no reemplaza un respaldo del Excel consolidado. Por eso conviene descargar el
archivo local antes de un `replace` o de cualquier publicacion sensible.

### Recuperar informacion desde el log

Buscar en `LOG_PUBLICACIONES` por:

- `publication_id`;
- `published_at`;
- `operation_type`;
- `facultad` y `carrera`;
- `rows_published` y `rows_replaced`;
- `pipeline_version`;
- `warnings`;
- `result_status` y `error_message`.

Con esos campos se puede determinar que operacion corrio, cuando corrio y si la
escritura termino bien o con observaciones.

### Si Google Sheets falla

1. No repetir la accion de inmediato varias veces.
2. Revisar el resumen post-publicacion en la app.
3. Consultar `LOG_PUBLICACIONES` para verificar si hubo registro de la operacion.
4. Confirmar manualmente en `BASE_ESTRUCTURAL` si el bloque quedo sin cambios,
   agregado o reemplazado.
5. Si se requiere correccion, usar el Excel local de respaldo o una corrida
   validada para volver a publicar de forma controlada.

### Si se publico mal con `append`

- Identificar la publicacion en `LOG_PUBLICACIONES`.
- Confirmar cuantas filas se agregaron y para que clave `FACULTAD + CARRERA`.
- Corregir el consolidado y ejecutar una accion controlada; no improvisar cambios
  directos sin trazabilidad.

### Si se publico mal con `replace`

- Recuperar el Excel local descargado antes de publicar, o la ultima version
  validada de esa carrera.
- Confirmar en `LOG_PUBLICACIONES` cuando ocurrio el reemplazo y cuantas filas
  afecto.
- Re-publicar la version correcta como `replace` solo despues de revisar de nuevo
  carrera, facultad y advertencias.

## Pruebas en sandbox

Las pruebas automatizadas no escriben en Google Sheets reales. Para una prueba
real de publicacion usar copias sandbox de `BASE_ESTRUCTURAL` y
`LOG_PUBLICACIONES`, siguiendo `docs/qa.md`.

## Politica de privacidad y archivos

Decision vigente para el MVP: **no persistencia por defecto**.

La app procesa datos institucionales cargados por el usuario, por lo que no debe
conservar PDFs, Excels ni artefactos generados despues de preparar la descarga
de la sesion.

### Archivos subidos

- Los PDFs y Excels se escriben solo en carpetas temporales de la corrida.
- No se guardan para auditoria en disco ni se versionan en Git.
- La auditoria de una corrida se realiza con el ZIP descargado por el usuario.
- El ZIP incluye nombre, tamaño y hash SHA-256 de cada archivo subido, pero no
  incluye rutas locales.

### Artefactos generados

- El ETL genera artefactos en un directorio temporal controlado.
- La app lee esos artefactos, arma el ZIP en memoria y elimina el directorio
  temporal.
- Si el ETL falla, el runner elimina el directorio de salida antes de devolver
  el error controlado.
- Si falla la preparacion de la descarga, la UI limpia el directorio de salida
  antes de informar el problema.

### Limites de tamaño

- Limite por archivo cargado: 50 MB.
- Si un archivo supera el limite, la UI bloquea validacion y procesamiento.
- El objetivo es evitar cargas accidentales con anexos, imagenes o insumos que
  no son necesarios para una corrida curricular.

### Logs y mensajes publicos

- La app no registra contenido de archivos cargados.
- Los mensajes visibles para usuarios no deben exponer rutas locales, trazas ni
  detalles tecnicos del servidor.
- Los errores controlados se muestran con una explicacion accionable.
- Los errores inesperados se muestran como mensaje generico de procesamiento.

### Acceso y autenticacion

- La app esta pensada para usuarios autorizados del proyecto MIDE.
- Para el MVP se usara Streamlit Community Cloud con acceso privado/restringido.
- La configuracion de despliegue y acceso queda documentada en
  `docs/despliegue.md`.
- No se deben agregar secretos para instalar el ETL: el paquete `tributacion`
  esta vendorizado en este repositorio.

### Continuidad operativa

- Si se requiere auditoria historica, debe almacenarse fuera de la app usando el
  ZIP descargado, con control de acceso institucional.
- Cualquier cambio hacia persistencia en servidor requiere nuevo issue y una
  decision explicita sobre ubicacion, plazo de retencion y responsables.

## Despliegue

El despliegue objetivo inicial es Streamlit Community Cloud.

Para evitar secretos de instalacion, la app incluye una instantanea vendorizada
del paquete `tributacion` y sus catalogos livianos. La plataforma solo necesita
instalar las dependencias declaradas en `pyproject.toml`; no necesita leer el
repositorio privado `mide-tributacion-curricular` durante el build.

La decision completa y el commit fuente se documentan en `docs/etl-vendor.md`.

La decision de despliegue y las instrucciones minimas se documentan en
`docs/despliegue.md`.
