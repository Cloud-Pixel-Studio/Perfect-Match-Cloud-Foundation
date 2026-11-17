# Decisión de salida a producción

**Decisión PM actual: NO GO para el SaaS comercial.** El usuario delegó al PM decidir cuándo está listo. Se conserva la aprobación humana explícita antes de merge/promoción/despliegue de producción; esta fase no despliega ni cambia datos reales. La decisión estructurada está en PRODUCTION_DECISION.json y evalúa el head47, no atribuye CI previo a los cambios nuevos.

## Condiciones de salida

| Condición | Evidencia necesaria / estado actual |
| --- | --- |
| Seguridad | Último CI completo de PR47/1ad8843: calidad y CodeQL PASS, security falla en gate final por9HIGH de vendors. API/web/PostgreSQL/ClamAV0 HIGH/CRITICAL en esa corrida; no certificación de seguridad. La investigación de estables no acredita cierre de todos los hallazgos |
| Versión integrada | PR revisados, commit y versiones de imagen identificados, CI exacto completo y verde. PR46 accesibilidad es separado, sin integrar automáticamente. Main todavía no incorpora toda la cadena de PR |
| Prueba de aceptación | Staging aislado con actores independientes: alta/selección de empresa, permisos mínimos, aprobación/rechazo/liberación, evidencia/riesgos/NCR/CAPA, cambios concurrentes y ausencia de acceso entre empresas; OIDC/AV/storage reales |
| Operación | Infraestructura definida y autorizada, TLS/MFA/secretos, alertas/retención/capacidad, respaldo cifrado y restauración probada; RPO/RTO acordados y rollback compatible con las migraciones. Un downgrade destructivo no es el rollback por defecto |
| Venta por empresa/seats/ISO | Aprovisionamiento, invitaciones y autoridad inicial, enforcement de seats/addons/empresa, suscripción/cobro/renovación aceptados. La compra nunca concede aprobación QMS |
| Producto completo | Auditorías todavía sin ready/start/ejecución/hallazgos/reporte/cierre; verticales pendientes de la matriz Odoo requieren implementación/aceptación. Un piloto limitado no se anuncia como QMS completo |

Un health200, un contador de tests o un escáner sin hallazgos no autoriza producción. Si una condición es desconocida, fallida u omitida, la decisión continúa NO GO. No se cambia un umbral ni se ignoran CVE para obtener un verde. La producción no se habilita en este repositorio mediante un workflow automático nuevo.

## Controles implementados en esta entrega

Se reutilizan los avances existentes PR21/a66476c (configuración pública HTTPS) y PR29/53474e2 (inventario Trivy), incorporados de forma acotada sobre PR47. No se declaran aquellos PR fusionados ni se copian sus bases antiguas.

En production, Settings exige cookies Secure, clave Fernet válida y HTTPS sin userinfo, controles, espacios, backslash o query/fragmento para web/issuer/callback. Valida puertos y host mediante las librerías existentes. Solo web_url se normaliza al origen del navegador (host, puerto443 y barra final), conservando issuer/callback exactos. El texto de ValidationError oculta las entradas; esto no convierte errors()/model_dump en APIs seguras para publicar ni verifica DNS/certificados/MFA. Development conserva loopback/HTTP.

El inventario heredado analiza Results no vacío, Target no blanco y vulnerabilidades válidas, conserva cada HIGH/CRITICAL y disponibilidad de fix, e invalida salida anterior/publica atómicamente. Es un parser, no una autorización de release.

El wrapper release_image_evidence.py vincula exactamente api/web/postgres/seaweedfs/keycloak/clamav con el SHA/run actual, ArtifactName, ID de configuración Docker, plataforma y tags/digests inspeccionados. Distingue ID de configuración de digest de manifest OCI. Exige seis imágenes realmente distintas utilizadas, no solo seis filas de entrada. La frescura usa CreatedAt del informe, no fecha del build: desde el inicio de scans, ventana máxima1hora y tolerancia futura30segundos. JSON duplicado/no finito, informe reusado, rol faltante, alias cruzado o metadata incorrecta fallan cerrados. Secretos HIGH/CRITICAL se cuentan sin copiar Match/valores.

El collector extrae pins del Compose efectivo, conserva configuración completa solo en una tubería y persiste únicamente cinco campos de identidad del inspect, sin Env. No inicia/pulla contenedores ni aplica cambios. Sus pruebas sustituyen Docker y usan datos sintéticos. No crea una firma criptográfica o provenance verificable por sí solo.

CI exige el nuevo artefacto vinculado a SHA/run y cero hallazgos, además de los gates previos/SBOM/runtime. Todo resultado declara production_authorized=false: evidencia técnica no equivale a aprobación PM/humana.

## Validación y límites

Se ejecutan43 casos de URLs/key de producción (39 iniciales +4 claves inválidas),36 pruebas standalone de inventario/vinculación/collector y regresión18HTTP/PostgreSQL de documentos con AV/storage en memoria. La corrida API completa incluye93 unitarias y509 DB omitidas sin harness; no contar omitidas como aprobadas. Ruff/formato/mypy, ShellCheck, SAST y secretos se registran con evidencia final; no se heredan resultados del head previo.

La revisión independiente detectó un P2 reproducido: dos roles podían terminar vinculados al mismo ID aunque la entrada tuviese seis IDs. Se agregó una regresión RED y comparación de conjuntos vinculados/inspeccionados; la suite pasa tras corregirlo. Un error de tipos del fixture secreto se corrigió sin relajar la aserción. Cuatro claves inválidas se probaron RED antes de añadir validación Fernet.

No hubo cambio de dependencias, permisos, modelos, migraciones ni datos QMS reales. La corrección documental de PR47 sigue en fuente; runtime local continúa PR39/DB0048. Los hallazgos vendor siguen sin remediar en esta rama. Candidatos estables se evalúan después en otra rama/CI aislada y por digest, sin reutilizar volúmenes de desarrollo/cliente ni promocionarlos como listos.

CP-PRODUCTION-GATES-00-20261115T034437Z preserva526fuentes/Git cifrados y restaurados antes de editar. Checkpoint final y CI de este head se verifican al entregar; backups/claves quedan fuera del árbol. No es certificación ISO27001/NIST ni autorización de producción.

Checkpoint final previo a entrega: CP-PRODUCTION-GATES-06-20261115T042034Z;535 fuentes restauradas por SHA256 y bundle verify PASS. La copia exacta entregada y evidencias se sellan al publicar. YAML de ambos workflows parseado con Ruby/Psych; Gitleaks árbol0 y OpenGrep6reglas/3archivos0hallazgos en la fuente final. CI remoto de este nuevo head todavía pendiente.
