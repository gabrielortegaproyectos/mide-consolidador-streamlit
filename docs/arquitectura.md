# Arquitectura

La aplicacion Streamlit es una capa de interfaz y operacion sobre el ETL MIDE.
No debe duplicar parsers, reglas de merge, normalizacion RA ni enriquecimiento
de codigos.

```text
Usuario
  -> Streamlit
  -> app/services/pipeline_runner.py
  -> tributacion.pipeline.run_pipeline_result
  -> artefactos descargables
```

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

## Decisiones pendientes

- Destino de despliegue.
- Politica de persistencia o eliminacion de archivos cargados.

