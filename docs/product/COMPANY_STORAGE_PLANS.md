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
- Se avisa al 80 % y al 90 %. Una carga que superaría el 100 % se rechaza indicando el espacio disponible. La consulta, descarga y exportación autorizadas, la edición de datos sin nuevos archivos y el historial permanecen disponibles. Al bajar de plan con uso superior a la nueva cuota, el cliente conserva sus archivos y puede gestionar el espacio hasta volver a tener capacidad.

## Costo de referencia

Estimación mensual en USD a ocupación completa durante un mes. Se usó Amazon S3 Standard en Virginia del Norte al tramo inicial de USD 0,023 por unidad binaria de 2³⁰ bytes al mes. La última columna modela también una copia del mismo tamaño a la misma tarifa y descargas equivalentes al 25 % de la cuota, valoradas a USD 0,09 por unidad binaria. Es un escenario presupuestario. El costo de transferencia de cada factura depende del volumen total y de la ruta real. [Lista regional de precios AWS](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-1/index.json), [precios y unidades de Amazon S3](https://aws.amazon.com/s3/pricing/).

| Capacidad | Almacenamiento principal | Escenario con copia y descargas |
| ---: | ---: | ---: |
| 5 000 MB | USD 0,11 | USD 0,32 |
| 25 000 MB | USD 0,54 | USD 1,59 |
| 100 000 MB | USD 2,14 | USD 6,38 |
| 250 000 MB | USD 5,36 | USD 15,95 |

Los importes se calculan a partir de los bytes exactos de cada cuota y se redondean al final. El precio del contrato también cubre solicitudes a la nube, análisis de archivos, cómputo, base de datos, conservación de respaldos, monitoreo y soporte. Para fijarlo, sumar estos costos por empresa y dividir el total por uno menos el margen bruto objetivo. Medir descargas, cantidad de archivos y retención en el piloto antes de fijar la tarifa. Los totales de la tabla son costos de referencia del proveedor, no precios al cliente.

## Implementación prevista

1. Registrar la capacidad contractual en bytes con vigencia y versión. La web comercial mostrará la capacidad incluida por plan al aprobarse la oferta. El panel de la empresa mostrará MB usados, disponibles y contratados. Operación de plataforma verá consumo, alertas y cambios de capacidad sin acceder al contenido de los archivos.
2. Centralizar el control de consumo para el espacio privado de cada empresa. El cargador de PDF existente guarda el tamaño real por revisión y valida el archivo con el analizador de seguridad. Usar ese inventario como punto de partida para medir el uso y reconciliarlo con el almacén. El límite actual de 20 MiB por PDF sigue siendo un límite por archivo.
3. Reservar los bytes antes de escribir el objeto privado. La reserva se hará atómicamente por empresa para que dos cargas simultáneas no rebasen el cupo. Confirmar el uso al conservar el archivo, liberar reservas de cargas rechazadas y reconciliar operaciones interrumpidas con el almacén. Aplicar el mismo control a las fotos, versiones y adjuntos según se incorporen. Registrar las ampliaciones y cambios sin copiar contenido de clientes a la bitácora.
4. Probar límites exactos, empresa sin autorización, cargas concurrentes, reemplazos, fallos de almacén, archivos archivados, retención, restauración y reducción de plan. Habilitar el bloqueo cuando se hayan conciliado los archivos existentes y se haya verificado el límite en todos los cargadores aplicables.

Actualmente hay almacenamiento por archivo para documentos. La cuota contratada, la medición por plan, las ampliaciones facturables y las fotos privadas persistentes quedan pendientes de implementación.
