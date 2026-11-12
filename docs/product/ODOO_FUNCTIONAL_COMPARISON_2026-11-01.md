# Comparación funcional Odoo QMS → SaaS propio

Fecha de corte: 1 de noviembre de 2026.

## Resultado ejecutivo

La referencia Odoo verificada es
`Perfect-Match-Systems/Perfect-Match-QMS2026`, rama `main`, commit
[`d89330cc1a8e9a2ea16992c9b49394f1dc481b7f`](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/commit/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f).

- El árbol contiene 22 directorios `pm_qms_*`.
- 20 son addons funcionales con manifiesto, modelos, vistas o wizards y pruebas.
- `pm_qms_ai` y `pm_qms_portal` son placeholders; sus README indican que Odoo aún no
  tiene implementación.
- De los 20 addons funcionales, el SaaS tiene 9 contrapartes parciales y 11 dominios
  todavía sin contraparte funcional.
- No existe todavía equivalencia completa y aceptada de ningún addon de extremo a
  extremo. “9 contrapartes parciales” no significa 45 % de funciones terminadas.

## Matriz por addon funcional

| Addon Odoo | Capacidades actuales verificadas en Odoo | Equivalencia SaaS | Brecha determinante |
| --- | --- | --- | --- |
| `pm_qms_action_center` | Bandeja unificada de acciones, propietario, vencimiento, prioridad, origen y apertura del registro | Ausente | Falta bandeja transversal de trabajo con permisos y filtros. |
| `pm_qms_app` | Shell y dashboard con readiness, actividades, evidencia, riesgos, NCR, CAPA, auditorías, objetivos, personas y calibración | Parcial | Existe shell/navegación y un tablero operativo de siguientes acciones derivadas de workflow, CAPA, controles y evidencia. Faltan readiness transversal, tendencias y widgets de los módulos aún ausentes. |
| `pm_qms_audit` | Programa, auditoría, alcance, criterios, plan, independencia, evidencia, hallazgos, seguimiento y creación de NCR | Ausente | La bitácora técnica actual no es auditoría interna QMS. |
| `pm_qms_calibration` | Tipos/proveedores/equipos, frecuencia, eventos, mediciones, certificado, fuera de tolerancia, impacto, NCR/CAPA y cuarentena | Ausente | No existe inventario de equipos ni ciclo metrológico. |
| `pm_qms_capa` | Origen NCR/riesgo, 5 Why/Ishikawa/Es-No-Es, acciones, implementación, verificación, eficacia, reapertura, cierre y relaciones | Parcial avanzada | Falta equivalencia de adjuntos, vínculos a controles, algunas relaciones bidireccionales, reportes y aceptación completa. |
| `pm_qms_core` | Organización, sitio, procesos, controles, instancias, actividades, requisitos de evidencia, eventos, historia y mappings externos | Parcial | La plataforma SaaS cubre tenant/unidades/procesos/permisos/historia; falta cotejo de todas las entidades y mappings del core. |
| `pm_qms_cost_quality` | Tipos y eventos de costo, prevención, evaluación, fallas internas/externas, recuperación, COPQ y correcciones | Ausente | No existe contabilidad analítica de costo de calidad. |
| `pm_qms_customer_quality` | Reclamos, contención, respuesta al cliente, alertas, causa raíz, 8D, issues de proveedor, SCAR, NCR y CAPA | Ausente | Falta el dominio completo de cliente/proveedor y 8D/SCAR. |
| `pm_qms_documents` | Documento y revisiones, review/approve/reject/activate/obsolete/supersede, archivo, responsables y relaciones | Parcial avanzada | El ciclo principal existe y el almacenamiento es más seguro; faltan equivalencia de relaciones/adjuntos, búsquedas/reportes y aceptación UX completa. |
| `pm_qms_evidence` | Evidencia genérica por instancia/requisito, adjuntos/documentos, fechas, expiración, submit/review/accept/reject/expire | Parcial | El SaaS tiene evidencia de implementación por control con revisión independiente, pero no un registro genérico con expiración y múltiples fuentes. |
| `pm_qms_implementation` | Proyectos por packs, controles generados, tareas, readiness center, assessments y snapshots de brechas/evidencia/actividades | Parcial | Existen controles, instancias, actividades y evidencia; faltan proyecto guiado, pack lifecycle, assessment snapshot y readiness center equivalentes. |
| `pm_qms_iso9001` | Perfiles/ediciones, escenarios de transición, gap assessment, acciones, revisión y paquetes de migración; pack 2026 permanece draft | Ausente | No hay catálogo/versionado propio de ISO 9001 ni transición aprobada ni entitlement. |
| `pm_qms_kpi` | Objetivos, KPI, mediciones, frecuencia, umbrales, tendencias, satisfacción/desempeño de clientes y evaluación/desempeño de proveedores | Ausente | No existen objetivos, series de medición ni evaluaciones de desempeño. |
| `pm_qms_license` | Licenciamiento Odoo, activación, organización, sitios y capacidad | Ausente con adaptación obligatoria | El SaaS necesita suscripciones, tenants, seats y derechos por norma; no debe copiar el mecanismo offline. |
| `pm_qms_management_review` | Periodo, agenda, participantes, snapshot de entradas, decisiones, acciones, métricas y cierre | Ausente | No existe revisión por la dirección ni snapshots trazables. |
| `pm_qms_migration` | Wizards CSV para documentos y evidencia con validación de alcance y relaciones | Ausente | Falta importación controlada, prevalidación, resultados por fila, rollback y trazabilidad. |
| `pm_qms_ncr` | Ocho orígenes, severidad, contención, disposición, causa, workflow, vencimiento, vínculos, adjuntos y cierre | Parcial avanzada | Falta origen desde hallazgo, adjuntos controlados, secuencia automática, vista de CAPA relacionada, reportes y aceptación completa. |
| `pm_qms_pack_quality` | Pack base de calidad, perfiles de mapping versionados, cobertura/completitud, activación y retiro | Parcial | Hay definiciones de controles y metodología; falta lifecycle de packs/mappings, métricas de cobertura y gobierno de edición. |
| `pm_qms_people` | Personas QMS, roles, competencias, matrices, formación, cualificaciones, vigencias y acuses documentales | Ausente | Identidad y permisos de plataforma no equivalen a gestión de competencia. |
| `pm_qms_risk` | Riesgos y oportunidades, scoring inicial/residual, estrategia, plan, revisión, vencimiento, controles/documentos y cierre | Parcial avanzada | El núcleo coincide; faltan adjuntos, paridad de navegación/reportes, relaciones transversales y aceptación completa. |

## Comparación de las áreas más avanzadas

### Control documental

Odoo usa los estados de documento `draft → under_review → approved → active →
obsolete` y, por revisión, agrega `superseded` y `rejected`. El SaaS implementa el
ciclo equivalente de revisión, aprobación, rechazo, liberación y obsolescencia.
Además, el SaaS ya exige almacenamiento privado, análisis antivirus, hash SHA-256 y
separación entre preparador y aprobador.

La brecha restante no es el flujo básico: son las relaciones funcionales completas,
adjuntos adicionales, búsqueda/paginación/reportes y la aceptación visual con usuarios.

### Riesgos y oportunidades

Odoo maneja `draft`, `assessed`, `action_required`, `monitoring` y `closed`, con
probabilidad e impacto 1–5, valoración residual, estrategia, fechas, vencimiento y
relación con controles/documentos. El SaaS cubre ese núcleo, agrega umbrales registrados
por riesgo y conserva vínculos mediante snapshots retirables.

Para cerrar paridad faltan adjuntos, reportes/tendencias, enlaces transversales completos
y el recorrido de aceptación visual.

### No conformidades

Odoo maneja `draft`, `open`, `containment`, `investigation`, `action_required`,
`verification`, `closed` y `cancelled`. El SaaS tiene la misma cadena principal,
validaciones de contención y cierre, concurrencia optimista y vínculos a riesgo,
implementación de control, revisión documental limpia y evidencia aceptada.

Quedan origen automático desde hallazgo de auditoría, adjuntos, numeración automática,
relación visible con CAPA, reportes y aceptación visual completa.

### CAPA

Odoo incluye origen NCR/riesgo, análisis 5 Why, Ishikawa y Es/No-Es, plan, acciones,
implementación, eficacia, reapertura, cierre y cancelación. El SaaS cubre esa columna
vertebral y añade verificación independiente del implementador, ciclos históricos de
eficacia y evidencia documental con hash.

Quedan los vínculos de CAPA a implementaciones/evidencia, vínculos a controles,
adjuntos, algunos rollups y reportes. Por ello sigue siendo parcial aunque sea una de
las áreas más maduras.

## Seguridad: equivalencia y diferencias

Odoo aplica grupos, reglas de acceso, alcance de compañía/organización, restricciones de
workflow, tracking y pruebas por addon. El SaaS ya aplica OIDC, CSRF, aislamiento
tenant/unidad con PostgreSQL RLS forzado, capacidades QMS explícitas, bitácora append-only,
concurrencia por versión, almacenamiento privado, antivirus y hashes.

Estas mejoras no compensan funciones ausentes. Tampoco permiten declarar producción:
continúan pendientes MFA/TLS productivos, backup/restore y RPO/RTO probados, resolución
de vulnerabilidades upstream, mapeo ASVS/ISO 27001/NIST, revisión de aislamiento,
escaneo autenticado y pentest.

## Orden recomendado para alcanzar paridad

1. Terminar CAPA: evidencia/implementaciones, relaciones y aceptación visual.
2. Construir auditoría interna completa para habilitar hallazgo → NCR → CAPA.
3. Implementar dashboard ejecutivo y Action Center sobre los módulos ya existentes.
4. Implementar personas/competencias y calibración.
5. Implementar KPI/objetivos y revisión por la dirección.
6. Implementar calidad de cliente/proveedor, 8D, SCAR y costo de calidad.
7. Implementar migración controlada.
8. Completar packs/mappings versionados y luego ISO 9001 como addon comercial.
9. Construir suscripciones, seats y entitlements como servicio SaaS propio.

## Evidencia consultada

- Árbol completo de `addons/` y manifiestos del commit de referencia.
- Modelos y workflows de documentos, riesgos, NCR, CAPA, auditoría, calibración,
  KPI/objetivos, revisión por la dirección, personas, calidad de cliente/proveedor,
  costos, implementación, mappings e ISO 9001.
- Código, migraciones, rutas, pruebas, arquitectura y `CHECKPOINT.md` del SaaS local.

Esta comparación describe funcionalidad evidenciada; no evalúa licencias para copiar
contenido, certificación ISO, aptitud productiva ni aceptación del usuario.
