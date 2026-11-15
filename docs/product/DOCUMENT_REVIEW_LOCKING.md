# Decisiones documentales con mínimo privilegio

Corrección M01 y orden transaccional de reemplazo, sobre PR44/db302b6. Implementado y probado contra PostgreSQL desechable; no desplegado en el runtime de desarrollo, que sigue PR39/DB0048.

## Comportamiento

Un revisor con documents.review puede enviar/rechazar; un aprobador independiente con documents.approve puede aprobar. Estas decisiones ya no necesitan documents.author, documents.release o documents.obsolete sobre el padre. Se conservan la comprobación de capabilities exactas, RLS, CSRF, independencia del preparador, archivo limpio, estados, expected_version y ledger atómico. No se conceden permisos ni se modifican políticas, modelos, migraciones o contratos API.

Submit/approve/reject leen el ámbito inmutable del padre y bloquean la revisión con populate_existing. La inmutabilidad de empresa/unidad/proceso/identidad del documento está en el guard SQL existente0011. El padre no cambia en esas decisiones; FOR UPDATE exigía autoridad de escritura del padre y ocultaba la fila al revisor mínimo.

Release bloquea primero el padre y después la revisión. El documento serializa la sustitución de revisiones para que un comando en espera no retenga un hijo que otro release necesita. Las otras operaciones conservan su protocolo: create_revision comienza por el padre, upload solo lee el padre y obsolete solo bloquea el padre. No se agrega una regla de negocio sobre obsolescencia.

## Segundo fallo descubierto y corregido

Actualizar anterior→superseded y nueva→active con un único flush dependía del orden de UUID usado por SQLAlchemy. Si activaba primero la nueva, el índice único inmediato qms_document_one_active_revision producía23505. La anterior se persiste antes de activar la nueva. Ambos flushes, cambios de padre/hijos y evento permanecen en el mismo try/rollback y transacción; no existe commit intermedio.

## Evidencia ejecutada

- Cuatro casos RED contra el código inicial: decisiones mínimas, ausencia de bloqueo de escritura innecesario y orden de bloqueo en release. Los cuatro pasan después de corregir M01.
- Dos RED deterministas con UUID nuevo menor que el anterior reproducen23505 antes de corregir el orden de persistencia; ambos pasan con la corrección, incluida inyección de fallo del ledger.
- 18 pruebas HTTP/PostgreSQL PASS: perfiles mínimos sin documents.read adicional, submit/reject/resubmit/approve/release, lector sin autoridad, padre sin permiso UPDATE, autoaprobación denegada, CSRF/versión, aislamiento al cambiar de empresa, rollback, revocación durante espera, un ganador/un409 para approve/reject y releases paralelos conservando exactamente una revisión activa y el puntero correcto.
- 199 regresiones PostgreSQL de procesos/documentos/controles/evidencia/riesgos/NCR/CAPA PASS, roundtrip vacío y rechazo de downgrade con historia protegida PASS. Son distintas de las18 nuevas.
- 50 API unitarias PASS;509 integraciones omitidas en la corrida sin harness, no aceptadas por esa corrida. Ruff/formato/mypy75 PASS; ShellCheck, Gitleaks de árbol y OpenGrep6reglas/1archivo/0hallazgos. Revisión independiente de solo lectura sin P1/P2 pendientes en el diff inspeccionado.

Una expectativa de fixture comparaba UUID de PostgreSQL con string JSON: se corrigió el tipo y se conservó la comparación exacta. Las dos advertencias previas de Starlette/AnyIO siguen presentes. La primera ejecución de Ruff detectó formato/imports/contextos de los tests; corregidos. Ningún fallo se convirtió en éxito mediante permisos adicionales o XFAIL.

El harness scripts/run-document-review-integrity.sh utiliza PostgreSQL sintético tmpfs512MiB, puerto loopback55478 y la fixture compartida con DB pmcloud_tenant_suspension. CI construye imagen por defecto; local puede reutilizar la imagen explícitamente con PMC_TEST_REUSE_POSTGRES_IMAGE=1. Bootstrap/migrador/runtime separados y secretos efímeros; solo se elimina el contenedor propio al terminar. AV/storage se sustituyen por memoria; no prueba IdP, antivirus o almacenamiento externos. No se ejecutó browser/frontend nuevo porque no cambia UI.

## Recuperación y límites

CP-DOCUMENT-REVIEW-LOCK-00-20261115T030903Z cifró y restauró521fuentes/Git antes de editar; SHA256 y bundle verify PASS. CP-DOCUMENT-REVIEW-LOCK-06-20261115T032536Z preserva fuente/Git cifrados y restaurados antes de entrega. No hay modificación ni backup nuevo de la DB real en esta corrección. Los respaldos anteriores del runtime siguen separados fuera de Git.

La auditoría PR45 conserva correctamente M01 como fallo del baseline PR41; esta rama posterior lo corrige sin reescribir esa evidencia histórica. Integrar y desplegar una versión revisada es un paso posterior. CI del head final y aprobación humana siguen pendientes.

El gate de producción conserva los hallazgos de imágenes vendor. La investigación independiente docs/security/VENDOR_EVALUATION_2026-11-14.md consulta fuentes oficiales y distingue candidatos de pruebas; las últimas estables inspeccionadas no acreditan cerrar los9HIGH. No se actualizan imágenes, se mezclan escáneres ni se ignoran CVE en esta entrega.
