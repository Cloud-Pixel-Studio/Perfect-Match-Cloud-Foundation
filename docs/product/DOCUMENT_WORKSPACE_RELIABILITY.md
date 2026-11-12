# Fiabilidad del workspace de Documentos

12 noviembre2026. Rama `codex/document-workspace-reliability`, base `acaf7dd` del
PR25. Cambio acotado al componente existente y sus regresiones de navegador.
No reconstruye Documentos ni usa el prototipo externo `document_control.py`.

## Comportamiento corregido

- Buscar, refrescar o paginar vuelve a cargar los procesos/miembros mediante una
  generación explícita. Ya no depende de que React renderice el pulso temporal
  de capacidades vacías y restauradas.
- Cada lectura de ámbito cancela la anterior y verifica su generación después
  de cada espera. Una respuesta anterior no restaura registros, capacidades,
  referencias, errores o estado de carga de otro ámbito.
- Las capacidades visibles solo corresponden a la unidad verificada. La revisión
  seleccionada debe pertenecer al documento actual. Esto complementa la UI;
  la autorización efectiva sigue siendo responsabilidad de la API/RLS existente.
- Carga de registro, referencias y mutaciones tienen estados diferenciados.
  Los errores de referencias se pueden recuperar sin reutilizar catálogos viejos.
- Una búsqueda de procesos sin resultados permite cancelar/reabrir y corregir el
  filtro. Crear exige referencias listas y un proceso de la selección vigente;
  la validación del servidor permanece intacta.
- Las confirmaciones de obsolescencia y formularios se cierran al cambiar registro
  o ámbito. Las acciones durante una mutación no cambian de registro por accidente.
- El paginador está fuera del grid del registro fijo. Con50 registros el aside
  ya no cubre “Next”; la prueba usa un clic normal, sin forzarlo.

## Evidencia y alcance

Se reprodujeron dos fallos en el runtime anterior: cancelar una búsqueda de
procesos vacía dejaba bloqueado New document, y la confirmación de obsolescencia
se heredaba al seleccionar otro documento. La prueba real de búsqueda/refresco
pasó también antes del arreglo: la pérdida por batching no se reproduce en cada
ejecución. Su causa está documentada por revisión del código.

La prueba nueva de51 registros descubrió además la superposición real del aside
sobre Next. Después de mover el paginador, los siete casos de documentos pasan.

| Caso nuevo | Tipo de evidencia |
| --- | --- |
| Buscar/refrescar y abrir procesos/miembros | Login real, API local y datos sintéticos existentes; sin escribir QMS. |
| Proceso sin resultados, cancelar y reabrir | Fixture de lecturas, cliente autenticado. |
| Referencias503 y recuperación | Fixture503→200, sin mutaciones. |
| Registro51: Next/Previous y referencias | Fixture paginada; clics normales y captura adjunta. |
| Respuesta de referencias retenida al cambiar unidad | Barrera liberada y asentada antes de verificar. |
| Revocación mientras quedan referencias pendientes | Capabilities vacías en fixture; registro/acciones quedan vacíos. |
| Confirmación de obsolescencia al cambiar documento | Fixture, no se ejecuta la obsolescencia. |

Las seis fixtures interceptan únicamente lecturas del componente y rechazan
mutaciones documentales. No prueban por sí solas RLS, aislamiento PostgreSQL o
revocación del servidor. No se cambiaron autenticación, permisos, esquema,
modelos, contratos, dependencias o infraestructura productiva.

Validación final: **59/59 unitarias**, ESLint, TypeScript y build PASS; **26/26
Playwright en Darwin y26/26 en Linux**, sin actualizar snapshots ni reintentos.
Linux usa Playwright1.64.1 fijado por digest
`sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f`.
Los escenarios existentes incluyen axe A/AA y reflow, módulos, login, Action Center,
marketing y galería; los siete nuevos cubren este hito. No se cambiaron los PNG
baseline. Gitleaks árbol/historial y política de licencias PASS; pnpm audit conserva
1 Moderate preexistente y0 High/Critical. No se añadieron dependencias.
Revisión independiente de fuentes: sin bloqueadores P1/P2. CI del head nuevo
sigue requerido; estas pruebas locales no son aprobación de producción.

## Verificación del hito anterior

El PR25 exacto `acaf7ddde631f3572ea29a674bac78f7ee915368` pasó los10 jobs de calidad,
CodeQL, runtime desechable y19 Playwright/axe. Seguridad falla solo en el gate
final: Keycloak26.8.1 tiene7 High y SeaweedFS4.51 tiene2 High. API, web, PostgreSQL
y ClamAV tienen0 High/Critical. ZAP2.17:0 High/Medium/Low y14 informativos; cinco
SBOM válidos. [Run43235351029](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/43235351029),
artifact13953825008, SHA256 `db6dc963c7a9a8844ad32e577101548c2d6efa370e73b7ff634ee34c8fb22a42`.
Este resultado no se atribuye al nuevo head. No merge ni despliegue autorizado.

## Recuperación y pendientes

Checkpoint final preintegración: **CP-DOCUMENTS-06-20261112T144338Z**. Fuente/Git cifrados fuera del repositorio, restauración aislada por hashes y bundle verify antes de subir la rama.

El manifiesto inicial CP-DOCUMENTS-00 está en `.ai/checkpoints/`. La fuente402
entradas y bundle completos se cifraron fuera del árbol; descifrado con hashes
de cada archivo y bundle verify PASS. Clave0600 separada. Sin nueva copia/restore
de DB porque no se cambió esquema ni contenido QMS.

El tratamiento UI preexistente de401/403 durante uploads, otras mejoras de
revisiones, la fixture demo de aprobación completa y la equivalencia funcional
total siguen como tareas separadas. No se declara terminado el QMS ni conformidad
WCAG/ISO por estas pruebas.

Durante el diagnóstico se mostró una cookie de una sesión sintética en una
traza local; esa sesión se revocó por logout y `/auth/me` devolvió401. Las trazas
no se incorporan al repositorio ni a los backups de fuente.
