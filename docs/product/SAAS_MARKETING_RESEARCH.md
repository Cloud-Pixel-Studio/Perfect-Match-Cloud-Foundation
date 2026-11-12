# Web comercial: investigación y aplicación

Fecha: 2026-11-12. Alcance: presentación pública de Perfect Match QMS en `/products`. Esta investigación informa decisiones de diseño; no acredita ventas, certificaciones, paridad con Odoo ni preparación para producción.

## Muestra consultada

Las fichas de reseñas se consultaron el 11 de noviembre de 2026. Las cifras cambian y no constituyen una clasificación global de los mejores SaaS. Las valoraciones pertenecen a los productos de referencia, nunca a Perfect Match QMS.

| Producto | Capterra, corte consultado | Uso en la investigación |
| --- | --- | --- |
| monday.com | [4,6/5; 6.140 reseñas](https://www.capterra.com/p/147657/monday-com/reviews/) | Presentación de una plataforma amplia y recorridos por equipo. |
| ClickUp | [4,6/5; 4.799 reseñas](https://www.capterra.com/p/158833/ClickUp/reviews/) | Agrupación de capacidades y exploración del producto. |
| Qualio | [4,6/5; 138 reseñas](https://www.capterra.com/p/134050/Quality-Management-Software/reviews/) | Referencia del mismo dominio QMS y conversación comercial. |
| Mitti, antes SafetyCulture | [4,6/5; 355 reseñas](https://www.capterra.com/p/141080/iAuditor/reviews/) | Conexión entre tareas operativas, evidencia y compradores. |

La revisión de presentación se hizo sobre fuentes de los proveedores: [monday.com](https://monday.com/), [ClickUp](https://clickup.com/), [Qualio](https://www.qualio.com/), [precios de Qualio](https://www.qualio.com/pricing), [Asana](https://asana.com/) y [Mitti/SafetyCulture](https://mitti.com/safetyculture). No se copiaron identidades, diseños, testimonios ni resultados comerciales. El cambio de nombre SafetyCulture → Mitti está explicado por [el proveedor](https://mitti.com/about) y en su [changelog técnico](https://developer.mitti.com/es/changelog/safetyculture-is-now-mitti).

## Patrones observados y decisiones propias

Las conclusiones siguientes son una interpretación de la muestra, no reglas universales ni evidencia de una mejora de conversión medida.

| Patrón útil | Aplicación en Perfect Match QMS |
| --- | --- |
| Explicar el resultado antes de enumerar funcionalidades. | El hero presenta documentos, riesgos y acciones correctivas dentro del espacio propio de cada empresa. |
| Mostrar el producto pronto. | Captura auténtica del workspace y recorrido con tres vistas: documentos, riesgos y CAPA. |
| Dar una entrada relevante a cada comprador. | Preguntas específicas para responsables de calidad, dueños de procesos e IT/assurance. No se publican módulos ficticios por persona. |
| Separar exploración, conversación comercial y acceso de clientes. | `Explore the product`, `Request a demo` y `Log in` tienen destinos y propósitos distintos. |
| Explicar la oferta sin obligar al visitante a descifrar la arquitectura. | Un espacio por empresa, seats dentro de ese espacio y normas ISO por estándar/edición. El QMS operativo es el producto base. |
| Resolver objeciones próximas a la decisión. | FAQ sobre separación por empresa, autoridad QMS, ISO, certificación y disponibilidad comercial. |
| Hacer concreto el siguiente paso. | Brief local y correo preparado con tamaño del equipo, prioridad y normas de interés. |

## Implementación realizada

- `apps/web/src/app/products/page.tsx` y su CSS acotado presentan la narrativa comercial, audiencias, oferta, estados ISO, seguridad, FAQ y contacto.
- `ProductTour` permite cambiar entre tres capturas con ratón o teclado. Los archivos son capturas del runtime local existente, con datos sintéticos y vistas parciales identificadas.
- `ProductDemoRequest` genera un brief y un enlace `mailto:` dirigido exclusivamente a **Demo@invperfectmatch.com**, correo proporcionado por el usuario. No hay envío desde el servidor, almacenamiento de leads, agenda ni confirmación simulada de entrega.
- `product-enquiry.ts` valida seats enteros entre 1 y 10.000, limita la empresa, normaliza caracteres de control y acepta únicamente prioridades y normas enumeradas. El asunto y el destinatario son fijos; el contenido se codifica en el cuerpo del correo.
- `public/brand/product/asset-manifest.json` registra procedencia, dimensiones, clasificación sintética y SHA-256 de cuatro PNG. `scripts/capture-product-marketing.mjs` restringe las capturas a los servicios loopback autorizados y no modifica registros QMS.
- Se reutilizan identidad Aligned Evidence, tokens, tipografía, iconografía y temas existentes. No se añaden dependencias ni se cambia backend, autenticación, permisos, contratos API o esquema.

La mera existencia de estas implementaciones no equivale a una prueba superada. Los resultados finales de build, pruebas unitarias, navegador, accesibilidad y revisión visual deben leerse en el informe del hito y en el checkpoint correspondiente.

## Límites comerciales explícitos

1. La web presenta una **vista previa**. Pricing, compra y trial automático siguen sin habilitarse.
2. ISO 9001 está en preparación; ISO 14001 e ISO 45001 están planificadas. Las selecciones expresan interés, no adquieren derechos ni habilitan contenido. Ediciones, licencias de contenido y términos requieren confirmación antes de contratar.
3. Seats representan capacidad comercial; no conceden autoridad de lectura, revisión o aprobación. El enforcement de suscripciones/seats no se declara terminado por mostrar este formulario.
4. ISO/IEC 27001 y NIST son objetivos de seguridad. La web no afirma certificación, conformidad total ni aprobación de producción.
5. No se publican logos de clientes, reseñas propias, cifras de adopción, ROI, descuentos o testimonios sin evidencia y autorización.
6. Los PNG contienen datos sintéticos. Sus contadores son ilustrativos y no prueban capacidad, rendimiento ni uso por clientes reales.

## Verificación y evolución

La evaluación inicial debe cubrir reflow móvil/tablet/escritorio, temas claro/oscuro, foco visible, navegación de tabs, FAQ con teclado, contraste automatizado, enlace de correo y contenido real del brief descargado. Axe y capturas no sustituyen una evaluación completa WCAG o aceptación con usuarios de calidad.

Tras contar con una web publicada y una política de privacidad aprobada, se podrá medir si los visitantes encuentran el recorrido y completan una solicitud. No se instala analítica ni se contacta a terceros en este hito. Las siguientes necesidades comerciales son confirmar disponibilidad/precios, definir recepción de solicitudes y completar el área cliente y enforcement de suscripciones sin confundirlas con esta mejora de presentación.
