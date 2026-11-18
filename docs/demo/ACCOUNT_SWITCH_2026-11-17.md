# Cambio de cuenta y perfil demo completo

## Problema reproducido y corrección

El botón Log out revocaba correctamente la sesión SaaS, pero la sesión SSO del proveedor permanecía. Pulsar Continue to Perfect Match creaba otra sesión del mismo usuario sin pedir credenciales, impidiendo elegir fácilmente otro actor.

Las solicitudes de login explícito incorporan ahora `prompt=login`, según [OpenID Connect Core, Authentication Request](https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest). Se conservan state, nonce, PKCE S256, código y validaciones de tokens. No se introdujo login_hint ni una URL de redirección externa controlada por el usuario.

Esto exige reautenticación al entrar explícitamente; no significa logout global de otras aplicaciones del proveedor. Keycloak puede mostrar inicialmente el usuario previo con solo Password: el botón con nombre accesible **Restart login**, junto al usuario, abre los campos Username or email y Password para cambiarlo. Se verificó en el navegador operador → administrador → cuenta completa sin borrar cookies ni usar incógnito.

Solo la imagen API de la demo fue sustituida por `pmqms-demo-api:account-switch-20261117`. El override adicional `infrastructure/demo/account-switch.override.yml` debe aplicarse después de los otros dos compose. El código OIDC desplegado coincide con el local por SHA256 `ac98600b77a7e1a5924fb4451b09ee1a797d8c3507e212f825e28fcba97bd17e`. Se conservaron readonly, cap_drop ALL, no-new-privileges y las imágenes/procesos de la instalación anterior.

## Cuenta de recorrido

Usuario **pmc-demo-full**, séptima cuenta sintética. La contraseña está solamente en el Markdown privado de Descargas, nunca en este repositorio. Pertenece únicamente a Perfect Match Industries · DEMO, con rol owner y 28 capacidades QMS explícitas en DEMO-PRACTICA. Las asignó el owner original mediante APIs normales a este actor distinto; el rechazo de autoasignación no se modificó. No es una cuenta de administración de infraestructura.

Muestra las 13 áreas existentes: Overview, Action center, Workflows, Processes, Documents, Controls & evidence, Internal audits, Risks & opportunities, Nonconformities, Corrective actions, Organization, Permissions y Audit trail. El permiso audits.execute no implementa las operaciones de auditoría aún pendientes.

La solicitud **DEMO · Completar mi primera solicitud** está asignada a esta cuenta y permanece pendiente para que el usuario la ejecute. También hay un documento QA liberado con historia de preparación, revisión y liberación por actores diferentes. Los ejemplos previos no se sobrescribieron.

## Verificación y recuperación

- Test de regresión: falló por ausencia de prompt antes del cambio; 14 tests OIDC PASS después, también por revisor independiente.
- API local: 100 PASS / 573 DB omitidas / dos avisos de deprecación existentes; Ruff/formato y mypy82 PASS. Raíz:90 PASS con wrapper. SAST estricto:6 reglas/1 archivo/0 hallazgos.
- Perfil completo:14 lecturas reales de módulos por HTTPS devolvieron200. Tiene un único tenant y el logout devuelve auth/me401.
- Diez verificaciones nuevas: crea documento y revisión, carga PDF limpio con AV real, envía revisión, deniega autoaprobación, otro revisor aprueba y libera, descarga/hash coincide, deniega autogrant y selección de empresa ajena. Solo registros QA sintéticos nuevos, conservados con historia.
- CP-DEMO-SWITCH-00-20261117T221729Z: checkpoint cifrado de fuentes/Git antes del cambio.
- CP-DEMO-ACCESS-00: backup cifrado PostgreSQL antes de ampliar el perfil, restaurado en tmpfs sin red; conteos/hashes de57 tablas coincidentes. La prueba excluye owners/ACL y no prueba restauración de S3/Keycloak.

La creación inicial de identidades usa el procedimiento de fixture demo existente, no un onboarding comercial. No se cambiaron otras membresías, licencias, permisos de producción ni reglas de revisión. La guía privada y las capturas en artifacts/previews/2026-11-17-account-switch son locales, fuera de Git.

La nueva petición del usuario es ampliar los datos y archivos con flujos conectados. Esa ampliación fue cargada y verificada después; véase CONNECTED_STUDY_GUIDE.md y sus informes propios. Las pruebas anteriores de account-switch no sustituyen esa evidencia. Persisten los seis HIGH del Keycloak evaluado y la prohibición de promover producción sin resolver los gates.
