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
- smoke test de artefactos publicos que arma ZIP y `resumen_validacion.md`;
- deteccion en Google Sheets, decision `append`/`replace`/`cancel` y
  confirmacion textual `REEMPLAZAR` con dobles y mocks.

## Datos privados

Los tests automatizados del repositorio no deben requerir insumos privados.

Si se agrega una prueba con PDFs o matrices institucionales, debe:

- usar `@pytest.mark.private_data`;
- no subir insumos al repositorio;
- documentar donde restaurar los archivos autorizados;
- poder omitirse en un clon limpio.

## Prueba manual de publicacion online con sandbox

Las pruebas automatizadas no escriben en Google Sheets reales. Cualquier prueba
real debe hacerse con copias o sandbox de `BASE_ESTRUCTURAL` y
`LOG_PUBLICACIONES`.

### Preparacion

1. Duplicar la hoja maestra y la hoja de log en un entorno sandbox.
2. Configurar temporalmente `google_sheets` para apuntar a esas copias.
3. Verificar que la service account tenga permiso **Editor** sobre ambas Sheets.
4. Confirmar que la sandbox tenga la misma estructura de columnas que la base
   real.

### Casos minimos a probar

#### Caso 1: append

1. Ejecutar una carrera que no exista en la sandbox.
2. Completar la revision humana.
3. Elegir `append`.
4. Publicar.
5. Verificar que `BASE_ESTRUCTURAL` agregue solo el nuevo bloque.
6. Verificar que `LOG_PUBLICACIONES` registre `operation_type=append`.

#### Caso 2: replace

1. Ejecutar una carrera que ya exista en la sandbox.
2. Confirmar filas actuales a reemplazar y filas nuevas.
3. Descargar el Excel local si se requiere respaldo.
4. Elegir `replace`.
5. Escribir exactamente `REEMPLAZAR`.
6. Publicar.
7. Verificar que la sandbox conserve un solo bloque vigente para esa clave.
8. Verificar que `LOG_PUBLICACIONES` registre `operation_type=replace` y las
   filas reemplazadas.

#### Caso 3: cancel

1. Llegar hasta la decision operativa.
2. Elegir `cancel`.
3. Confirmar la cancelacion desde la interfaz.
4. Verificar que `BASE_ESTRUCTURAL` no cambie.
5. Verificar el mensaje final de cancelacion en la app.

### Verificaciones obligatorias en sandbox

- `BASE_ESTRUCTURAL` no recibe columnas tecnicas.
- `LOG_PUBLICACIONES` registra carrera, facultad, filas publicadas,
  filas reemplazadas, resultado y errores/advertencias si existen.
- El operador distingue claramente descarga local vs publicacion online.
- La publicacion no avanza si falta revisar carrera, facultad o advertencias.

### Cierre de la prueba

1. Guardar evidencia basica del resultado (captura, `publication_id` o nota de
   prueba).
2. Restaurar la configuracion normal de secrets si la prueba fue local.
3. No reutilizar una sandbox contaminada sin limpiarla o recrearla.

## Checklist manual con insumo autorizado

Usar solo archivos institucionales autorizados para prueba.

1. Abrir la app local o el despliegue MVP.
2. Cargar PDF de plan de estudio.
3. Cargar matriz Excel con hoja `Asignaturas - RA`.
4. Ejecutar `Procesar carrera`.
5. Confirmar que la validacion integrada muestra check si la matriz es
   compatible.
6. Si hay errores estructurales, confirmar que se muestran sin rutas locales.
7. Revisar estado final, conteos y asignaturas problematicas.
8. Revisar la previsualizacion del consolidado.
9. Descargar `tributacion_final.xlsx`.
10. Si la integracion online esta habilitada, revisar carrera, facultad,
    advertencias y deteccion en `BASE_ESTRUCTURAL` antes de decidir
    `append`/`replace`/`cancel`.
11. En caso de `replace`, verificar que la app exige `REEMPLAZAR`.
12. Confirmar que el Excel abre y conserva las columnas esperadas.
13. Verificar que la app no muestra rutas locales ni trazas tecnicas.

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
