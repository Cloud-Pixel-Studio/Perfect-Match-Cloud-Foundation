# Catálogo de ediciones ISO y política de mapeo

Estado: referencia de producto verificada el 28 de octubre de 2026. No habilita
checkout, no define precios y no implica que una norma esté implementada en el SaaS.

## Alcance comercial

El QMS completo es el producto base. Los únicos addons comerciales son perfiles ISO
y sus ediciones, conforme al alcance confirmado en `PRODUCT_SCOPE.md`. La selección
de una edición debe habilitar un perfil versionado y sus mappings internos, nunca
alterar el histórico de evidencias. NIST CSF se usa como referencia interna de
ciberseguridad y mapeo; no se ofrece como addon en este catálogo.

## Ediciones a representar en el catálogo

| Identificador | Publicación/estado oficial | Decisión de catálogo |
| --- | --- | --- |
| ISO 9001:2026 | Edición 6, publicada en septiembre de 2026 | Edición actual para el perfil de gestión de calidad. La edición 2015 figura retirada en ISO. |
| ISO 14001:2026 | Edición 4, publicada en abril de 2026 | Edición actual para el perfil de gestión ambiental. |
| ISO/IEC 27001:2022 + Amd 1:2024 | Edición 3 publicada en octubre de 2022; enmienda de acción climática 2024 | Referencia actual de seguridad de la información para el perfil ISO. Guardar base y enmienda explícitamente. |
| ISO 45001:2018 + Amd 1:2024 | Edición publicada; el sucesor DIS está en desarrollo | Puede aparecer como edición publicada, con estado de ciclo de vida y aviso de revisión. No presentar un DIS como edición comprable o requisito final. |
| ISO 22301:2019 + Amd 1:2024 | Edición publicada; ISO indica revisión en curso | Candidato futuro al catálogo, sujeto a confirmar alcance comercial y su estado antes de activar venta. |

El catálogo inicial de producto se prioriza en ISO 9001, ISO 14001 e ISO/IEC 27001.
La inclusión de otros perfiles debe validarse contra los addons originales y la
demanda comercial antes de marcarlos disponibles. Referencias oficiales: [ISO
9001:2026](https://www.iso.org/standard/9001), [ISO 14001:2026](https://www.iso.org/standard/14001),
[ISO/IEC 27001:2022](https://www.iso.org/standard/27001), [ISO 45001:2018 y revisión](https://www.iso.org/standard/45001/rev),
y [ISO 22301:2019](https://www.iso.org/standard/75106.html).

## NIST CSF

NIST CSF 2.0 (publicado en 2024) es un framework para gestionar riesgo de
ciberseguridad. Su función, categorías y mappings se mantienen como una capa de
referencia de seguridad del producto; no es una norma ISO ni una certificación.
La referencia canónica es [NIST CSF 2.0](https://www.nist.gov/cyberframework).

## Política de contenido y mapeos

- Guardar metadatos bibliográficos: identificador exacto, nombre oficial, edición,
  publicación, enmiendas, estado del ciclo de vida, fuente oficial y condición de
  licencia. No copiar requisitos, anexos, explicaciones ni tablas protegidas al SaaS
  hasta tener permiso de distribución aplicable.
- Mantener separado el perfil de implementación propio de Perfect Match y el texto
  oficial. El addon comercial habilita workflows, estructuras y mapeos propios; no
  vende la publicación ISO ni promete certificación.
- Un mapping versionado debe señalar edición + referencia de cláusula/control,
  relación con controles QMS de PMC, justificación propia, aplicabilidad, dueño y
  método de evidencia. Evitar texto normativo copiado.
- Al cambiar edición, crear una nueva versión de perfil y snapshot de sus relaciones.
  Las instancias, decisiones de aplicabilidad y evidencias existentes conservan la
  edición contra la que fueron evaluadas. Migración de edición debe ser explícita,
  auditable y aprobada por el tenant.
- Separar `published`, `withdrawn`, `under_revision`, `draft` y `planned`; no mostrar
  una edición en desarrollo como producto disponible.

## Implementación pendiente

Este documento valida metadatos y reglas de producto, pero no implementa el catálogo,
entitlements, cobro ni mappings. Antes de habilitar una edición para tenants, falta
inventariar sus addons Odoo originales, acordar el alcance comercial, confirmar la
licencia de contenido y validar el perfil de PMC con especialistas.

## Evidencia del producto Odoo de referencia

Se consultó el árbol `main` de `Perfect-Match-Systems/Perfect-Match-QMS2026` el
28 de octubre de 2026. El directorio `addons/` enumera 22 módulos y
`standard_packs/` siete paquetes. Los módulos funcionales que deben entrar en la
matriz de paridad son: `pm_qms_action_center`, `pm_qms_ai`, `pm_qms_app`,
`pm_qms_audit`, `pm_qms_calibration`, `pm_qms_capa`, `pm_qms_core`,
`pm_qms_cost_quality`, `pm_qms_customer_quality`, `pm_qms_documents`,
`pm_qms_evidence`, `pm_qms_implementation`, `pm_qms_iso9001`, `pm_qms_kpi`,
`pm_qms_license`, `pm_qms_management_review`, `pm_qms_migration`, `pm_qms_ncr`,
`pm_qms_pack_quality`, `pm_qms_people`, `pm_qms_portal` y `pm_qms_risk`.

Paquetes encontrados: `pm_as9120`, `pm_cmmc_l1`, `pm_cmmc_l2`,
`pm_iatf16949`, `pm_iso14001`, `pm_iso45001` y `pm_iso9001`. AS9120, CMMC e
IATF no son addons ISO genéricos según el alcance comercial confirmado; su presencia
en Odoo no autoriza venderlos en este SaaS. No aparece paquete ISO/IEC 27001 en el
listado actual, así que su contenido y alcance deben diseñarse y validarse como
trabajo propio antes de ofrecerlo. Tampoco debe asumirse que los paquetes existentes
usan las ediciones oficiales actuales; falta verificar el contenido y las transiciones
de cada uno antes de cualquier migración.

Esta lista sirve como entrada a la matriz de paridad funcional y no afirma que esos
módulos estén implementados en el SaaS. Fuente primaria: [repositorio Odoo de
referencia](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026),
directorios `addons/` y `standard_packs/` en `main`.
