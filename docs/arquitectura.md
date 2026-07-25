# Arquitectura

La aplicacion Streamlit es una capa de interfaz y operacion sobre el ETL MIDE.
No debe duplicar parsers, reglas de merge, normalizacion RA ni enriquecimiento
de codigos.

```text
Usuario
  -> Streamlit
  -> app/ui/auth.py
  -> app/services/auth.py
  -> sesion autenticada
  -> app/services/pipeline_runner.py
  -> tributacion.pipeline.run_pipeline_result
  -> artefactos descargables
```

La barrera de autenticacion corre antes de renderizar el contenido principal. Si
la sesion no esta autenticada, la app no muestra encabezado, pestanas, manual,
integraciones ni panel de carga.

## Barrera de acceso

`app/ui/auth.py` contiene la interfaz de acceso restringido:

- muestra el formulario de contrasena solo cuando `[auth].password` esta
  configurado;
- informa bloqueo seguro cuando falta el secreto;
- marca la sesion como autenticada despues de una contrasena correcta;
- muestra **Cerrar sesion** en el sidebar cuando el usuario ya esta autenticado.

`app/services/auth.py` contiene la logica de autenticacion:

- lee la contrasena esperada desde Streamlit Secrets (`[auth].password`);
- descarta valores vacios y no define una contrasena por defecto;
- compara la contrasena ingresada con `hmac.compare_digest`;
- guarda solo el estado booleano de sesion (`mide_authenticated`);
- no persiste la contrasena ingresada ni la contrasena esperada.

El limite arquitectonico es intencional: esta barrera controla acceso a la UI
Streamlit del MVP, no reemplaza controles institucionales externos ni autorizacion
por usuario individual. La configuracion, verificacion y rotacion del secreto se
documentan en `docs/despliegue.md`; los casos QA estan en `docs/qa.md` y el
protocolo operativo en `docs/operacion.md`.

## Repositorios

- `mide-tributacion-curricular`: ETL, contratos de salida, validaciones,
  parsers, tests y documentacion tecnica.
- `mide-consolidador-streamlit`: carga de archivos, mensajes, UI, manual,
  operacion, descarga, seguridad de sesion y una instantanea vendorizada del
  paquete `tributacion` para despliegue sin secretos en Streamlit Community
  Cloud.

## Decision de dependencia ETL

La app usa vendor controlado del paquete `tributacion` en la raiz del repo. La
fuente canonica sigue siendo `mide-tributacion-curricular`; la instantanea y su
commit de origen se documentan en `docs/etl-vendor.md`.

Esta decision evita depender de un segundo repositorio privado durante el
despliegue en Streamlit Community Cloud.

## Decisiones vigentes

- El destino MVP es Streamlit Community Cloud.
- El acceso MVP combina visibilidad privada/restringida con contrasena
  compartida configurada en Secrets.
- La politica de datos es no persistir archivos cargados por defecto; ver
  `docs/operacion.md`.
