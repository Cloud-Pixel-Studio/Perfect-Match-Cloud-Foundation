# Bloqueo de entrega de la guía ·18 noviembre2026

La guía está implementada y publicada en PR66; **su instalación en la demo está retenida**. No se cambiaron dependencias, lockfile ni umbrales para superar este bloqueo.

## Evidencia del commit de código 3aa7f95

- Foundation quality44328844659: success; sus11jobs concluyeron success. CodeQL44328844679: success.
- Foundation security44328844583: failure en Dependency audits. pip-audit terminó sin vulnerabilidades conocidas; pnpm audit informó1HIGH/1moderate, con GHSA-fc5q-39xc-vjpf para picomatch como HIGH. La réplica local devolvió exit1 y el mismo HIGH.
- No atribuir este fallo únicamente a los6HIGH previos de Keycloak. Al abortar la auditoría de dependencias, se omitieron build/runtime, navegador/axe y ZAP; los escaneos posteriores fallaron por imágenes ausentes. No son nuevos escaneos completos exitosos.
- Vendor image candidate44328844730: failure en el gate de HIGH/CRITICAL; no se adoptó ni desplegó un candidato.

Fuente primaria: [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), revisada17noviembre2026; afecta<=4.0.7 y no identifica versión corregida. Consulta al registro oficial mediante `pnpm view picomatch version` devolvió4.0.7. El riesgo descrito es bloqueo del event loop por patrones extglob maliciosos. No se ejecutó un exploit contra la demo.

Picomatch aparece en cadenas de ESLint/Vitest. Además, inspeccionar la imagen web preparada encontró `next/dist/compiled/picomatch/package.json`, sin versión en ese manifiesto. Esto **no demuestra explotabilidad del SaaS ni identifica por sí solo la versión integrada**; tampoco permite declarar ausente el componente en runtime. No se parcheó manualmente código integrado del proveedor.

## Disposición

La nueva imagen `pmqms-demo-web:guided-journeys-3aa7f95` existe, vinculada por OCI revision al commit3aa7f95a45f07b08731b709875d09b950ed3b615. IDsha256:9f5309cf1db4856616d836cf3148e041be72c4df078a1b1c0b79f71389befab5. Es una preparación, **no un despliegue** ni una aprobación de seguridad. Build Linux desde archivo Git verificado SHA256, instalación frozen y límites1536MiB/1.5CPU/256pids; sin configuración privada montada. Se comprobó que los6contenedores anteriores mantienen sus IDs e imágenes y están healthy. Marketing HTTPS200, API anónima401, admin/master404.

CP-GUIDED-DEMO-CONFIG-00-20261118T145214Z conserva cifrados fuera del árbol los5archivos relevantes: baseCompose, demo override, account-switch override, plantillaNginx y env privado. Decrypt/hash por archivo y rechazo de manipulación verificados. No se modificó Nginx ni se afirma respaldo nuevo de certificados, DB, almacenamiento o IdP. No se aplicó el override nuevo ni hubo rollback necesario.

## Para retomar

1. Revisar una corrección oficial de picomatch y su adopción por Next/herramientas; mantener la versión e integridad fijadas y examinar diferencias.
2. Repetir instalación frozen, auditorías, suite/lint/typecheck/build y CI. Conservar fallo y evidencia históricos; sin exclusiones ni downgrade del umbral.
3. Completar navegador/axe/regresión visual en runtime aislado. Resolver también los bloqueadores de imágenes/Keycloak antes de cualquier aprobación de producción.
4. Construir una imagen nueva desde el código aprobado, renovar checkpoint de configuración y verificar solo el cambio web en la demo autorizada. La imagen preparada aquí no se instala automáticamente al resolver otro PR.

La demo existente también requiere seguimiento de dependencias; mantenerla sin actualizar no es una afirmación de que esté libre de vulnerabilidades. Este informe no sustituye evaluación de exposición o pentest.

## Actualización posterior del18noviembre2026

GitHub retiró GHSA-fc5q-39xc-vjpf. El registro sigue4.0.7; repetir la auditoría devolvió exit0,0HIGH/0CRITICAL/1moderate sin modificar dependencias ni gates. El bloqueo documentado arriba representa la evidencia histórica de3aa7f95, no el estado actual del aviso. Esto permite volver a ejecutar runtime/browser enCI; no resuelve los6HIGHKeycloak ni constituye aprobación de producción. La imagen antigua preparada sigue sin instalarse. Véase docs/product/PERSISTENT_QMS_PROJECTS_2026-11-18.md.
