# Continuidad del proyecto

Al comenzar trabajo en este workspace, leer `CHECKPOINT.md` como resumen de decisiones, evidencia y pendientes. Consultar fuentes originales cuando una decisión o validación dependa de ellas.

Actualizar `CHECKPOINT.md` al completar hitos o cambiar decisiones importantes. Mantenerlo breve, distinguir implementado de probado y no presentar propuestas como decisiones del usuario.

El objetivo es el SaaS propio de Perfect Match QMS con equivalencia funcional con Odoo y la misma exigencia de ciberseguridad y validaciones, adaptadas a la arquitectura del SaaS.

## Seguridad e integridad de los datos de clientes

La integridad y la seguridad de los datos de clientes tienen prioridad sobre la velocidad de entrega, la comodidad y el alcance de una función.

- Preservar el aislamiento entre empresas y exigir permisos explícitos con el menor acceso necesario. Verificar los controles en la API, la base de datos y el almacenamiento de archivos según corresponda.
- Proteger la trazabilidad de cambios y aprobaciones. Si una operación puede fallar, repetirse o ejecutarse en paralelo, verificar que conserve registros, versiones, evidencias y totales correctos.
- Usar datos sintéticos en pruebas y demos. Evitar datos de clientes y secretos en logs, capturas, archivos de prueba y repositorios.
- Para cambios que afecten datos, probar casos permitidos y denegados, incluidos cruces entre empresas cuando apliquen. Antes de migraciones con datos, verificar el respaldo y la restauración en un entorno aislado. Documentar la evidencia y priorizar cualquier hallazgo de pérdida de datos o acceso no autorizado antes de publicar.
