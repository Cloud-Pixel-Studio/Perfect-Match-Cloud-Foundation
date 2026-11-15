# Auditoría de operabilidad por módulo — 14 noviembre 2026

El SaaS tiene operaciones QMS implementadas y evidencia relevante de integridad, pero **no todas las funciones están aceptadas por HTTP ni existe un QMS completo listo para producción**. Esta revisión además reproduce un defecto funcional de mínimo privilegio: un revisor documental con lectura/revisión/aprobación, sin poderes de autor/liberador, recibe404 al rechazar o aprobar. El defecto M01 permanece abierto y no se ocultó mediante cambios de producto o permisos reales.

## Alcance, base y resultados

Rama independiente `codex/audit-module-operability`, base `8133bac47a0731c31738d942f131b17902bb6fe5` (fuente PR41/0049). Se modifican pruebas de auditoría, documentos/evidencia y un ajuste acotado del scanner/CI por checksums verificados; no API de producto, migraciones, permisos o DB de desarrollo/producción. Odoo no se ejecutó.

La DB local permanece documentada en0048; esta rama no aplicó0049 al entorno real. Los PASS PostgreSQL corresponden a bases desechables sintéticas en tmpfs, con roles bootstrap/migrador/runtime separados. La recuperación de infraestructura local realizada por el agente principal es un trabajo separado y no convierte estas pruebas en aceptación de producción.

| Validación | Resultado y alcance |
| --- | --- |
| Regresión PostgreSQL heredada y verificada en esta rama por el agente inicial |449 casos distintos PASS:199 procesos/documentos/controles/riesgos/NCR/CAPA +121 auditorías +31 suspensión +31 workflows +27 aislamiento +23 grants +17 organización |
| Nuevos casos HTTP/SQL, finalizados en el relevo |3 PASS y **2 XFAILstrict M01**, excluidos de los PASS; AV/S3 en memoria, sesiones/CSRF/API/RLS/ledger reales en SQL desechable |
| Total PostgreSQL |**452 PASS +2 defectos esperados reproducidos**, no454PASS |
| API sin harness DB, corrida final |50 unitarias PASS;454 integraciones omitidas, no aprobadas por esa corrida |
| Web, evidencia del agente inicial sobre la misma fuente |60 unitarias PASS; lint/tipos/build PASS. No se reejecutan por añadir solo pruebas Python/documentación |
| Calidad final API |Ruff/formato PASS, mypy74 archivos PASS; ShellCheck del harness y análisis de secretos acotado de la entrega PASS |
| Observación de ejecución |516 identificadores de función con entrada observada en test PASS;132 funciones de ruta observadas y48 sin observación. **No es cobertura de sentencias/ramas ni éxito HTTP** |
| HTTP positivo registrado explícitamente |30 operaciones de producto con respuesta2xx en los tres casos dedicados PASS; límite inferior de esa instrumentación, no inventario de todo HTTP probado previamente |

Las452 integraciones y50 unitarias suman502 identidades pytest PASS distintas. Las60 pruebas web pertenecen a otra herramienta; no se mezclan como porcentaje de producto ni con los XFAIL. Dos advertencias previas de Starlette/AnyIO se conservan en logs.

## Cómo leer el inventario

[MODULE_OPERABILITY_ROUTES.md](MODULE_OPERABILITY_ROUTES.md) enumera las **180 operaciones de producto en131paths**, reconciliadas exactamente con `app.openapi()`:176 decoradores y cuatro comandos documentales registrados por fábrica. `/openapi.json` del framework no forma parte de esas180 operaciones.

[MODULE_OPERABILITY_EVIDENCE.json](MODULE_OPERABILITY_EVIDENCE.json) vincula operación, función/archivo/línea, tests PASS asociados, HTTP2xx observado, funciones internas, JUnit y hashes. Las trazas registran únicamente entrada de función y nombre de test, nunca argumentos, tokens o cuerpos. Una función puede haberse llamado directamente desde Python, durante setup o para devolver403/404; se documenta esa limitación en cada fila. Los cuatro comandos documentales comparten una función de fábrica: solo la metadata HTTP adicional distingue sus paths.

«No observada» significa ausencia de esa evidencia en esta corrida, aunque pueda haber servicios SQL de ese módulo probados. «HTTP2xx» no significa todas las transiciones, roles, concurrencia, browser ni servicios externos aceptados. Tampoco un contador global de tests demuestra completitud de una vertical.

## Módulo por módulo

| Módulo / funciones actuales | Evidencia concreta | Pendiente o límite material |
| --- | --- | --- |
| Identidad/sesión/empresa | Unitarias OIDC/seguridad;27 aislamiento y31 suspensión; nuevas sesiones sintéticas con cookies/CSRF reales; cambio de empresa autorizado por HTTP en caso de seguimiento | No nuevo intercambio Keycloak/OIDC real ni onboarding comercial; no aceptación de TLS/MFA en producción |
| Organización |17 integraciones: unidades, jerarquía/asignaciones, integridad y aislamiento; rutas/servicios identificados en inventario | Invitaciones/membresías/perfil comercial pendientes; lectura del directorio intratenant sigue amplia |
| Responsabilidades QMS |23 integraciones, concesión/revocación por owner y exactitud de unidad; nuevos casos usan también los comandos HTTP reales | A02limit100 vigente en esta base, desarrollo separado; no seat/licencia ni herencia de autoridad |
| Procesos/sedes | Registro, estados, responsables/sedes y dependencias dentro de las199 integraciones; trazas de servicios concretos | No equivale a mapa completo de procesos, importación ni aceptación de cada rol por HTTP |
| Documentos/revisiones/archivos | Caso HTTP positivo: crear documento/revisión, upload limpio simulado, submit→reject→resubmit→approve independiente→release,409 por versión vieja, descarga bytes/hash/cabeceras, snapshots y ledger SQL. Caso independiente prueba rollback ante fallo del ledger | **M01 bloquea al revisor mínimo**. El positivo usa revisor con documents.release explícito; AV/S3 no son servicios reales ni un PDF de cliente validado |
| Catálogo de controles | Crear definición/actividad/requisito, activar y crear implementación por HTTP/SQL en caso de seguimiento; integridad y estados también en199 casos | No todos los caminos UI de no aplicabilidad/evidencia requerida ni todos los roles/estados HTTP completados |
| Actividades de implementación | Generación, asignación/fecha por HTTP, proyección de vencimiento/actor en Centro de Acciones; comandos de dominio cubiertos por suites de integridad | No se declara ejecución browser completa de cada actividad |
| Evidencia y revisión | Asociación a revisión documental liberada/limpia simulada, envío por HTTP; cola de revisión independiente y retiro del acceso efectivo | Las pruebas no certifican evidencia real, antivirus, storage ni cumplimiento normativo |
| Riesgos y relaciones | Creación/valoración/revisión/estados y relaciones gobernadas en suite SQL; validaciones de fuente y alcance | No se añaden escenarios de cliente ni se confunde risk assessment con importación o verticales completas Odoo |
| NCR y relaciones | Intake/contención/revisión/cierre y vínculos/evidencias en suite SQL, con invariantes de actor/unidad/estado | No hay creación automática de NCR desde hallazgos de auditoría ejecutada, porque esa vertical no existe aún |
| CAPA/intake/análisis | Fuente NCR/riesgo/externa, métodos/estructura, edición controlada y gates en suite SQL; nuevo caso HTTP crea CAPA other, inicia análisis, completa5why y abre planificación | No reemplaza toda variante comercial o de cliente/proveedor |
| CAPA/acciones/efectividad | Registro/ejecución/verificación/revisión/decisiones/retrabajo/cierre/cancelación y trazabilidad dentro de las199 integraciones; nuevo HTTP crea acción asignada y verifica cola | El nuevo caso no ejecuta por HTTP todo el ciclo hasta efectividad/cierre; distinguirlo de pruebas directas de servicio/SQL |
| Workflows genéricos |31 integraciones: definición/versiones/publicación/instancias/transición/segregación/inmutabilidad/concurrencia; instancia real sintética alimenta seguimiento | Persisten auditor-only imposible y profundidad SQL de UPDATE de instancias A05/A06. No configura las aprobaciones documentales/NCR/CAPA |
| Centro de Acciones | Nuevo caso HTTP/SQL prueba las cuatro fuentes existentes: workflow, CAPA, actividad y revisión de evidencia; mine/team, vencimientos, nombres y enlaces exactos | No tareas de KPI/calibración/auditorías ejecutadas inexistentes ni garantía de cola ilimitada; no aceptación browser en esta rama |
| Bitácora técnica | Eventos/rechazo de mutación/atomicidad probados en suites y nuevo rollback documental; historial vinculado a comandos | Lectura owner/admin/auditor empresarial sigue A04; no es módulo de auditorías internas de calidad |
| Auditorías: programas/plan |121 integraciones abarcan estados y versionado del plan, alcance/criterios/equipo/agenda/independencia/autoridad/competencia | El contador121 no demuestra ejecución/hallazgos/reporting/cierre: siguen sin vertical entregada |
| Auditorías: competencia | Registro humano específico con fuente liberada/limpia de fixture, vigencia y revisión append-only/segregación | No formación corporativa general ni certificación; no escaneo/archivo real en esa suite |
| Marketing/Design Studio | Web unitarias/build prueban contratos y composición; browser de recorrido se entrega por separado | No envío de demo, alta, persistencia/aprobación completa Design Studio ni licencia comercial |
| KPI/dirección/personas/calibración/cliente-proveedor/costos/importación/packs ISO | Sin vertical completa equivalente entregada, según fuente y catálogo previo | Deben construirse y aceptarse; no se infiere un PASS porque otras suites estén verdes |
| Suscripción/licencia/billing | No endpoint comercial de licencia/entitlements/seats/ISO/facturación en las180 operaciones | No enforcement ni renovación; propuesta Básico1empresa+3seats+1ISO no equivale a decisión de precio/edición implementada |

Los nombres de tests completos y las funciones realmente observadas están en el JSON; no se atribuye una ruta HTTP positiva a un test que solo invocó su servicio.

## M01 — revisor documental mínimo no puede decidir

**Prioridad P2 funcional y de mínimo privilegio; abierto, reproducido y sin corregir en esta rama.**

Un actor distinto del preparador recibe solo `documents.read`, `documents.review` y `documents.approve` para la unidad exacta. Ve la revisión under_review por GET. Sin embargo, POST/reject y POST/approve devuelven404 `document not found`; revisión y ledger quedan sin cambios.

Causa observada:

1. `documents.transition_revision` bloquea revisión y también documento padre con `SELECT ... FOR UPDATE` antes de validar/ejecutar reject/approve (`apps/api/src/pmc_api/documents.py:449`, parentlock`:474`).
2. La política UPDATE del padre solo admite documents.author/release/obsolete (`apps/api/migrations/versions/0013_document_obsolescence.py:25`). La fila visible mediante SELECT ordinario no aparece en SELECT FOR UPDATE con el revisor mínimo.
3. La función interpreta la ausencia del lock como documento inexistente. No es una denegación por autoaprobación ni un documento de otra empresa: se verifica actor independiente, capabilities exactos y lectura previa200.

Reproductor: [test_document_http_minimal_reviewer_can_decide_without_parent_write_grants](../../../apps/api/tests/test_module_operability_http_integrity.py#L443), parametrizado reject/approve. Un tipo de excepción específico convierte únicamente ese404 exacto, con pruebas de visibilidad SQL e inmutabilidad/ledger, en XFAIL. Cualquier error distinto falla normalmente; una decisión200 produce XPASSstrict y exige revisar el test. **Los XFAIL no cuentan como aceptaciones.**

Para poder verificar las otras propiedades del ciclo, los positivos declaran expresamente un actor independiente con revisión/aprobación **y documents.release** en la DB desechable. No se añadieron grants al entorno real ni se recomienda ampliar permisos a un cliente para sortear el defecto. La futura corrección debe resolver el protocolo de locks/concurrencia conservando mínimo privilegio, atomicidad y segregación, con regresión de revisiones activas/previas y carreras; no ampliar indiscriminadamente UPDATE RLS del padre.

## Qué prueban los tres nuevos casos HTTP

- **Ciclo documental con actor combinado declarado.** Conserva aprobación por persona distinta, rechazo/resubmisión, release,409 viejo, descarga hash/bytes y cabeceras privadas; confirma estado padre/revisión y eventos exactos en PostgreSQL. Upload/veredicto/objetos se simulan en memoria.
- **Fallo del ledger.** Inyecta RuntimeError en el hook real `audit_service.record_document`; el POSTsubmit propaga el fallo y SQL demuestra draft/versión original y ningún evento submitted. No intercepta ni falsifica el comando HTTP de negocio.
- **Cola real derivada de SQL sintético.** Crea control/actividad/requisito/implementación, evidencia under_review y CAPA con acción asignada/vencida, junto con workflow del fixture. Miembro ve workflow+CAPA+actividad, revisor ve evidencia; team administrativo ve las cuatro fuentes. Memberteam403; revocar evidence.review por API elimina esa revisión de su cola; seleccionar empresaBeta por API devuelve cola vacía sin mezclar registros.

Los tres usan la API vía TestClient con sesiones persistidas sintéticas, hashes/cookies/CSRF, actor/capabilities/RLS/triggers/ledger reales. Solo se sustituye `get_db` para apuntar al PostgreSQL desechable y las integraciones AV/S3 por memoria. No prueba IdP externo ni descargas contra S3 real.

## Reproducción y calidad

Desde la raíz, con toolchain/dependencias instalados y la imagen local aprobada ya disponible:

```sh
PMC_TEST_POSTGRES_PORT=55477 '/Users/Gerdel_Garcia/Documents/ChatGPT/SaaS QMS PerfectMatchSystems/scripts/with-local-tools.sh' bash docs/audits/2026-11-14/module-operability-evidence/run-module-http-integrity.sh
```

El harness reutiliza `pmcloud-postgres:local`, publica solo loopback, usa tmpfs512MiB, roles/secretos sintéticos efímeros y elimina únicamente su contenedor al salir. No construye imagen, limpia Docker ni accede a DB local. Migra la DB vacía a0049, verifica0049→0048→0049 y ejecuta exclusivamente estos cinco casos; resultado esperado actual3PASS+2XFAIL. Cada respuesta se registra como método/path/status/rol sin headers, cuerpos ni tokens.

Para regenerar el inventario a partir de todos los JUnit/trazas conservados en artifacts:

```sh
'/Users/Gerdel_Garcia/Documents/ChatGPT/SaaS QMS PerfectMatchSystems/scripts/with-local-tools.sh' uv run --project apps/api --no-sync python docs/audits/2026-11-14/module-operability-evidence/build_evidence.py
```

Los scripts originales de integridad en/scripts permiten repetir las suites de base; la instrumentación añade únicamente JUnit y el plugin de trazas de esta auditoría. Se necesitan los artifacts previos para reconstruir la asociación completa; sus hashes se incluyen y su archivo cifrado se restaura/verifica fuera de Git. Ningún script crea datos reales de cliente.

Los primeros tres fallos HTTP se conservan en [log inicial](module-operability-evidence/module-http-initial-failures.log): M01 real y target de monkeypatch `record_event` inexistente. Dos intentos posteriores descubrieron errores de fixture —query `control_instance_id` en vez de `instance_id`, y revocación SQL administrativa sin contexto de actor—; se corrigieron al contrato real y a revocación/cambio de empresa por HTTP, sin cambiar producto ni relajar las aserciones. Los logs versionados normalizan únicamente finales de línea/espacios finales; los logs/JUnit raw originales permanecen intactos en artifacts con sus hashes separados. La primera ejecución instrumentada de aislamiento sin evidencia se repitió sin cambios y dio27PASS.

[Log HTTP final](module-operability-evidence/module-http-integrity.log), [mypy final](module-operability-evidence/api-mypy-final.log), [Ruff final](module-operability-evidence/api-ruff-final.log) y [formato final](module-operability-evidence/api-format-final.log). La auditoría no añade dependencias ni afirma escaneo completo nuevo de vulnerabilidades, DAST o pentest.

La entrega incluye el ajuste transversal del scanner aprobado en las otras ramas: cuatro SHA256 verificados contra la base8133 se permiten únicamente en el path del inventario de arquitectura y únicamente para generic-api-key, con condición AND de path+valor. No se exceptúan credenciales. El bloque previo de agenda permanece al final para conservar sus controles. Nueve controles nuevos (cuatro valores permitidos, cuatro fuera de path detectados, un valor distinto detectado) y cuatro previos PASS; CI ejecuta ambos tests. Se verifica fuente propia y el historial de esta rama, sin atribuir un PASS de todos los refs a esta revisión. Los26 logs se inspeccionan aparte del ignore de Git: cinco URLs PostgreSQL ya enmascaradas, cero patrones de credencial sin máscara y cero coincidencias con secretos actuales de desarrollo; ningún valor secreto se imprime.

## Recuperación y criterios de cierre

Checkpoint fuente inicial `CP-MODULE-AUDIT-00-20261114T184106Z`; relevo `CP-MODULE-HANDOFF-00-20261114T204719Z` restaura509 entradas fuente/Git y bundlePASS antes de editar. Se preservan fuente final, pruebas, logs/JSON y raw artifacts cifrados/restaurados con hashes fuera de Git en `CP-MODULE-AUDIT-06B-20261114T210826Z`. No se afirma backup/restauración nueva de la DB real.

Prioridad siguiente: corregir M01 en una rama de producto con pruebas mínimas por actor/comando; cerrar brechas Workflow/lecturas/accesos que siguen abiertas; completar lifecycle/ejecución de auditorías y alta/licencia comercial. Después verificar servicios externos, flujos con actores reales de prueba y gates de operación/seguridad antes de producción. El CI del head de entrega sigue pendiente. Este orden es recomendación de ingeniería, no una decisión comercial ni autorización para desplegar.
