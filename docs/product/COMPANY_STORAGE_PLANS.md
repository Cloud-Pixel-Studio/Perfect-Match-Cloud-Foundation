# Almacenamiento por empresa y plan

Propuesta comercial del 27 de noviembre de 2026. Las cuotas de todos los planes y los nombres de los planes superiores al Básico están pendientes de aprobación. La tabla servirá para cotizar cuando la oferta esté aprobada y el producto pueda medir el consumo.

## Capacidad incluida

| Plan | Capacidad incluida por empresa | Uso previsto |
| --- | ---: | --- |
| Básico | 5 000 MB (5 GB) | Primera implementación y archivo documental inicial. Incluye una empresa, 3 seats y 1 addon ISO según las condiciones de disponibilidad. |
| Equipo | 25 000 MB (25 GB) | Varias áreas que cargan documentos, fotos y evidencias con regularidad. |
| Profesional | 100 000 MB (100 GB) | Operación con más sedes, revisiones y auditorías. |
| Empresarial | 250 000 MB (250 GB) | Operación de mayor volumen. Capacidad superior bajo cotización. |

Cada cuota pertenece al espacio de una empresa. Los planes superiores conservan el QMS completo y el contrato indica sus seats y ediciones ISO. Los seats y los addons ISO son independientes de la capacidad. Dos empresas tienen suscripciones y cuotas independientes, incluso si comparten un administrador. La cuota mide el espacio ocupado, se mantiene durante la vigencia del plan y no se recarga cada mes. Un MB comercial equivale a 1 000 000 bytes y un GB a 1 000 MB.

## Qué incluye el contrato

- La tarifa recurrente incluye la capacidad contratada, su operación y los respaldos gestionados por Perfect Match. Una ampliación de capacidad se incorpora al contrato con importe, vigencia y nueva cuota. La unidad inicial propuesta para ampliar es 25 000 MB. Las ampliaciones y los cambios de plan requieren autorización del cliente. Al alcanzar la cuota, no se factura un excedente automático.
- Consumen espacio los archivos conservados para la empresa: revisiones de documentos, fotos de trabajadores, evidencias y anexos. Una versión anterior o archivada sigue contando mientras deba conservarse. Las copias técnicas de respaldo, miniaturas internas y archivos temporales no se suman a la cuota de cara al cliente. Su costo se contempla internamente. Una eliminación permitida libera espacio una vez confirmada.
- Se avisa al 80 % y al 90 %. Una carga que superaría el 100 % se rechaza. Los administradores autorizados pueden consultar el espacio disponible en el panel. La consulta, descarga y exportación autorizadas, la edición de datos sin nuevos archivos y el historial permanecen disponibles. Al bajar de plan con uso superior a la nueva cuota, el cliente conserva sus archivos y puede gestionar el espacio hasta volver a tener capacidad.

## Costo de referencia

Estimación mensual en USD a ocupación completa durante un mes. Se usó Amazon S3 Standard en Virginia del Norte al tramo inicial de USD 0,023 por unidad binaria de 2³⁰ bytes al mes. La última columna modela también una copia del mismo tamaño a la misma tarifa y descargas equivalentes al 25 % de la cuota, valoradas a USD 0,09 por unidad binaria. Es un escenario presupuestario. El costo de transferencia de cada factura depende del volumen total y de la ruta real. [Lista regional de precios AWS](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-1/index.json), [precios y unidades de Amazon S3](https://aws.amazon.com/s3/pricing/).

| Capacidad | Almacenamiento principal | Escenario con copia y descargas |
| ---: | ---: | ---: |
| 5 000 MB | USD 0,11 | USD 0,32 |
| 25 000 MB | USD 0,54 | USD 1,59 |
| 100 000 MB | USD 2,14 | USD 6,38 |
| 250 000 MB | USD 5,36 | USD 15,95 |

Los importes se calculan a partir de los bytes exactos de cada cuota y se redondean al final. El precio del contrato también cubre solicitudes a la nube, análisis de archivos, cómputo, base de datos, conservación de respaldos, monitoreo y soporte. Para fijarlo, sumar estos costos por empresa y dividir el total por uno menos el margen bruto objetivo. Medir descargas, cantidad de archivos y retención en el piloto antes de fijar la tarifa. Los totales de la tabla son costos de referencia del proveedor, no precios al cliente.

## Desglose para el anexo comercial

Completar una ficha por empresa al emitir la oferta. El resumen de demo muestra intereses y capacidad propuesta. El anexo firmado fija los valores aplicables.

| Campo | Dato que debe quedar escrito |
| --- | --- |
| Empresa y espacio de trabajo | Razón social, identificador del espacio y plan contratado. |
| Capacidad total | MB incluidos y capacidad adicional autorizada, expresados también en bytes. Fecha de inicio y de renovación. |
| Alcance del producto | QMS incluido, cantidad de seats y normas ISO con sus ediciones y disponibilidad. |
| Precio recurrente | Importe, moneda, periodicidad y desglose de cualquier ampliación autorizada. Indicar que el almacenamiento contratado y los respaldos gestionados forman parte del precio. |
| Servicios de implementación | Alcance y cargos únicos de configuración, formación o migración, si corresponden. Desglosar el total del primer año y el importe recurrente de renovación. |
| Consumo y continuidad | Archivos que cuentan, retención de revisiones, avisos, qué ocurre al alcanzar la cuota y cómo solicitar más espacio. |
| Cambios posteriores | Nueva capacidad, importe, fecha efectiva y constancia de aceptación del cliente. |

La comparación de capacidad propuesta está en `/products/plans`. Su asistente estima la cuota mínima según el almacenamiento previsto y cuantifica seats o espacio adicionales cuando existe una diferencia. El cliente puede preparar un correo o descargar su resumen de demo con su estimación editable y el alcance que falta confirmar.

## Implementación prevista

1. Registrar la capacidad contractual en bytes con vigencia y versión. La web comercial mostrará la capacidad incluida por plan al aprobarse la oferta. El panel de la empresa mostrará MB usados, disponibles y contratados. Operación de plataforma verá consumo, alertas y cambios de capacidad sin acceder al contenido de los archivos.
2. Centralizar el control de consumo para el espacio privado de cada empresa. El cargador de PDF existente guarda el tamaño real por revisión y valida el archivo con el analizador de seguridad. Usar ese inventario como punto de partida para medir el uso y reconciliarlo con el almacén. El límite actual de 20 MiB por PDF sigue siendo un límite por archivo.
3. Reservar los bytes antes de escribir el objeto privado. La reserva se hará atómicamente por empresa para que dos cargas simultáneas no rebasen el cupo. Confirmar el uso al conservar el archivo, liberar reservas de cargas rechazadas y reconciliar operaciones interrumpidas con el almacén. Aplicar el mismo control a las fotos, versiones y adjuntos según se incorporen. Registrar las ampliaciones y cambios sin copiar contenido de clientes a la bitácora.
4. Probar límites exactos, empresa sin autorización, cargas concurrentes, reemplazos, fallos de almacén, archivos archivados, retención, restauración y reducción de plan. Habilitar el bloqueo cuando se hayan conciliado los archivos existentes y se haya verificado el límite en todos los cargadores aplicables.

## Medición disponible en Control de empresa

**Storage usage** muestra a propietarios y administradores los bytes registrados y el número de archivos PDF de su empresa. Incluye revisiones anteriores conservadas y archivos registrados como limpios aunque estén en borrador. Los archivos rechazados o en cuarentena quedan fuera de ese total.

La migración `0062_company_document_storage` calcula el total inicial a partir de las revisiones existentes. Las cargas posteriores actualizan los totales por empresa en la misma transacción que la revisión. El medidor usa metadatos confirmados en PostgreSQL. El agregado no otorga permisos sobre documentos ni devuelve nombres o rutas de archivos. El costo de las copias técnicas sigue pendiente.

## Activación de la cuota aprobada

La migración `0063_company_storage_allowance` permite registrar la capacidad aprobada por empresa en bytes. El sitio comercial conserva las cuotas propuestas. El panel muestra **pendiente de activación** hasta que exista un registro aprobado. Después muestra el espacio disponible según los PDFs registrados y distingue 80 %, 90 %, capacidad agotada y uso por encima de la cuota. Los avisos están en el panel.

El registro se hace desde operaciones autorizadas con la identidad propietaria del esquema. La función SQL interna `public.record_company_storage_allowance(empresa, bytes, versión_esperada, aprobación)` recibe el UUID de empresa, los bytes acordados, la última versión conocida (cero para el alta) y un UUID que identifica la aprobación en el sistema de operaciones. La versión guarda la identidad de la conexión y la fecha de registro. Repetir la misma aprobación con los mismos datos devuelve la versión original. Cambios posteriores requieren la versión vigente y su propia aprobación. Las versiones anteriores se conservan.

La cuenta de la aplicación y los administradores de las empresas carecen de permiso para registrar cuotas. El panel expone la capacidad vigente a las autoridades de la empresa seleccionada y conserva las referencias internas de aprobación fuera de la respuesta.

## Aplicación en cargas de PDF

La migración `0064_document_storage_quota` activa el límite para empresas con una cuota aprobada. El cargador compara los bytes reales del PDF tras el análisis de seguridad y antes de escribir el objeto privado. PostgreSQL serializa por empresa la comprobación, la escritura documental y los cambios de cupo. La proyección vuelve a comprobar cada aumento de bytes al registrar la revisión. Un aumento que excede la cuota se rechaza, incluso si un único comando agrupa varias revisiones.

El rechazo conserva el borrador y los PDFs existentes. Si baja la cuota por debajo del consumo actual, permanecen disponibles las descargas autorizadas y el historial. Las empresas sin cuota aprobada conservan el comportamiento de carga anterior. El error informa que el PDF no cabe y remite al medidor. Los totales exactos siguen reservados a propietarios y administradores.

Ante un fallo antes del intento de confirmar la transacción se intenta retirar exclusivamente el objeto de la carga fallida. Si se pierde la conexión durante la confirmación, se conserva el objeto privado porque su revisión puede haber quedado confirmada. Los avisos fuera del panel, la facturación y las fotos privadas siguen pendientes.

## Conciliación de PDFs privados

El equipo de operaciones puede ejecutar un inventario manual de solo lectura para el UUID de una empresa. Compara las referencias de todas sus revisiones con el listado paginado del prefijo privado `qms/<uuid>/`. Confirma una ausencia o diferencia de tamaño con una segunda consulta de metadatos. Un acceso denegado, un listado fuera de ese prefijo o un problema de permisos en la base de datos interrumpen el informe.

Desde el entorno de ejecución de la API, con las credenciales de inventario inyectadas por el gestor de secretos:

```bash
python -m pmc_api.document_storage_reconciliation --tenant "$COMPANY_UUID"
python -m pmc_api.document_storage_reconciliation --tenant "$COMPANY_UUID" \
  --report "$PRIVATE_REPORT_DIR/pdf-reconciliation.json"
```

- `PMC_RECONCILE_DATABASE_URL` usa el esquema `postgresql+pg8000` con una cuenta dedicada sin permisos de escritura ni superusuario. La cuenta necesita `USAGE` en el esquema `public`, `SELECT (id)` en `tenants` y `SELECT (id, tenant_id, file_object_key, file_size)` en `qms_document_revisions`. La lectura completa de revisiones requiere `BYPASSRLS`. Mantener esta credencial fuera de la API, limitar su acceso al entorno de operaciones y comprobar sus privilegios efectivos antes de habilitarla.
- `PMC_RECONCILE_S3_ENDPOINT`, `PMC_RECONCILE_S3_DOCUMENTS_BUCKET`, `PMC_RECONCILE_S3_ACCESS_KEY`, `PMC_RECONCILE_S3_SECRET_KEY` y, si corresponde, `PMC_RECONCILE_S3_REGION` configuran el almacén. Limitar la identidad de inventario al listado del prefijo de la empresa y a `HEAD` sobre sus objetos. En AWS S3, `HEAD` requiere `s3:GetObject`, que también permite leer contenido. Usar credenciales de alcance limitado y reservarlas para esta operación. Una ausencia verificada devuelve 404. Un 403 se registra como inventario incompleto. [Permisos de HeadObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html).
- La salida normal contiene cantidades. Con `--report` se crea un archivo nuevo, con permisos `0600`, en un directorio privado administrado por operaciones. El detalle incluye claves internas, IDs de revisión y tamaños donde corresponda. El comando no descarga archivos ni incluye nombres de documentos. El código de salida es `0` sin hallazgos que requieran revisión, `1` con hallazgos y `2` si el informe queda incompleto.

Los objetos sin referencia de menos de 24 horas se cuentan por separado para dar margen a las cargas en curso. Cualquier objeto más antiguo sin referencia es un candidato a investigación. Repetir la conciliación antes de actuar y verificar la bitácora y los respaldos si la diferencia persiste. Cada ejecución conserva los objetos, las revisiones y los totales. Inventariar tamaño no verifica el contenido ni ejecuta una restauración. La programación periódica y la conciliación de otros tipos de adjuntos siguen pendientes.
