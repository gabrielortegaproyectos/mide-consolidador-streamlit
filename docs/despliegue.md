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

La app debe configurarse como **privada/restringida** en Streamlit Community
Cloud cuando procese insumos institucionales reales.

Reglas:

- compartir acceso solo con usuarios autorizados del proyecto MIDE;
- no publicar la URL como recurso abierto;
- no agregar autenticacion propia dentro de la app para el MVP;
- usar los controles de acceso de Streamlit Community Cloud;
- si se requiere control institucional mas estricto, re-evaluar Cloud Run,
  servidor interno o VM con autenticacion corporativa.

## Repositorio y entrada

Configuracion minima esperada:

```text
Repository: gabrielortegaproyectos/mide-consolidador-streamlit
Branch: main
Main file path: app/main.py
Python dependencies: pyproject.toml / uv.lock
Secrets: ninguno para instalar o ejecutar el MVP
```

## Pasos minimos

1. Entrar a Streamlit Community Cloud.
2. Crear una app nueva desde el repo GitHub `gabrielortegaproyectos/mide-consolidador-streamlit`.
3. Seleccionar branch `main`.
4. Usar `app/main.py` como archivo principal.
5. Confirmar que el build instala dependencias desde `pyproject.toml`.
6. Configurar visibilidad privada/restringida antes de cargar datos reales.
7. Hacer una corrida de smoke con insumos de prueba.
8. Descargar el consolidado Excel y revisar la previsualizacion en pantalla.

## Evaluacion de opciones

| Opcion | Decision MVP | Motivo |
| --- | --- | --- |
| Streamlit Community Cloud | Elegida | Menor costo operativo y despliegue simple desde GitHub. |
| VM interna | Diferir | Mayor mantencion; util si se exige control de red o almacenamiento local. |
| Cloud Run / contenedor | Diferir | Mejor para IAM y observabilidad, pero aumenta setup y costos. |
| Ejecucion local asistida | Fallback | Sirve para soporte interno si la nube no esta disponible. |

## Limitaciones conocidas

- El control de acceso depende de la configuracion de Streamlit Community Cloud.
- El repositorio operativo del despliegue MVP vive en una cuenta personal, no en
  la organizacion.
- No debe usarse como app publica para datos institucionales reales.
- El almacenamiento persistente en servidor queda fuera del MVP.
- Los logs de plataforma se usan solo para diagnostico tecnico y no deben incluir
  contenido de archivos cargados.
- Si cambia la politica de datos o se requiere auditoria historica centralizada,
  hay que abrir una decision nueva antes de guardar archivos en servidor.

## Criterios de exito

- La app arranca desde `app/main.py`.
- No requiere secretos para instalar el ETL.
- La carga, procesamiento y descarga funcionan con datos de prueba.
- La descarga entrega el consolidado Excel esperado.
- El acceso esta restringido antes de procesar insumos reales.
