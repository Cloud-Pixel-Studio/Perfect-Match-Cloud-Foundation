# Revisión de proyectos persistentes ·19 noviembre2026

## Hallazgo SQL de la migración0050

La revisión independiente identificó referencias a relaciones sin esquema en las funciones nuevas que validan catálogo y completitud de pasos. El rol runtime puede crear tablas temporales; PostgreSQL busca implícitamente `pg_temp` antes de otros esquemas para relaciones cuando no aparece explícitamente en `search_path`. Esto permite ocultar el catálogo público y falsear sus validaciones desde una sesión SQL con privilegios runtime. No se ha demostrado una ruta HTTP para ejecutar ese SQL.

Clasificación: **P1 / integridad**, impacto en identidad de recorrido/paso y brechas del producto; exige acceso SQL runtime o un compromiso que lo permita. Corregido: relaciones y ayudas explícitas en `public`, `pg_temp` al final del `search_path` de las cinco funciones nuevas. Seis regresiones fallaron antes con `DID NOT RAISE DBAPIError` y pasan después verificando SQLSTATE23514 y rollback. Suite completa del módulo:56PASS. Revisión independiente acotada del fix y logs sin nuevosP0/P1/P2; revisión ampliada del backend y CI del nuevo head todavía pendientes al preparar esta corrección.

La migración no está aplicada en demo ni en una base de cliente. No se revocan permisos globales de TEMP como sustituto de corregir las funciones; no se relaja RLS.

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
