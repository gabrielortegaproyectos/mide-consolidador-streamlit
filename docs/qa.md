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
- previsualizacion y descarga del consolidado;
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
4. Ejecutar `Procesar carrera`.
5. Confirmar que la validacion integrada muestra check si la matriz es compatible.
6. Si hay errores estructurales, confirmar que se muestran sin rutas locales.
7. Revisar estado final, conteos y asignaturas problematicas.
8. Revisar la previsualizacion del consolidado.
9. Descargar `tributacion_final.xlsx`.
10. Confirmar que el Excel abre y conserva las columnas esperadas.
11. Verificar que la app no muestra rutas locales ni trazas tecnicas.

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
