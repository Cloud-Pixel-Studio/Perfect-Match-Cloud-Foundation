# Matriz inicial de paridad funcional Odoo → SaaS

**Corte histórico2nov.** Para estado vigente leer [comparativa12nov](ODOO_GAP_REVIEW_2026-11-12.md) y [NCR/riesgo→CAPA](CAPA_ORIGIN_WORKFLOW.md). La auditoría0040 ya tiene planificación backend: el conteo actual es11bloques parciales/9sinvertical, sin equivalencia completa verificada.

Estado SaaS actualizado: 2 de noviembre de 2026; inventario Odoo verificado contra
`main@d89330cc1a8e9a2ea16992c9b49394f1dc481b7f`. Esta matriz compara el inventario
`addons/` del repositorio Odoo de referencia con el estado evidenciado en
`CHECKPOINT.md`, arquitectura y recorridos locales. Resume módulos, no funciones
individuales; “parcial” nunca significa paridad suficiente para comercializar.

Conteo corregido: **22 directorios**, de los cuales **20 son addons funcionales y 2 son
placeholders sin implementación en Odoo** (`pm_qms_ai` y `pm_qms_portal`). Entre los
20 addons funcionales, **10 tienen contraparte parcial en el SaaS y 10 no tienen todavía
contraparte funcional**. Ninguno tiene equivalencia completa verificada; este conteo no
mide porcentaje de funciones ni permite afirmar “45 % terminado”.

| Addon Odoo | Función principal según su ficha | Estado en SaaS | Alcance ya evidenciado / brecha principal |
| --- | --- | --- | --- |
| `pm_qms_action_center` | Centro unificado de acciones | Parcial | Cola unificada derivada de workflows, acciones CAPA, actividades de control y revisiones de evidencia, con vista personal/equipo, ownership, vencimientos, permisos tenant/unidad y URL protegida al registro exacto. La integración PostgreSQL verifica asignación, lecturas puntuales y aislamiento entre tenants; Playwright/axe Linux verifica el estado vacío responsive. Falta cotejo completo con Odoo, escenario visual poblado y aceptación con usuarios. Ver `docs/architecture/QMS_ACTION_CENTER.md`. |
| `pm_qms_ai` | Placeholder para funciones futuras de IA | No aplica a la paridad actual | Odoo solo contiene un README que declara que no existe implementación. Cualquier IA futura requiere diseño separado de privacidad, aislamiento tenant, evaluación y controles. |
| `pm_qms_app` | Shell de aplicación y dashboard ejecutivo | Parcial | Shell tenant autenticado, navegación modular y tablero operativo con acciones abiertas, vencidas y próximas según permisos. Faltan tendencias, KPIs, readiness ejecutivo, configuración de widgets y aceptación gerencial. |
| `pm_qms_audit` | Programa de auditoría interna, planificación, evidencia, hallazgos/NCR | No implementado | La bitácora técnica del SaaS no equivale a auditoría interna. Faltan programa, agenda, alcance/criterios, independencia, ejecución, evidencia, hallazgos y seguimiento. Odoo permite crear NCR desde un hallazgo emitido con proceso; el SaaS aún no tiene ese flujo. |
| `pm_qms_calibration` | Equipos, calibración, verificación y fuera de tolerancia | No implementado | Falta registro de equipos, ciclo de calibración, impacto y tratamiento de resultados vencidos/fuera de tolerancia. |
| `pm_qms_capa` | Acciones correctivas y preventivas | Parcial | Registro y análisis 5 Why/Ishikawa/Es-No-Es, plan, acciones, ejecución, verificación independiente, revisión de eficacia con ciclos, cierre, cancelación, referencia externa y vínculos versionados a revisiones documentales, implementaciones y evidencia aceptada, con API/UI e integridad PostgreSQL (0026–0039). La UI separa referencias directas de la trazabilidad heredada de la NCR/riesgo fuente. Faltan cotejo opción por opción, reportes, recorrido OIDC/proxy de 0039 y aceptación UX. Ver `docs/architecture/QMS_CAPA_IMPLEMENTATION.md`. |
| `pm_qms_core` | Entidades y servicios base QMS | Parcial | Tenant, unidades, procesos, permisos, controles y documentos base; falta mapear el resto de entidades originales. |
| `pm_qms_cost_quality` | Costos de calidad y COPQ | No implementado | Falta clasificación de eventos, costos, analítica e integración con revisión de dirección. |
| `pm_qms_customer_quality` | Reclamos, 8D, issues de proveedor y SCAR | No implementado | Falta flujo de reclamación, análisis 8D, coordinación con proveedor y seguimiento. |
| `pm_qms_documents` | Documentos controlados y revisiones | Parcial | Registro, revisiones, aprobación/liberación, AV, storage privado y obsolescencia; falta recorrido visual UX, búsquedas/paginación autenticadas visualmente y aceptación funcional completa. |
| `pm_qms_evidence` | Evidencias y revisión de implementaciones | Parcial | Snapshots por control, enlace documental limpio, envío, revisión independiente y gate de readiness; falta validación de catálogo ISO y otros workflows. |
| `pm_qms_implementation` | Framework packs, proyectos, controles y readiness | Parcial | Controles por proceso, actividades y evidencias; falta proyecto guiado completo, catálogo/versiones de perfiles y transiciones de edición. |
| `pm_qms_iso9001` | Perfiles ISO 9001 versionados y migración | No implementado | Falta perfil propio actualizado, mapping, transición aprobada y entitlement comercial. |
| `pm_qms_kpi` | Objetivos, mediciones y desempeño | No implementado | Falta objetivo, series de medición, umbrales, calidad de cliente/proveedor y tendencias auditables. |
| `pm_qms_license` | Licencia comercial offline y capacidad de derechos | No implementado | Falta modelo SaaS de suscripción, seats, addons ISO, eventos firmados/idempotentes y suspensión/renovación. No copiar el licensing offline de Odoo sin validar adaptación. |
| `pm_qms_management_review` | Snapshots, decisiones y acciones de revisión gerencial | No implementado | Falta agenda de inputs, snapshot, acta/decisiones y acciones trazables. |
| `pm_qms_migration` | Herramientas de migración de documentos/evidencia | No implementado | Falta importación controlada, validación, reporte de errores y trazabilidad de migración. |
| `pm_qms_ncr` | Gestión de no conformidades | Parcial | Registro, ocho orígenes, severidad, contención, causa/disposición, workflow y cierre auditado con RLS/capabilities/UI. Migraciones 0024–0025 añaden relaciones a riesgos, implementaciones, evidencias aceptadas y revisiones documentales limpias, con snapshots y retiro trazable. Conjunto PostgreSQL de 154 pruebas y OIDC/API/proxy PASS. Faltan origen de hallazgo, CAPA, adjuntos controlados, secuencia automática, reportes y aceptación visual. Ver `docs/architecture/QMS_NONCONFORMITIES.md`. |
| `pm_qms_pack_quality` | Controles de calidad y metadatos de mappings | Parcial | Definiciones de controles/metodología QMS; falta confirmar cobertura contra el pack original y separar framework propio de mappings licenciados. |
| `pm_qms_people` | Competencias, formación, cualificaciones y acuses | No implementado | Identidad, membresías y grants son plataforma, no equivalencia del módulo. Faltan personas QMS, roles, matrices de competencia, formación, cualificaciones, acuses, vigencias y alertas. |
| `pm_qms_portal` | Placeholder para portal futuro | No aplica a la paridad actual | Odoo solo contiene un README que declara que no existe implementación. Un portal futuro debe diseñar identidad externa, acceso mínimo, segregación y auditoría. |
| `pm_qms_risk` | Riesgos y oportunidades | Parcial | Registro tenant/unidad/proceso, ratings inicial/residual 1–5 y niveles, estrategia, plan, fechas, workflow y cierre auditado, RLS/capabilities y UI implementados. Conjunto actual de108 pruebas PostgreSQL PASS; OIDC/API/proxy PASS. Enlaces a implementaciones de control/revisiones documentales implementados con snapshots, retiro/historial y permisos del destino. Faltan vínculos NCR/CAPA, política configurable, reportes y recorrido visual. Ver `docs/architecture/QMS_RISKS.md`. |

## Orden de continuación recomendado (propuesta)

1. Completar revisión visual/documental de los tres bloques existentes (organización,
   control documental, controles/evidencia), incluyendo roles independientes.
2. Revisar los addons Odoo a nivel de modelos, workflows, vistas, reglas de acceso,
   reportes y pruebas; convertir cada fila en requisitos verificables y estimación.
3. Construir el catálogo QMS base por dominios: riesgos, no conformidades, CAPA y
   auditoría interna; validar vínculos y trazabilidad entre ellos.
4. Implementar competencias/equipos/KPI/revisión gerencial y resto funcional según
   procesos de negocio y dependencias confirmadas.
5. Diseñar por separado catálogo de ediciones ISO y el billing/seats/entitlements;
   no anunciar disponibilidad antes de validación y controles de seguridad.

Este orden es recomendación de trabajo, no una decisión comercial nueva. El usuario
confirmó que QMS completo es base comercial, que los únicos addons son normas ISO y
que se busca equivalencia funcional con Odoo.

## Fuente y límites de la evaluación

Fuente primaria de inventario: [repositorio Odoo privado de referencia](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026),
árbol y código en `main@d89330cc1a8e9a2ea16992c9b49394f1dc481b7f`, verificados
el 1 de noviembre de 2026. Las
descripciones de la tabla resumen `summary` y `description` de cada ficha. Estado SaaS
basado en el checkpoint del workspace y en los recorridos descritos allí; el siguiente
nivel de auditoría debe leer código fuente, pruebas y reglas de acceso módulo por módulo.
No se infiere que el código Odoo esté licenciado para copiarse ni que el SaaS tenga
paridad, certificación o aptitud de producción.
