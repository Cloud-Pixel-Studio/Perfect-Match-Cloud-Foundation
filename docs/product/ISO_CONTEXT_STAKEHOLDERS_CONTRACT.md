# Contrato funcional: contexto y partes interesadas (ISO 9001:2026, 4.1-4.2)

El registro de la primera entrega está disponible en la guía de implementación al seleccionar una unidad. La referencia de diseño es ISO 9001:2026, cláusulas 4.1 y 4.2.

## Implementación de la primera entrega

- El API exige una unidad concreta para cada registro. Un administrador puede elegir la unidad que representa a toda la empresa en su estructura. El alcance general sin unidad requiere una política de autoridad propia y queda pendiente.
- El esquema combina ambos tipos en un registro versionado. Los temas usan `classification` para origen interno o externo, `category` para categoría y `relevance` para la pertinencia climática del tema. Las partes interesadas usan `classification` para tipo de parte y `relevance` para pertinencia al QMS. `description`, `requirements` y `evidence_summary` conservan el razonamiento, los requisitos atendidos y el resumen de evidencias según el tipo.
- El responsable debe pertenecer a la empresa. La fecha de revisión es obligatoria. Revisar exige una decisión de pertinencia, fundamento y fecha futura. La base rechaza la revisión por el creador y por la última persona que editó el contenido. Una edición posterior vuelve a dejar el registro pendiente de revisión.
- El historial conserva versiones con contenido, motivo y actor. La bitácora general recibe únicamente metadatos. El retiro exige motivo y conserva el historial. El rol de aplicación carece de permisos de escritura directa sobre la tabla de versiones y de borrado sobre el registro.
- Las capacidades `context.read`, `context.manage` y `context.review` se otorgan por unidad. Gestionar o revisar exige también lectura. El rol de auditor admite la capacidad explícita de lectura. La asignación de un responsable carece de efecto sobre el acceso.
- Las rutas de detalle, historial, edición, revisión y retiro reciben `unit_id` en la consulta. `PATCH` recibe los campos editables completos y la versión esperada. Se añadieron `GET /context/members`, `GET /context/{kind}/{id}/history` y `POST /context/{kind}/{id}/retire`. El listado filtra por estado y el historial pagina por versión.
- Quedan pendientes la decisión climática consolidada para todo el QMS, los vínculos tipados a evidencias, riesgos y objetivos, y la conexión con el alcance 4.3.

## Requisitos individuales de partes interesadas

- Cada requisito tiene identificador estable dentro de la ficha, enunciado, fuente, decisión y fundamento. La decisión distingue pendiente, atendido por el QMS y gestionado fuera del QMS. Una decisión tomada exige fundamento.
- La revisión independiente se habilita cuando todos los requisitos tienen decisión o se documentó por qué no se identificaron requisitos relevantes. Una parte marcada como no relevante no puede tener requisitos atendidos por el QMS en una versión revisada.
- La ficha admite hasta 20 requisitos. El API y PostgreSQL validan el contenido y conservan cada versión. Retirar un requisito de una edición lo elimina de la ficha vigente y conserva la versión histórica que lo contenía.
- Los campos `party_requirements` y `no_requirements_reason` se incorporaron en `0053_qms_party_requirements`. Un cliente antiguo puede omitirlos en `PATCH` y conserva los valores existentes. La migración conserva estado, notas y revisiones anteriores. Las fichas anteriores requieren completar la evaluación antes de una nueva revisión.
- La fuente se registra como texto. Un requisito decidido para el QMS también puede enlazarse con un proceso.

## Vínculos de requisitos con procesos

- El selector ofrece procesos activos registrados en la misma unidad. El enlace registra motivo, copia del requisito, código y nombre del proceso, y las versiones de ambos registros.
- La guía señala si el proceso fue actualizado o archivado y si el vínculo corresponde a una versión anterior del requisito. Retirar el enlace exige motivo y conserva los datos originales. El vínculo es una referencia operativa. La conformidad del proceso se verifica por separado.
- Se exige `context.read` y `processes.read` para ver historial o datos del proceso y también `context.manage` para vincular o retirar. Quien revisa la ficha con autoridad de contexto puede ver los requisitos. Para inspeccionar los vínculos necesita además lectura de procesos.
- La migración `0054_qms_party_process_links` conserva los vínculos por empresa y unidad con claves compuestas, RLS forzada y control de versiones. Vincular o retirar crea una nueva versión pendiente de revisión en la ficha. El historial del enlace conserva su versión y su motivo.

Las secciones siguientes conservan el diseño de partida para comparar el alcance previsto con la primera entrega.

## Alcance

Cada registro pertenece a un tenant y, opcionalmente, a una unidad organizacional. No se permite consultar ni mutar registros de otra empresa aunque el usuario tenga un rol válido en su propio tenant.

## Entidades

### ContextIssue

- `id`, `tenant_id`, `unit_id` opcional
- `code`, `title`, `description`
- `direction`: `internal` | `external`
- `category`: `legal` | `regulatory` | `technology` | `market` | `culture` | `social` | `economic` | `environmental` | `strategic` | `other`
- `climate_relevance`: `relevant` | `not_relevant` | `under_review`
- `impact_summary`, `evidence_summary`
- `status`: `draft` | `active` | `retired`
- `owner_user_id`, `review_due_at`, `last_reviewed_at`
- timestamps y actor de creación/modificación

### InterestedParty

- `id`, `tenant_id`, `unit_id` opcional
- `code`, `name`, `party_type`
- `needs_expectations`, `applicable_requirements`
- `relevance`: `relevant` | `not_relevant` | `under_review`
- `status`: `draft` | `active` | `retired`
- `owner_user_id`, `review_due_at`, `last_reviewed_at`
- timestamps y actor de creación/modificación

## Reglas de autoridad

- Lectura requiere una capacidad explícita de contexto para la unidad seleccionada.
- Crear/editar/retirar requiere `context.manage` en la unidad.
- Revisar requiere `context.review` y no puede ser el mismo actor que creó el registro cuando la revisión sea de aprobación.
- Retirar conserva el registro y exige motivo; no se permite borrado físico.
- Cambiar tenant, unidad, estado o relevancia se registra en la bitácora.
- Un tenant suspendido no permite lecturas operativas ni comandos.

## Contrato HTTP propuesto

- `GET /context/issues?unit_id=&status=&limit=&offset=`
- `POST /context/issues`
- `GET /context/issues/{id}`
- `PATCH /context/issues/{id}`
- `POST /context/issues/{id}/review`
- `GET /context/interested-parties?unit_id=&status=&limit=&offset=`
- `POST /context/interested-parties`
- `GET /context/interested-parties/{id}`
- `PATCH /context/interested-parties/{id}`
- `POST /context/interested-parties/{id}/review`

Todas las respuestas deben incluir `X-Tenant-ID`, usar `private, no-store` y validar nuevamente identidad, tenant, unidad y capacidad al terminar la consulta o comando.

## Criterios de aceptación

1. Un registro de Tenant A nunca aparece, se modifica ni se cuenta desde Tenant B.
2. Una unidad fuera del alcance del actor devuelve 403/404 sin revelar existencia.
3. Un usuario sin `context.manage` puede leer solo lo permitido y no puede enviar comandos.
4. La revisión exige actor distinto al creador cuando la política de aprobación esté activa.
5. Retirar conserva historial, motivo, actor y fecha.
6. Las lecturas tardías de una unidad anterior no contaminan la unidad actual en la UI.
7. Se prueban 401, 403, 404, 409 por cambio de contexto, CSRF, paginación, filtros, suspensión y concurrencia.
8. La guía de implementación muestra estos registros como observaciones, nunca como certificación automática.

## Dependencias

Reutilizar `OrganizationUnit`, `actor_context`, `require_capability`, RLS y el patrón de auditoría existente. No introducir permisos globales ni bypass de RLS.
