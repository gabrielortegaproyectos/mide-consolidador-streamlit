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

## Prueba manual con Google Sheet sandbox

Las pruebas automatizadas de publicacion online usan `DataFrame`, fakes y mocks;
nunca deben leer ni escribir `BASE_ESTRUCTURAL`, `LOG_PUBLICACIONES`, secrets
reales ni una Google Sheet productiva.

Si se necesita validar la integracion real, usar solo una copia o sandbox:

1. Crear o duplicar una Google Sheet de prueba separada de la base real.
2. Configurar temporalmente `google_sheets` y `gcp_service_account` para apuntar
   a esa sandbox.
3. Ejecutar el flujo completo y validar lectura de base, `append` o `replace`,
   y escritura en `LOG_PUBLICACIONES`.
4. Confirmar que los metadatos de auditoria quedan en la hoja de log y que la
   base maestra conserva solo las columnas estructurales.
5. Restaurar la configuracion normal al finalizar la prueba manual.

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
