# Estándar visual y de interacción del QMS

Actualizado el 2 de noviembre de 2026. Las nueve referencias visuales aportadas
por el usuario el 30 de octubre y reafirmadas el 1 de noviembre se mantienen como
requisitos activos. La identidad del producto sigue siendo sobria y profesional;
los colores de las referencias son ilustrativos y no sustituyen la marca propia.

## Mapeo de las nueve referencias

1. Estados de carga mediante esqueletos que preserven la estructura.
2. Diseño realmente adaptable a 375 px, 768 px y 1280 px o más.
3. Jerarquía visual, contenido escaneable y una acción principal clara.
4. Tokens compartidos para color, tipografía, espaciado, bordes y sombras.
5. Consistencia de componentes y comportamiento en modo claro y oscuro.
6. Accesibilidad: texto alternativo, nombres accesibles, foco y contraste.
7. Estados explícitos de vacío, error y éxito, con recuperación apropiada.
8. Estados de interacción hover, focus, active y disabled.
9. Principio rector: una aplicación profesional debe ser consistente,
   accesible y fácil de usar, además de verse bien.

| Criterio | Comportamiento exigido | Estado comprobado |
| --- | --- | --- |
| Carga | Mantener la estructura del contenido con esqueletos y anunciar la carga a tecnologías de asistencia. | Esqueleto reutilizable en CAPA, NCR, riesgos, controles, permisos, organización, procesos, documentos y workflows. |
| Adaptación | Cambiar la composición para móvil, tablet y escritorio, con acceso a toda función. | Menú compacto hasta 920 px y registros de una columna hasta 800 px. Playwright comprueba catálogo a 375/768/1280 px y workspace autenticado a 375/1280 px sin desbordamiento. Permisos cambia la tabla por registros etiquetados en móvil. |
| Jerarquía | Una acción principal por contexto, encabezados claros y texto fácil de escanear. | Navegación por áreas, encabezados consistentes, registro/detalle y acciones principales jerarquizadas en los módulos actuales. Los flujos extensos todavía requieren aceptación con usuarios reales. |
| Tokens | Usar colores, tipografía, espacios, bordes, sombras y estados compartidos. | Tokens centrales en `packages/design-system/tokens.css`; Inter variable se incluye en la aplicación para que la tipografía declarada sea real y reproducible. |
| Consistencia | Los mismos componentes y estados funcionan en temas claro y oscuro. | Tema claro/oscuro, tokens compartidos, paneles y estructura registro/detalle unificada; recorrido visual real realizado en ambos temas. No sustituye aceptación de usuario. |
| Accesibilidad | Teclado, foco visible, nombres accesibles, contraste y movimiento reducido. | Foco global, enlace para saltar, etiquetas semánticas y reducción de movimiento. Axe no reporta violaciones WCAG A/AA en las seis vistas automatizadas; corrigió un nombre accesible de marca. Falta lector de pantalla y aceptación manual completa. |
| Estados | Vistas explícitas de vacío, error y éxito, con recuperación cuando procede. | Estados presentes en registros principales; mensajes de éxito y error ahora comparten tratamiento visual y semántico. Falta validar todos los errores de red y expiración en recorrido manual. |
| Interacción | Hover, foco, activo y deshabilitado distinguibles sin depender solo del color. | Acciones primarias/secundarias y registros tienen foco, hover, active y disabled consistentes; siguen pendientes pruebas exhaustivas de teclado sobre flujos completos. |

La sección pública `/products` usa el mismo sistema visual y explica el modelo
comercial confirmado: QMS base, seats por tenant y addons ISO controlados por
edición. Se verificó en 375, 768 y 1280 px, claro y oscuro, sin desbordamiento. Los
estados de catálogo distinguen preparación y planificación para no presentar
como vendible lo que aún carece de licencias, precios o evidencia de release.

Objetivo de aceptación: WCAG 2.2 AA. El [criterio de contraste de texto](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
exige 4.5:1 para texto normal y 3:1 para texto grande. El [contraste de controles](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast)
requiere 3:1 para las señales visuales necesarias; el [criterio de
reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) usa 320 píxeles CSS
para contenido vertical. Estas metas son requisitos de prueba, no una declaración
de conformidad actual. Las pruebas automáticas de tokens tampoco sustituyen una
revisión visual, de teclado y de lector de pantalla.

## Regresión visual automatizada

Playwright 1.64.1 y `@axe-core/playwright` 4.14.0 son dependencias exclusivas de
desarrollo. Se conservan seis baselines: catálogo móvil, tablet, escritorio y
escritorio oscuro; workspace autenticado móvil y escritorio. Cada ejecución
verifica fuentes cargadas, ausencia de overflow, navegación/foco pertinente,
axe WCAG A/AA y comparación de screenshots. El workflow de seguridad ejecuta
este gate contra el runtime desechable antes de escanear las imágenes finales.

Los baselines están bajo `apps/web/e2e/__screenshots__`; traces, videos, reportes
y capturas de fallo permanecen en `artifacts/` y no se versionan. Una actualización
de baseline requiere inspección humana y debe corresponder a un cambio visual
intencional.
