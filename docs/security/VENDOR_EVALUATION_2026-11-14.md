# Investigación vendor — lectura independiente

Consulta realizada 15 noviembre 2026 UTC (14 noviembre por la noche en Nueva York). Solo se leyeron fuentes oficiales, metadata pública de registros y el repositorio. No se cambiaron archivos/ramas del proyecto; no se instalaron herramientas ni se hizo build, pull, despliegue o escaneo nuevo de un tercero. La única escritura de esta fase es este informe temporal. El análisis Quay citado ya estaba publicado (`status=scanned`).

**Conclusión: las últimas versiones estables oficiales verificadas no acreditan cierre de los9HIGH.** Hay candidatos concretos para una rama de evaluación, pero no una imagen verificada que autorice producción o garantice escáner cero. No propongo reemplazar JARs, actualizar el root/JDK manualmente ni ignorar CVEs en bloque.

## Base local inspeccionada

`docs/security/RELEASE_BLOCKERS_2026-11-14.json`: SeaweedFS2HIGH y Keycloak7HIGH. Compose y workflow fijan Keycloak26.8.1/SeaweedFS4.51 por digest; el workflow repite las referencias en scans de vendor y en SBOM Keycloak. Un futuro cambio de prueba deberá mantener consistentes compose, scan y SBOM, sin rebajar el gate HIGH/CRITICAL. Compose usa Keycloak `start-dev` y HTTP/loopback: ese entorno no es configuración de producción.

## Versiones, identidad y digest: no confundir índice con plataforma

| Candidato estable oficial | Publicación release | Índice multi-arquitectura | Manifest Linux AMD64 | Manifest Linux ARM64 |
| --- | --- | --- | --- | --- |
| Keycloak26.8.2 |2026-11-05; tag de contenedor reconstruido2026-11-12 |`sha256:c68e286cacd87b942ac1939a0a1481461109d6acd3a57dc496969a319a76bbf0` |`sha256:4da21f9a53bcbac1026a0d654b740a81e98e5de4c45457076acc74b4d94b1551` |`sha256:923a431c08971d49727a857e64870d8d63b5bf294a730e5dde729b5138c26c9e` |
| SeaweedFS4.53 |2026-11-08 |`sha256:ccad23e18639c8b98cee17e7100b95830a06077b56d8e5b006d6dcf8ec5e94a0` |`sha256:972ba30c529dfc72a6a12ed427e94d99c7b6a6e59d97bfa52be0a849f43e2cc9` |`sha256:210d0f5999432219ca23f61bf467965869520202d4a820d717a6a6c008b77a41` |

Referencias oficiales verificadas: [Keycloak release](https://www.keycloak.org/2026/11/keycloak-2682-released), [downloads](https://www.keycloak.org/downloads), [Quay tag API](https://quay.io/api/v1/repository/keycloak/keycloak/tag/?specificTag=26.8.2), [Quay OCI index](https://quay.io/v2/keycloak/keycloak/manifests/26.8.2), [SeaweedFS release4.53](https://github.com/seaweedfs/seaweedfs/releases/tag/4.53), [Docker Hub API4.53](https://hub.docker.com/v2/repositories/chrislusf/seaweedfs/tags/4.53).

La API Quay conserva también digests históricos del tag26.8.2: se seleccionó el registro activo sin end_ts, no el digest de la primera publicación. El header `Docker-Content-Digest` del índice coincide con c68e… . Los manifests con arquitectura/os `unknown` son attestations y no imágenes AMD64/ARM64. Las versiones de paquetes descritas abajo se inspeccionaron solo para el manifest AMD64; no se infiere que ARM64 tenga idéntico análisis de vulnerabilidades.

## Metadata pública relevante (sin credenciales, headers de autorización ni capas de imagen)

Fuentes: [Quay análisis preexistente AMD64](https://quay.io/api/v1/repository/keycloak/keycloak/manifest/sha256:4da21f9a53bcbac1026a0d654b740a81e98e5de4c45457076acc74b4d94b1551/security?vulnerabilities=true) y [Docker Hub tag](https://hub.docker.com/v2/repositories/chrislusf/seaweedfs/tags/4.53).

```json
{
  "keycloak": {
    "tag": "26.8.2",
    "tag_last_modified": "2026-11-12T13:34:23Z",
    "quay_existing_analysis_status": "scanned",
    "existing_analysis_features": 526,
    "amd64_selected_features": [
      {"Name":"java-21-openjdk-headless","Version":"1:21.0.13.0.9-1.2.el9","Vulnerabilities":[]},
      {"Name":"ca-certificates","Version":"2026.2.92_v9.0.319-90.3.el9_8","Vulnerabilities":[]},
      {"Name":"sqlite-libs","Version":"3.34.1-11.el9_8","note":"same package version as blocked image; Clair lists other Low/Medium CVEs, not proof that Trivy's four SQLite HIGHs are fixed"},
      {"Name":"com.google.guava:guava","Version":"33.6.0-jre","Vulnerabilities":[{"Name":"GHSA-xxph-c9ww-hj94","Severity":"High","FixedBy":"33.7.2"}]}
    ]
  },
  "seaweedfs": {
    "tag":"4.53",
    "tag_last_updated":"2026-11-08T20:49:55.711048Z",
    "tag_status":"active",
    "source_commit":"4ab66fb76da83700739f5839e62fcaf15fb7d02a",
    "source_go_mod":{"go":"1.26.6","github.com/go-jose/go-jose/v4":"v4.1.6","golang.org/x/net":"v0.61.0"}
  }
}
```

Clair/Quay y Trivy no son resultados intercambiables. Un array vacío en Clair no es un nuevo PASS de Trivy ni evidencia de cero vulnerabilidades. El índice Quay devolvió análisis unsupported; se consultó el análisis existente del manifest AMD64 concreto.

## Los nueve hallazgos

| CVE | Candidato / evaluación verificable | Límite |
| --- | --- | --- |
| CVE-2026-116587, go-jose4.1.5 | [Advisory del mantenedor](https://github.com/go-jose/go-jose/security/advisories/GHSA-mgcc-cww5-fp2q): corregido en4.1.6. [go.mod4.53 inmutable](https://raw.githubusercontent.com/seaweedfs/seaweedfs/4ab66fb76da83700739f5839e62fcaf15fb7d02a/go.mod) declara4.1.6 | Fuente corregida; falta verificar el binario/SBOM y escanear la imagen candidata propia |
| CVE-2026-78661, x/net0.61 | [Go oficial GO-2026-6860](https://pkg.go.dev/vuln/GO-2026-6860) afecta html.Parse antes0.62.0;4.53 todavía declara0.61.0 | Upgrade estable4.53 por sí solo no cierra este HIGH. No se demuestra alcance de parser en este servicio ni se descarta |
| CVE-2026-91415, OpenJDK21.0.12 | [Red Hat](https://access.redhat.com/security/cve/cve-2026-91415); metadata AMD6426.8.2 contiene21.0.13.0.9, que coincide con FixedVersion del informe local | Candidato favorable, sin nuevo scan de nuestra imagen/arquitectura |
| CVE-2026-91403, truststore OpenJDK | [Red Hat](https://access.redhat.com/security/cve/cve-2026-91403) explica que el primer bloqueo de intermediarios fue insuficiente; RHEL resuelve mediante ca-certificates/CVE-2026-114406, no declarando fix de91403. [RHSA-2026:88459](https://access.redhat.com/errata/RHSA-2026:88459) fija ca-certificates2026.2.92_v9.0.319-90.3.el9_8, presente en la metadata candidata | `will_not_fix` no significa inocuo. Deben verificarse truststore efectivo y tratamiento del vendor; Trivy puede seguir reportando el ID original. Sin ignore automático |
| CVE-2026-119373, SQLite FTS5 | [Red Hat](https://access.redhat.com/security/cve/cve-2026-119373): precondiciones FTS5/detail=none/rowids maliciosos. sqlite-libs candidata sigue3.34.1-11.el9_8 | No se acreditó parche/backport para ese RPM. No confundir errata de SQLite embebido en Node24 con arreglo del RPM sqlite-libs |
| CVE-2026-119374, SQLite FTS5 | [Errata oficial RHSA-2026:96226](https://access.redhat.com/errata/RHSA-2026:96226) enumera el CVE, pero corresponde al módulo Node.js24, no a sqlite-libs del contenedor | Sin prueba de corrección/aplicabilidad específica de este RPM; sigue pendiente |
| CVE-2026-119379, SQLite session | [Red Hat](https://access.redhat.com/security/cve/cve-2026-119379): cambiosets maliciosos en extensión session. Misma versión RPM en candidata | Requiere parche vendor o prueba específica de no afectación; no se elimina por usar PostgreSQL en nuestra API |
| CVE-2026-119586, SQLite CLI | [SQLite upstream](https://www.sqlite.org/cves.html) aclara que concierne a .recover y piping de su salida al CLI, no a un defecto del core library | Buena base para investigar VEX acotado; todavía falta probar ausencia de CLI/camino de recuperación vulnerable en el artefacto. No blanket ignore de SQLite |
| CVE-2026-102554, Guava33.6.0 | [Release upstream33.7.2](https://github.com/google/guava/releases/tag/v33.7.2) corrige deserialización/asignación descontrolada. La candidata Keycloak26.8.2 aún publica33.6.0-jre y Clair High | Upgrade oficial26.8.2 no cierra este HIGH. No sustituir JAR por fuera del grafo soportado ni prometer compatibilidad |

## Experimento SeaweedFS master, no promoción

El commit inmutable observado en master es **ddd3b3666fa27ab52d8dc6de8d6b9e137c72fc78**, committer2026-11-15T00:34:44Z. [Commit](https://github.com/seaweedfs/seaweedfs/commit/ddd3b3666fa27ab52d8dc6de8d6b9e137c72fc78), [go.mod inmutable](https://raw.githubusercontent.com/seaweedfs/seaweedfs/ddd3b3666fa27ab52d8dc6de8d6b9e137c72fc78/go.mod). Declara Go1.26.6, go-jose4.1.6 y x/net0.62.0. En la consulta, master estaba125commits por delante de4.53 ([compare](https://github.com/seaweedfs/seaweedfs/compare/4.53...master)). No es el tag estable y contiene más cambios que esos dos upgrades.

Propuesta concreta: futura rama de evaluación separada, por ejemplo codex/vendor-refresh-evaluation, con stable4.53 como control y un build aislado del commit completo anterior como experimento. Usar volúmenes/DB de prueba y datos sintéticos nuevos; no adjuntar seaweedfs_data real. Registrar nuevo digest por plataforma, provenance, SBOM y licencias al construir; **no existe aquí un digest de imagen experimental verificado porque no se construyó ni descargó imagen alguna**. No usar la etiqueta flotante master/latest para promoción y no pasar el gate por cambiarle la severidad o desactivar CVEs.

## Compatibilidad y licencia

- Ambos proyectos core mantienen Apache-2.0: [Keycloak26.8.2 LICENSE](https://raw.githubusercontent.com/keycloak/keycloak/26.8.2/LICENSE.txt), [SeaweedFS4.53 LICENSE](https://raw.githubusercontent.com/seaweedfs/seaweedfs/4.53/LICENSE). Esto no convierte todos los RPM/JAR/módulos de sus imágenes en Apache: conservar SBOM, avisos y validación de licencias transitivas.
- Keycloak26.8.2 es candidato de patch para nuestro Authorization Code+PKCES256/discovery/JWKS/issuer/audience/nonce; la compatibilidad es una inferencia por contrato, no una prueba realizada. [Guía de migración](https://www.keycloak.org/docs/latest/upgrading/index.html#migrating-to-26-8-2): cambia autorización de protocol mappers/DCR y Admin REST exige audiencia+scope kc-admin-api. admin-cli incorpora el scope por defecto; el bootstrap local usa admin-cli, pero debe probarse. No desactivar audience check para sortear fallos. Respaldar/restaurar copia del estado Keycloak antes de experimentar; no downgrade directo sobre su volumen después de una migración.
- [Cambios26.8.2](https://www.keycloak.org/2026/11/keycloak-2682-released) incluyen fixes de autenticación/SSO, mappers y SAML adicionales a los9hallazgos del archivo local; ese archivo no es un inventario exhaustivo actual.
- Seaweed mantiene el gateway [S3 oficial](https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API) y `weed server -s3`. Nuestro adaptador usa create/list bucket, put/head/get/delete object, SDKboto3/path style/us-east-1. Probar bytes+SHA256, objetos privados, credenciales incorrectas y acceso anónimo, reinicio/persistencia/rollback con storage/AV y expiración/negativas. No inferir compatibilidad de todos los detalles de IAM/S3 a partir de que exista endpoint8333.
- Las notas4.52/4.53 incluyen cambios de autorización/metadatos S3/IAM y comportamiento de filer, no solo dependencias. `WEED_JWT_FILER_SIGNING_KEY` no autentica universalmente todos los endpoints del filer; mantener límites de red/autenticación específicos. No exponer interfaces internas por suponer que esa clave las cubre.

## Decisión que permite esta investigación

Sí existe una pareja estable, fijada por digest, para probar compatibilidad y mejoras parciales: Keycloak26.8.2/SeaweedFS4.53. **No existe evidencia aquí de una pareja oficial estable que cierre los9HIGH.** Siguen al menos x/net y Guava sin actualización en stable, y los cuatro SQLite no están acreditados como resueltos para ese RPM; el caso CA requiere su análisis preciso incluso con paquete nuevo. No calculo un total residual Trivy ni declaro cero a partir de Clair.

El camino permitido es evaluación aislada con gates intactos y revisión de resultados. Si producción exige HIGH/CRITICAL0, el bloqueo vendor permanece hasta nuevas imágenes soportadas/evidencia de no afectación aceptada de forma específica, o una fase posterior explícita de construcción/compatibilidad que esta investigación no autoriza ni ejecuta. No hay propuesta de JAR override, root/JDK upgrade ad hoc, eliminación forzada de SQLite o waiver general.
