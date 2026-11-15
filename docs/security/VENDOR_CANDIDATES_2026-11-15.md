# Evaluación aislada de imágenes estables

Rama `codex/vendor-stable-candidates-20261115`, sobre PR50/f698d0a. **Candidatos, sin autorización de producción.** NO GO comercial permanece. No se reemplazan imágenes del runtime local, no se inicia Compose, no se migran DB reales ni se reutilizan volúmenes de cliente/desarrollo.

Se fijan Keycloak26.8.2 y SeaweedFS4.53 por digest del índice OCI, verificado de nuevo en registros oficiales el15noviembre2026UTC. La metadata pública y sus hashes están en VENDOR_CANDIDATES_2026-11-15.json; no es firma del proveedor ni garantía de cero vulnerabilidades. Los pins coinciden en Compose, Trivy y SBOM. ClamAV/PostgreSQL y contratos/API/permisos no cambian.

Fuentes: [Keycloak26.8.2](https://www.keycloak.org/2026/11/keycloak-2682-released), [Quay](https://quay.io/api/v1/repository/keycloak/keycloak/tag/?specificTag=26.8.2), [SeaweedFS4.53](https://github.com/seaweedfs/seaweedfs/releases/tag/4.53), [Docker Hub](https://hub.docker.com/v2/repositories/chrislusf/seaweedfs/tags/4.53). Investigación previa detallada: VENDOR_EVALUATION_2026-11-14.md.

## Evidencia requerida

GitHub Actions crea un runtime desechable con datos sintéticos: bootstrap Keycloak/Admin API, OIDC, API/storage/antivirus, browser responsive y axe, scans de las seis imágenes y SBOM. El collector de PR50 vincula informe/imagen/plataforma/SHA/run/frescura. Los umbrales HIGH/CRITICAL no cambian. La nueva versión Admin API debe superar bootstrap sin desactivar validación de audience; no se alteran JAR/JDK ni se silencian CVE.

Baseline medido PR47: SeaweedFS2HIGH y Keycloak7HIGH. Las notas de release y dependencias sugieren que pueden persistir hallazgos; solo el scanner exacto determina la diferencia. CI nuevo pendiente al crear este documento. Los resultados y artefactos verificados se registrarán después de la corrida. Un fallo de integridad o runtime impide atribuir un verde a la actualización.

CP-VENDOR-CANDIDATES-00-20261115T042218Z:535 fuentes cifradas/restauradas por SHA256 y bundle verify PASS antes de modificar. Revertir el pin en un runtime desechable no demuestra rollback de datos tras upgrade de Keycloak. Promoción real requiere respaldo DB recuperable y restauración probada, staging y aprobación humana. En esta evaluación no hay migración de datos persistentes reales.

Avances externos detectados: PR48/49 proponen BEMS Quality y marketing; son drafts separados con comprobaciones visuales pendientes. No se mezclan sus fuentes antiguas con esta rama de seguridad ni se cambia identidad por inferencia.

Validación local:36 pruebas de evidencia/parser/collector PASS; ambos YAML parseados; Compose efectivo/scan/SBOM contienen los mismos pins exactos (credenciales solo en RAM); Gitleaks árbol0 hallazgos. No se han descargado/ejecutado estas imágenes localmente. CP-VENDOR-CANDIDATES-06-20261115T042319Z restaura537fuentes por SHA256 y bundle verify PASS. CI funcional y CVE de candidatos todavía pendiente.

## Resultado posterior verificado

099d011: calidad43715161768 y CodeQL43715161763 PASS. Security43715161783 falla solo gate final: Keycloak6HIGH, SeaweedFS1HIGH, otras4imágenes0HIGH/CRITICAL y0secret. Artefacto14162129065 ZIP SHA256440671006ea19de6d6f42e672da17f67a0d4d136badb2cdd20457811ccd8933d verificado; runtime/browser/binding/scans/SBOM/ZAP PASS. No atribuir este resultado a9b398e4, que solo incorpora logging50 y requiere su propio CI. NO GO se mantiene; ver docs/reviews/MERGE_REPAIRS_2026-11-15.md/json.
