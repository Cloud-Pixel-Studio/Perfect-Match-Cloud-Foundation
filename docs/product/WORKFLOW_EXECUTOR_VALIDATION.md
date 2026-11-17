# Workflows — responsables ejecutables ·16 noviembre2026

Rama codex/workflow-executor-validation sobre PR56/0aabd96. Corrige A05, que
permitía publicar con auditor como único ejecutor. No hay nuevos roles, grants,
capabilities, modelos, migraciones, dependencias ni firma QMS.

## Comportamiento implementado

- Cada asignación directa requiere usuario y membresía activos en la empresa,
  con rol técnico owner/admin/member. Auditor permanece de solo lectura.
- Una asignación por rol requiere al menos una persona activa con ese rol.
- Una unidad debe estar activa y tener una asignación activa a un ejecutor.
  Una unidad vacía o compuesta solo de auditores no basta; una mixta sí puede.
- Los borradores se conservan, pero cada target configurado se valida al publicar.
- Al iniciar se revalidan todos los pasos, incluidos los futuros: personas y
  asignaciones pueden haber cambiado desde la publicación.
- Una transición a tarea/aprobación comprueba ejecutores del destino. Ante409,
  no avanzan la versión ni el historial. Llegar a fin no exige otro responsable.
- El inicio debe ser tarea/aprobación. Un inicio directamente en fin producía
  una instancia activa sin acciones para terminar; ahora se rechaza al publicar.
- Plantillas retiradas no publican ni inician trabajo nuevo. Sus instancias
  existentes pueden terminar/cancelarse con autoridad, preservando su historia.

Se reutiliza organization_member_directory y se consultan solo ID/rol, con sus
filtros de actividad/empresa y las asignaciones bajo RLS. Un seat, cargo de unidad
o asignación como auditor interno no concede ejecución Workflow. Tampoco se
reemplazan los comandos de aprobación de documentos, evidencia o CAPA.

El constructor conserva el borrador y muestra el error de servidor. Corregir
personas/asignaciones legítimas o preparar una nueva versión; no se autoconceden
permisos ni cambian roles. Las versiones publicadas no se reescriben. Los checks
describen el estado al validar, no garantizan disponibilidad perpetua ni bloquean
cambios organizativos futuros. Instancias antiguas atascadas requieren revisión
o cancelación autorizada; no se reparan silenciosamente.

La defensa completa de comandos/transiciones por SQL(A06), paginación/editor y
UX completos(A09) continúan pendientes. No se declara paridad o certificación.

## Evidencia

| Validación | Resultado |
| --- | --- |
| Regresiones antes del arreglo |4RED: auditor único, unidad vacía, ejecutor futuro perdido y plantilla retirada |
| Suite nueva HTTP/PostgreSQL0049 |32PASS |
| Misma suite sobre0048, compatible con demo |32PASS, otra DB temporal |
| Workflows existentes |31PASS; downgrade con historia denegado como se esperaba |
| Centro de Acciones |18PASS |
| API unitarias |93PASS;562DB omitidas sin harness, no declaradas PASS |
| Ruff/formato/mypy |PASS;128 archivos/79 fuentes |
| ShellCheck/diff |PASS |
| Gitleaks árbol / OpenGrep |0hallazgos;6reglas/2archivos |
| OIDC/API local real |8 comprobaciones PASS;0cambios de rol/grant,0borrados |

Casos: usuario/rol/unidad, persona deshabilitada, membresía revocada, rol cambiado
a auditor, asignación inactiva, borrador/historia intactos al denegar, pasos futuros,
retiro y restauración legítima sin reescribir la versión. El caso de auditor del
Centro de Acciones ahora publica con admin válido y lo cambia después a auditor:
mantiene la regresión sin publicar intencionalmente un grafo nuevo inválido.

```sh
./scripts/run-workflow-executor-integrity.sh
# Reutilización explícita de imagen local existente para el harness aislado:
PMC_TEST_REUSE_POSTGRES_IMAGE=1 ./scripts/run-workflow-executor-integrity.sh
# QA real local: sin argumento no escribe; --apply requiere backup DB verificado:
apps/api/.venv/bin/python scripts/runtime-workflow-executors-e2e.py --apply
```

La fixture exige DB pmcloud_tenant_suspension, credenciales y contenedor propios,
tmpfs512m y limpieza de ese contenedor. CI añade la suite al job workflow-integrity
y al checkpoint. No hay nueva UI ni corrida browser/build frontend en este hito;
QA OIDC/API no equivale a probar todos los botones.

## Runtime y recuperación

Solo API local se actualizó mediante capa sobre la imagen preservada
pmcloud-api:before-workflow-executors-20261116. Rootfs read-only, cap_drop y
no-new-privileges conservados; otros servicios intactos. DB sigue0048, sin0049.
Se copian workflow_service.py y su dependencia existente tenant_access.py, que
comprueba empresa/actor activos en API Workflow. Esto no despliega toda la
suspensión legacy/RLS0049 ni cierra A01 globalmente. Procesos y cola conservan
sus fixes previos; sin datos privados, licencias o producción modificados.

QA crea tres plantillas nuevas LAB-WFX-*, una unidad y una instancia completada.
Plantillas retiradas/unidad archivada, historia preservada. Ejemplos anteriores
intactos. No usar QA como firma, envío o aprobación humana QMS.

CP-WORKFLOW-EXECUTORS-00-20261116T223317Z:551fuentes/Git;02-20261116T224107Z:553;
02B-20261116T224744Z:554. Backups cifrados externos, restauración SHA256 y bundle
PASS. CP-WORKFLOW-EXECUTORS-DB-00-20261116T224106Z restauró0048/57tablas aislada
antes de QA; servicio runtime original cifrado/descifrado idéntico. No se restauró
sobre la DB real. Revertir API desde la imagen anterior no requiere restaurar DB.

PR56/0aabd96: calidad43960367180 y CodeQL43960367203 PASS; security43960367674
falla solo gate final. No se inventa conteo CVE actualizado sin su artefacto.
Esta entrega requiere CI propio y revisión independiente. PM NO GO, sin merge
ni autorización de producción.
