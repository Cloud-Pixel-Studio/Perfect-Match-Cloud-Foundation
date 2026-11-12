# Control documental — diseño cotejado con Odoo

Fecha de revisión de las fuentes: 2026-10-28. Este documento registra hallazgos y diseño; no presenta el módulo SaaS como implementado.

## Evidencia original

Se leyeron en el repositorio privado `Perfect-Match-Systems/Perfect-Match-QMS2026`, rama `main`:

- `addons/pm_qms_documents/models/document.py` (blob `ca3adaeefacdc7cb251803ca2f0e76405287c1ab`)
- `addons/pm_qms_documents/models/document_revision.py` (blob `9f130199f7a589ba052a95c2724340394a12a78e`)
- `addons/pm_qms_documents/security/ir.model.access.csv` (blob `69e026e7b59b18e5cfe5bfeb80d781f02241ee4f`)
- `addons/pm_qms_documents/__manifest__.py` (blob `9dac6dc103f18ea61f1841455ee30f5b8e84abf6`)

El documento Odoo tiene organización y proceso obligatorios, propietario opcional, código único por compañía, tipo, estado, revisiones, fecha efectiva y de revisión, controles de marco y controles implantados. Comprueba que proceso, organización y controles relacionados pertenezcan a la misma compañía/organización. La versión consultada permite al administrador eliminar el documento, pero las revisiones no borrador rechazan unlink.

Cada revisión guarda etiqueta, fecha, actores preparador/revisor/aprobador, aprobación, resumen, archivo enlazado y estado draft/under_review/approved/active/superseded/rejected. El ORM exige una revisión activa como máximo, pero esa comprobación no sustituye una exclusión transaccional concurrente en la arquitectura nueva.

Los ACL CSV dan lectura al usuario QMS; manager y controller pueden crear/escribir (no borrar); administrador también tiene unlink. Las acciones de flujo se limitan a manager, aunque el mismo actor que revisa puede aprobar en el código leído. La próxima implementación conserva los estados y actores, endurece la separación autor/aprobador y conserva registros de auditoría; esas son medidas de seguridad SaaS, no equivalencia literal de las ACL de Odoo.

El addon depende de `pm_qms_core`; su manifiesto no incluye pruebas en el paquete de documentos. El 404 de `addons/pm_qms_documents/tests/test_document.py` confirma que esa ruta no existe en `main`, no que el repositorio carezca de pruebas en otra ruta.

## Diseño SaaS

1. Documentos y revisiones son entidades tenant-scoped y usan RLS forzado. Documento requiere organización/unidad y proceso en esa misma unidad. Controles quedan fuera de claves foráneas hasta que el dominio de controles exista; no aceptar identificadores de texto sin validación.
2. Capacidades existentes `documents.read`, `.author`, `.review`, `.approve`, `.release` se conceden por unidad. `documents.approve` deniega al preparador de la revisión. Los roles de plataforma, el propietario documental y seats no dan permiso de negocio automáticamente.
3. Sólo comandos tipados cambian estado. PATCH de contenido no acepta estado, actores, revisión vigente ni referencias de almacenamiento. Aprobación registra revisor/aprobador; liberación bloquea el documento, activa la revisión aprobada y supersede la vigente en una sola transacción auditada.
4. Revisión liberada y auditoría histórica no se borran ni alteran. Cualquier cambio requiere nueva revisión. Obsolescencia conserva las revisiones y referencias de archivo.
5. Las cargas entran a cuarentena en almacenamiento privado; se validan tamaño, tipo declarado y firma, se calcula hash y quedan no descargables hasta que un proceso de análisis las marque limpias. La API nunca toma bucket/key/signed URL del cliente como autoridad. Descarga vuelve a validar actor, tenant, unidad, documento/revisión y estado; no crear URLs públicas.
6. El servicio de storage actual ofrece put/get/delete/head pero no implementa análisis antivirus ni estado de cuarentena. No conectar liberación documental a carga directa hasta añadir dicha frontera de confianza.

## Orden de implementación

### Estado de implementación — 2026-10-28

Implementado parcialmente: migraciones `0010`–`0012`, tablas y restricciones, RLS forzado, capacidades por unidad, historial de revisiones, comandos de flujo y auditoría. El upload sostiene el PDF temporalmente en RAM, con máximo 20 MiB por archivo y cuatro cargas simultáneas por proceso; valida firma y lo envía por ClamD `INSTREAM`. Solo después de un veredicto limpio o infectado lo persiste en storage privado como `clean` o `rejected`. Si ClamD falla o sus firmas superan 48 horas, se aborta sin persistir ni marcar el archivo. El contenedor oficial ClamAV 1.5.4 está fijado por digest, solo en red privada de app más una red de salida dedicada para FreshClam, sin puertos publicados. La imagen Alpine inspeccionada solo ofrece `amd64`; local corre por emulación en Apple Silicon y producción necesita arquitectura compatible. La descarga comprueba tamaño y SHA-256 y aplica `attachment`, `no-store`, `nosniff` y CSP sandbox. La aplicación no ofrece ningún comando para marcar un archivo limpio.

Validado: migraciones desde cero, reversión hasta `0008` y nueva migración a head; la suite PostgreSQL de procesos/documentos pasó 27 pruebas con `0013` y `0014` (upgrade/downgrade/upgrade, permiso dedicado, auditoría de obsolescencia, propietario tenant-activo, proceso archivado rechazado y registro documental denegado sin responsabilidad). El paso final de downgrade tras crear datos auditados fue rechazado por la restricción histórica, como protección de auditoría. Suite unitaria API41 pasó/122 omitidas por requerir DB; web8 pasó. El smoke OIDC negativo confirmó denegación API/proxy para miembro sin responsabilidad. El E2E positivo local real verificó tenant/grants, alta de documento/revisión, ClamAV limpio, SeaweedFS privado, envío, revisor distinto del preparador, aprobación, liberación, listado por proxy web, exclusión de `file_object_key`, descarga por proxy con hash/cabeceras y obsolescencia auditada. También comprobó que el detalle de revisión expone nombres de actores activos y fechas de revisión/vigencia. Los grants temporales se revocaron; el documento DEV-E2E quedó obsoleto. El registro de auditoría contiene `revision.submitted`, `.approved` y `.released`; esa prueba descubrió y permitió corregir el constructor duplicado de `revision_date` y los contratos faltantes del validador de auditoría. El contenedor real ClamAV ya había aceptado un PDF benigno y detectado EICAR; Trivy del digest fijado reportó cero vulnerabilidades el 2026-10-28. Esta etapa añadió contrato de respuestas que excluye `file_object_key`, lectura de capacidades efectivas, listado reducido de procesos (requiere `documents.author` y `processes.read`), búsqueda/paginación documental, selección de propietario, permiso/acción de obsolescencia (`0013`), validación DB del propietario/proceso (`0014`), UI y raíz proxy permitida. Además, lista y revisiones de documentos exigen capacidad documental en API alineada con RLS. `make health`, Ruff, mypy y `git diff --check` pasaron. Falta recorrido visual/autenticado desde el navegador y aceptación funcional UX completa.

Pendiente antes del uso operativo: integrar la UI con API/PostgreSQL/storage en la app local; validar tenant cruzado, permisos revocados, transiciones, resultado infectado, descarga real y escaneo autenticado; completar detalles de aceptación UX. `0013` y `0014` pasaron en DB desechable y se aplicaron a la base de desarrollo persistente mediante `make up`. El socket ClamD TCP no autentica ni cifra; su aislamiento depende de las redes de contenedores y no debe publicarse.

El orden restante es: pruebas de integración API+storage completas; validación visual del registro/editor con acciones según capacidad; resolver elementos funcionales pendientes y revisar equivalencia Odoo. No se afirma paridad total.

Aceptación completa continúa en `docs/product/DOCUMENT_CONTROL_ACCEPTANCE.md`. Límites actuales: el modelo de procesos no tiene asociación multisedes, y SaaS aún no tiene dominio de controles, análisis de archivos ni control documental.
