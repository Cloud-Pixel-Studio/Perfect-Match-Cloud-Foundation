# Revisión de proyectos persistentes ·19 noviembre2026

## Hallazgo SQL de la migración0050

La revisión independiente identificó referencias a relaciones sin esquema en las funciones nuevas que validan catálogo y completitud de pasos. El rol runtime puede crear tablas temporales; PostgreSQL busca implícitamente `pg_temp` antes de otros esquemas para relaciones cuando no aparece explícitamente en `search_path`. Esto permite ocultar el catálogo público y falsear sus validaciones desde una sesión SQL con privilegios runtime. No se ha demostrado una ruta HTTP para ejecutar ese SQL.

Clasificación: **P1 / integridad**, impacto en identidad de recorrido/paso y brechas del producto; exige acceso SQL runtime o un compromiso que lo permita. Corregido: relaciones y ayudas explícitas en `public`, `pg_temp` al final del `search_path` de las cinco funciones nuevas. Seis regresiones fallaron antes con `DID NOT RAISE DBAPIError` y pasan después verificando SQLSTATE23514 y rollback. Suite completa del módulo:56PASS. Revisión independiente acotada del fix y logs sin nuevosP0/P1/P2; revisión ampliada del backend y CI del nuevo head todavía pendientes al preparar esta corrección.

La migración no está aplicada en demo ni en una base de cliente. No se revocan permisos globales de TEMP como sustituto de corregir las funciones; no se relaja RLS.

## Contrato de texto entre API, SQL y navegador

La revisión ampliada detectó tres problemasP2 del módulo: notas obligatorias compuestas por espacios Unicode/control que el CHECK inicial no rechazaba; identidades SQL de código/nombre vacías o sin normalización, capaces de invalidar una lista del cliente; y límites de texto contados como unidadesUTF-16 en el navegador, aunque API/PostgreSQL cuentan puntos de código. Al recorrer esas rutas también se confirmó una diferencia con U+FEFF y con el trim de NEL, que podía producir un recibo inesperado después de guardar.

Decisión técnica acotada al proyecto: normalizar solo los extremos de código/nombre/motivo con los29caracteres whitespace de Python3.12 más U+FEFF, antes de validar longitud. SQL y cliente usan exactamente el mismo conjunto de30. Las notas conservan todos sus caracteres; el conjunto solo determina si un estado bloqueado/reportado tiene texto. Los límites numéricos y campos existentes se mantienen. El navegador cuenta puntos de código, admite su representaciónUTF-16 en los controles y verifica longitud antes de enviar, preservando el borrador si se excede.

El contrato se precisa en docs/product/QMS_PROJECT_API_CONTRACT.json. Comparación estática de fuentes: conjuntoAPI=cliente=cinco literalesSQL,30caracteresPASS. Suite final PostgreSQL:93PASS; API109PASS/666DBskip, web282PASS, Ruff/formato135/mypy85 ySAST124/0hallazgos/0erroresPASS.0050up/down/up, guard de downgrade y restauración61tablas/hash/tamperPASS en CP-QMS-PROJECTS-DB-06-20261119T123805Z.

Revisor independiente completó lectura del backend sobre043afbd y seguimiento de API/SQL/lector/formularios/testsposteriores: sinP0/P1/P2 restantes en ese alcance, ligado a SHA256 de diez archivos. Inspeccionó logs de ejecución; no repitió pruebas/payloads. No cubre toda la UI de nuevo, OIDC real, migración demo/cliente, carga, pentest autenticado ni restauraciónowners/ACL/S3/IdP. Preparado para actualizar PRborrador, no para merge/release.14casos Playwright del módulo incluyenUnicode375px/lectura/edición/límites; ejecución del nuevo head pendiente.

Fallos intermedios conservados: notasSQL12FAIL/8PASS antes del fix, luego20PASS; identidad/BOM15FAIL/1PASS más1HTTPFAIL antes del fix, luego17PASS; APIunit7FAIL antes, luego9PASS en ese archivo; lectorUnicode2fallos de comportamiento yblank4fallos más2helper ausente, luego71clientPASS. Ruff detectó una constante demasiado larga; se dividió sin excepciones de estilo. No sumar estas reejecuciones a las93pruebas distintas del módulo.

Logs locales protegidos: `/private/tmp/qms-project-temp-red-six.log`, `qms-project-temp-green.log` y `qms-project-temp-full-green.log`. El último registra0050up/down/up,56PASS, rechazo del downgrade con historial y CP-QMS-PROJECTS-DB-06-20261119T064946Z:restauración cifrada de61tablas con hashes y rechazo de manipulación. Nueva comprobación root de Ruff/formato/mypy85 y SAST124archivos/6reglas/0hallazgos/0erroresPASS. No equivale a una certificación de seguridad.

## Escaneo de imágenes: nuevo bloqueo crítico

Evidencia de PR67/head06275d2: [Foundation security44449858112](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/44449858112), artefacto14495218547. ZIP descargado y SHA256 contrastado con el log del upload:

`eb05242af29d183f06994ad390dacf4fc28e4d76eb912204a9299ba44e8626fc`

Los seis reportes `trivy-*-image.json` existen y fueron leídos. API, web, PostgreSQL, SeaweedFS y ClamAV:0HIGH/CRITICAL. Keycloak: **1CRITICAL +6HIGH**, siete entradas paquete/CVE. Imagen exacta:

`quay.io/keycloak/keycloak:26.8.2@sha256:c68e286cacd87b942ac1939a0a1481461109d6acd3a57dc496969a319a76bbf0`

|CVE|Paquete|Severidad del reporte|Versión corregida indicada|
|---|---|---|---|
|CVE-2026-114938|java-21-openjdk-headless|CRITICAL|No indicada|
|CVE-2026-91403|java-21-openjdk-headless|HIGH|No indicada; will_not_fix|
|CVE-2026-119373|sqlite-libs|HIGH|No indicada|
|CVE-2026-119374|sqlite-libs|HIGH|No indicada|
|CVE-2026-119379|sqlite-libs|HIGH|No indicada|
|CVE-2026-119586|sqlite-libs|HIGH|No indicada|
|CVE-2026-102554|com.google.guava:guava|HIGH|33.7.2|

El nuevo crítico se describe en el reporte como corrupción de memoria de OpenJDK en x86-64 con AVX-512VBMI. No se ejecutó explotación ni se verificó su alcanzabilidad desde el SaaS. El escaneo prueba presencia del componente señalado; no prueba explotación del servicio ni autoriza descartar el riesgo por arquitectura/CPU.

La [última release oficial de Keycloak](https://github.com/keycloak/keycloak/releases/tag/26.8.2) sigue26.8.2 en la consulta del19noviembre. La página pública de NVD para el nuevo CVE no devolvió contenido legible en esta consulta; no atribuirle una confirmación independiente de detalles que se obtuvieron del artefacto. No se sustituyeron JAR/JDK, no se añadieron excepciones y no se desplegó una imagen candidata. Producción sigue **NO GO**. El conteo histórico de seis altos queda preservado como evidencia anterior, no como conteo actual.

## CI y pruebas de esta revisión

CodeQL44449858248:success. Calidad44449858162 detectó ocho retornosAny en helpers de tests y uso accidental de `rg` en el harness de PostgreSQL. Tipado explícito y comprobación portable con `grep` corregidos localmente; mypy sobre85archivos y harness50tests con restauración61tablas pasaron después. Falta CI del nuevo head.

Navegador:190casos ejecutados en security44449858112,189PASS y un fallo nuevo por selector ambiguo mientras el formulario terminaba de guardar. El test ahora espera que el formulario cierre antes de buscar el badge. No cambia la lógica del producto y aún requiere la repetición exacta enCI. Los resultados de esa repetición deben quedar en CHECKPOINT y el informe de producto antes de cerrar la entrega.

Repetición de código ba61137: [calidad44479633563](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/44479633563) aprobó12jobs yCodeQL44479633561aprobó. [Security44479633585](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/44479633585) ejecutó190browserPASS yZAP66PASS/2WARN/0FAIL; falló solo el control final de imágenes. ZIP14508592667 SHA256 `b4d18eb19b0d028941aaefa34ea3fc3bb645d27a62f9f780c563e88ba95f4e6b` verificado: Keycloak1CRITICAL+6HIGH, otras cinco imágenes0HIGH/CRITICAL. Esta CI precede al contrato de texto final: su propia ejecución se registra en el cuerpo dePR67 y checkpoint externo, sin extrapolar los resultados anteriores.


## Cierre verificado del código506da8f

[Calidad44535548505](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/44535548505) aprobó sus12jobs;CodeQL44535548447aprobó. [Security44535548502](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/actions/runs/44535548502) ejecutó191browserPASS, incluidos14casos del módulo y el flujoUnicode375px de lectura/edición/límites. ZAP66PASS/2WARN/0FAIL. Falló solo el control final de imágenes; no afirmar que toda la suite de seguridad aprobó. El job PostgreSQL repitió93PASS, guard de downgrade y restauración61tablas/hash/tamperPASS.

Artefacto14536002806 descargado (enlace temporal renovado tras403 de caducidad), ZIP SHA256verificado:

`610f75b6ad4594c79a9df3ae79a6264985de7e43b33940c7a22272b2cc1eafee`

API/web/PostgreSQL/SeaweedFS/ClamAV:0HIGH/CRITICAL. Misma imagenKeycloak26.8.2/digestc68e286: **1CRITICAL +10HIGH**, once entradaspaquete/CVE. Frente al artefacto anterior aparecen además cuatroHIGH dejava-21-openjdk-headless: CVE-2026-114939, CVE-2026-114940, CVE-2026-114941 yCVE-2026-114942. El conteo cambia con la información del escáner; no hubo sustitución de imagen ni excepciones. No se comprobó alcanzabilidad/explotación. La consulta oficiallatest repetida el19nov sigue26.8.2. Merge/producción permanecen bloqueados.

Este cierre es documentación posterior a la CI de506da8f. Los archivos de aplicación permanecen idénticos; el cuerpo dePR67 y el checkpoint externo recogen cualquier CI posterior, sin atribuir aprobaciones antes de ejecutarla.
