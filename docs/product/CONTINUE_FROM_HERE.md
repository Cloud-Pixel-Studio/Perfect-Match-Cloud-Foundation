# Retomar Perfect Match QMS desde otro chat

Actualizado: 11 de noviembre de 2026 (America/New_York).

## Leer primero

Repositorio oficial: https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation

La rama con el trabajo visual más reciente es **`codex/ai-design-studio`**,
PR borrador [#17](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/17).
Leer `CHECKPOINT.md` y este archivo en esa rama. `main` todavía no contiene estos
cambios. No fusionar ni desplegar sin aprobación humana.

Cadena de PRs aún sin fusionar: #13 plataforma/seguridad → #14 identidad →
#15 cierre visual → #16 auditoría interna 0040 → #17 Design Studio. El PR #17
tiene como base `codex/internal-audit-foundation`; no volver a apilarlo sobre main
sin revisar la cadena completa.

## Producto y estado real

- SaaS propio, independiente de Odoo. Cada empresa tiene un espacio separado
  (tenant) y seats dentro de ese espacio. El QMS completo es el producto base;
  los addons comerciales son normas ISO/ediciones. No hay precios confirmados.
- Next/React/TypeScript e Inter; FastAPI; PostgreSQL con RLS forzado; Keycloak
  OIDC; almacenamiento privado S3/SeaweedFS y ClamAV. Seats y roles no conceden
  autoridad QMS: las capacidades se asignan de forma explícita por ámbito.
- Ya existen organización, procesos, documentos controlados, controles y
  evidencia, riesgos, NCR, CAPA, workflows, Centro de Acciones y bitácora técnica.
  La equivalencia funcional completa con Odoo sigue pendiente. Consultar
  `docs/product/ODOO_FUNCTIONAL_PARITY_MATRIX.md` antes de afirmar paridad.
- Auditoría interna 0040 tiene planificación backend probada; aún faltan las
  siguientes verticales y su interfaz. La bitácora técnica no la reemplaza.
- Subscripciones, enforcement de seats, entitlements ISO, facturas y renovación
  siguen pendientes de backend y política comercial.

## Hito visual actual

Identidad **Aligned Evidence**: logos SVG/PNG, tokens, Inter empaquetada,
claro/oscuro y catálogo `/products`. `/design-studio` contiene seis PNG finales,
dos fondos originales generados y una captura real con datos sintéticos.
Brand Kit, dimensiones, procedencia y SHA-256 están en
`apps/web/public/brand/design-studio/`.

El último ajuste corrige el logo bloqueado por CSP mediante clases CSS26/40,
añade tema claro/oscuro a la galería, descarga directa de los seis PNG, un acceso
móvil desde el catálogo y títulos de página sin duplicar el nombre de marca.
Cada vista previa muestra exactamente el PNG que descarga.
No se habilitaron proveedores de generación ni publicación. Los assets siguen
en revisión humana. Ver `docs/design-studio/IMPLEMENTATION-REPORT.md`.

## Pruebas y límites

La primera entrega tiene 43 unitarias y 15 Playwright/axe Linux PASS en GitHub
(`4ad33be`). Su release gate permanece FAIL: 7 High en Keycloak y 2 en
SeaweedFS; API/web/PostgreSQL/ClamAV tienen 0 High/Critical. ZAP2.17 reporta
solo hallazgos informativos. Artifact13901631672, SHA-256
`7d62b27c9902ad3d067cbcfeafafd03443e108a1216a6a154b08cd7b9619b634`.
El último ajuste pasa43 unitarias, lint/tipos/build, secretos y licencias.
Darwin:16/16 de la suite y luego3/3 de galería tras usar PNG exactos.
Linux final:16/16 y otra repetición16/16 sin actualizar capturas ni reintentos.
Los checks remotos del commit que se vaya a revisar deben consultarse en el PR;
no extrapolar evidencia de un commit a otro.

Quedan pendientes aceptación humana, lectores de pantalla, ampliación200/400%,
forced colors y más escenarios responsive. Scanners/axe PASS no prueban por sí
solos seguridad, certificación ISO ni conformidad WCAG completa.

## Acceso local correcto

- SaaS: http://127.0.0.1:3000/
- Catálogo: http://127.0.0.1:3000/products
- Galería: http://127.0.0.1:3000/design-studio
- API8000, Keycloak8080; contenedores Colima `pmqms`.

El puerto3100 era una vista previa: su proxy intentaba resolver `api` fuera de
Docker. OIDC regresa a3000 y CSRF exige ese origen. Para operar el SaaS usar el
runtime Docker en3000. No desactivar CSRF ni cambiar autenticación para solucionar
una vista previa. La sesión existente y la carga de DEMO-NCR-001 fueron
verificadas en el navegador. Nunca poner contraseñas o archivos `.env` en GitHub.

Las compilaciones locales llenaron el disco de la VM. Se retiraron solo tres
imágenes intermedias creadas por esta tarea; el login volvió a303. No se borraron
volúmenes ni datos. Antes de otra compilación completa comprobar espacio y no
limpiar volúmenes de forma automática.

## Trabajo local pendiente preservado en GitHub

La rama **`codex/wip-audit-scope-recovery`**, commit
`6b10edff046abd12089fb052d30e76e949ac35cc`, conserva el borrador0041 y sus
invariantes. Leer `docs/recovery/WIP_INTERNAL_AUDIT_SCOPE.md` en esa rama.
Solo se verificaron sintaxis Python y secretos: NO está probado en PostgreSQL,
NO tiene API/UI y NO debe ejecutarse con `alembic upgrade head`.
El original sigue intacto en el worktree `codex/internal-audit-scope-team`.

## Siguiente paso

1. Revisar checks y diff del PR #17 en su último commit, sin fusionar.
2. Mantener el foco visual: validar con el usuario navegación, catálogo y
   módulos existentes; evitar alterar permisos o contratos por estética.
3. Retomar0041 solo como tarea independiente con pruebas aisladas de RLS,
   migración, independencia y transiciones antes de exponerlo en la interfaz.
4. Resolver los High de imágenes y demás condiciones de release antes de
   considerar producción. No aceptar excepciones silenciosas.

Los checkpoints cifrados y claves se conservan fuera del repositorio. GitHub
contiene código/documentación; no contiene copias de la base, secretos ni claves.
