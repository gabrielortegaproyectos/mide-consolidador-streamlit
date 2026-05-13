# Operacion

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
- Mientras se use Streamlit Community Cloud, el acceso debe restringirse desde
  la configuracion de despliegue o por distribucion controlada del enlace.
- No se deben agregar secretos para instalar el ETL: el paquete `tributacion`
  esta vendorizado en este repositorio.

### Continuidad operativa

- Si se requiere auditoria historica, debe almacenarse fuera de la app usando el
  ZIP descargado, con control de acceso institucional.
- Cualquier cambio hacia persistencia en servidor requiere nuevo issue y una
  decision explicita sobre ubicacion, plazo de retencion y responsables.

## Despliegue pendiente

El despliegue objetivo inicial es Streamlit Community Cloud.

Para evitar secretos de instalacion, la app incluye una instantanea vendorizada
del paquete `tributacion` y sus catalogos livianos. La plataforma solo necesita
instalar las dependencias declaradas en `pyproject.toml`; no necesita leer el
repositorio privado `mide-tributacion-curricular` durante el build.

La decision completa y el commit fuente se documentan en `docs/etl-vendor.md`.

Queda por cerrar el mecanismo final de autenticacion/restriccion del despliegue
en el issue correspondiente.

