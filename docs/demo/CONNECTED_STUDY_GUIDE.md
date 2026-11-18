# Recorrido de estudio del QMS

Datos ficticios preparados para la demo aislada el 17 de noviembre de 2026. Los registros `EST-*` amplían los ejemplos anteriores `LAB-*`, que se conservan. No representan clientes, certificados, auditorías realizadas ni evaluaciones reales.

## Entrar y encontrar los ejemplos

1. Visitar [Productos](https://demo.3-238-70-198.sslip.io/products), página pública, y entrar al panel de empresa.
2. Usar `pmc-demo-full`; la contraseña está únicamente en el archivo privado `Perfect-Match-QMS-Demo-Accesos.md` de Descargas.
3. Seleccionar **Perfect Match Industries · DEMO** y la sede **DEMO · 01 · Laboratorio de práctica**, código `DEMO-PRACTICA`. Las unidades hijas no heredan automáticamente todas las capacidades de esta sede.
4. Abrir **Module** para cambiar de área. Buscar `EST-` por código o título. Usar **Refresh** si se mantenía una sesión abierta antes de la carga.

Una empresa corresponde a su espacio independiente. Las sedes y equipos pertenecen a esa empresa. La segunda empresa conserva sus datos y accesos propios; la cuenta completa no tiene acceso a ella.

## Qué contiene esta ampliación

| Área | Ejemplos nuevos | Cómo estudiarlos |
|---|---:|---|
| Procesos | 6 | Compras/recepción, documentos, producción, mejora, auditorías y entregas |
| Documentos | 8 | PDF completos de dos páginas; revisiones con distintos estados |
| Controles | 6 | 12 actividades definidas y 12 requisitos de evidencia |
| Implementaciones | 3 | Dos implementadas y una en progreso para practicar |
| Riesgos y oportunidades | 8 | Borrador, evaluado, requiere acción, seguimiento y cerrado |
| No conformidades | 6 | Borrador, contención, investigación, requiere acción, cerrada y cancelada |
| CAPA | 4 | Implementación, cerrada, análisis Ishikawa y plan pendiente |
| Auditorías | 3 programas / 4 planes | Alcance, criterios, equipo y agenda; validación humana pendiente |
| Workflows | 4 | Tarea pendiente, revisión pendiente, recorrido terminado y diseño en borrador |

Se verificaron **52 vínculos activos**, cuatro evidencias aceptadas y ocho descargas PDF cuyos hashes coinciden con los archivos. En la cuenta completa había ocho tareas pendientes al concluir la carga; cambiarán al practicar. Organización, permisos y bitácora muestran las unidades, responsabilidades y cambios reales del ejercicio, no métricas inventadas.

## Cómo se relacionan los registros y los archivos

El **proceso** define dónde ocurre el trabajo. El **documento** es el registro controlado; sus **revisiones** contienen el PDF, su hash y su estado. El PDF se analiza con antivirus y se guarda en almacenamiento privado. Crear un borrador no sustituye una revisión vigente.

Un **control** define qué hay que comprobar. Su **implementación** contiene actividades asignadas y requisitos de evidencia. Una **evidencia aceptada** puede identificar una revisión documental concreta. Riesgos, no conformidades y CAPA añaden referencias explícitas para reconstruir qué información se utilizó.

Los vínculos conservan identificadores, versiones y datos del destino en ese momento. Publicar una revisión nueva no reescribe silenciosamente el soporte de una CAPA cerrada. Retirar una referencia conserva el motivo y el historial.

Dos reglas diferentes del sistema:

- Una evidencia documental de un control debe pertenecer a **la misma empresa, sede y proceso** que su implementación, y utilizar una revisión liberada y limpia.
- Los vínculos explícitos de riesgos, no conformidades y CAPA pueden relacionar **procesos distintos de la misma empresa y sede**. Esto permite conectar recepción con mejora documental; no autoriza cruces entre empresas.

Un enlace demuestra una referencia, no demuestra por sí solo que una causa sea verdadera, una acción eficaz o una auditoría ejecutada. Esos juicios requieren revisión del contenido.

## Recorrido 1: recepción del lote y acción correctiva abierta

1. En **Processes**, abrir `EST-PROC-001`, compras, recepción e inspección.
2. En **Documents**, descargar `EST-DOC-001` (procedimiento), `EST-DOC-002` (registro de inspección del lote `LOTE-DEMO-2411`) y `EST-DOC-007` (soporte ficticio del certificado). Leer los requisitos y resultados, no solo los nombres de los archivos.
3. En **Controls & evidence**, abrir `EST-CTL-001` y `EST-IMP-001`: actividades completadas y evidencia documental aceptada por un actor distinto de quien la presentó.
4. En **Risks & opportunities**, abrir `EST-RSK-001`: valoración inicial 4 × 5 = 20, respuesta y seguimiento. La valoración residual 2 × 3 = 6 es parte del ejercicio, no una certificación de reducción real.
5. En **Nonconformities**, abrir `EST-NCR-001`: certificado incompleto, contención registrada y estado requiere acción. Revisar sus referencias al riesgo, control, evidencia y documento.
6. En **Corrective actions**, abrir `EST-CAPA-001`: origen `EST-NCR-001`, análisis de cinco porqués, acciones y referencias directas/heredadas. La primera acción está en progreso y la segunda abierta.
7. El plan vigente es `EST-DOC-005` revisión **2.0**. La referencia anterior 1.0 se retiró con motivo y permanece visible. El título histórico contiene el alias `CAPA-EST-001`; el PDF vigente y la CAPA usan `EST-CAPA-001`.
8. Para practicar, completar una acción y entrar con el revisor para verificarla. Después completar el resto y solicitar revisión de eficacia. Una CAPA no cierra automáticamente la no conformidad: verificar y cerrar cada registro explícitamente cuando corresponda.

La cuenta completa permite ver y operar las capacidades implementadas, pero no elimina la separación de funciones: no puede aprobar su propio documento ni verificar una acción que ella misma completó. Usar `pmc-multi-user` para las revisiones independientes en empresa A; las claves están en el MD privado.

## Recorrido 2: documentos e historial

- `EST-DOC-003`: revisión 1.0 vigente y **2.0 en revisión**, preparada por `pmc-user-a`. La cuenta completa puede revisar este borrador porque es otro actor. Aprobar y liberar son pasos separados.
- `EST-DOC-004`: revisión 1.0 vigente y **2.0 rechazada**. Un rechazo no elimina el documento ni sustituye la versión vigente.
- `EST-DOC-005`: **1.0 sustituida**, **2.0 vigente**, **3.0 borrador sin archivo**. Seleccionar 2.0 para descargar el plan actual. Seleccionar 3.0 para practicar adjuntar PDF y enviar a revisión. La revisión 3.0 no está aprobada.
- `EST-NCR-002` y `EST-CAPA-002`: caso histórico cerrado mediante acciones verificadas y revisión de eficacia independiente. Consultar el historial y las versiones citadas. La referencia histórica a `EST-DOC-005` 1.0 se conserva como ejemplo de snapshot; el plan de ese PDF corresponde al caso de proveedor y no debe tomarse como prueba específica de eficacia documental. El soporte documental propio se consulta a través de `EST-DOC-003` y `EST-IMP-002`.

El paquete incluye los ocho PDF vigentes y una copia histórica de `EST-DOC-005` 1.0. El manifiesto identifica revisión, tamaño y SHA-256. Los archivos descargados fuera del SaaS son copias de estudio; consultar el registro para confirmar vigencia.

## Recorrido 3: trabajo pendiente y coordinación

- `EST-IMP-003` tiene actividades y evidencia pendientes. Completar el trabajo, aportar soporte del mismo proceso y solicitar aceptación independiente. Un resumen en borrador no equivale a evidencia aceptada.
- `EST-CAPA-003` conserva hipótesis Ishikawa sin confirmar. Contrastar antes de declarar una causa verificada.
- `EST-CAPA-004` tiene un plan y dos acciones abiertas de requisitos de entrega.
- `EST-WF-001` está en tarea de preparación; `EST-WF-002`, en revisión; `EST-WF-003`, completado; `EST-WF-004`, en borrador editable.
- **Action center** reúne tareas autorizadas de CAPA, controles y workflows. Abrir una tarea conduce al registro correspondiente. Los workflows coordinan tareas; no conceden permisos ni reemplazan aprobaciones QMS.

## Auditorías: hasta dónde llega hoy

`EST-PRG-001…003` y `EST-AUD-001…004` contienen programas, alcance, criterios, dos integrantes y dos bloques de agenda por auditoría. `EST-DOC-008` ofrece soporte ficticio para estudiar la preparación.

La independencia y competencia se dejan pendientes de juicio humano. Estar programada no significa estar lista para ejecución. El sistema mantiene `ready_for_execution=false`: **ejecución, evidencias de auditoría, hallazgos, informe y cierre todavía no están implementados**. No se generaron certificaciones ni resultados ficticios para aparentar esas funciones.

## Practicar sin perder trazabilidad

Crear ejemplos propios con un prefijo diferente. Editar campos cuando el estado y los permisos lo permitan; registrar motivos al retirar referencias o cancelar. No todas las entidades se borran físicamente: el sistema conserva historial y bloquea cambios en etapas cerradas.

El cargador agrega registros que faltan y preserva los existentes. No restablece automáticamente datos que se hayan editado ni completa todos los pasos de una carga interrumpida. La verificación estricta detecta hijos o hitos esenciales incompletos/modificados y se detiene sin resetear datos. Tras practicar, una discrepancia con el baseline no implica necesariamente un defecto del producto.

Material original sintético. Sin secretos ni información de clientes. Las pruebas de esta ampliación no equivalen a paridad con Odoo, certificación ISO/NIST/WCAG ni autorización de producción.
