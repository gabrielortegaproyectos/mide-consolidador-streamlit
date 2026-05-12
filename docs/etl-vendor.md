# Vendor del ETL MIDE

## Decision

Para el despliegue inicial en Streamlit Community Cloud, la app incluye una
instantanea controlada del paquete `tributacion` dentro de este repositorio.

Esta decision evita que el despliegue tenga que instalar una dependencia desde
otro repositorio privado de GitHub, lo que requeriria secretos, tokens o deploy
keys adicionales.

## Fuente canonica

El repositorio canonico del ETL sigue siendo:

```text
asesorias-analitica-educativa/mide-tributacion-curricular
```

Instantanea vendorizada:

```text
repo: asesorias-analitica-educativa/mide-tributacion-curricular
branch: issue-3-api-publica-etl
commit: e0e99d29a14fabb143346e0393d920a090e15573
```

Contenido copiado:

```text
tributacion/
data/ciclos_manual/
data/codigos/
data/normalizacion_ra/
```

No se copian PDFs, matrices Excel institucionales, `data/output/` ni otros
artefactos derivados.

## Regla operativa

- Los cambios funcionales al ETL deben hacerse primero en
  `mide-tributacion-curricular`.
- Este repositorio solo actualiza la instantanea vendorizada cuando necesita una
  nueva version del contrato ETL.
- Cada actualizacion debe registrar el commit fuente en este documento.
- La app debe consumir el ETL mediante `tributacion.pipeline.run_pipeline_result`
  o la capa `app/services/pipeline_runner.py`; no debe importar parsers internos
  desde la UI.

## Dependencias

Las dependencias necesarias para ejecutar el paquete vendorizado se declaran en
`pyproject.toml` de esta app. No hay dependencia Git privada hacia el repo ETL.

## Re-evaluacion futura

Si el despliegue cambia a una plataforma con soporte comodo para secretos o
deploy keys, se puede reemplazar este vendor por una dependencia Git privada
fijada a tag o commit. Si app y ETL crecen juntos, tambien se puede evaluar un
monorepo.
