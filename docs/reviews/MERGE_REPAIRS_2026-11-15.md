# Reparación y limpieza de ramas

El usuario autorizó decidir y limpiar lo que no sirve. Se retiraron **6 PR** sin fusionar ni borrar sus ramas; quedan **31 PR abiertos** al corte. No hubo reset, force-push, limpieza de archivos de usuario, aplicación de migraciones ni despliegue. El informe MERGE_READINESS_2026-11-15 conserva el corte histórico anterior; este documento registra lo que cambió después.

## Decisiones ejecutadas

|PR|Acción|Evidencia / límites|
|---|---|---|
|21|Cerrado por sustitución|Guard HTTPS ampliado y43 pruebas de configuración/key en50; nota histórica conservada en su rama, no todo Markdown copiado|
|23|Cerrado por contenido incorporado|22 recibió las2correcciones de formato; árbol completo idéntico a23, AST idéntico,6 pruebas PASS|
|24|Cerrado; alternativa retirada|Inventario reutilizado en50. Workflow alternativo de candidatos y su test NO se copiaron a50: se decide usar el CI vinculado de53. El código alternativo sigue en ramas históricas, no se desactivaron scanners globalmente|
|28/29|Cerrados por sustitución|Salida atómica y Results/Target estrictos incorporados y ampliados en50; ramas preservadas|
|48|Archivado como exploración|3SVG y namingdoc exactos preservados en49, guía íntegra con nota histórica. Variante mínima sobre main viejo no se importa sobre metadata moderna. Favicon/PWA/OG/legibilidad y revisión legal siguen pendientes|
|22|Formato corregido|da41f6d: calidad y CodeQL PASS; no lógica de negocio cambiada|
|51|Sintaxis de aserción corregida|65 unitarias y lint/tipos PASS; calidad/CodeQL de reparación PASS. No se inventan KPI reales|
|52|Meses exactos y missing≠zero|94 unitarias PASS,17 casos añadidos, lint/tipos/build Next default PASS. Se conserva el avance externo9365bea y se anexan cambios con lease, sin sobrescribirlo|
|49/51/52|Controles de checksums actualizados|Misma configuración de5valores ya verificados, restringida a path/valor/regla.13 controles positivos/negativos y su paso CI; fixtures Git públicos inmutables, no logs privados|
|50|Logs de scanner protegidos|Mensajes constantes;39 standalone PASS. Conteos HIGH/secret siguen en JSON, Match no se copia; timestamps inválidos/rutas no se imprimen. CodeQL y calidad PASS; alerta original resuelta|
|43|Harness de auditoría protegido|Sin body de health; estado finito; temporal exclusivo0600+sync/rename.28browser PASS en runtime existente y503 sintético:5PASS/1BLOCK. Reemplazo0644→0600 y limpieza temporal PASS;0escrituras QMS. CodeQL/calidad PASS; cuatro hilos históricos resueltos/outdated|
|53|Conserva fix de privacidad50|Pins y gates iguales; nuevo head9b398e4 debe completar CI, sin heredar el verde del099d011|

La prueba de build temporal inicial de52 falló por resolver Next fuera de la raíz mediante symlinks. Se creó una vista de dependencias con hardlinks dentro del directorio de pruebas, sin instalar/cambiar paquetes ni debilitar las reglas de pnpm; build Next default de49 y52 PASS. Los CLI se ejecutan directamente para evitar modificar el estado de tareas de una dependencia enlazada. La evidencia de fallo se conserva, no se atribuye al código.

La revisión independiente detectó que mode0600 solo protegía archivos nuevos; se corrigió con publicación atómica y se probó sobre archivo0644 existente. También evitó afirmar que el workflow alternativo de24 estaba copiado íntegro. No hay P1/P2 nuevos pendientes en el diff de limpieza inspeccionado; no es una aprobación global de todos los PR.

## Secretos y supply chain

Con la configuración antigua, el espejo de293 commits publicados produjo exactamente5 hallazgos: checksum de agenda y4 hashes de archivos de auditoría. Con la configuración revisada existente, el mismo espejo produjo0. No se añaden nuevos valores ni se ignoran carpetas de código/secretos. Los13 controles comprueban que el mismo valor fuera de su path y un valor distinto en el path se detecten. Gitleaks conserva redacción. Las dos falsas detecciones de commits locales intermedios no publicados siguen preservadas; este PASS del espejo no se extiende a todos los refs locales.

## Producción y pendientes reales

Artefacto14162129065 de099d011/run43715161783: ZIP SHA256440671006ea19de6d6f42e672da17f67a0d4d136badb2cdd20457811ccd8933d verificado antes de leerlo. Evidencia vincula SHA/run/6imágenes: **7HIGH** (Keycloak6, SeaweedFS1),0secret; API/web/PostgreSQL/ClamAV0HIGH/CRITICAL en esa corrida. Bajó del corte previo9 a7, no a0. Bootstrap, browser, scanner, SBOM y ZAP aprobaron; gate final falló correctamente. No se intercambian JAR/JDK/SQLite ni se exceptúan CVE para fabricar un PASS.

**PM NO GO** sigue vigente. Faltan remediación vendor verificable, integración y revisión humana, staging de comandos reales, operación/recuperación, onboarding/entitlements/billing y alcance QMS. PR13 conserva4hilos: el P1 documental tiene fix47 aún no integrado en13; el Centro de Acciones todavía omite CAPA in_progress, incluye acciones de padres terminales y limita250antes de elegibilidad personal. Esas3correcciones de negocio requieren pruebas HTTP/PostgreSQL y concurrencia/autorización pertinentes; no se resuelven con una limpieza de Git ni ampliando grants.

Los cambios externos9365bea de52 se detectaron tras rechazo de lease y se conservaron. Los workspaces original/Studio no se tocaron ni se activó0041/lifecycle WIP. El runtime real sigue PR39/DB0048; las pruebas de navegador de este turno validan el harness contra ese runtime, no un despliegue de la última fuente.

SHA, árboles, resultados, CI observado y hashes de logs están en el JSON adjunto. Logs completos, ZIP, screenshots y respaldos quedan fuera de Git. No se publica información de sesiones/credenciales ni se atribuye un CI anterior a un head nuevo.

Una detección nueva del informe correspondía al tag público de imagen API con SHA del commit; se omitió esa representación redundante del resumen y se conserva en el ZIP verificado. No se añadió excepción ni se cambió el scanner. El JSON mantiene source_sha y conteos; el artefacto íntegro conserva la identidad exacta.

## Seguimiento tras desbloquear los escaneos

Al ejecutarse el runtime aparecieron3fallos visuales antes ocultos por Gitleaks. En49 se preserva el nombre compatible del TXT descargable;3casos browser locales del recorrido/tour/mailto/descarga/FAQ PASS. Las capturas Linux375/768 del ZIP3bf2fcdedb75612e4ea460b4c7b631e33520423e14f2d6508d3fa40b9321888e se inspeccionaron visualmente y solo se aceptó la diferencia de marca/reflow; escritorio/dark ya comparaban correctamente. Se conservan hashes antes/después y el umbral2% sin cambios. No se refrescaron referencias Darwin de branding ni se declara aprobación visual universal.

En51/52 se retiran del runtime los paneles de KPI sin datos reales; se conservan propuesta, catálogo puro y contratos matemáticos probados. El overview operativo se restaura exactamente a la base25, con sus módulos y acceso existentes. No se añaden métricas falsas ni se modifican API/permisos. La prueba browser local del overview omitió4casos por ausencia de credencial: no es PASS ni se eludió autenticación; CI aislado debe confirmar el recorrido.

También falló audit-integrity51 antes de iniciar pytest, sin diagnóstico suficiente, incluso tras repetir el job. No se atribuye una causa exacta al log antiguo. Se reutilizó el harness ya revisado de22: puerto aislado asignado por Docker, espera SELECT1 por TCP final y diagnóstico de errores propagado. ShellCheck y27casos tenant-isolation PASS en fixture nueva;575no seleccionados, no contarlos como aprobados. Esto elimina una carrera conocida del servidor temporal de initdb y conserva evidencia si reaparece otro fallo. Los heads posteriores requieren su CI exacto.

Los cambios se anexan con lease a49/51/52 y se conservan en la continuación54. No se borra trabajo anterior para obtener un verde.

Checkpoint final previo a entrega: CP-MERGE-REPAIR-06C-20261115T134806Z;541 fuentes cifradas/restauradas por SHA256 y Git bundle verify PASS. Copia exacta entregada y todos los heads/evidencias se sellan separadamente al publicar. Gitleaks fuente y ShellCheck PASS; no se declara CI nuevo antes de consultarlo.
