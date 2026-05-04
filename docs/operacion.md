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

La decision de despliegue debe evaluar acceso a repositorios privados, control
de usuarios, manejo de datos institucionales, logs y limpieza de temporales.

