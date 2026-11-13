# Retomar Perfect Match QMS desde otro chat

Actualizado: 13 de noviembre de 2026 (America/New_York).

Repositorio oficial: https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation

## Punto de continuación

Hito activo: **codex/internal-audit-agenda**, [PR borrador35](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/35), sobre PR34/4d2e80f.
Funcional35674c9ff02727b48ffa9af91edea57a657daec7, arbol79003f8b7477c2dea0959fb8a0ecb04ff0d80e36 identico.
Leer INTERNAL_AUDIT_AGENDA.md y CHECKPOINT.md.0045 añade agenda UTC por minuto,
auditor/auditee/alcance activos, protección de vínculos y solapes dentro de la
misma auditoría. Asignar no concede acceso/ejecución/competencia/independencia.
Local0045 y demo real idempotente; restore previo0044/post0045 verificados.58+199DB,50API/60webunit,
108Linux+11Darwin PASS, sin retries/goldenupdates. Historial retirado conserva
fechas originales tras reprogramar. Checkpoint final/entrega en CHECKPOINT.

PR34: calidad43365509636/CodeQL43365509645 PASS; security43365509662 FAILsolo
gate final. No heredar esos resultados a0045. No aplicar0041 original, mezclarWIP,
fusionar o desplegar. Siguiente: independencia/readiness, ejecución/evidencia/
hallazgos/NCR. Pricing/billing/entitlements siguen pendientes.

Hito anterior: **`codex/capa-origin-workflow`**, [PR30](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/30), finala7b2a9f. Calidad/CodeQL/runtime/50PlaywrightPASS;
releaseFAILsoloKeycloak7High/SeaweedFS2High. No trasladar esta evidencia a otra rama.

Predecesor: **`codex/document-command-feedback`**, [PR27](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/27), entrega funcional683c68e con árbol idéntico. En `ba884bc`, calidad/CodeQL/runtime y36Playwright PASS;
security FAILsolo Keycloak7High/SeaweedFS2High. Esto no acredita el head nuevo.
No modificar seed/datos para adaptar pruebas; usar código de unidad DEV-ACCESS-UI.

Hito anterior: **`codex/document-workspace-reliability`**, [PR borrador #26](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/26), basado en el PR25. Entrega funcional3dfacae; árbol local/remoto idéntico.
Leer `DOCUMENT_WORKSPACE_RELIABILITY.md`: búsqueda/recarga de referencias,
respuestas tardías, filtros vacíos, confirmaciones por registro y paginación.
No hay cambio API/DB/autorización. El checkpoint principal registra las pruebas
finales de este hito; conservar el WIP0041 en su worktree separado.


El hito comercial anterior se conserva en **`codex/product-marketing`**, [PR borrador #25](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/25). La entrega funcional remota `8cbc5c5` tiene el mismo árbol verificado local; el seguimiento posterior solo documenta el handoff. El worktree activo es
`SaaS QMS PerfectMatchSystems Design Studio`; el checkout original conserva el
WIP de Auditoría Interna0041. No resetear, limpiar ni mezclar ese borrador.

La base comercial conserva todas las funciones visuales verificadas en91b26b5.
El remoto `codex/branding-identity-system@ae8f262` tiene el mismo árbol. Los
merges17→16→15 propagaron trabajo entre ramas; no equivalen a integración completa
en main. PR19 consolida hacia la fundación del PR13. Main13e672a contiene PMC-04.
Consultar `EXTERNAL_PROGRESS_RECONCILIATION.md` para refs, tests y límites.

## Hito comercial

`/products` presenta resultados, capturas reales con datos sintéticos, recorrido
de documentos/riesgos/CAPA, preguntas por comprador, espacio por empresa, seats,
normas ISO, seguridad y FAQ. Brief con prioridad, equipo e interés ISO: correo
preparado a **Demo@invperfectmatch.com**, proporcionado por el usuario, y descarga
TXT local. El visitante debe revisar/enviar desde su correo; no hay envío,
backend de leads, agenda, compra, trial automático ni precios confirmados.

Fuentes y decisiones: `SAAS_MARKETING_RESEARCH.md`. Implementación, resultados
y límites: `MARKETING_IMPLEMENTATION_REPORT.md`. Capturas/manifiesto en
`apps/web/public/brand/product/`; renderer restringido a loopback en
`apps/web/scripts/capture-product-marketing.mjs`.

## Producto real

SaaS independiente de Odoo. Empresa=tenant separado; seats internos. QMS completo
como producto base, addons comerciales solo por norma ISO/edición. ISO9001 en
preparación,14001/45001 planeadas. Roles/seats no conceden autoridad QMS.

Next/React/TypeScript, FastAPI, PostgreSQL/RLS, Keycloak, S3 privado y ClamAV.
Ya existen organización, procesos, documentos, controles/evidencia, riesgos,
NCR, CAPA, workflows, Centro de Acciones y bitácora. Auditoría Interna0040 tiene
planificación backend probada, sin UI; faltan siguientes verticales.
`ODOO_FUNCTIONAL_PARITY_MATRIX.md` es el mapa de paridad pendiente.

0041 está preservado en `codex/wip-audit-scope-recovery@6b10edff`, sin validar
migración/RLS/API. No ejecutar su alembic upgrade. El nuevo prototipo externo
`document_control.py` tampoco reemplaza documentos existentes: no tiene API ni
persistencia. No contar manifiestos de agentes como plataforma autónoma terminada.

## Acceso y comprobaciones

- SaaS: http://127.0.0.1:3000/
- Productos: http://127.0.0.1:3000/products
- Biblioteca: http://127.0.0.1:3000/design-studio
- API8000, Keycloak8080; Colima pmqms. El puerto3100 no coincide con OIDC/CSRF.
- Herramientas locales: `scripts/with-local-tools.sh` del workspace original.
- Secretos fuera de Git; no imprimir dev.env ni subir dumps/claves.
- Disco VM limitado. No limpiar volúmenes. Preview comercial usa una capa local
  sobre la imagen existente; no cambió el Dockerfile ni la infraestructura productiva.

## Pendientes que siguen abiertos

1. Verificar CI del head exacto, revisar PR comercial y consolidación19/13 con
   aprobación humana. No fusionar ni desplegar automáticamente.
2. Resolver CVE de imágenes proveedoras y requisitos TLS/MFA/secrets/backups,
   staging/DAST/pentest y evidencia de cumplimiento antes de producción.
3. Completar auditoría interna y paridad Odoo por verticales probadas.
4. Suscripciones, seats enforcement, entitlements ISO, facturas y renovación.
5. Aceptación por usuarios de calidad, lector de pantalla, zoom200/400%, forced
   colors, revisión legal de marca y contenido ISO; axe no es conformidad total.
6. Design Studio tiene assets reales y contratos de agentes, pero no generación
   persistida por tenant, worker/proveedores/costos/aprobación ni publicación.

Backups cifrados y claves separados, fuera del repo. GitHub no contiene secretos,
bases ni copias de datos de clientes. Cada nueva etapa debe actualizar este handoff.


Delivery: [draft PR31](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/31), functional commit `9b066a0e95ed531a48b6bed93bd892933d6b27ac`, tree `c650921234ce1295dd6d413c942561149484dab0` verified identical locally/remotely. This follow-up is documentation only. CI of the latest head remains to be verified.

Entrega: [PR borrador32](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/32), sobre PR31. Commit funcional `072e309484b78144cf811bc228ab292361382bbc`, árbol `c0a934d0af58e38e8c7dba96f94004b145a80ca4` idéntico local/remoto. Este seguimiento solo documenta continuidad. CI del nuevo head pendiente, revisión independiente y aprobación humana antes de merge; sin producción.

Entrega: [PR borrador33](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/33), sobre PR32/8c60a50. Commit funcional `da5f3aa9e44e2e630d178b1d3c07ed49e6d4e627`, árbol `8dbf955688d97604fea96b0d62bbee2b2121934d` idéntico local/remoto. Este seguimiento solo registra continuidad; CI exacto nuevo, revisión independiente y aprobación humana pendientes. Sin merge ni producción.

Entrega: [PR borrador34](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/34), sobre PR33/4de65f0. Commit funcional `81cb998c015a5e97044fba4e4d286110a0a13de2`, árbol `05ba90d7dd4b9774a5bfe8a525f2944e0d67ee73` idéntico local/remoto. Este seguimiento solo documenta continuidad; CI exacto nuevo, revisión independiente y aprobación humana antes de merge siguen pendientes. Sin producción.
