# Recorridos de implantación, cambio y migración: Odoo frente al SaaS

Verificación:18 de noviembre de2026. Repositorio funcional de referencia `Cloud-Pixel-Studio/perfect-match-qms`, `main` confirmado en `d89330cc1a8e9a2ea16992c9b49394f1dc481b7f`; SaaS oficial revisado en `7c206acbdd92808f72e776b0035ee3671d7ae6d5`. Odoo solo es referencia; no se incorporan sus dependencias al SaaS.

## Conclusión

La referencia Odoo contempla empresas sin QMS, sistemas existentes, mejora, cambio de edición, sistemas heredados y preparación para evaluaciones. El SaaS ya tiene operaciones QMS reutilizables por módulo, pero no el proyecto maestro que organiza esos recorridos de principio a fin. La demo conectada demuestra relaciones entre registros, no sustituye una implantación ISO completa.

Presencia de modelos, métodos y pruebas en Odoo no significa que todos los escenarios estén aprobados o que hayan sido ejecutados en esta revisión. Esta es inspección de código y contratos, sin ejecutar Odoo, sin nuevas pruebas operativas del SaaS y sin cambios de aplicación, VM o datos.

## Tres dimensiones que no deben confundirse

1. **Cambiar el sistema de gestión:** crear procesos, corregir responsabilidades o ampliar alcance. Puede ocurrir sin cambiar de edición ISO ni de software.
2. **Cambiar de edición de la norma:** comparar una línea base con una edición objetivo; conservar decisiones, evaluaciones y evidencia previas. No equivale a renombrar una revisión documental.
3. **Cambiar de plataforma QMS:** inventariar/exportar/importar datos y archivos de otro sistema, validando relaciones e historia. Puede mantener la misma edición ISO o combinarse con una transición.

La preparación para auditoría es un objetivo que puede acompañar cualquiera de esas dimensiones. Un cliente podría necesitar migrar de plataforma, actualizar la edición y preparar una auditoría dentro del mismo programa, con hitos separados.

## Comparación de los cinco recorridos solicitados

| Recorrido | Referencia Odoo observada | SaaS actual comprobado | Qué falta para un recorrido completo |
|---|---|---|---|
| **Empezar desde cero** | Proyecto generado desde packs activos; estructura por fases, controles, actividades/tareas, responsables, fechas, evidencia y evaluaciones de preparación. Blueprint inicialv1.1:13fases/37actividades. | Organización/unidades, procesos, documentos/revisiones, controles, implementaciones de control, actividades y evidencia se crean por APIs/UI. | Proyecto maestro por empresa, diagnóstico inicial, alcance/contexto global, perfil normativo versionado, generación del plan integral y seguimiento por fases. KPI, formación, revisión de dirección y otros módulos del recorrido siguen pendientes. |
| **Modificar u optimizar un QMS existente** | Tipos de proyecto `optimization`, `gap_assessment` y `custom`, sincronización de framework y escenario de ampliación de alcance. Evidencia y evaluaciones históricas se conservan. | Se pueden modificar registros permitidos, crear revisiones documentales con aprobación/liberación, archivar procesos y retirar referencias con motivo/versiones. | Expediente transversal de cambio: solicitud, impacto en requisitos/procesos/documentos/formación, aprobación, implantación, reevaluación y nueva línea base. La sincronización de Odoo tampoco prueba por sí sola ese expediente integral. |
| **Actualizar una edición ISO** | Escenario2015→2026; perfil origen/destino, evaluación de brechas, acciones, revisión de preparación, paquete controlado y registro de ejecución. El pack de implantación2026 está expresamente en borrador y bloqueado para activación. | Hay tareas clasificables como transición/remediación y referencias escritas por el usuario, pero no edición origen/destino ni motor normativo. | Catálogo/perfiles/ediciones, matriz versionada de diferencias, aplicabilidad, brechas/acciones por requisito, decisión de transición y conservación de la línea base anterior. Revisión competente y liberación del contenido objetivo. |
| **Prepararse para auditoría o recertificación** | Objetivos de preparación interna, certificación, seguimiento, auditoría de cliente, evaluación regulatoria u otro. Centro y snapshots de preparación; escenarios de recertificación con transición y sin cambio de edición. | Programas, planes, alcance, criterios, equipo, agenda, independencia, competencia y HTML imprimible. Documentos, evidencia y CAPA aportan soporte operativo. | Diagnóstico global por requisitos y preparación consolidada, KPI y revisión por dirección; ejecución de auditoría, evidencia/hallazgos, informe y cierre. `ready_for_execution` continúa falso. El software no otorga certificación. |
| **Migrar desde otro QMS, Excel o archivos heredados** | Escenario legacy y wizardsCSV para documentos/revisiones y evidencia, con relaciones de empresa/organización/proceso, responsables, notas y adjuntosbase64. Se prevalidan filas; la evidencia importada no puede entrar como aceptada. | Alta/carga individual de documentos y PDF, CRUD autorizado y lecturas paginadas. Seed/demo solo sirve para datos sintéticos restringidos. | Área de importación de cliente, formatos/mapping/preview, lotes e idempotencia, IDs/procedencia externos, validación antivirus y relaciones, reconciliación de cantidades/hashes, tratamiento del histórico y aceptación del cliente. No existe un conector universal ni en el código Odoo inspeccionado. |

## Catálogo exacto de escenarios Odoo

`ISO9001_TRANSITION_SCENARIOS` define **nueve escenarios**, agrupados en ocho tipos. Todos son definiciones de recorrido, no nueve procesos completos probados hoy:

| Código | Caso |
|---|---|
| ISO9001-2026-INITIAL | Implantación nueva |
| ISO9001-2026-TRANSITION-2015 | Transición2015→2026 |
| ISO9001-2026-LEGACY | Sistema heredado o incompleto |
| ISO9001-2026-RECERTIFICATION | Recertificación acompañada de transición |
| ISO9001-2026-RECERTIFICATION-SAME-EDITION | Recertificación manteniendo edición |
| ISO9001-2026-SCOPE-EXPANSION | Ampliar productos, servicios, procesos o sedes |
| ISO9001-2026-MULTI-SITE | Desplegar en varias sedes |
| ISO9001-2026-INTEGRATED | Coordinar varios sistemas de gestión conservando perfiles independientes |
| ISO9001-2026-PARTIAL | Implantación parcial con límites y brechas explícitos |

El generador genérico tiene **seis modos de proyecto**, distintos del catálogo ISO: implantación nueva, migración, optimización, evaluación de brechas, actualización y personalizado. A su vez ofrece **seis objetivos de evaluación**: preparación interna, certificación, seguimiento, auditoría de cliente, evaluación regulatoria u otro. No se suman estos conteos: describen dimensiones solapadas del producto.

## Qué significa «desde cero» en la referencia

El blueprint inicial versionado contiene13fases: gobierno, contexto/alcance, arquitectura de procesos, liderazgo/responsabilidades, riesgos/planificación, objetivos/KPI/recursos, competencia/comunicación, información documentada, controles operativos, cliente/proveedor, medición/desempeño, auditoría/CAPA y revisión de dirección/preparación. Las37entradas son actividades de ese blueprintv1.1, no requisitos normativos ni módulos independientes.

En el SaaS, `QMSControlInstance` representa **la implantación de un control** en una sede/proceso. No es un proyecto completo de implantación ISO: carece de norma/edición/proyecto maestro. Las categorías `qms_implementation`, `readiness_assessment`, `certification_preparation`, `transition` y `gap_remediation` clasifican actividades; sus nombres no acreditan un motor global.

## Límites importantes encontrados en Odoo

- El pack inicial legado se define activo en su blueprint; eso no libera el nuevo pack2026. Este último tiene7áreas,38controles y `activation_allowed=false`; su activación requiere revisión competente y una liberación separada.
- El catálogo ISO9001:2026 oficial figura publicado como edición6 al consultar [ISO](https://www.iso.org/standard/9001) el18noviembre2026. **Borrador del pack de Perfect Match** y **estado oficial de la norma** son estados distintos. No cambiar automáticamente la aprobación de nuestro contenido por la publicación de la norma.
- El paquete de migración ISO es un expediente con backups, ensayo, validaciones, autorización y rollback documentados. `action_record_start`/`action_record_outcome` registran inicio, evidencia y resultado: no son un motor que mueva datos de cualquier QMS.
- La importaciónCSV de Odoo sí crea registros y adjuntos, pero es acotada. Requiere procesos/relaciones previos, rechaza códigos documentales existentes y permite una revisión por código en el lote; no reconstruye automáticamente todo el histórico de revisiones, firmas y eventos de otra plataforma. Tampoco importa de forma universal CAPA, riesgos, formación, objetivos y todos los demás módulos.
- Aceptar un documento como migrado no debe fabricar una aprobación histórica. El SaaS actual fija actor/fecha de preparación presentes y aprobación vacía al crear una revisión; una fecha de revisión proporcionada por el usuario no preserva por sí sola la autoría original. Hace falta un contrato explícito de procedencia y de revisión de los datos importados.

## Propuesta para completar el SaaS

Es una propuesta técnica de esta revisión, no una funcionalidad disponible ni una nueva decisión comercial del usuario:

1. **Proyecto QMS por empresa:** situación inicial, alcance/sedes, responsables, objetivo de evaluación y fechas. Debe permitir combinar mejora, migración y transición sin duplicar los mismos registros.
2. **Perfiles y packs versionados:** contenido propio revisado, referencias normativas, aplicabilidad y relación con procesos/controles/documentos/evidencia. Habilitación del addon independiente de los permisos de operación.
3. **Implantación y cambios:** plan por fases, tareas/evidencia, baseline, impacto, revisiones y decisiones de preparación respaldadas por datos; nunca porcentajes inventados o presentados como certificación.
4. **Migración controlada de cliente:** inventario y formatos, prueba aislada, validación y reconciliación, procedencia, revisión/aceptación y recuperación; incorporar tipos de datos por etapas.
5. **Preparación y ejecución de auditoría:** cerrar módulos faltantes de desempeño/revisión de dirección y el workflow de auditoría antes de ofrecer el recorrido integral.

No es necesario reescribir documentos, controles, riesgos, NCR o CAPA que ya funcionan. La brecha principal es la coordinación y trazabilidad global, además de los módulos realmente ausentes.

## Fuentes reproducibles y alcance de verificación

Fuentes Odoo leídas en el commit indicado, con enlaces inmutables:

- [Escenarios y política de preservación](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/hooks.py#L101).
- [Generador: tipos y objetivos](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_implementation/wizard/project_generator_wizard.py#L15).
- [Proyecto y generación](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_implementation/models/implementation_project.py).
- [Blueprint inicialv1.1](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/content/initial_implementation_v1_1.json).
- [Pack2026 en borrador](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/content/iso9001_2026_implementation_pack_v1_draft.json) y [bloqueo de activación](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/models/framework_pack.py#L26).
- [Brechas](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/models/gap_assessment.py), [acciones](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/models/transition_action.py) y [revisión](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/models/transition_review.py).
- [Paquete de migración](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/models/migration_package.py) y [registro de ejecución](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_iso9001/models/migration_execution.py#L352).
- [Importación documental](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_migration/wizard/document_import_wizard.py) y [evidencia](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/blob/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f/addons/pm_qms_migration/wizard/evidence_import_wizard.py).

Fuentes SaaS: `apps/api/src/pmc_api/models.py` (`QMSControlInstance`, documento/revisión), `controls.py` (generación por control), `documents.py` (alta/borrador y revisiones), `control_definitions.py` (categorías), `internal_audits.py`, `internal_audit_independence.py`, `internal_audit_criteria.py`, `main.py` y `apps/web/src/lib/identity-path.ts` (rutas efectivas). UI de criterios explica que una referencia escrita no verifica una norma. ExportaciónHTML de plan y descargas individuales dePDF no equivalen a exportación integral de QMS.

Se revisaron también pruebas fuente de escenarios, implantación inicial y pack2026 de Odoo; no se ejecutaron. La comprobación SaaS de modelos/rutas fue revisada de forma independiente y solo lectura. No se convierten tests históricos en resultados nuevos ni se afirma aceptación funcional de los cinco recorridos.
