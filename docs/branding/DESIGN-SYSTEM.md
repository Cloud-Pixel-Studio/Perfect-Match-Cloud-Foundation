# Design system

## Capas

1. Foundation: tokens, tipografía, foco, motion y temas.
2. Primitives: Button, Field, Badge, Panel, Dialog y FeedbackState.
3. Patterns: FilterBar, Register/Detail, DataTable responsive, KPI y timeline.
4. Product: documentos, evidencia, auditoría y trazabilidad.

No se añade otra librería completa. React/Next, Lucide y CSS tokens cubren el
alcance actual. Los componentes deben exponer nombre/estado semántico, foco
visible, teclado y reduced motion. En móvil, registro y detalle son pasos; no una
versión de escritorio encogida.

La navegación visible se deriva de tenant + unidad + capacidad QMS + tarea. Esto
mejora presentación, pero el servidor conserva toda autoridad de acceso.
