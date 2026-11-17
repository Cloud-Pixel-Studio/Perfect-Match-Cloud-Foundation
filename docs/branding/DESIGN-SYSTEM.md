# Design system

## Capas

1. Foundation: tokens, tipografía, foco, motion y temas.
2. Primitives: Button, Field, Badge, Panel, Dialog y FeedbackState.
3. Patterns: FilterBar, Register/Detail, DataTable responsive, KPI y timeline.
4. Product: documentos, evidencia, auditoría y trazabilidad.

`ModalDialog` es el primitive modal actual: usa el elemento nativo `dialog`,
`showModal`, cierre con Escape, retorno de foco del navegador, backdrop y
contenido etiquetado. Audit trail implementa el patrón de filtros, métricas,
registro expandible y diferencias campo a campo sin renderizar HTML de payloads.

No se añade otra librería completa. React/Next, Lucide y CSS tokens cubren el
alcance actual. Los componentes deben exponer nombre/estado semántico, foco
visible, teclado y reduced motion. En móvil, registro y detalle son pasos; no una
versión de escritorio encogida.

La navegación visible se deriva de tenant + rol de membresía + familias de
capacidades QMS activas. Unidad, estado y tarea siguen siendo la siguiente capa
de personalización. Esto mejora presentación, pero el servidor conserva toda
autoridad de acceso.
