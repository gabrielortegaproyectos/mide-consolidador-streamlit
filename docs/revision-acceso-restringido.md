# Revision transversal del acceso restringido

Fecha de revision: 2026-07-25

## Alcance

Documentos revisados:

- `README.md`
- `docs/arquitectura.md`
- `docs/operacion.md`
- `docs/qa.md`
- `docs/despliegue.md`
- `docs/cierre-mvp.md`
- `docs/roadmap.md`

Codigo y pruebas contrastadas:

- `app/services/auth.py`
- `app/ui/auth.py`
- `app/main.py`
- `tests/test_auth.py`
- `tests/test_auth_gate.py`

## Resultado

- La documentacion publica describe que la app bloquea el contenido principal
  hasta validar una contrasena compartida configurada en `[auth].password`.
- La arquitectura registra la barrera previa al renderizado y separa UI
  (`app/ui/auth.py`) de logica de autenticacion (`app/services/auth.py`).
- Operacion y QA incluyen ingreso, sesion activa, cierre de sesion, bloqueo
  seguro sin secreto y validacion con ventana nueva o privada.
- Despliegue mantiene `docs/despliegue.md` como fuente de configuracion,
  verificacion y rotacion del secreto.
- Las referencias a secrets adicionales de Google Sheets quedan diferenciadas
  del secreto obligatorio de acceso.
- No se documentan valores reales de contrasena, tokens ni credenciales.

## Checks ejecutados

```bash
uv run --group dev pytest tests/test_auth.py tests/test_auth_gate.py
rg -n "acceso|autentic|contrase|password|secret|Secrets|privad|restring|sesion|sesion|Cerrar sesion" README.md docs app tests
rg -n "TODO|FIXME|confidential|secret|token|password|api_key|apikey|csv|xlsx|pickle|pkl|data/" README.md docs app tests pyproject.toml .gitignore
```

## Observaciones

- Las coincidencias de `password`, `secret` y `token` que permanecen son nombres
  de configuracion, placeholders no reales, endpoints publicos de OAuth o datos
  de prueba.
- Los archivos institucionales versionados bajo `data/` son catalogos livianos
  ya exceptuados por `.gitignore`; no se agregaron datasets privados.
