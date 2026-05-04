# Arquitectura

La aplicacion Streamlit es una capa de interfaz y operacion sobre el ETL MIDE.
No debe duplicar parsers, reglas de merge, normalizacion RA ni enriquecimiento
de codigos.

```text
Usuario
  -> Streamlit
  -> app/services/pipeline_runner.py
  -> tributacion.pipeline.run_pipeline
  -> artefactos descargables
```

## Repositorios

- `mide-tributacion-curricular`: ETL, contratos de salida, validaciones,
  parsers, tests y documentacion tecnica.
- `mide-consolidador-streamlit`: carga de archivos, mensajes, UI, manual,
  operacion, descarga y seguridad de sesion.

## Decisiones pendientes

- Dependencia Git privada, paquete interno o submodulo.
- Destino de despliegue.
- Politica de persistencia o eliminacion de archivos cargados.

