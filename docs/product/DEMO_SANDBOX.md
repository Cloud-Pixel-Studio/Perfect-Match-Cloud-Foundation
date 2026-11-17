# Demo editable de Perfect Match QMS · 16 noviembre 2026

Disponible en el entorno **local de desarrollo**, no como servicio público:
http://127.0.0.1:3000/. Empresa de desarrollo `Tenant A`; unidad
**DEMO-PRACTICA · DEMO · Laboratorio de práctica**. Es una unidad nueva dentro
de la empresa demo existente, no una nueva empresa ni una suscripción contratada.
Se conservó la demo anterior DEV-ACCESS-UI. No hay datos de clientes reales.

## Acceso y perfiles

La pestaña de entrega queda abierta con el operador `pmc-user-a`. En cada módulo
seleccionar la unidad de práctica si no se conserva la selección. La búsqueda por
prefijos LAB-PROC, LAB-DOC, LAB-CTL, LAB-RSK, LAB-NCR y LAB-CAPA separa los ejemplos
del historial QA (LAB-QA). Las contraseñas locales existentes permanecen fuera de
Git; no se cambiaron ni se crearon cuentas, credenciales o roles comerciales.

| Perfil existente | Para qué sirve |
| --- | --- |
| `pmc-user-a` | Operar procesos, documentos, controles/evidencias, riesgos, NCR, CAPA y planificación de auditorías en esta unidad. |
| `pmc-multi-user` | Revisar documentos/evidencias/CAPA y decisiones de auditoría con las responsabilidades explícitas correspondientes. No se puede revisar evidencia propia. |
| `pmc-local-owner` | Estructura, asignaciones, grants, plantillas Workflow y bitácora. Ser owner no concede autoridad QMS ni permite autoconcederse responsabilidades. |

La demo no convierte al operador en administrador global. Las asignaciones y
grants añadidos son únicamente sobre la unidad de práctica; los otros espacios
siguen aislados. Los departamentos ilustrativos no heredan grants de la sede.

## Ejemplos cargados y operaciones reales

Estos son los ejemplos iniciales, no el número total posterior a las pruebas.
Los comandos de QA añaden registros sintéticos independientes y conservan historia.

| Área | Ejemplos iniciales | Cómo practicar |
| --- | --- | --- |
| Organización | Una sede y dos departamentos; dos asignaciones | Owner crea/edita unidades y asignaciones. Archivo/restauración sujetos a dependencias. |
| Responsabilidades | Dos perfiles QMS explícitos | Owner concede/revoca; operador consulta sus accesos. No hay bypass de permisos. |
| Procesos | Tres procesos | Nuevo, editar, archivar/restaurar. LAB-UI-001 se creó, editó, archivó y restauró desde el navegador real. |
| Documentos | Tres documentos y tres PDF válidos analizados | Crear documento/revisión, descargar y solicitar decisiones con el perfil autorizado. Para modificar un archivo se crea otra revisión; la carga no sobrescribe un archivo existente. Retiro por Obsolete. Los títulos/tipos no tienen un editor genérico posterior al alta. |
| Controles | Uno activo y dos borradores editables | Crear/editar borradores y sus definiciones; activar/retirar. Las definiciones activadas quedan bloqueadas. |
| Implementación | Una implementación, dos actividades y dos evidencias en borrador | Asignar fechas/responsables, ejecutar tareas y completar resúmenes; enviar evidencia y revisarla con otra persona. No hay borrado genérico de evidencia. |
| Riesgos/oportunidades | Dos riesgos y una oportunidad en borrador | Crear, editar valoraciones, tratar, revisar y cerrar. Cierre terminal, sin borrado físico. |
| NCR | Tres borradores | Crear, editar, abrir y recorrer tratamiento; cancelar/cerrar según estado y autoridad. |
| CAPA | Una con plan y acción; otra en borrador | Crear desde NCR/riesgo, editar según etapa, investigar, planificar y ejecutar. Revisor verifica/cancela y decide eficacia. No se inventa una revisión humana real. |
| Auditorías internas | Un programa, dos auditorías, dos alcances, criterios, asignaciones de auditor y actividades de agenda | Crear/editar planificación, retirar alcances/criterios/equipo/agenda con justificación y cancelar expedientes. Independencia/competencia quedan pendientes de decisión real; no se crean atestaciones ficticias. |
| Workflows | Un flujo publicado con tarea asignada y una definición editable | Operador ejecuta su tarea; owner configura versiones y puede retirar/cancelar. No reemplaza los comandos documentales/CAPA. Workflow es de empresa, sin unidad de negocio propia. |
| Centro de Acciones | Tareas reales generadas por CAPA, actividades y Workflow | Abrir registro y operar desde su módulo. La cola es derivada; no se agregan/eliminan filas manualmente. |
| Bitácora | Eventos reales de la carga y pruebas | Owner consulta. No se permite editar o borrar eventos. |

“Quitar” significa la operación de retiro permitida por cada dominio, no borrar
historia. Los registros terminales, las revisiones liberadas y la evidencia
aceptada conservan sus protecciones. Algunas operaciones son irreversibles
dentro del expediente; practicar con un nuevo registro ficticio cuando corresponda.

No se incluyen funciones inexistentes: ejecución/hallazgos/cierre completo de
auditoría, KPI reales, revisión de dirección, formación general, calibración,
calidad cliente/proveedor, costos, importación, billing o packs ISO comerciales.
No hay reset masivo, compra, envío de correo ni sandbox de navegador sin backend.

## Carga reproducible y verificación

Usar el Python del entorno del backend con sus dependencias ya instaladas.
Ejecutar desde la raíz del checkout oficial:

```sh
apps/api/.venv/bin/python scripts/seed-demo-sandbox.py
apps/api/.venv/bin/python scripts/seed-demo-sandbox.py --verify
# Solo después de checkpoint DB verificado; añade datos sintéticos por API:
apps/api/.venv/bin/python scripts/seed-demo-sandbox.py --apply
# Crea registros QA nuevos y comprueba comandos/denegaciones; no borra historia:
apps/api/.venv/bin/python scripts/exercise-demo-sandbox.py --apply
apps/api/.venv/bin/python -m unittest discover -s tests -p test_demo_sandbox.py
```

Sin `--apply`, la carga no modifica QMS. `--verify` inicia sesiones normales y
consulta registros, sin mutaciones de negocio. Los destinos están fijados a
loopback, el fichero local debe declarar development y el login valida el destino
Keycloak local. La ejecución verificada también comprobó la configuración real
del runtime local. No apuntar estos scripts a proxies de producción.

Una segunda carga conservó todos los ejemplos, sin duplicarlos. No sobrescribe
ediciones, no restaura registros archivados ni responsabilidades revocadas.
Catálogos sin paginación que alcancen100 hacen fallar la carga para no inferir
ausencia. Una carga interrumpida puede dejar registros parciales: se detiene,
conserva lo creado y requiere inspección; no intenta reset ni recuperación ciega.

## Corrección descubierta durante QA

El formulario de procesos envía campos y `site_ids` juntos. SQLAlchemy podía
autoflushar el padre al reemplazar sus sedes antes de incrementar la versión,
provocando23514/HTTP500. Ahora la versión avanza antes de esa consulta y un error
de sedes revierte también los datos del padre. No cambia schemas, capacidades,
RLS, contratos API ni dependencias. Tres regresiones confirmaron RED→GREEN;
202 pruebas PostgreSQL del conjunto pasaron, incluido rollback/auditoría.

Runtime: sigue basado en PR39/DB0048, con **solo este archivo corregido** en una
capa local de imagen API. Se preservó la imagen anterior
`pmcloud-api:before-demo-20261116`; solo se recreó API, sin migración ni cambios de
web/Keycloak/storage. Root filesystem read-only y demás protecciones se mantienen.
No atribuir a esta demo las mejoras0049/A02 que solo están en la rama fuente.
Un rebuild desde esta rama incluye el arreglo; volver a una imagen antigua lo pierde.

## Evidencia y recuperación

- CP-DEMO-SANDBOX-00-20261116T192954Z:541 fuentes/Git cifrados y restaurados por hash; bundle PASS antes de cambios.
- CP-DEMO-SANDBOX-DB-00-20261116T193300Z: DB0048/57 tablas; backup cifrado fuera de Git y restauración aislada tmpfs PASS antes de la carga. Incluye respaldo cifrado del módulo API anterior. No se restauró sobre la DB real.
- CP-DEMO-SANDBOX-06-20261116T195151Z:546 fuentes restauradas/SHA256 y bundle PASS; CP-DEMO-SANDBOX-DB-06-20261116T195500Z: respaldo posterior de DB0048/57 tablas restaurado aislado PASS. Sin restaurar sobre la DB real.
-10 pruebas de seguridad del cargador;47 comprobaciones HTTP reales;202 regresiones PostgreSQL PASS. Ruff/formato y mypy de los dos archivos backend PASS; Gitleaks del árbol sin hallazgos; OpenGrep6 reglas/3 archivos sin hallazgos.
- Navegador real sin mocks: crear/editar/archivar/restaurar LAB-UI-001 PASS; documento LAB-DOC-001 con PDF clean y descarga disponible verificados. Capturas locales en artifacts/previews/2026-11-16/.
- Fallos iniciales de los helpers quedaron separados: contexto transaccional incompleto del test, intento de sobrescribir archivo409, cancelación de auditoría sin review403 y salto de estado de actividad409. Se corrigieron los helpers sin relajar validaciones.

Detalle de casos: DEMO_SANDBOX_EVIDENCE.json. No se probaron todos los botones,
no se repitió la auditoría de imágenes y no hay aprobación de producción ni
certificación WCAG/ISO/NIST. El backup DB no sustituye un backup separado de S3;
no se modificaron archivos preexistentes. Los nuevos PDF de práctica se generan
determinísticamente desde el cargador; la recuperación completa con objetos sigue
siendo un requisito operativo independiente.
