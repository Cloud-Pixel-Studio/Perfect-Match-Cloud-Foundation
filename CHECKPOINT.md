# Perfect Match QMS — continuidad del 14 de noviembre de 2026

## Retomar
Repositorio oficial Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation. Worktree activo: tenant-suspension, rama **codex/qms-access-history**, base PR41/8133bac. Entrega funcional [PR44](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/44), commit b14a10aa51218e503952afae69069f6d3ea08e0d. Leer docs/product/QMS_ACCESS_HISTORY.md. Hay seguimiento documental y de controles CI posterior; consultar HEAD/upstream reales. Sin merge ni producción.

Empresa=tenant independiente; sedes/departamentos=unidades. El QMS completo es alcance base y addons=normas/ediciones ISO. Propuesta Básico: una empresa, tres seats y una ISO; no inventar precios ni enforcement. Odoo es referencia funcional, nunca plataforma del SaaS. Stack: Next/React/TypeScript/Inter/Lucide/tokens Aligned Evidence claro/oscuro; FastAPI/PostgreSQL FORCE RLS/Keycloak OIDC/storage privado/ClamAV.

## Implementado y probado en PR44
A02: historial de grants paginado y filtrable, orden created_at DESC/id ASC; cursor ligado a empresa/lector/rol/filtros/límite, sin autoridad propia. Owner ve su empresa; demás roles solo su historia, sin cargar directorios. RLS y revalidación de actividad al terminar. Legacy array100 permanece. Catálogos owner añaden X-Tenant-ID y no-store, conservando JSON. No hay migración, roles, permisos ni dependencias nuevas.

UI: búsqueda, estados, páginas anterior/siguiente, confirmación de revocación y comprobación de duplicado contra conjunto activo exacto. Respuestas/contexto se validan; resultado incierto bloquea reenvío hasta Refresh. Seat/rol comercial no concede aprobación QMS. El catálogo owner de miembros/unidades todavía carga primera100; no confundir ese pendiente con historial paginado resuelto.

Evidencia:42 integraciones HTTP/PostgreSQL +23 regresiones grants PASS;50 API unitarias PASS/491 DB omitidas sin harness.64 web unitarias, lint/typecheck/build, Ruff/formato/mypy74 PASS.16 browser con API/identidad en memoria PASS,375/1440px claro/oscuro comprobados, axe/overflow en cuatro estados acotados. Cuatro capturas y manifiesto en docs/product. Revisión independiente sin P1/P2 en diff acotado; no certificación de seguridad/WCAG.

CP inicial CP-QMS-ACCESS-HISTORY-00-20261114T162818Z:505 fuentes/Git. Relevo CP-PARALLEL-AUDIT-WIP-00-20261114T183858Z:509. CP-QMS-ACCESS-HISTORY-06B-20261114T205452Z:516. Fuentes/Git cifrados fuera del árbol, restaurados por SHA256 y bundle verify PASS. Evidencia final se preserva aparte al entregar.

## Tres auditorías independientes solicitadas
Todas parten de PR41/8133bac y conservan sus worktrees; no integran A02 como si fuera baseline.
- Arquitectura/accesos: **codex/audit-architecture-access**, [PR42](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/42).180 operaciones/131 paths, roles/capabilities/proyecciones/getters y deuda priorizada.50 API unitarias nuevas PASS;449 DB omitidas en esta rama.
- Flujo completo: **codex/audit-complete-flow**, [PR43](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/43).115 casos browser de negocio en memoria PASS. Conserva incidente inicial DB503. Tras recuperación:28 casos PASS,24 reales de marketing/OIDC/lectura y4 simulados;11 pantallas miembro y6 owner, sin POST QMS real ni grants. No equivale a transacciones comerciales completas.
- Operabilidad: **codex/audit-module-operability**, informe MODULE_OPERABILITY_AUDIT.md y PR separado al finalizar.452 integraciones PostgreSQL PASS (449 existentes+3 HTTP nuevas), dos XFAIL estrictos reproducen M01;50 API y60 web unitarias PASS. Inventario180 operaciones; llamadas de funciones no equivalen a HTTP positivo ni cobertura completa.

M01 abierto: reviewer documental mínimo recibe404 al rechazar/aprobar; parent FOR UPDATE requiere author/release/obsolete por RLS. Las pruebas positivas declaran reviewer+release combinado, no ocultan el fallo. Corregir con diseño de bloqueo/integridad y pruebas de concurrencia; no ampliar grants automáticamente.

## Runtime y controles CI
App local http://127.0.0.1:3000/products y SaaS http://127.0.0.1:3000/. **Sigue PR39/DB0048, sin0049 ni A02 desplegados.** El disco Colima48 GiB se llenó y detuvo PostgreSQL. Se amplió a52 GiB conservando4CPU/6GiB y todos los volúmenes. /health volvió200. No se borraron datos, imágenes ni volúmenes; solo88.52MB de caché descartable antes de ampliar. Leer docs/recovery/LOCAL_RUNTIME_RECOVERY_2026-11-14.md.

Config CP-LOCAL-VM-DISK-00-20261114T205033Z cifrada/restaurada. CP-LOCAL-RECOVERED-DB-06-20261114T205600Z:0048/57 tablas, respaldo cifrado y restore aislado tmpfs PASS, sin mutaciones ni migración. No se restauró una copia antigua sobre la DB real.

CI del commit funcional b14a10a: calidad43640244793 y CodeQL43640244784 PASS; security43640244781 FAIL en Gitleaks porque checkout escanea también refs de la auditoría. Cuatro SHA256 verificados de inventario produjeron falsos positivos. Seguimiento limita excepción a esos cuatro valores+path+regla;9 controles nuevos y4 previos PASS, Gitleaks árbol/historia compartida PASS. No desactivar gates. CI del HEAD final y revisión humana antes de merge pendientes.

## Protección y próximos pasos
Original Documents/SaaS QMS PerfectMatchSystems conserva WIP de alcance/equipo y0041 no válido. Design Studio conserva frontend lifecycle incompleto y dos fixtures; no activarlo ni aplicar0041.0049 pertenece a seguridad; futuras migraciones usan ID nuevo. No reset/clean/force-push/pull sobre WIP. Historial detallado preservado en docs/recovery/CHECKPOINT_BEFORE_PARALLEL_DELIVERY_2026-11-14.md y RECOVERY_CHECKPOINTS.md.

Pendientes: corregir M01; validar/aplicar0049 con backup/gates; catálogos grandes y lectura por función/unidad; Workflow auditor-only e integridad SQL; onboarding/invitaciones/autoridad inicial; entitlements tenant/seats/ISO y billing. Auditorías solo plan/preparación: ready_for_execution siempre false; faltan ready/start, ejecución/evidencia/hallazgos→NCR/CAPA, reporte/cierre. Faltan verticales KPI/objetivos, revisión de dirección, formación general, calibración, calidad cliente/proveedor, costos e importación. No hay paridad Odoo completa ni certificación ISO27001/NIST.

Toolchain: usar wrapper absoluto del checkout original Documents/scripts/with-local-tools.sh. Secretos en ~/.config/pmcloud/dev.env, nunca imprimir. Puerto3100 no es callback OIDC autorizado. Mantener backups cifrados y claves separados fuera de Git.
