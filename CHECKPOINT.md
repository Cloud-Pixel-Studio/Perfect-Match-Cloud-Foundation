# Perfect Match QMS — continuidad ·16 noviembre2026

## Retomar
- Repositorio oficial: Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation. Odoo es solo referencia funcional; no introducir sus dependencias ni mezclar infraestructura.
- Rama actual: **codex/audit-plan-export**, base PR58/8a24809. Consultar git status/HEAD/upstream y PR asociado antes de editar. Sin merge/producción; revisión humana requerida.
- Empresa=tenant independiente; sedes/departamentos son unidades. QMS completo es base, addons=normas/ediciones ISO. Básico1empresa+3seats+1ISO es propuesta del usuario, sin precio ni enforcement implementados.
- Stack vigente: Next/React/TypeScript/Inter/Lucide/tokens claro-oscuro; FastAPI/PostgreSQL FORCE RLS/Keycloak OIDC/storage privado/ClamAV. No reescribir lo operativo.

## Último hito: plan de auditoría descargable
- Leer docs/product/AUDIT_PLAN_EXPORT.md. Nuevo botón Download audit plan: HTML listo para imprimir desde registros reales, alcance/criterios/equipo/agenda, retirados+motivos, empresa/unidad/versión. Solo lectura autorizada; no informe emitido ni ready/start. Sin backend/modelos/contratos/permisos nuevos.
-19 casos nuevos→83frontend PASS; lint/typecheck/build/licencias PASS;24lecturas OIDC/API/proxy de regresión PASS. Paginación completa50/página hasta500/sección, rechazo de duplicados/ámbitos/referencias/cambios de plan-empresa-usuario y permisos; abortar descarga y HTML escapado/CSP.2E2E añadidos con capturas/axe, pendientes de ejecución CI; no afirmar PASS ni pixelbaseline.
-Descarga real navegador LAB-AUD-002/v5 PASS; fichero y capturas en artifacts/previews/2026-11-17. Documento1280 y marco375 sin overflow; claro/oscuro UI inspeccionados y restaurado claro.5pares contrasteAA medidos, no certificaciónWCAG. Ruta team incorrecta detectada en primer intento→team-members corregida y descarga repetida con éxito.0mutaciones QMS/grants/schema.
-Next/eslint-config-next actualizados16.4.3→16.4.5 por GHSA-mfr8-8qww-v76h verificado; patrón vulnerable no encontrado en fuentes. Auditpaquetes:1Moderate dev(minimatch),0HIGH/CRITICAL. Vendors/seguridad global siguen pendientes.
-Web local construido en fuente aislada PR39/f856254+export+Next16.4.5 para no activar A02 sin API. Fuente completa de esta rama también compila. Web healthy/rootfsreadonly/capdrop/no-new-privileges, versiónNext real16.4.5. Anterior pmcloud-web:before-audit-plan-export-20261117. No API/DB/otros servicios cambiados.
-CP-AUDIT-EXPORT-00-20261117T010817Z(559fuentes) y02-20261117T012025Z(562): cifrados externos/restauración SHA256/bundle PASS. Sin cambiosDB, no restoreDB/S3 nuevo. CP final/evidencias se sella tras entrega Git.
-PR58 corregido8a24809: calidad43993188442/CodeQL43993188323 PASS; seguridad43993188444 falla solo gate final. Nueva rama requiere CI/revisión independiente/humana. Sin merge/producción.

## Hito previo: preparación de auditorías consistente
- Leer docs/product/AUDIT_PREPARATION_CONSISTENCY.md. API detecta evaluaciones de independencia/competencia añadidas o retiradas durante la consulta (409/refresh), revalida empresa/actor/lectura y los permisos usados para totales sensibles (403/404). Competencia recalcula la disponibilidad de evaluar tras revocación de review. Historial intacto; sin grants/esquemas/contratos nuevos.
-6 fallos reproducidos antes del fix→6 PASS;127 integración PostgreSQL0049 PASS sobre código final;6 compatibilidad0048 PASS.93 unitarias PASS/568DB omitidas sin harness. Ruff/formato79/mypy43, diff PASS; OpenGrep6reglas/2archivos0, Gitleaks árbol0. Sin nuevo browser/buildfrontend/WCAG.
- Preview API local actualizado SOLO internal_audit_independence.py/internal_audit_competence.py; health/rootfs-readonly/cap_drop/no-new-privileges PASS.24 comprobaciones OIDC/API/proxy PASS, incluida denegación otra empresa.0mutaciones QMS/grants/schema. Lecturas puntuales; no snapshot serializable ni autoridad de ejecución. ready_for_execution sigue false.
-CP-AUDIT-READINESS-00-20261117T003532Z y02-20261117T004122Z:557 fuentes/Git restauradas SHA256/bundle PASS;2 archivos runtime previos cifrados/descifrados idénticos. Imagen anterior pmcloud-api:before-audit-readiness-20261117. Sin cambio DB; no nuevo restoreDB/S3 afirmado.
-PR58/19fafd0: CodeQL43990314033 PASS; calidad43990314141 falla en mypy tests por2 referencias no reexportadas; auditorías/otras suites/frontend PASS. Seguridad43990314009 falla solo gate final. Seguimiento corrige imports de tests sin omitir checks; mypy src tests79 PASS local. Mi validación previa cubría solo43 módulos. Nueva CI/revisión pendientes; sin merge/producción.

## Hito previo: ejecutores Workflow
- Leer docs/product/WORKFLOW_EXECUTOR_VALIDATION.md y WORKFLOW_EXECUTOR_EVIDENCE.json. A05 corregido en API: cada usuario/rol/unidad asignado debe disponer de ejecutor activo owner/admin/member; auditor técnico solo lectura, unidad vacía insuficiente.
- Publicación e inicio revalidan responsables; inicio valida pasos futuros. Transiciones a tareas/aprobaciones exigen ejecutor destino. Inicio terminal y publicación/inicio de plantilla retirada se rechazan. Instancias previas pueden terminar; versiones/historia intactas. No autogrants ni cambio de roles/modelos/migraciones/deps. A06 SQL completo y A09 editor/paginación siguen pendientes.
- Pruebas:4RED previos corregidos;32HTTP/PostgreSQL0049 PASS y32compatibilidad0048 PASS;31Workflowlegacy y18CentroAcciones PASS. Caso cola de auditor ahora publica con admin válido y cambia a auditor después, sin omitir cobertura.
-93API unitarias PASS;562DB omitidas sin harness NO son PASS. Ruff/formato128/mypy79,ShellCheck/diff PASS.49unittest raíz PASS;Gitleaks árbol0,OpenGrep6reglas/2archivos0. QA local OIDC/API8checks PASS,0roles/grants/borrados: solo3plantillas QA retiradas, unidad archivada e instancia completada. No nueva UI/browser/buildfrontend en este hito.

## Demo y runtime real
- http://127.0.0.1:3000/ y /products. Tenant A; unidad **DEMO-PRACTICA · DEMO · Laboratorio de práctica**. Operador pmc-user-a; revisor pmc-multi-user; owner pmc-local-owner configura. Contraseñas en fichero privado, nunca Git.
- Leer docs/product/DEMO_SANDBOX.md. Ejemplos LAB-* persistentes: procesos/documentos-PDF/controles-tareas-evidencia/riesgos/NCR/CAPA/planificación auditoría/Workflow. LAB-QA/LAB-WFX son pruebas con historia. Retirar/cancelar/archivar según dominio, no borrar historia ni resetear datos.
- scripts/seed-demo-sandbox.py --verify solo lee; --apply añade sin sobrescribir ni restaurar grants revocados. scripts/exercise-demo-sandbox.py --apply tiene47checks; runtime-workflow-executors-e2e.py --apply crea SOLO QA local y requiere checkpoint DB verificado. Sin --apply no escriben negocio.
- Runtime sigue **DB0048/PR39** con capas API locales: processes.py fix formulario, action_center.py/action_center_queries.py, workflow_service.py y dependencia existente tenant_access.py y los2 módulos de preparación de auditorías del último hito. tenant_access.py comprueba empresa/actor activos en API Workflow. No se desplegó toda suspensión legacy/RLS0049 ni A02; no atribuirlos al runtime.
- API conserva capas previas; web ahora tiene el export/Next16.4.5 aislado descrito arriba, rootfs read-only/cap_drop/no-new-privileges conservados. Imagen anterior: pmcloud-api:before-workflow-executors-20261116. Otros servicios/datos previos intactos; no vendors nuevos ni producción.

## Entregas y seguridad
- PR55 demo: fix formulario procesos campos+site_ids,3regresiones→202PG PASS;10loader unitarias/47API y browser crear-editar-archivar-restaurar PASS. CI820e482 calidad43957691112/CodeQL43957691140 PASS; fallo global-python/httpx corregido sin instalar deps ni omitir tests.
- PR56 CentroAcciones/0aabd96: elegibilidad antes del límite, resumen completo/misma sentencia, CAPA in_progress/padres operables; filtro unidad excluye Workflow sin scope.18HTTP/PG,31Workflow,10lecturas y browser poblado/deeplink PASS. Ver docs/product/ACTION_CENTER_INTEGRITY.md.
- PR56 calidad43960367180 y CodeQL43960367203 PASS; security43960367674 falla SOLO Enforce final release gates. No inventar CVE actuales sin artefacto verificado. Última evidencia vendor verificada de PR53 tenía7HIGH; no extrapolar al runtime.
- PM **NO GO** comercial. Ningún scanner acredita certificación ISO27001/NIST/WCAG ni toda la funcionalidad. CI/revisión independiente del head de la rama nueva siguen requeridos.

## Recuperación y protección
- CP-WORKFLOW-EXECUTORS-00-20261116T223317Z:551fuentes/Git;02-20261116T224107Z:553;02B-20261116T224744Z:554. Cifrados externos, restauración SHA256/bundle PASS. Respaldo final se sella aparte.
- CP-WORKFLOW-EXECUTORS-DB-00-20261116T224106Z:0048/57tablas restauradas en DB aislada tmpfs antes de QA. Servicio runtime original cifrado/descifrado idéntico; nunca restore sobre DB real. Imagen previa permite revertir solo API. DBbackup no sustituye S3backup; esta QA no cambia archivos.
- Original Documents/SaaS QMS PerfectMatchSystems y Design Studio conservan WIP separado, incluido0041 inválido/lifecycle incompleto: no activar ni sobrescribir. Nunca reset/clean/force-push ni pull/rebase sobre trabajo sin preservar.
- Wrapper de herramientas: /Users/Gerdel_Garcia/Documents/ChatGPT/SaaS QMS PerfectMatchSystems/scripts/with-local-tools.sh. Backend .venv en apps/api. Entorno privado ~/.config/pmcloud/dev.env; no imprimir valores. Puerto3100 no es callback OIDC autorizado.

## Pendientes de producto
- Auditorías: planificación/alcance/criterios/equipo/agenda/independencia/competencia existen; faltan ready/start, ejecución/evidencia/hallazgos→NCR/CAPA, informe/cierre. Nunca activar borrador sin backend/pruebas.
- Alta comercial/invitaciones/autoridad inicial; tenant/seats/ISO entitlements y billing. Catálogos owner aún limitados a100; minimización por unidad/rol, lectura de bitácora y Workflow SQL completo pendientes.
- KPI/objetivos reales, revisión de dirección, formación general, calibración, calidad cliente/proveedor, costos, importación y packs ISO. No hay paridad Odoo completa.
- Staging/operación/TLS-MFA/recuperación integral/S3/aceptación y resolución vendors antes de producción. Sin merge ni despliegue automático.

## Historia preservada
Leer docs/recovery/CHECKPOINT_HISTORY_2026-11-16_WORKFLOW_EXECUTORS.md para checkpoints/pruebas anteriores. Los informes de cada hito son la fuente para sus límites; no reutilizar conteos o PASS históricos como corridas actuales.
