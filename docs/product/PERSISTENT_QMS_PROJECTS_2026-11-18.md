# Proyectos QMS persistentes ·18 noviembre2026

## Implementado

La guía de6recorridos dispone ahora de proyectos guardados por empresa/unidad. Permite crear, listar, reabrir, editar alcance/coordinador/fecha, archivar y restaurar. Cada proyecto genera atómicamente sus6–8pasos del catálogo `guided-qms-v1` (44entradas entre los6recorridos).

Cada paso guarda responsable, fecha y notas con estados **no iniciado / en curso / bloqueado / trabajo reportado**. Reportado significa trabajo declarado pendiente de verificación: no aprobación, evidencia aceptada ni faseISO completada. Bloqueado/reportado requieren notas. Los pasos de funciones ausentes mantienen `feature_pending`; pueden planificarse, pero no declararse implementados. No hay porcentajes normativos ni cierre formal del proyecto.

El catálogo congela identidades, orden y brechas del producto; no es una copia histórica completa del texto de las instrucciones ni una normaISO aprobada. Las observaciones operativas siguen siendo registros de la sede, sin vínculo de evidencia al proyecto en esta entrega.

## Autorización, integridad y recuperación de edición

- Capacidades nuevas `projects.read` y `projects.manage`, otorgadas explícitamente por unidad. Escrituras requieren ambas; owner/admin no tienen bypass. Asignar coordinador/responsable no concede acceso. Un lector con `projects.read` puede descubrir la guía, pero las APIs validan su unidad exacta. Auditor solo lectura.
- Proyecto y pasos con RLS forzada, FKs compuestas empresa/unidad, actor y unidad activos, identidades/catálogo inmutables. Catálogo global no sensible de solo lectura; proyección privada de dependencias sin privilegios runtime. No afirmar RLSforzada en estas dos tablas auxiliares.
- Locks de padre y ámbito; versiones esperadas de proyecto/paso; guardas SQL impiden crear pasos incompletos, alterar brechas o escribir un paso sin avanzar su padre en la misma transacción. Proyecto abierto impide archivar su unidad, incluso en interleavings probados.
- Archivar retiene el plan y bloquea su edición; restaurar exige autoridad actual y motivo. NoDELETE. Si luego se archiva la unidad, su historial requiere restaurarla conforme al modelo vigente de capacidades; no se abrió acceso histórico por bypass.
- MutacionesAPI y evento de auditoría confirman/retroceden juntos. Eventos conservan actor/estado/versiones y huellas de narrativas/motivos; **no son revisiones completas del texto histórico**. No se añadió un mecanismo de recibo de auditoría obligatorio para SQL arbitrario autorizado; se mantiene la convención transaccional de las APIs existentes.
- Cliente comprueba identidad antes/después, empresa/unidad, catálogo, campos, límites y recibo de versión/contenido. No-store, CSRF, abort y claves de contexto;401/403 retiran información. Catálogo incompatible se explica y bloquea edición sin atribuirlo a permisos.
-409rechazado conserva el borrador y permite reconciliar.500/502/504 o recibo ambiguo quedan sin confirmar, sin reintento automático. Recarga fallida de un paso conserva el borrador y el error. Navegación de módulo/unidad/empresa se bloquea durante edición; salida/recarga de página tiene aviso beforeunload. Logout sigue disponible.

## Evidencia ejecutada

|Comprobación|Resultado|
|---|---|
|Frontend unitario|268PASS,24archivos; baseline208|
|API unitario|102PASS,623DBskip; losskip no sonPASS|
|PostgreSQL HTTP/SQL directo|104PASS =50casos nuevos de proyectos +54existentes de acceso/suspensión|
|Historial de permisos en fixture propio|42PASS; no sumarlos como funcionalidad nueva|
|CI nueva|Job qms-project-integrity conecta el harness de104checks y restauración; ejecución del head publicado pendiente|
|Migración0050vacía|up/down/upPASS; downgrade no vacío bloqueado|
|Restauración antes/después|57/61tablas, hashes y rechazo de manipulaciónPASS en fixtures aislados|
|Ruff/formato/mypy|PASS;45fuentes API tipadas;135archivos formateados según evidencia del implementador|
|SAST estricto1.29|124archivos,6reglas,0hallazgos/0errores; no cubre todo riesgo ni certifica seguridad|
|Lint/typecheck/build web|PASS local después de correcciones|
|Nuevos Playwright|13casos enumerados/typechecked; ejecuciónCI pendiente al preparar el PR|

CUA sobre build local con backend de prueba/reproducción: creación y reapertura; trabajo reportado separado;409→500recarga con borrador conservado (RED observado antes del fix yGREEN después); bloqueo de salida por módulo; recarga/rebase explícitos y guardado; archivar/restaurar preservando notas; capturas claro/oscuro y375px sin desbordamiento horizontal. Es QA de interfaz con fixture, no prueba de OIDC ni persistencia PostgreSQL desde ese navegador. La persistencia real se verifica por los104tests HTTP/SQL independientes del fixture visual. Capturas ignoradas en `artifacts/previews/2026-11-18-qms-projects`.

Revisión frontend independiente encontró4P2 (borrador perdido tras recarga fallida,5xx ambiguo, salida por módulo, catálogo mal explicado): corregidos con regresiones unitarias y casosUI; seguimiento estático confirma correcciones. Un casoPlaywright que intentaba pulsar un enlace aria-disabled se cambió a activación forzada deliberada. Revisión backend independiente comprobó RLS/catálogo/lineaje/tests, sinP0/P1 confirmados en su avance; **se interrumpió por límite de uso antes del veredicto final**. Root completó lectura de API/migración y evidencia, pero esto no sustituye su veredicto independiente final.

Fallos intermedios corregidos: primerSQLcompuesto de trigger no compilaba;403delector daba404 por SELECTFORUPDATE+RLS; faltaba no-store; GETpodía mezclar versiones padre/pasos; organización no leía SQLSTATEpg8000 y devolvía500en vez de409; test de suspensión fijaba0049comohead; ejecución de historial enDBequivocada produjo42errores de fixture, luego su harness propio pasó. Se mantienen avisos preexistentes de deprecaciónhttpx/TestClient/anyio; sin añadir dependencias.

## Checkpoints y estado de entrega

CP-QMS-PROJECTS-00-20261118T195326Z:750fuentes/Git restaurados por hashes/modos/bundle/AESGCMtamper, previo a cambios. Backups fuera del árbol, claves separadas. DBdeshechable: CP-QMS-PROJECTS-DB-00-20261118T203826Z (57tablas) yCP-QMS-PROJECTS-DB-06-20261118T204209Z (61), dump cifrado/restaurado enPostgreSQLtmpfs sin red, sinowners/ACL. No prueba nueva deDBdemo,S3,IdP ni certificados. Checkpoint fuente final y referenciaPR se registran enCHECKPOINT/handoff.

No se cambió la demo ni producción, ni se concedieron las nuevas capacidades a cuentas existentes. Para instalar0050en una base real se requiere un checkpointDB independiente y procedimiento de restauración de esa base, además de revisión/CI de la entrega. No aplicar downgrade sobre datos para hacer rollback; retener esquema y volver a imagen compatible.

El avisoGHSA-fc5q-39xc-vjpf fue retirado por GitHub el18noviembre2026. La repetición de `pnpm audit --audit-level high` pasó con0HIGH/0CRITICAL/1moderate, sin cambio de paquetes/lockfile/umbral. Esto no prueba ausencia de riesgo de globs; la edición actual del aviso es [fuente primaria](https://github.com/advisories/GHSA-fc5q-39xc-vjpf). Persisten los6HIGH conocidos deKeycloak y el requisito de CI/revisión antes de merge/producción.

## Pendiente

Vincular evidencias concretas al proyecto/paso, revisiones independientes y snapshots formales, historial narrativo completo, perfiles/mappings y transiciónISO aprobados, importación comercial, ejecución de auditorías y módulos de formación/KPI/revisión por dirección. Esta entrega guarda el plan y trabajo reportado; no presenta esos motores como terminados.
