# Web comercial y revisión externa — 12 noviembre 2026

## Entrega implementada

La página `/products` explica el resultado del producto antes de sus módulos,
muestra el SaaS real y conduce a una demostración concreta. Reutiliza Aligned
Evidence, Inter, Lucide y tokens claro/oscuro; no añade dependencias.

- Hero con captura auténtica y dos pasos claros: explorar y solicitar demo.
- Recorrido de documentos, riesgos y CAPA con tabs accesibles por teclado.
- Preguntas específicas para calidad, responsables de procesos e IT/assurance.
- Oferta: espacio independiente por empresa, seats y normas ISO por edición.
  El QMS es el producto base; no se venden áreas operativas separadas.
- Estados ISO, FAQ y límites comerciales explícitos.
- Brief validado, correo preparado a **Demo@invperfectmatch.com** y descarga TXT
  cuyo contenido coincide con el cuerpo del correo. No hay envío automático.
- Cuatro PNG del runtime con datos sintéticos, filtro real por código DEMO,
  dimensiones y SHA-256. Capturador local restringido a loopback, sin mutaciones QMS.
- CSS acotado a marketing, breakpoints, foco visible y motion reducido heredado.
- Investigación y reconciliación de ramas: `SAAS_MARKETING_RESEARCH.md` y
  `EXTERNAL_PROGRESS_RECONCILIATION.md`. Handoff y checkpoint abreviados.

No cambia API, datos, autenticación, capacidades, licencias, infraestructura o
Dockerfile productivo. El preview de3000 usa una capa local pequeña sobre la
imagen existente para conservar espacio de la VM y el origen OIDC/CSRF.

## Evidencia de verificación

| Comprobación local | Resultado |
| --- | --- |
| Vitest | **59/59 PASS**, incluidas16 pruebas del brief: límites, whitelist, inyección de cabeceras, Unicode y asunto/destinatario fijos. |
| ESLint, TypeScript, Next production build | **PASS**. |
| Darwin Playwright | **19/19 PASS**, ejecución final sin actualizar snapshots ni reintentos. |
| Linux Playwright1.64.1 | **19/19 PASS** al regenerar referencias y **19/19 PASS** en reproducción sin updates ni reintentos. Imagen fijada por digest `sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f`. |
| Productos responsive/axe |375/768/1280px, dark desktop, foco; cero overflow y violaciones axe A/AA en las vistas verificadas. Navegación/FAQ también a320px. |
| Recorrido comercial | Tabs Arrow/Home/End, imagen real cargada, validación seats, mailto fijo/codificado, brief descargado exacto y reset sin persistencia: PASS. No se envió email. |
| Regresiones existentes | Login sintético, administración/bitácora, fallo seguro del refresco, seis módulos, workspace, deep links, Action Center y galería/descarga PNG: PASS en la suite. |
| Gitleaks | Árbol e historial sin secretos detectados. |
| Licencias | Política PASS; sin nuevas dependencias. |
| pnpm audit |0 High/Critical;1 Moderate preexistente en minimatch. |
| OpenGrep local |0 findings en6 reglas Python/91 archivos;1 archivo parcialmente analizado y exclusiones existentes. Esta configuración no valida el nuevo TypeScript. CodeQL remoto del head sigue requerido. |
| Revisión independiente | Sin bloqueadores P1/P2 en fuente; no sustituye CI ni aprobación humana. |

Las primeras ejecuciones detectaron expectativas de copy obsoletas, un selector
de alerta ambiguo y un nombre accesible de marca distinto de su texto visible.
Se actualizaron contratos/selectores y se retiró el override accesible; no se
deshabilitaron reglas axe. Las capturas esperaban incorrectamente al final del
scroll: se sincroniza el scroll y se recalcula el crop. La regeneración filtrada
detectó nombres de búsqueda distintos por módulo; el script ahora los respeta.
Los resultados anteriores a estas correcciones no se presentan como PASS final.

Se inspeccionaron la composición móvil, hero/tour/demo de escritorio y tema
oscuro, los PNG sintéticos y la composición Linux. Los baselines antes de este
cambio permanecen en el historial Git y checkpoint inicial.

## Recuperación y GitHub

Inicial: **CP-MARKETING-00-20261112T024646Z**,768 entradas; fuente y bundle cifrados
fuera del repositorio, descifrado/listado y `git bundle verify` PASS. El manifiesto
sin secretos está en `.ai/checkpoints/`.

Frontera preintegración: **CP-MARKETING-06-20261112T140941Z**. Backups y verificación
se guardan fuera del árbol; claves0600 separadas. El manifiesto externo contiene
inventario/hash de archivos y cifrados. No hubo cambios de esquema/datos; no se
capturó ni se atribuye una restauración nueva de base a este hito.

Entrega sincronizada: [PR borrador #25](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/25), commit funcional `8cbc5c548c12d01c49b9071ed7faf7e6938c06c8`, árbol `a90e7d3ce74588113773894aa13d4006cc0846dd` idéntico al local verificado. Seguimiento de handoff solo documental.

Rama dedicada: `codex/product-marketing`, base de revisión
`codex/branding-identity-system`. Main no contiene aún todo el stack de la
fundación. Consultar CI del head exacto del nuevo PR; esta evidencia local no
supone que sus checks remotos hayan terminado. No merge ni despliegue.

## Límites y pendientes reales

- Correo requiere un cliente mailto o escribir directamente al contacto. Enter
  dentro de los campos no envía ni abre correo; activar el enlace visible. No
  agenda, CRM, almacenamiento de leads o verificación de entrega implementados.
- La captura documental del registro DEMO muestra honestamente que no tiene
  revisiones; no es una demostración completa del ciclo de aprobación. Falta
  preparar una fixture de revisión representativa en un hito funcional separado.
- En el runtime existente, filtrar documentos puede dejar vacío el catálogo
  auxiliar de procesos y deshabilitar creación hasta recargar ámbito. Es una
  observación preexistente de la captura, no pérdida de datos; requiere prueba
  específica y corrección funcional separada, sin cambios aquí.
- No se midió conversión ni rendimiento bajo carga. Las calificaciones de
  productos de referencia no son reseñas de Perfect Match QMS.
- No hay precios, compra, trial automático o addons ISO liberados. Facturas,
  suscripciones, enforcement de seats/entitlements y paridad Odoo siguen abiertos.
- Axe no acredita conformidad WCAG completa. Faltan lector de pantalla,
  forced-colors, zoom y aceptación de usuarios de calidad.
- Release sigue bloqueado por imágenes proveedoras. No se cambian pins ni gates.
  Los prototipos/configuraciones externos no se declaran funciones integradas.
