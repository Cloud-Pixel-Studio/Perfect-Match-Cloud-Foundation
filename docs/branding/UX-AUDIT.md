# UX audit

Pantallas reales: acceso, tenant, overview/acciones, procesos, documentos,
controles, riesgos, NCR, CAPA, organización, permisos, workflows, audit trail y
catálogo. Ausentes: onboarding, billing, proveedores, auditoría interna,
formación, reportes y otros módulos de paridad; no deben mostrarse como terminados.

Prioridades:

1. Extender la presentación ya derivada por rol/capacidad a unidad, estado y tarea.
2. Gestionar foco al cambiar de módulo y probar tree/tab semantics.
3. QA owner/member/auditor, dark autenticado, 320 px, zoom y teclado.

Completado el 10 nov: `window.prompt` fue sustituido por un diálogo accesible y
reutilizable. Audit trail dispone de filtros, carga incremental y comparación
campo a campo. La navegación de operaciones se reduce a familias con capacidades
QMS activas; rol de plataforma o seat no se interpretan como autoridad de calidad.
Deep links fuera de las áreas visibles regresan a Overview sin conservar targets
obsoletos. Estas reglas de presentación no reemplazan la autorización del servidor.

Los detalles y reglas por persona se mantienen en
`docs/product/UI_DESIGN_STANDARD.md`.
