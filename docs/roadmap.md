# Roadmap

## Fase 0 - Bootstrap

- Crear estructura base Streamlit.
- Documentar proposito, instalacion y comando local.
- Dejar una app minima ejecutable.

## Fase 1 - Contrato ETL

- Estabilizar API publica en `mide-tributacion-curricular`.
- Definir estrategia de dependencia privada.
- Implementar `pipeline_runner.py` para uploads temporales.

## Fase 2 - Validaciones y UX de errores

- Validar Excel antes de ejecutar el pipeline.
- Crear catalogo de mensajes para usuarios no tecnicos.
- Mostrar resumen de validacion y asignaturas problematicas.

## Fase 3 - UI, manual y branding

- Construir flujo principal de carga, metadatos, procesamiento y descarga.
- Integrar logo oficial UBO cuando exista asset autorizado.
- Agregar manual integrado y descripcion de campos extraidos.

## Fase 4 - Entrega, seguridad y deploy

- Generar ZIP de entrega.
- Definir politica de privacidad y limpieza de temporales.
- Decidir destino de despliegue y autenticacion.
- Agregar pruebas de smoke y QA de flujo completo.

