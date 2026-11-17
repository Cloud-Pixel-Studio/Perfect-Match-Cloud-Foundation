# Reconciliación de avances externos

Corte: 2026-11-12. Repositorio oficial: [Perfect-Match-Cloud-Foundation](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation). Se revisaron refs descargadas, metadatos de PR y fuentes originales. No se integraron automáticamente ramas, no se aplicaron migraciones y no se hizo merge o despliegue.

## Historia y punto de continuación

| Referencia verificada | Estado y consecuencia |
| --- | --- |
| [`main@13e672a6269c4200c124a0eaf88efe86cedc67ab`](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/commit/13e672a6269c4200c124a0eaf88efe86cedc67ab) | Incluye el workflow engine del PR #12. No contiene toda la fundación QMS desarrollada en ramas. |
| [`91b26b55166f043e53a44328fd12524a29d744ed`](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/commit/91b26b55166f043e53a44328fd12524a29d744ed) | Baseline local validado de Design Studio, antes del nuevo trabajo comercial. |
| [`codex/branding-identity-system@ae8f26298b43179297974b5a5edd48d23b11a8f5`](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/commit/ae8f26298b43179297974b5a5edd48d23b11a8f5) | Tiene exactamente el mismo árbol que `91b26b5`: `547d0ec6b260aca88f5b571cd003ec5aa29719a9`. La diferencia de historial no indica pérdida del trabajo visual. |
| [PR #17](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/17) → [#16](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/16) → [#15](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/15) | Sus merges propagaron Design Studio, planificación de auditorías y UI hacia ramas ascendentes. No significan que todo esté en `main`. |
| [PR #19](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/19) → [PR #13](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/13) | Sigue pendiente la consolidación de la cadena en la fundación y después en `main`, con checks sobre el head exacto, revisión independiente y aprobación humana. |

El trabajo comercial continúa en `codex/product-marketing`, sin incorporar el diff no relacionado de especialistas, hardening o prototipos. Esto conserva una revisión acotada; no presenta como integradas mejoras que aún viven en otros PR.

## Avances encontrados y límites

| Avance | Evidencia | Qué está y qué falta |
| --- | --- | --- |
| Especialistas Codex | [PR #20](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/20), [PR #22](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/22), head `d877a255e62d646f27f15d890f75793c8b07a6ec` | Once manifiestos especializados y límite de cuatro concurrentes; validador y utilidades de lease/reconciliación. Son configuración y helpers, no un scheduler/worker remoto ni una plataforma autónoma completa. Las instrucciones de rol no constituyen un sandbox. |
| URLs públicas productivas | [PR #21](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/21), [`a66476cacf09137067949af2e1a93d2fc7d11c38`](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/commit/a66476cacf09137067949af2e1a93d2fc7d11c38) | Rechaza HTTP, credenciales y partes indebidas de URLs en producción; conserva loopback de desarrollo. Cambio independiente, no incorporado a marketing ni acreditación de seguridad productiva. |
| Candidatos de imágenes | Workflow de candidatos en PR #22 | Escaneo por digest y evidencia para Keycloak 26.8.2/SeaweedFS 4.53. Los candidatos conservan 6 + 1 hallazgos High/Critical; los pins reales 26.8.1/4.51 no cambiaron. No hay remediación completada. |
| Formato de prototipo documental | [PR #23](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/23), [`be195e79e74505d3fcda478c609b47a43e5cf322`](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/commit/be195e79e74505d3fcda478c609b47a43e5cf322) | Ajuste Ruff de dos archivos; no representa una nueva vertical documental. |
| Inventario CVE | [PR #24](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/24), [`7f61d96898b564d4b4717cd86bd91d9a43215226`](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/commit/7f61d96898b564d4b4717cd86bd91d9a43215226) | Script de inventario y cinco tests. No está conectado al workflow. Acepta `Results: []` y comprueba longitud del digest sin validar hexadecimal/repositorio; no debe sustituir el gate estricto de escaneo. |

### Evitar reconstruir documentos

El nuevo `apps/api/src/pmc_api/document_control.py` es un prototipo de 74 líneas: dataclass inmutable, estados y transiciones puras. Solo lo importan sus tests; carece de rutas, persistencia, capacidades y eventos auditables. Sus estados `in_review/effective` difieren de `under_review/active` del módulo `documents.py` existente.

No se debe sustituir la vertical documental ya desarrollada ni sumar este prototipo como una segunda función terminada. Primero debe justificarse su necesidad y conciliar contratos, estados, autorización y migraciones mediante una propuesta explícita.

### Preservación de Auditoría Interna 0041

El borrador sigue separado en [`codex/wip-audit-scope-recovery@6b10edff046abd12089fb052d30e76e949ac35cc`](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/commit/6b10edff046abd12089fb052d30e76e949ac35cc). No forma parte de marketing. Que esté respaldado en GitHub no valida migración, RLS o API; no aplicar `alembic upgrade head` desde esa rama hasta completar sus pruebas.

## Validación independiente realizada

El agente de revisión externa ejecutó pruebas puras desde un `git archive` temporal del SHA exacto `7f61d96898b564d4b4717cd86bd91d9a43215226`, usando Python 3.12.15 y dependencias API disponibles. No instaló paquetes ni levantó contenedores, no accedió a una base y eliminó después el snapshot temporal.

| Verificación | Resultado reportado |
| --- | --- |
| `scripts/check-codex-agents.py` | PASS; 11 especialistas, concurrencia 4. |
| `unittest` · `test_trivy_cve_inventory.py` | 5 PASS. |
| `unittest` · `test_codex_agent_manifest_validator.py` | 4 PASS. |
| `unittest` · `test_vendor_candidate_workflow.py` | 7 PASS. |
| `pytest` · `apps/api/tests/test_document_control.py` | 6 PASS. |

Total: **22 pruebas puras PASS**. Esto valida esos tests en ese snapshot; no equivale a CI completo del head, integración PostgreSQL, aislamiento RLS, runtime OIDC ni aprobación de release. Los resultados de marketing se registran por separado.

## Riesgos y próximos pasos

1. Mantener el release bloqueado hasta resolver los hallazgos de proveedores y verificar las imágenes efectivas. El escaneo previo de pins documentaba 7 High de Keycloak + 2 de SeaweedFS; el resultado 6 + 1 corresponde a candidatos y otro corte. No comparar como si fueran la misma imagen o base de vulnerabilidades.
2. Revisar y validar los heads exactos antes de consolidar PR #19/#13. No extender un PASS histórico a commits posteriores.
3. Revisar el inventario CVE antes de integrarlo en CI, preservando los umbrales existentes y la validación estricta de informes/digests.
4. Continuar la auditoría interna desde la vertical 0040 validada, conciliando el WIP 0041 sin duplicar modelos ni aplicar borradores no probados.
5. Respetar el README de derechos actualizado: los derechos personales de Bárbara De Sola y la consultoría Perfect Match Investments LLC son ámbitos distintos. No inferir titularidad comercial adicional en la web.
6. La equivalencia funcional total con Odoo, suscripciones/seats/entitlements, validación humana de UX y requisitos productivos siguen abiertos en sus documentos de alcance. Ninguno se declara cerrado por estos avances externos.

No se autorizan merge, despliegue ni relajación de controles por este informe.
