# Operacion

## Politica inicial

Hasta que exista una decision formal, la app debe asumir no persistencia por
defecto:

- guardar uploads solo en temporales por sesion;
- limpiar archivos al finalizar o fallar;
- no mostrar rutas locales al usuario;
- no registrar contenido de archivos en logs;
- incluir nombre/hash de archivos en el resumen de validacion cuando se
  implemente trazabilidad.

## Despliegue pendiente

El despliegue objetivo inicial es Streamlit Community Cloud.

Para evitar secretos de instalacion, la app incluye una instantanea vendorizada
del paquete `tributacion` y sus catalogos livianos. La plataforma solo necesita
instalar las dependencias declaradas en `pyproject.toml`; no necesita leer el
repositorio privado `mide-tributacion-curricular` durante el build.

La decision completa y el commit fuente se documentan en `docs/etl-vendor.md`.

Quedan por evaluar control de usuarios, manejo de datos institucionales, logs y
limpieza de temporales.

