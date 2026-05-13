# QA y smoke tests

## Pruebas publicas

Estas pruebas deben correr en un clon limpio sin PDFs ni matrices
institucionales:

```bash
uv run --group dev pytest
uv run --group dev ruff check app tests tributacion
uv run python -c "import app.main; print('app import ok')"
```

Cobertura publica actual:

- contrato vendorizado del ETL;
- `pipeline_runner` con mocks livianos;
- validacion previa de Excel;
- catalogo de mensajes de error;
- resumen de validacion;
- paquete ZIP auditable;
- politica de privacidad y mensajes publicos;
- smoke test de import del entrypoint Streamlit;
- smoke test de artefactos publicos que arma ZIP y `resumen_validacion.md`.

## Datos privados

Los tests automatizados del repositorio no deben requerir insumos privados.

Si se agrega una prueba con PDFs o matrices institucionales, debe:

- usar `@pytest.mark.private_data`;
- no subir insumos al repositorio;
- documentar donde restaurar los archivos autorizados;
- poder omitirse en un clon limpio.

## Checklist manual con insumo autorizado

Usar solo archivos institucionales autorizados para prueba.

1. Abrir la app local o el despliegue MVP.
2. Cargar PDF de plan de estudio.
3. Cargar matriz Excel con hoja `Asignaturas - RA`.
4. Completar carrera y metadatos disponibles.
5. Ejecutar `Validar insumos`.
6. Confirmar que errores estructurales se muestran sin rutas locales.
7. Ejecutar `Procesar carrera`.
8. Revisar estado final, conteos y asignaturas problematicas.
9. Descargar ZIP final.
10. Confirmar que el ZIP contiene:
    - `tributacion_final.xlsx`;
    - `tributacion_final_horas_pdf.csv`;
    - `tributacion_final_matching.csv`;
    - `tributacion_final_subject_codes_matching.csv`;
    - `resumen_validacion.md`.
11. Abrir `resumen_validacion.md` y confirmar:
    - fecha/hora de corrida;
    - metadatos ingresados;
    - nombre y hash SHA-256 de uploads;
    - version ETL;
    - advertencias y limitaciones.
12. Verificar que la app no muestra rutas locales ni trazas tecnicas.

## Smoke antes de deploy

Antes de mergear cambios de aplicacion:

```bash
uv run --group dev pytest
uv run --group dev ruff check app tests tributacion
uv run python -c "import app.main; print('app import ok')"
```

Cuando el cambio afecte UI o dependencias, levantar Streamlit localmente:

```bash
uv run streamlit run app/main.py
```

Luego abrir `http://localhost:8501` y comprobar que la primera pantalla carga.
