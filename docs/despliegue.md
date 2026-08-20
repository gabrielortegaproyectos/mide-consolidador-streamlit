# Despliegue Streamlit

## Decision para MVP

La app se despliega inicialmente en **Streamlit Community Cloud** desde el
repositorio `gabrielortegaproyectos/mide-consolidador-streamlit`.

URL de MVP:

```text
https://mide-etl.streamlit.app/
```

El repositorio se transfirio a la cuenta personal `gabrielortegaproyectos`
porque el plan gratuito de Streamlit funciono con esa configuracion. Esta es
una decision operativa del MVP; si el proyecto requiere administracion
organizacional estricta, se debe re-evaluar una plataforma con control de
acceso institucional.

Esta opcion se elige para el MVP porque:

- no requiere operar una VM ni contenedores propios;
- instala dependencias desde `pyproject.toml`;
- puede conectarse al repositorio GitHub del proyecto;
- permite publicar rapido cambios mergeados a `main`;
- evita secretos de instalacion porque el ETL esta vendorizado en este repo;
- mantiene la politica de no persistencia definida en `docs/operacion.md`.

## Decision de acceso

La app implementa una barrera de acceso propia mediante contrasena
compartida (issue-milestone E1M0), ademas de la visibilidad restringida que
ofrece Streamlit Community Cloud.

Reglas:

- compartir acceso solo con usuarios autorizados del proyecto MIDE;
- no publicar la URL como recurso abierto;
- la app bloquea encabezado, pestanas, manual e integraciones hasta validar
  la contrasena compartida configurada en Secrets;
- la contrasena real nunca vive en el repositorio ni en el historial de Git;
- usar ademas los controles de acceso de Streamlit Community Cloud cuando
  esten disponibles;
- si se requiere control institucional mas estricto (cuentas individuales,
  roles, OIDC), re-evaluar Cloud Run, servidor interno o VM con
  autenticacion corporativa.

### Configuracion del secreto de acceso

1. Copiar `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml`
   en entorno local, o abrir **Settings > Secrets** en Streamlit Community
   Cloud.
2. Completar `[auth]` con la contrasena real:

   ```toml
   [auth]
   password = "contrasena-real-aqui"
   ```

3. Guardar y redeployar si Streamlit Community Cloud lo solicita.
4. Nunca commitear `.streamlit/secrets.toml`; el archivo real ya esta
   ignorado por git.

### Verificacion del acceso restringido

1. Abrir la URL desplegada en una ventana nueva o navegador privado.
2. Confirmar que la app muestra la pantalla de acceso y no el contenido
   principal.
3. Ingresar una contrasena incorrecta y confirmar el mensaje generico de
   error.
4. Ingresar la contrasena correcta y confirmar que se habilita el
   contenido.
5. Usar `Cerrar sesion` y confirmar que la app vuelve a bloquearse.
6. Confirmar que la contrasena no aparece en pantalla, logs ni mensajes de
   error.

### Rotacion del secreto

1. Definir la nueva contrasena por un canal privado (no GitHub, no logs).
2. Actualizar `[auth].password` en **Settings > Secrets** de Streamlit
   Community Cloud.
3. Guardar; Streamlit reinicia la app con el nuevo valor.
4. Notificar a los usuarios autorizados por el mismo canal privado usado
   para distribuir la contrasena anterior.
5. Verificar que la contrasena anterior ya no habilita el acceso.

### Si el secreto falta o debe revocarse

- **Falta el secreto:** la app se bloquea de forma segura y muestra un
  mensaje indicando que falta configuracion; ningun contenido queda
  expuesto. Configurar `[auth].password` en Secrets para habilitar el
  acceso.
- **Revocar acceso inmediato:** cambiar `[auth].password` por un valor
  nuevo en Secrets. Las sesiones ya autenticadas en el navegador
  mantienen acceso hasta que el usuario cierre sesion o la sesion expire;
  si se requiere corte inmediato, redeployar la app para reiniciar el
  proceso del servidor.

## Repositorio y entrada

Configuracion minima esperada:

```text
Repository: gabrielortegaproyectos/mide-consolidador-streamlit
Branch: main
Main file path: app/main.py
Python dependencies: pyproject.toml / uv.lock
Secrets obligatorios: [auth].password
Secrets adicionales: Google Sheets se configura via Streamlit Secrets
```

## Secrets adicionales para Google Sheets

La app requiere `[auth].password` para habilitar el acceso. Sin los secrets de
Google Sheets, el flujo local de carga, procesamiento y descarga del consolidado
permanece habilitado despues de autenticar la sesion.

Si se quiere dejar preparada la integracion online de Google Sheets para issues
posteriores:

1. Copiar `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml` en
   entorno local, o cargar el mismo contenido en el panel de Secrets de
   Streamlit Community Cloud.
2. Completar la seccion `[gcp_service_account]` con la service account real de
   Google Cloud.
3. Confirmar que `[google_sheets]` apunte a las hojas correctas.
4. No subir nunca `.streamlit/secrets.toml` al repositorio; el archivo real ya
   esta ignorado por git.

En Streamlit Community Cloud:

- abrir la app;
- entrar a **Settings > Secrets**;
- pegar el contenido TOML con los valores reales;
- guardar y redeployar si Streamlit lo solicita.

## Pasos minimos

1. Entrar a Streamlit Community Cloud.
2. Crear una app nueva desde el repo GitHub `gabrielortegaproyectos/mide-consolidador-streamlit`.
3. Seleccionar branch `main`.
4. Usar `app/main.py` como archivo principal.
5. Confirmar que el build instala dependencias desde `pyproject.toml`.
6. Configurar visibilidad privada/restringida antes de cargar datos reales.
7. Configurar `[auth].password` en Secrets con la contrasena compartida real.
8. Hacer una corrida de smoke con insumos de prueba, incluyendo el ingreso
   con contrasena.
9. Descargar el consolidado Excel y revisar la previsualizacion en pantalla.

Si la integracion Google Sheets se configura, la app debe mostrarla como
habilitada sin reemplazar la descarga local del Excel.

## Evaluacion de opciones

| Opcion | Decision MVP | Motivo |
| --- | --- | --- |
| Streamlit Community Cloud | Elegida | Menor costo operativo y despliegue simple desde GitHub. |
| VM interna | Diferir | Mayor mantencion; util si se exige control de red o almacenamiento local. |
| Cloud Run / contenedor | Diferir | Mejor para IAM y observabilidad, pero aumenta setup y costos. |
| Ejecucion local asistida | Fallback | Sirve para soporte interno si la nube no esta disponible. |

## Limitaciones conocidas

- El control de acceso combina la contrasena compartida de la app con la
  configuracion de Streamlit Community Cloud; ninguno reemplaza cuentas
  individuales, roles ni OIDC.
- El repositorio operativo del despliegue MVP vive en una cuenta personal, no en
  la organizacion.
- No debe usarse como app publica para datos institucionales reales.
- El almacenamiento persistente en servidor queda fuera del MVP.
- Los logs de plataforma se usan solo para diagnostico tecnico y no deben incluir
  contenido de archivos cargados.
- Si cambia la politica de datos o se requiere auditoria historica centralizada,
  hay que abrir una decision nueva antes de guardar archivos en servidor.

## Instrucciones para la contraparte (validacion de acceso restringido)

Enviar por el canal privado definido para esta entrega, junto con la
contrasena (nunca por GitHub, issues ni correo sin cifrar si la politica del
proyecto lo restringe):

1. Abrir <https://mide-etl.streamlit.app/>.
2. Confirmar que la app pide una contrasena antes de mostrar cualquier
   contenido.
3. Ingresar la contrasena compartida recibida por el canal privado.
4. Confirmar que se habilita la pestana "Procesar carrera" y "Manual".
5. Probar `Cerrar sesion` y confirmar que la app vuelve a pedir la
   contrasena.
6. Reportar el resultado (aprobado u observaciones) en la entrega #71.

## Criterios de exito

- La app arranca desde `app/main.py`.
- No requiere secretos para instalar el ETL.
- La carga, procesamiento y descarga funcionan con datos de prueba.
- La descarga entrega el consolidado Excel esperado.
- El acceso esta restringido antes de procesar insumos reales: la app
  bloquea todo contenido hasta validar la contrasena compartida configurada
  en `[auth].password`.
