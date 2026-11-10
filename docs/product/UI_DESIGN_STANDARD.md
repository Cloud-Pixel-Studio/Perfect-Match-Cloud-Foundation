# Estándar visual y de interacción del QMS

Actualizado el 3 de noviembre de 2026. Las nueve referencias visuales aportadas
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
| Adaptación | Cambiar la composición para móvil, tablet y escritorio, con acceso a toda función. | Menú compacto hasta 920 px y registros de una columna hasta 800 px. Playwright comprueba catálogo a 375/768/1280 px, workspace autenticado a 375/1280 px y seis módulos operativos a 375/1440 px sin desbordamiento. Permisos cambia la tabla por registros etiquetados en móvil. |
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

## Arquitectura por persona, alcance y tarea

La aplicación no debe ser un menú ERP uniforme. La navegación visible se deriva
de la intersección `tenant + unidad + capacidad QMS + responsabilidad actual`;
ocultar una opción sin permiso mejora claridad, pero la API continúa siendo la
frontera de autorización. Cada persona entra al trabajo que debe completar:

| Persona | Inicio prioritario | Navegación visible por defecto | Profundidad secundaria |
| --- | --- | --- | --- |
| Colaborador | Mis acciones, vencimientos y formación pendiente | Documentos publicados, eventos que puede crear y tareas asignadas | Historial propio y referencias relacionadas |
| Responsable de proceso | Salud del proceso, riesgos, controles y NCR de su alcance | Procesos, controles, riesgos, NCR y CAPA de sus unidades | Tendencias, evidencia y dependencias |
| Calidad | Cola de revisión, excepciones y cumplimiento | Todos los módulos QMS autorizados, reportes y auditoría funcional | Configuración de plantillas y análisis transversal |
| Aprobador/revisor | Decisiones pendientes y segregación de funciones | Bandejas de revisión/aprobación y registros vinculados | Evidencia, versión y trazabilidad de la decisión |
| Administrador del tenant | Licencia, seats, estructura y acceso | Organización, usuarios, permisos, workflows y productos contratados | Configuración técnica y auditoría administrativa |
| Ejecutivo/auditor | Riesgo, eficacia y evidencia resumida | Dashboard de solo lectura, reportes y trazabilidad | Drill-down al registro, sin controles de edición |

Reglas de presentación:

1. Mostrar primero `Mi trabajo`, luego `Mi alcance`, después `Explorar`; la
   administración queda separada y solo aparece a quien corresponda.
2. Una página de lista responde qué requiere atención; una página de registro
   responde estado, responsable, próxima decisión, evidencia y trazabilidad.
3. Usar divulgación progresiva: resumen y acción primaria visibles; historial,
   configuración y datos técnicos bajo pestañas o paneles expandibles.
4. No usar el seat o el rol comercial como permiso QMS. Las acciones se muestran
   por capacidad explícita y alcance de unidad, con segregación de funciones.
5. Conservar filtros por persona/unidad/estado y permitir vistas guardadas sin
   alterar la política de acceso.
6. En móvil reestructurar: lista y detalle se vuelven pasos separados; no se
   encoge simplemente la versión de escritorio.
7. Mantener lenguaje específico del dominio: “Revisión pendiente”, “Eficacia por
   verificar” o “Documento por liberar”, no tarjetas genéricas como “Elemento”.

Estas reglas se apoyan en patrones oficiales role-based/adaptive de SAP Fiori,
variantes por persona y páginas list/record de ServiceNow, bandejas “My actions”
de Qualio y acceso contextual por ubicación/rol de ETQ. Son referencias de
arquitectura de información; Perfect Match conserva identidad y componentes
propios y no copia interfaces propietarias.

El hito visual local del 3 de noviembre eleva la presentación sin cambiar el
alcance funcional: el catálogo incorpora una demostración ilustrativa rotulada,
una progresión comercial tenant→seats→addons y una explicación visual del ciclo
Define→Operate→Prove. El workspace usa un encabezado ejecutivo, contexto privado
del tenant, iconografía consistente por área y un Centro de Acciones poblado. La
segunda capa convierte procesos, documentos, controles, riesgos, NCR y CAPA en
espacios de trabajo escaneables: registros laterales con desplazamiento,
superficies de detalle jerarquizadas, metadatos y vínculos agrupados, y un
catálogo de controles plegable en dos columnas. Las seis capturas Darwin fueron
inspeccionadas y actualizadas. Las equivalentes Linux del workspace se
regeneraron e inspeccionaron en el contenedor oficial Playwright 1.64.1; los 13
escenarios pasaron en ese entorno y CI debe confirmar el nuevo baseline antes de
cerrar la regresión multiplataforma.

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

La ejecución local posterior al hito cubrió nueve escenarios: los cuatro del
catálogo, workspace autenticado en móvil y escritorio, navegación desde una
acción al registro autorizado exacto y recorridos de los seis módulos operativos
en móvil y escritorio. Los nueve pasaron Playwright; las vistas que ejecutan axe
conservaron cero hallazgos WCAG A/AA y no presentaron overflow. El recorrido de
módulos adjunta capturas completas al reporte para inspección. Esto es evidencia
automatizada y visual acotada, no una declaración de conformidad WCAG ni
sustituto de pruebas con lector de pantalla y usuarios reales.
