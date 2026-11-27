# Contrato funcional: contexto, partes interesadas y alcance (ISO 9001:2026, 4.1-4.3)

El registro de la primera entrega está disponible en la guía de implementación al seleccionar una unidad. La referencia de diseño es ISO 9001:2026, cláusulas 4.1 y 4.2.

## Implementación de la primera entrega

- El API exige una unidad concreta para cada registro. Un administrador puede elegir la unidad que representa a toda la empresa en su estructura. El alcance general sin unidad requiere una política de autoridad propia y queda pendiente.
- El esquema combina ambos tipos en un registro versionado. Los temas usan `classification` para origen interno o externo, `category` para categoría y `relevance` para la pertinencia climática del tema. Las partes interesadas usan `classification` para tipo de parte y `relevance` para pertinencia al QMS. `description`, `requirements` y `evidence_summary` conservan el razonamiento, los requisitos atendidos y el resumen de evidencias según el tipo.
- El responsable debe pertenecer a la empresa. La fecha de revisión es obligatoria. Revisar exige una decisión de pertinencia, fundamento y fecha futura. La base rechaza la revisión por el creador y por la última persona que editó el contenido. Una edición posterior vuelve a dejar el registro pendiente de revisión.
- El historial conserva versiones con contenido, motivo y actor. La bitácora general recibe únicamente metadatos. El retiro exige motivo y conserva el historial. El rol de aplicación carece de permisos de escritura directa sobre la tabla de versiones y de borrado sobre el registro.
- Las capacidades `context.read`, `context.manage` y `context.review` se otorgan por unidad. Gestionar o revisar exige también lectura. El rol de auditor admite la capacidad explícita de lectura. La asignación de un responsable carece de efecto sobre el acceso.
- Las rutas de detalle, historial, edición, revisión y retiro reciben `unit_id` en la consulta. `PATCH` recibe los campos editables completos y la versión esperada. Se añadieron `GET /context/members`, `GET /context/{kind}/{id}/history` y `POST /context/{kind}/{id}/retire`. El listado filtra por estado y el historial pagina por versión.
- Quedan pendientes la decisión climática consolidada y los vínculos con objetivos de calidad.

## Requisitos individuales de partes interesadas

- Cada requisito tiene identificador estable dentro de la ficha, enunciado, fuente, decisión y fundamento. La decisión distingue pendiente, atendido por el QMS y gestionado fuera del QMS. Una decisión tomada exige fundamento.
- La revisión independiente se habilita cuando todos los requisitos tienen decisión o se documentó por qué no se identificaron requisitos relevantes. Una parte marcada como no relevante no puede tener requisitos atendidos por el QMS en una versión revisada.
- La ficha admite hasta 20 requisitos. El API y PostgreSQL validan el contenido y conservan cada versión. Retirar un requisito de una edición lo elimina de la ficha vigente y conserva la versión histórica que lo contenía.
- Los campos `party_requirements` y `no_requirements_reason` se incorporaron en `0053_qms_party_requirements`. Un cliente antiguo puede omitirlos en `PATCH` y conserva los valores existentes. La migración conserva estado, notas y revisiones anteriores. Las fichas anteriores requieren completar la evaluación antes de una nueva revisión.
- La fuente se registra como texto. Un requisito atendido por el QMS puede enlazarse con procesos, revisiones documentales liberadas, evidencia operativa aceptada y riesgos u oportunidades evaluados.

## Vínculos de requisitos con procesos

- El selector ofrece procesos activos registrados en la misma unidad. El enlace registra motivo, copia del requisito, código y nombre del proceso, y las versiones de ambos registros.
- La guía señala si el proceso fue actualizado o archivado y si el vínculo corresponde a una versión anterior del requisito. Retirar el enlace exige motivo y conserva los datos originales. El vínculo es una referencia operativa. La conformidad del proceso se verifica por separado.
- Se exige `context.read` y `processes.read` para ver historial o datos del proceso y también `context.manage` para vincular o retirar. Quien revisa la ficha con autoridad de contexto puede ver los requisitos. Para inspeccionar los vínculos necesita además lectura de procesos.
- La migración `0054_qms_party_process_links` conserva los vínculos por empresa y unidad con claves compuestas, RLS forzada y control de versiones. Vincular o retirar crea una nueva versión pendiente de revisión en la ficha. El historial del enlace conserva su versión y su motivo.

## Evidencia documental de un requisito

- El selector ofrece revisiones vigentes y liberadas de documentos activos de la misma unidad. La revisión debe tener un archivo limpio y una huella SHA-256 válida. El API y PostgreSQL verifican también las versiones seleccionadas.
- El historial conserva código, título, revisión, huella, motivo y versión de la ficha que creó o retiró el vínculo. La vista indica si la revisión sigue vigente, fue sustituida, quedó obsoleta o cambió desde la vinculación.
- La ficha de contexto y el historial documental tienen permisos separados. Leer vínculos exige `context.read` y `documents.read`. Vincular o retirar exige además `context.manage`. La autorización para descargar archivos se resuelve en el módulo documental.
- `0055_qms_party_document_links` añade el historial protegido de las citas. Cambiar un vínculo vuelve a dejar pendiente de revisión la ficha.

## Evidencia operativa aceptada

- El selector ofrece registros de evidencia aceptados de implementaciones activas en la misma unidad. PostgreSQL valida la relación entre ambos registros y comprueba sus versiones al guardar.
- La cita conserva código de implementación, nombre y tipo de evidencia, fecha de aceptación, versiones y motivo. Si se archiva la implementación, la ficha muestra ese estado y conserva la cita. Retirar la cita agrega motivo y versión de retiro.
- Leer el vínculo exige `context.read` y `control_instances.read`. Vincular o retirar exige también `context.manage` y reabre la revisión independiente de la ficha. La evidencia conserva su proceso de aceptación original.
- `0056_qms_party_evidence_links` protege estas relaciones por empresa y unidad y veta un retroceso que descartaría el historial.

## Riesgos y oportunidades relacionados con un requisito

- El selector muestra riesgos y oportunidades de la misma unidad en estado evaluado, con acción requerida o en seguimiento. Validar la versión al guardar evita citar una evaluación que ya había cambiado al comenzar el guardado.
- La ficha conserva el fundamento, la copia del requisito, el código, el nombre, el tipo, el estado y las versiones al vincular. La vista muestra también el estado actual. Cuando cambia la evaluación o el riesgo se cierra, la versión citada sigue disponible. Retirar el vínculo exige motivo.
- Leer exige `context.read` y `risks.read`. Vincular o retirar exige también `context.manage` y devuelve la ficha a revisión independiente. La evaluación y el cierre del riesgo se gestionan desde el registro de riesgos.
- `0057_qms_party_risk_links` protege las citas mediante claves por empresa y unidad, RLS forzada y un veto a la reversión que perdería el historial.

## Alcance declarado del QMS

- En la guía de implementación se selecciona una unidad y, en el registro de contexto, la opción **QMS scope**. La empresa puede elegir la unidad responsable de su alcance general. Se admite un alcance declarado por unidad.
- El borrador documenta límites, productos y servicios, contexto y requisitos considerados, y la decisión sobre aplicabilidad. Si se declaran requisitos no aplicables, la aprobación exige identificar y justificar la decisión en la ficha. La revisión exige responsable, decisión y fecha futura.
- Leer exige `context.read`. Redactar exige además `context.manage`. Aprobar exige `context.review` y un actor distinto del creador y del último editor. El historial conserva cada versión. El autor actualiza el alcance mediante una nueva versión y el registro vigente cambia al aprobarla.
- `GET /context/qms-scope/current?unit_id=…` devuelve la última versión aprobada o un resultado vacío si todavía no existe. Tiene el mismo límite por empresa y unidad que las demás rutas de contexto. El borrador se consulta desde el registro.
- `0058_qms_scope` reutiliza el historial de contexto y protege las aprobaciones mediante restricciones de forma y estado.
- `0059_qms_scope_basis` permite citar hasta 20 temas revisados o requisitos individuales de partes interesadas que se decidió atender en el QMS. El selector ofrece registros revisados de la unidad seleccionada. Al guardar, PostgreSQL deriva el código, el título y el enunciado desde la versión revisada de la fuente. El historial de la fuente y de la ficha conserva lo que se consideró aun cuando el registro original cambie.
- Agregar o retirar una referencia guarda el alcance como borrador. La versión vigente conserva sus referencias hasta la siguiente aprobación. El API admite fichas existentes sin citas y conserva las referencias cuando un cliente anterior edita el alcance sin enviar el campo nuevo.

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
