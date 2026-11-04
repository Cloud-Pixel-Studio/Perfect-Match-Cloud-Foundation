# Checkpoint de continuidad — 2026-10-28

## Decisiones confirmadas
- Construir SaaS propio completo con equivalencia funcional respecto a Odoo; Odoo es referencia, no runtime del SaaS.
- Comercial: tenant por empresa + seats + addons ISO/ediciones. Todos los módulos QMS incluidos; no vender funciones QMS por separado.
- Sitio web con Productos; área del cliente con lo contratado, seats, normas habilitadas, facturas y renovaciones. Precios, reglas de seats externos y proveedor de pagos pendientes.
- Interfaz seria, bonita, profesional y accesible. Seguridad con la misma exigencia de Odoo; alineación solicitada con ISO 27001/NIST, sin afirmar cumplimiento/certificación.
- Continuar con todo lo necesario y mantener checkpoints breves. No publicar ni fusionar PRs sin autorización específica; no se realizó ninguna de esas acciones.

## Estado actual (leer primero)
- Prueba local 28/10 creó DEV-PROC-01/02 en DEV-ACCESS-UI. Son datos ficticios, conservados con auditoría; permiso temporal processes.manage revocado y verificado en navegador (sin procesos visibles). Sesiones app y SSO de owner/member cerradas. Captura artifacts/process-register-verified.png.
- Registro de procesos: migración 0009/API y panel inicial implementados localmente. 14 pruebas PostgreSQL PASS; aislamiento, permisos, jerarquía, concurrencia, auditoría y bloqueo de archivo de unidades. Detalle/límites: docs/architecture/PROCESS_REGISTER.md. Checkpoint integral PASS (artifacts/checkpoint-process.log): 137 backend distintos y 8 frontend (octavo test ejecutado adicionalmente en artifacts/process-web-tests.log). make up PASS con migración y servicios actualizados; validación visual/funcional del panel PASS el 28/10: crear/editar/responsable/padre-hijo, rechazar ciclo y archivo con hijos activos, archivar/bloquear edición/restaurar. Editor ampliado con responsable, padre y orden; estilos profesionales y foco visible. Ver artifacts/process-editor-final-check.log. No afirmar paridad completa ni producción lista.
- Panel QMS implementado: owner concede/revoca con confirmación e historial; demás roles ven permisos propios. Browser real PASS para login owner, grant, duplicado, cancelación/revocación y lectura member/auditor. Cambio de tenant/rol remonta paneles, deshabilita acciones durante transición y limpia auditoría/respuestas anteriores. Screenshot artifacts/qms-access-panel-verified.png. Último checkpoint PASS: 123 backend + 7 frontend.
- Fixture local pmc-local-owner solo desarrollo, password generada fuera de Git (no imprimir). Bootstrap rechaza entorno ausente/staging/producción (3 tests PASS); usuarios member existentes no elevados. Sede ficticia DEV-ACCESS-UI creada para prueba; grant de lectura a pmc-user-a ya revocado, historial retenido. Sesiones de prueba cerradas; ninguna operación productiva.
- Nuevo avance: migración 0008 + API qms-access/grants y helper SQL de capacidades QMS por unidad; sin permiso implícito por owner/admin ni por compra de seats. 21 pruebas PostgreSQL nuevas PASS. Validación de API previa: backend 120 + frontend 6; ver validación final arriba. Panel ya implementado; registro inicial de procesos añadido (ver arriba), control documental pendiente. Arquitectura: docs/architecture/QMS_ACCESS_ARCHITECTURE.md.
- Corregido proxy web: rechazaba UUIDs de recursos (bloqueaba detalles/edición organización/workflows). Valida segmentos nominales/UUID bajo raíces permitidas, conserva denegación de traversal/URLs/raíces desconocidas. 2 tests nuevos y smoke de ruta real a API PASS.
- Código en este workspace; origin: https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation.
- Rama local actual pmc/workflow-hardening, basada en head del PR #12 e2cdff8abc8781e6f3e246abec08d1db8f2540ea. Se cambió a esta rama para probar/corregir workflows; NO significa merge en main. Cambios locales sin commit/push.
- main remoto observado: 889a5f12e48104a9a612646063035525a8f0dabd (PMC-03). PR #12 sigue abierto; runs históricos quality 34439019052 y security 34439019035 success, pero no validan nuestras modificaciones ni advisories actuales.
- Aplicación completa funcionando en http://127.0.0.1:3000; servicios saludables y acceso visual comprobado. Colima pmqms local (4 CPU, 4 GiB, disco solicitado 24 GiB) sigue encendido. Solo desarrollo con datos ficticios.
- Checkpoint de desarrollo PASS; gate global de seguridad para release FAIL por imágenes de terceros. Evidencia y límites en docs/product/SECURITY_CHECKPOINT_2026-10-26.md. NO confundir PASS de make checkpoint con preparación productiva.

## Implementado en esta sesión
- Tooling aislado artifacts/tooling: Node 24.20.0, pnpm 12.3.4, Python 3.12.15 via uv 0.13.5; Docker CLI 29.9.2/daemon 29.5.2, Compose 5.6.1, Colima 0.10.3/Lima 2.2.1, buildx, jq, ShellCheck y scanners. No se reemplazó Node global. Binarios oficiales verificados por checksums/digests disponibles.
- Wrapper scripts/with-local-tools.sh; configuración secreta fuera de Git: ~/.config/pmcloud/dev.env. Nunca imprimir secretos.
- scripts/prepare-local.sh compatible con macOS, repetición conserva secretos/permisos 600; apps/api/.dockerignore evita enviar .venv al build.
- Migración 0006 bloquea mover configuración publicada a borrador (trigger verificaba solo destino). Regresión falló antes/pasó después.
- Migración 0007: ediciones toman locks compartidos de versiones; publish_version bloquea/refresca antes de validar grafo. Regresión de publicación precargada y de edición de paso durante publicación fallaron antes/pasaron después; suite completa 30 PASS.
- infrastructure/local/postgres.Dockerfile: base oficial PostgreSQL18, apk upgrade, su-exec reemplaza gosu, USER postgres y healthcheck. Trivy imagen 0 vulnerabilidades; Dockerfile 0 configs fallidas. Compose/tests/CI usan pmcloud-postgres:local; build-test-postgres.sh construye la misma imagen. Suites tenant27/org17/workflow30 PASS con ejecución no-root; runtime actualizado saludable.
- workflow_service refresca identidad ORM al bloquear para transición/cancelación: dos regresiones con sesión precargada fallaron antes/pasaron después.
- CSP nonce aleatorio por solicitud + render dinámico, sin unsafe-inline/eval en producción; headers COOP/COEP/CORP; indentación del árbol con CSS.
- Next/eslint-config-next 16.4.3, Vitest 5.0.3 y transitivas corregidas; certifi/urllib3/Mako y pytest actualizados. Lockfiles/export runtime regenerados.
- checkpoint local incluye audit/tenant, organización y workflow; CI ahora bloquea HIGH/CRITICAL también en imágenes de terceros.
- Pines oficiales actualizados: PostgreSQL 18 Alpine digest 10a5c69a…; Keycloak 26.8.1 digest a78d6b79…; SeaweedFS 4.51 digest f7a49e3f… (completos en Compose/reporte).

## Evidencia observada
- make checkpoint PASS (lint, tipos, tests, build, health, SAST/fixtures, secretos, licencias). Nuevo CI no ejecutado remotamente.
- Unit backend 28 PASS; PostgreSQL tenant 27, organización 17, workflow 30, QMS access 21 PASS. Total 123 casos distintos backend; audit payload 2 ya incluidos en unit. Frontend 7 tests PASS. Última evidencia artifacts/checkpoint-access-panel-final.log; runtime/smoke y Trivy repo sin vulnerabilidades/configs fallidas. CI editado, no ejecutado remotamente.
- Auditorías pnpm/pip sin vulnerabilidades conocidas; Trivy repo incluyendo dev sin vulnerabilidades/configs fallidas; imágenes API/web sin vulnerabilidades en scans ejecutados; Gitleaks tree/history sin leaks; OpenGrep 6 reglas, 0 hallazgos (alcance limitado).
- ZAP pasivo shell anónimo: 66 PASS, 2 WARN informativos; 0 alertas bajas/medias/altas. No equivale a pentest autenticado.
- OIDC/tenant/CSRF/denegación member/proxy/logout smoke PASS. HTTPX adapta cookies Secure solo en cliente loopback de prueba; NO prueba browser login/TLS/MFA productivos.
- Storage write/read/delete PASS; acceso anónimo DENIED. Licencias PASS. SBOM repo/API/web generados.
- Bloqueos actuales: Keycloak 2 HIGH OpenJDK sin fix listado (CVE-2026-91403 y CVE-2026-91415), SeaweedFS 1 UNKNOWN y observaciones menores requieren triage. PostgreSQL upstream tenía 1 CRITICAL/26 HIGH; imagen reforzada actual 0 vulnerabilidades. No suprimir ni declarar producción segura.
- Evidencia ignorada en artifacts/; reportes de continuidad en docs/product/. Scans finales no prueban comportamiento QMS todavía inexistente.

## Alcance y referencias
- SaaS integrado main: PMC-00 plataforma; PMC-01 identidad/multitenancy; PMC-02 trazabilidad (NO auditorías internas QMS); PMC-03 estructura organizacional. PMC-04 en PR abierto y rama local con correcciones adicionales.
- Stack recomendado: Next/React/TypeScript, FastAPI/Python, SQLAlchemy/Alembic, PostgreSQL RLS, OIDC, storage privado S3, Docker/CI. Sin razón demostrada para reescritura de stack.
- Referencia Odoo privada: https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026. Inventario confirmado de 20 addons en docs/product/SAAS_DELIVERY_BASELINE.md. Calidad de proveedores no aparece como addon separado: localizar modelos.
- PRODUCT_SCOPE.md define modelo comercial. docs/product/DOCUMENT_CONTROL_ACCEPTANCE.md detalla siguiente dominio a partir de document.py/document_revision.py Odoo leídos. Es especificación, NO módulo implementado.
- Referencias de seguridad verificadas: ISO/IEC 27001:2022, NIST CSF 2.0, OWASP ASVS 5.0.0; propuesta ASVS L2 + controles según riesgo, sin mapeo/control por control ni certificación.

## Próximos pasos
1. Resolver/triage los 2 HIGH de OpenJDK en Keycloak; mantener el gate fallido hasta evidencia suficiente. PostgreSQL ya remediado y probado. No modificar/suprimir scans para obtener PASS.
2. Publicación/grafo reforzados y probados; falta completar revisión general de autoridad del motor y PR #12. No fusionar sin autorización específica y política de Owner.
3. Capacidades QMS por unidad implementadas y probadas: concesión/revocación por owner activo a otra persona, scope explícito, auditores lectura, estados/identidad/tenant/unidad verificados al usar; historia inmutable y auditoría atómica. Panel de gestión implementado y probado; registro inicial de procesos implementado; faltan equivalencia multisedes y controles vinculados; independencia del autor/aprobador se aplica además en futuro dominio documental.
4. Implementar control documental/evidencias con archivos privados/quarantena, estados/revisiones, un activo por documento, permisos y pruebas negativas/concurrentes. Revisar ACLs y tests Odoo para equivalencia completa.
5. Suscripciones/seats/addons ISO, catálogo comercial y resto de módulos QMS siguen pendientes. No se implementaron en este hardening.
6. Faltan recuperación probada/RPO-RTO, MFA productivo, TLS, despliegue, mapeo ASVS/ISO/NIST y validación autenticada completa. Continuar guardando checkpoints al cerrar hitos.
