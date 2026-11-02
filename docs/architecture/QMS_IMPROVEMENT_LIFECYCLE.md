# Ciclo de riesgos, no conformidades, CAPA y auditorías

Estado: diseño e implementación en progreso, 29 de octubre de 2026. Este diseño
traduce comportamientos observados en los addons de Odoo a la arquitectura multi-tenant
del SaaS. El avance implementado se distingue a continuación del alcance pendiente;
no añade decisiones comerciales.

Avance: registro de riesgos, scores, lifecycle y enlaces a controles/documentos
implementados y validados según `QMS_RISKS.md`. El núcleo NCR también está implementado
con contención, investigación, disposición y cierre auditado, según
`QMS_NONCONFORMITIES.md` (28 pruebas PostgreSQL propias y OIDC/API/proxy PASS).
Las relaciones NCR a riesgos, controles, evidencia aceptada y revisiones documentales están implementadas
en `QMS_NONCONFORMITIES.md`; quedan CAPA y hallazgos. La aceptación visual de estos
flujos aún no está completada.
El contrato verificable CAPA y su separación entre reglas Odoo y controles SaaS
están en `QMS_CAPA_IMPLEMENTATION.md`; CAPA sigue sin código funcional.

## Dependencias y relaciones

El ciclo funcional conecta evaluaciones y procesos de origen con una acción verificable:

```text
Riesgo u oportunidad ─┐
Hallazgo de auditoría ─┼─> No conformidad ─> CAPA ─> acciones ─> revisión de eficacia
Problema de cliente ──┘                         └─> evidencia documental controlada
```

Odoo permite iniciar CAPA desde riesgo o NCR; una auditoría puede convertir un hallazgo
interno emitido en NCR. Una NCR puede relacionar control/implementación, documento,
evidencia y riesgos. La auditoría de proceso QMS también relaciona hallazgos con sus
criterios, evidencia de auditoría, proceso y controles. Estas relaciones deben ser
explícitas, navegables, tenant-safe y conservar el origen sin copiar datos privados a
otra unidad.

Orden de implementación recomendado por dependencias: (1) riesgos y oportunidades,
(2) NCR con relaciones a riesgo y documentos, (3) CAPA con origen NCR/riesgo y acciones,
(4) hallazgos de auditoría y creación transaccional de NCR, (5) centro de acciones y
reportes. La secuencia es propuesta técnica y puede ajustarse al validar el roadmap.

## Alcance funcional derivado de la fuente original

### Riesgos y oportunidades

- Registro versionado por tenant/unidad/proceso; tipo riesgo u oportunidad, categoría,
  fuente, descripción/causa/efecto o beneficio, responsable y fechas.
- Evaluación inicial y residual de probabilidad e impacto de 1 a 5, score calculado y
  nivel. Umbrales moderado/alto/crítico configurables con versión y ámbito, no como un
  ajuste global que afecte tenants silenciosamente.
- Estrategia de respuesta, plan, vencimiento, revisión y cierre con responsable y nota.
- Flujo de referencia: `draft → assessed → action_required → monitoring → closed`, con
  revisiones auditadas. La matriz exacta de transiciones se debe confirmar contra las
  acciones y validadores completos del addon antes de codificar.
- Relaciones con implementaciones de controles y revisiones documentales liberadas.
  CAPA puede originarse desde un riesgo y heredar su contexto con snapshot trazable.

### No conformidades

- Código único por tenant (compartido entre sus unidades); título, origen (`internal`, `customer`, `supplier`,
  `process`, `product`, `document`, `audit`, `other`), descripción, fecha/detector,
  owner, severidad (`minor`, `major`, `critical`) y fecha objetivo.
- Contención opcional/obligatoria con acción, responsable, fecha y confirmación. Si se
  exige, investigación no empieza ni se permite cierre mientras permanezca incompleta.
- Investigación y causa raíz, disposición (`use_as_is`, `rework`, `repair`, `return`,
  `scrap`, `information_only`, `other`), acción requerida y verificación/cierre con
  notas requeridas. Mantener origen de auditoría cuando aplique.
- Flujo de referencia Odoo: `draft → open → containment → investigation →
  action_required → verification → closed`; cancelación solo desde estados permitidos.
  La tabla ya confirmada e implementada permite omitir contención cuando no se exige
  y cerrar desde `action_required` o `verification`; ver `QMS_NONCONFORMITIES.md`.
- Conectar registros del mismo tenant/unidad; al enlazar controles/documentos validar
  ámbito y existencia. En el SaaS enlazar documentos mediante revisión liberada y limpia,
  nunca exponer claves de storage ni aceptar adjuntos sin antivirus.

### CAPA

- Origen explícito y mutuamente excluyente: NCR o riesgo, u otros tipos no vinculados.
  Solo un origen de los tipos compatibles; validar tenant, unidad y proceso.
- Enunciado del problema, método (`5why`, fishbone, `is_is_not`, other), análisis y
  causa raíz verificada. Los formularios guiados deben tener prompts originales PMC;
  no copiar texto protegido sin autorización.
- `5why` crea cinco slots estables una sola vez; no se borran, reordenan ni duplican.
  La transición a plan requiere respuesta inicial y respuestas contiguas desde el primer
  slot, además de análisis resumen. Fishbone permite causas múltiples y exige al menos
  una causa confirmada con base de evidencia/rationale; categorías del addon son seis.
  `is_is_not` crea cuatro dimensiones fijas (what/where/when/extent) y exige `is`,
  `is_not` y distinción; cambio es opcional. Método `other` exige nombre y queda
  bloqueado al comenzar análisis. Causa raíz se bloquea al implementar y puede
  refinarse al reabrir tras resultado ineficaz.
- Acciones individuales con dueño, plazo, estado y notas de verificación. No pasar a
  implementación sin acciones; no concluirla hasta que todas las acciones activas estén
  completadas o verificadas.
- Revisión de eficacia requerida por defecto, fecha, revisor diferente del responsable
  de implementar, resultado `effective`/`ineffective` y notas. Resultado ineficaz vuelve
  a `action_planned` sin borrar el resultado previo; no se presenta como cierre efectivo.
  La implementación no se completa sin al menos una acción activa; cada una debe estar
  completa o verificada. Registro de acciones conserva historial y después de iniciar no
  se elimina.
- Flujo de referencia: `draft → analysis → action_planned → implementation →
  effectiveness_review → effective/ineffective → closed`; se verificará cada transición
  contra código y tests originales. Acciones de CAPA: open → in_progress → completed →
  verified; manager verifica/cancela y acciones iniciadas no se borran.

## Seguridad y consistencia del SaaS

- Capacidades explícitas por scope y función (`risks.*`, `ncr.*`, `capa.*`), separando
  lectura, mantenimiento y revisión. Seat, owner, asignación de tarea y rol organizativo
  nunca conceden autoridad de aprobación. Auditores quedan limitados a lectura.
- PostgreSQL con RLS forzado; claves foráneas compuestas impiden mezcla tenant/unidad/
  proceso en registro y referencias. El API valida lo mismo para mensajes entendibles;
  triggers cubren escrituras directas.
- Las transiciones se hacen por comandos, con lock del padre primero, control de
  `row_version`, actor actual y decisiones obligatorias. No se permite editar estado
  directamente. Un cierre no elimina ni sobrescribe pasos anteriores.
- Eventos auditables en la misma transacción, con hash de campos narrativos, actor,
  decisión, timestamp y request ID. Fuera de alcance para perfil global: configuración
  por tenant con historial; no introducir privilegios `SECURITY DEFINER` innecesarios.
- Para causa raíz, evidencia, información de cliente/proveedor y notas de incidente,
  aplicar minimización en logs y reportes. Las lecturas y exports requieren autorización
  del módulo, unidad y datos enlazados.

## Aceptación mínima antes de integrar en producto

1. Crear, leer, modificar y revisar NCR/riesgo/CAPA con scopes permitidos; rechazar
   tenant, unidad, proceso, membresía y referencias inactivas o ajenas.
2. Forzar RLS: consultas anónimas/sin tenant, tenant alterno y auditor no pueden leer ni
   mutar; seats/owner sin grant no adquieren autoridad por accidente.
3. Rechazar salto de estado, write directo, transición con versión obsoleta, falta de
   causa/decisión/contención/acción/notas, autocierre o auto-revisión cuando el flujo
   requiere separación de funciones.
4. Verificar aislamiento en búsqueda, filtros, conteos, paginación, reportes y relaciones;
   no filtrar si existe un identificador externo de otro tenant.
5. Fallo al escribir evento revierte la operación. Las modificaciones concurrentes
   producen un conflicto recuperable sin perder la versión previa.
6. Los enlaces documentales solo resuelven revisiones limpias liberadas del mismo ámbito;
   malware, archivo en cuarentena, estado obsoleto o enlace directo de storage fallan.
7. Pruebas PostgreSQL de triggers/RLS, API OIDC con dos usuarios y tenants, browser UX
   con al menos responsable/revisor, y migración downgrade que preserve auditoría.

## Referencias originales revisadas

- [Addon de riesgos](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/tree/main/addons/pm_qms_risk): `models/risk.py` y sus pruebas.
- [Addon NCR](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/tree/main/addons/pm_qms_ncr): modelos, seguridad, vistas y `tests/test_ncr.py`.
- [Addon CAPA](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/tree/main/addons/pm_qms_capa): CAPA, acciones, análisis guiados e integraciones NCR/riesgo.
- [Addon de auditoría](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/tree/main/addons/pm_qms_audit): hallazgos e integración con NCR.

En los addons risk/NCR/CAPA/audit también se revisaron las pruebas centrales; CAPA
incluye regresiones de slots fijos, análisis guiados, vínculo origen→CAPA, aislamiento
multiempresa y cadena auditoría/NCR/CAPA. Falta revisar todos los archivos de cada addon,
completar matrices de permisos y confirmar flujos completos en la versión de Odoo
instalada antes de declarar equivalencia.
