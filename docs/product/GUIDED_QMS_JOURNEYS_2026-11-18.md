# Guía operacional por recorrido

## Entrega implementada

Nueva entrada **Implementation guide** en coordinación de owner/admin. Seis casos: desde cero, mejora, transición de edición, migración de información, preparación de auditoría y ampliación de alcance/sedes. Son44pasos guiados con motivo, instrucciones, salida esperada, criterio de revisión y acción para abrir el módulo disponible en el ámbito seleccionado.

La guía lee registros persistidos de una unidad mediante las APIs existentes y permisos efectivos. No crea un proyecto global, una matriz ISO, tareas ficticias o casillas de cumplimiento. **Records found** significa registros observados, no fase implantada. Las condiciones destacadas identifican estados concretos: proceso activo, documento activo con revisión vigente registrada, implementación de control activa/implementada o riesgo/NCR/CAPA cerrados. Auditorías permanecen como planificación; ninguna cuenta como ejecutada.

Los coordinadores ven esta entrada sin recibir autoridad QMS implícita. Cada lectura requiere capacidades de la unidad; los colaboradores mantienen sus tareas asignadas. La futura autoridad de proyectos deberá ser explícita. El selector no elige automáticamente la primera sede; respeta únicamente una preferencia accesible previamente seleccionada.

## Mejoras respecto a la referencia Odoo

Referencia inspeccionada: perfect-match-qms@d89330cc, implementation_control.py, implementation_project.py, readiness_center.py y sus vistas. Se reutiliza la idea de bloqueo, siguiente acción y criterio de terminación. Odoo fue revisado como fuente, no ejecutado.

- Separación entre función pendiente del producto, falta de permiso, imposibilidad de verificar, ausencia observada de registros y registros disponibles.
- Revisión pendiente no se presenta como aceptación. Las instrucciones separan aportar evidencia de esperar al revisor.
- Sin100% con denominador cero ni porcentajes normativos derivados de contar archivos.
- Identificación de empresa/unidad/fecha de lectura; muestras limitadas rotuladas como parciales.
- Conservación de scope al abrir módulos, sin atribuir a un proyecto todos los registros encontrados en la sede.

La guía abre el módulo y conserva la unidad; no se afirma navegación al registro exacto en todos los módulos, pues sus contratos todavía no la ofrecen. El detalle muestra códigos para localizar los ejemplos existentes.

## Seguridad y verificación

- Identidad/empresa verificadas antes y después de la consulta. Validación de unidad, permisos efectivos, IDs, ámbitos, tipos, estados, duplicados y límites. Sin nuevos permisos, backend, DB, autenticación ni dependencias.
- Solicitudes same-origin, credenciales incluidas y no-store. Abort/token y remount por actor/empresa/rol impiden reusar snapshots previos.401/403 de cualquier lectura invalida la observación completa; error de otro módulo es «no verificado», no ausencia.
- Documento API usa51filas para un límite50. Revisor detectó ese P2: se validan las51antes de mostrar50, incluyendo el centinela; tests cubren tenant/unit ajenos, duplicados, fila inválida y exceso. Regresión RED→GREEN. Las demás listas conservan sus límites reales.
-208pruebas unitarias frontend PASS (65lector/6catálogo y navegación nueva incluidas); lint, typecheck, build y diffcheck PASS. Nueve pruebas Playwright nuevas enumeradas/typechecked; ejecución automatizada/axe en CI pendiente. No se afirma certificación WCAG.
- Revisión independiente de contratos/API, ámbito, UI/CSS/teclado y tests:208PASS, P2decentinela corregido y sin otros hallazgos materiales en el alcance revisado. CUA detectó que Home con modificador cambiaba de caso; se respeta ahora Ctrl/Alt/Meta y se añadió comprobación al test de teclado.
- Lecturas HTTPS autorizadas sobre demo sintética:10procesos/13documentos/5implementaciones/12riesgos/10NCR/7CAPA/7planes enDEMO-PRACTICA; ninguna escritura de negocio. Solo se abrió/seleccionó/cerró una sesión de lectura.
- CUA sobre build local con reproducción protegida de esas respuestas confirmó seis casos, pasos y criterios, registros reales de ejemplo,401/403 con limpieza y recuperación; inspección móvil375 y desktop1280. La autenticación de esa reproducción es un fixture, no un nuevo OIDC real. Capturas ignoradas `artifacts/previews/2026-11-18-guided-journeys`.

## Demo y recuperación

CP-GUIDED-QMS-00-20261118T141059Z conserva739fuentes/Git previos, restaurados por hashes/modos/bundle ydecrypt/tamper. La instalación web de la demo autorizada requiere un checkpoint separado de configuración, imagen anterior retenida y nueva imagen construida desde el commit publicado. **Instalación remota retenida por el hallazgo sin parche de picomatch.** No merge ni producción; persisten los6HIGH conocidos de Keycloak.

El override `infrastructure/demo/guided-web.override.yml` solo sustituye la imagenweb. Se aplica después de base, demo y account-switch, con `DEMO_GUIDED_WEB_IMAGE` fijado a la imagen exacta de la entrega. No usar `up` sobre todos los servicios ni reiniciar API/DB/IdP para este cambio. El informe de instalación posterior debe registrar SHA, imagen, verificación y rollback.

## Pendiente del producto completo

Proyecto maestro persistente, relaciones explícitas de registros al proyecto y su baseline, evaluaciones/snapshots por proyecto, perfil/mappings ISO aprobados, transición, importación comercial, módulos de formación/KPI/revisión por dirección y ejecución de auditorías. Esta entrega hace navegable la orientación y muestra esas brechas; no las presenta como terminadas.

## Publicación y estado final

PR66: https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/66 . Commit de código3aa7f95a45f07b08731b709875d09b950ed3b615, árbol idéntico al local50e3683, que se preservó. CP-GUIDED-QMS-06-20261118T144946Z restauró749archivos y Git con hashes/modos/bundle/tamper verificados antes de publicar.

CI de ese commit: Foundation quality44328844659 yCodeQL44328844679 success. Seguridad falla antes de runtime por un HIGH de picomatch sin parche publicado, adicional a los bloqueos de imágenes previos. Las9pruebas browser/axe **no llegaron a ejecutarse**. Ver docs/security/GUIDED_JOURNEYS_RELEASE_BLOCK_2026-11-18.md. No alterar gates para presentar verde.

La compilación Linux aislada de la imagen web terminó, pero no se instaló. CP-GUIDED-DEMO-CONFIG-00-20261118T145214Z verificó5archivos de configuración cifrados y la imagen anterior queda retenida. Los6contenedores existentes conservaron IDs e imágenes y siguen healthy. El público todavía ve la versión anterior; la captura de los6recorridos corresponde al build local con reproducción de respuestas sintéticas, no a una función ya disponible en la demo pública.

Un último control visual detectó el título del paso tapado por la barra fija al recibir foco. Se conserva foco accesible y desplazamiento inmediato con margen superior, sin animación forzada. La regresión responsive comprueba que el título quede debajo de la barra; su ejecución automática está sujeta al mismo bloqueo browser indicado arriba.

Verificación final del ajuste: CUA sobre el build recompilado confirmó foco y título completo bajo la barra en1280y375píxeles; capturas `guided-step-heading-desktop-verified.png` y `guided-step-heading-mobile-verified.png`. Inspección de6tarjetas en tema claro/oscuro, sin declaración de conformidadWCAG.208unit/lint/typecheck/build repetidos después del cambio:PASS. Revisión independiente estática del ajuste sin hallazgos materiales; no sustituye browser/axeCI.
