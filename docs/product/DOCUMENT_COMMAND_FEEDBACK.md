# Feedback y recuperación de acciones documentales

12 noviembre2026. Continuación del PR26, rama `codex/document-command-feedback`.
[PR borrador #27](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/27), entrega funcional `683c68e788623cd122645d1adedadb511b6a0114`, árbol `537ee01878abb20834490b1968c484e75328fb29` verificado idéntico local/remoto. El seguimiento posterior solo documenta el handoff.
Se conserva el módulo existente; no cambia ningún contrato API, permiso, modelo,
esquema, dependencia o servicio productivo.

## Cambios implementados

- Las respuestas401/403 de uploads, comandos y lectura de revisiones invalidan
  contexto, capacidades visibles, registro, archivos/revisiones y referencias.
  Se cancelan lecturas y se invalidan operaciones pendientes antes de notificar
  al shell.403 se presenta como acción no permitida, sin inventar su causa.
- `jsonMutation` devuelve resultado explícito. Si crear documento/revisión falla,
  el formulario y sus valores siguen disponibles. Se cierra tras éxito confirmado
  o invalidación de acceso, sin afirmar guardado cuando la respuesta falla.
- Upload409 y comandos con versión optimista409 vuelven a leer el estado;
  no repiten la escritura automáticamente. Se conserva el documento/revisión
  objetivo si todavía pertenece a la página autorizada actual.
- Releer no selecciona arbitrariamente el primer documento después de subir PDF.
  Un clic en el documento ya seleccionado conserva las revisiones cargadas.
- Upload503 indica indisponibilidad temporal sin atribuirla necesariamente al
  antivirus. Un202 con `file_state=rejected` sigue sin permitir usar ese archivo.
  Los estados desconocidos tienen un mensaje neutro.
- El callback de acceso denegado usa un ref actualizado y una invalidación estable;
  un rerender del shell no reinicia por sí solo la selección de revisiones.

## Contratos conservados

| Acción | Autoridad y restricciones del backend existente |
| --- | --- |
| Submit / Reject | `documents.review`; estados admitidos por cada transición. |
| Approve | `documents.approve`, under_review, archivo limpio, actor distinto del preparador. |
| Release | `documents.release`, approved y archivo limpio. |
| Upload | `documents.author`, draft/missing; PDF y20MiB/AV validados en servidor. No se inventa `expected_version` para PUT. |
| Download | `documents.read` y archivo limpio; integridad controlada en servidor. |

La UI complementa estas restricciones, nunca las sustituye. No se habilita el
reemplazo de archivos rechazados ni se convierte un202 en aprobación del documento.

## Pruebas y límites

El hito añade fixtures de feedback con login sintético. Todo PUT/POST documental
se intercepta mediante whitelist, se responde en el navegador y nunca se remite
al backend. Una petición documental inesperada se bloquea y falla el test.
Los PDF usados aquí son buffers para probar feedback del cliente; no acreditan
validación real de PDF, antivirus, almacenamiento o transacciones del servidor.

Casos: reclic del documento actual; upload401/403; revisionesGET403; formularios de
documento y revisión preservados ante503; upload503 con retry manual; upload409
con nueva lectura y una sola escritura; archivo202 rechazado y contexto conservado;
conflicto del comando versionado sin reenvío automático.

Las primeras pruebas contra el preview anterior fallaron en el feedback de403 y
POST503. Resultados finales: **59/59 unitarias**, ESLint/TypeScript/build PASS;
**36/36 Playwright en Darwin y36/36 Linux**, sin updates de snapshots ni retries.
Incluye17 casos documentales y19 existentes. Linux usa Playwright1.64.1 por digest
`sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f`.
Gitleaks árbol/historial y licencias PASS; audit0High/Critical y1Moderate preexistente.
No hay nuevas dependencias. CI del nuevo head sigue requerido. Se conservan los snapshots de productos/workspace/galería existentes;
no se regeneran para aceptar diferencias. La revisión de fuente independiente
no identificó bloqueadores P1/P2; no equivale a integración backend o aprobación
de producción.

## Corrección de fixture de CI

PR26 en23b9abf pasó calidad/CodeQL pero Playwright reportó25PASS/1FAIL. La prueba
live usaba el nombre local “Development access review”; el seed limpio crea
“Perfect Match Demonstration Site”, con el mismo código `DEV-ACCESS-UI`.
Se corrigió únicamente la selección del test por código/valor en
`a0d7675ff1987feec6e887adb6325058e6ce1027`, sin cambiar seed, empresas o producción.
La correccióna0d7675 pasó calidad/CodeQL/runtime y26/26Playwright/axe. Security43242951782 fallósolo por Keycloak7High/SeaweedFS2High; API/web/PostgreSQL/ClamAV0High/Critical,5SBOMválidos,ZAP0High/Medium/Lowy13informativos. Artifact13955698379 SHA256 `48e704faa036caaeed03ca2ab7222d45006390b6c0350162245780dcfda86026`. Esta evidencia no acredita el head nuevo de PR27 ni convierte25/1 en un PASS histórico.
Artifact13955166926, SHA256 `b9fb8968dca07344411a3034fca2f86d374f81313a60688b857d22b239f313e7`.

## Recuperación y pendientes

CP-DOC-FEEDBACK-00-20261112T144935Z conserva la base:406 archivos y Git cifrados
fuera del repositorio, restauración aislada por cada hash y bundle verify PASS.
Clave0600 separada; sin DB ni datos de clientes. El checkpoint final **CP-DOC-FEEDBACK-06-20261112T150700Z** preserva
la implementación verificada antes de GitHub, con restore aislado y bundle verify.

Quedan fuera de este hito la selección automática de documentos recién creados,
formularios persistidos, más casos de múltiples revisiones, pruebas E2E de escritura
real adicionales y la paridad completa con Odoo. Se mantienen bloqueos de release
de imágenes proveedoras y requisitos productivos; no se fusiona ni despliega.
