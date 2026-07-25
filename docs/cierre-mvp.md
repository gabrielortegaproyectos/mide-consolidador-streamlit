# Cierre MVP Streamlit MIDE

## Estado

El MVP de `mide-consolidador-streamlit` queda funcional para una corrida por
carrera:

```text
PDF plan de estudio + matriz Excel + metadatos -> ETL vendorizado -> ZIP auditable
```

URL operativa del MVP:

```text
https://mide-etl.streamlit.app/
```

Repositorio operativo del despliegue:

```text
gabrielortegaproyectos/mide-consolidador-streamlit
```

## Criterios de cierre del issue paraguas

| Criterio | Estado | Evidencia |
| --- | --- | --- |
| Procesa una carrera por vez con 1 PDF, 1 Excel y metadatos | Cumplido | UI principal y `app/services/pipeline_runner.py` |
| Ejecuta el ETL sin copiar logica de parsers/merge en la UI | Cumplido | `run_uploaded_pipeline` consume `run_pipeline_result` |
| Descarga Excel final, CSV diagnosticos y resumen en ZIP | Cumplido | `app/services/delivery_package.py` |
| Informa errores en lenguaje claro | Cumplido | `app/services/message_catalog.py` y `app/services/privacy.py` |
| Incluye manual breve dentro de la UI | Cumplido | `app/services/manual.py` y `render_manual` |
| Declara politica de no persistencia | Cumplido | `docs/operacion.md` |
| Define despliegue y acceso MVP con contrasena compartida | Cumplido | `docs/despliegue.md`, `app/services/auth.py` y `app/ui/auth.py` |
| Incluye QA publico reproducible | Cumplido | `docs/qa.md` y suite `pytest` |
| Incorpora identidad visual UBO autorizada | Cumplido | `docs/branding.md` y `app/static/logo_ubo.webp` |

## Hitos cerrados

- #2 Bootstrap del repositorio Streamlit.
- #3 API publica del ETL para consumo desde apps.
- #4 Estrategia de dependencia privada/vendor.
- #5 Adaptador `pipeline_runner`.
- #6 Validacion previa del Excel.
- #7 Catalogo de mensajes de error.
- #8 Panel de resumen de validacion.
- #9 UI principal de carga, procesamiento y descarga.
- #10 Branding UBO y lineamientos visuales.
- #11 Manual integrado.
- #12 ZIP auditable y `resumen_validacion.md`.
- #13 Politica de privacidad y temporales.
- #14 Despliegue y acceso.
- #15 Smoke tests, fixtures y QA.

## Verificacion publica

Comandos esperados en clon limpio:

```bash
uv run --group dev pytest
uv run --group dev ruff check app tests tributacion
uv run python -c "import app.main; print('app import ok')"
```

La prueba con insumos institucionales reales debe seguir el checklist de
`docs/qa.md` y usar solo archivos autorizados.

## Limitaciones conocidas

- El ETL esta vendorizado desde `mide-tributacion-curricular`; cualquier cambio
  funcional del pipeline debe hacerse primero en el repo canonico y luego
  actualizar la instantanea.
- El despliegue gratuito operativo vive en una cuenta personal de GitHub, no en
  la organizacion.
- La app no persiste auditoria historica en servidor; la evidencia queda en el
  ZIP descargado.
- El acceso/restriccion depende de Streamlit Community Cloud y de mantener
  configurado `[auth].password` como contrasena compartida en Secrets.
- No hay tests publicos con PDFs/matrices institucionales reales por politica de
  datos.

## Impacto en informe final

Debe reflejarse en el informe final del proyecto MIDE como componente operativo
de apoyo al flujo:

```text
insumos -> ETL -> validacion -> paquete auditable -> operacion
```

Evidencias sugeridas:

- URL del MVP y repositorio operativo.
- Politica de no persistencia y manejo de datos.
- Barrera de acceso restringido con contrasena compartida, sesion activa y cierre
  de sesion.
- Ejemplo de `resumen_validacion.md` generado.
- Checklist de QA con insumo autorizado.
- Limitacion del vendor ETL y despliegue gratuito en cuenta personal.
