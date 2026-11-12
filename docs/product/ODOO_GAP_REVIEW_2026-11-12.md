# Brechas Odoo → SaaS · 12 noviembre2026

Comparación de código, modelos y flujos. No se ejecutó Odoo ni se verificó la
versión exacta de una instalación de cliente. No se trasladó código Odoo al SaaS.

Fuentes verificadas:

- Referencia secundaria oficial: [Cloud-Pixel-Studio/perfect-match-qms](https://github.com/Cloud-Pixel-Studio/perfect-match-qms/tree/d89330cc1a8e9a2ea16992c9b49394f1dc481b7f), HEAD `d89330cc1a8e9a2ea16992c9b49394f1dc481b7f`.
- Su `deployment/customer/modules.txt` contiene20 addons funcionales. AI y Portal
  son placeholders sin manifiesto y no se cuentan como funcionalidades existentes.
- SaaS propio: `ba884bcba9e75422218a7b1f409d6d0a7b88876e`, API/modelos/routers,
  componentes y arquitectura del checkout activo. Las notas locales no cambian código.
- El README del repositorio privado histórico coincide con el de la referencia;
  para esta revisión se usó la referencia secundaria oficial indicada por el usuario.

## Estado por los20 bloques funcionales de referencia

**11 tienen contraparte parcial;9 carecen de una vertical funcional equivalente.**
Es un conteo de bloques, no un porcentaje de funciones ni aceptación de paridad.
Todavía no hay equivalencia completa verificada opción por opción.

Parciales: core, app/dashboard, Action Center, documentos, evidencia, riesgos,
NCR, CAPA, auditoría interna, implementación y pack/metodología de calidad.

Sin vertical equivalente: KPI, revisión por la dirección, personas/competencias,
calibración, calidad cliente/proveedor, costos de calidad, importación/migración,
perfil ISO9001 y licensing comercial adaptado al SaaS.

## Funciones pendientes

| Área | Brecha vigente |
| --- | --- |
| Auditoría interna | Hay programas/planificación backend0040. Faltan alcance, criterios, agenda/equipo, independencia, ejecución, evidencias, hallazgos/seguimiento, hallazgo→NCR y UI. El borrador0041 no probado no cuenta como implementado. |
| Objetivos/KPI | Metas, frecuencia, umbrales, mediciones históricas verificadas, tendencias, satisfacción de clientes y evaluación/desempeño de proveedores. |
| Revisión por la dirección | Agenda/periodo/participantes, snapshot histórico de entradas, decisiones, acta y acciones con responsable/verificación/cierre. |
| Personas/competencias | Personas QMS, requisitos por rol, matrices/evaluaciones, formación, cualificaciones/vigencias y acuses de lectura. Usuarios/permisos no equivalen a este módulo. |
| Equipos/calibración | Inventario, programación, mediciones/eventos/certificados, revisión, cuarentena/retorno a servicio e impacto fuera de tolerancia→NCR/CAPA. |
| Calidad cliente/proveedor | Reclamos, respuesta al cliente, issues de proveedor,8D, SCAR, respuesta/eficacia, alertas y análisis de causa revisado. |
| Costos de calidad | Prevención/evaluación/fallas internas/externas, recuperaciones, costos netos/COPQ, vínculos de origen y correcciones trazables. |
| Implementación guiada | Los controles/actividades/evidencia ya existen. Faltan proyecto desde packs, sincronización, centro de preparación, brechas/bloqueadores y assessments históricos con snapshots. |
| Packs/mappings/ISO9001 | Gobierno de packs/versiones, revisión de mappings, cobertura/completitud, perfiles por norma/edición; escenarios, brechas y acciones de transición, revisión de preparación y migración/reconciliación aprobadas. |
| Importación general | CSV de documentos/evidencia, adjuntos, validación de columnas/fechas/ámbito y resolución de relaciones. No se atribuye a Odoo un preview/rollback UI no verificado. |
| Licenciamiento adaptado | Odoo tiene firma, entorno, vigencia y límites de compañías/sedes/usuarios. Falta implementar suscripción por empresa, seats y derechos ISO propios del SaaS. Cobros/facturación SaaS son adaptación comercial adicional, no una función offline que se copie. |

## Brechas dentro de módulos que ya funcionan

- Evidencia genérica con expiración, múltiples adjuntos/fuentes y sus estados.
  La evidencia actual del SaaS está ligada a implementaciones y revisiones documentales.
- Desde NCR/riesgo, lista/navegación y creación de CAPA equivalentes a Odoo.
  CAPA ya conoce su origen; esto es navegación/relación inversa, no ausencia de CAPA.
- Adjuntos adicionales de riesgos/NCR/CAPA, distintos del PDF documental enlazado.
- Numeración automática de NCR/CAPA. Odoo tiene `ir.sequence/next_by_code`; el SaaS
  recibe códigos de entrada y verifica su unicidad.
- Dashboard ejecutivo: preparación transversal, KPI/tendencias y resúmenes de los
  dominios pendientes. El tablero operativo y Centro de Acciones actuales sí existen.
- Extender Action Center a fuentes todavía ausentes, y cerrar equivalencia de vistas,
  análisis, reportes y relaciones por función; no se presume una lista de informes
  PDF personalizados que no se verificó en Odoo.

## Brechas antiguas que ya se resolvieron

No repetir como ausentes: Centro de Acciones; búsqueda/paginación documental;
UI responsive de procesos/documentos/controles/riesgos/NCR/CAPA; vínculos CAPA a
documentos liberados, implementaciones y evidencia aceptada; o planificación
backend de auditorías. Las comparaciones del1–2nov describían un estado anterior.

## Referencias de código

Odoo: `addons/pm_qms_audit/models/`; `pm_qms_kpi/models/`;
`pm_qms_management_review/models/management_review.py`; `pm_qms_people/models/`;
`pm_qms_calibration/models/`; `pm_qms_customer_quality/models/`;
`pm_qms_cost_quality/models/cost_quality.py`; `pm_qms_implementation/models/`;
`pm_qms_iso9001/models/`; `pm_qms_migration/wizard/`; `pm_qms_license/models/license.py`.
ISO9001:2026 está expresamente marcado como review draft y bloqueado para activación
en `pm_qms_iso9001/models/framework_pack.py`; no se presenta como edición liberada.

SaaS: `apps/api/src/pmc_api/{main,models,internal_audits,control_instance_evidence,capa,capa_trace_links}.py`,
`apps/web/src/components/{workspace-overview,nonconformities-workspace,risks-workspace,capa-workspace,documents-workspace}.tsx`.

Las ausencias se contrastaron con routers/modelos/componentes presentes; las pruebas
anteriores del SaaS no convierten este análisis de fuente en una prueba de paridad
o de comportamiento de una instalación Odoo de producción.

## Avance posterior al corte de comparación

La rama `codex/capa-origin-workflow` implementa listado, apertura y creación
de CAPA desde NCR/riesgo con comprobación de origen/empresa/unidad. Evidencia
y límites en `CAPA_ORIGIN_WORKFLOW.md`. El conteo11parciales/9sinvertical
no cambia: mejorar un bloque parcial no lo convierte en paridad completa.
