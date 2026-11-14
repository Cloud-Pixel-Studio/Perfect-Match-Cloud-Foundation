# Historial completo de responsabilidades QMS

Implementación A02 sobre PR41, rama `codex/qms-access-history`. Cada empresa mantiene su contexto independiente. Seat o rol de plataforma no concede facultad de aprobación QMS. No se cambian permisos, reglas de autoconcesión, migraciones, modelos ni licencias.

## Contrato y aislamiento

`GET /qms-access/grants/page`: limit1–100 (20 por defecto), cursor, status(all/active/revoked), q(hasta160), user_id, unit_id y capability conocida. Devuelve empresa, usuario/rol del lector, filas con etiquetas limitadas a esos grants y next_cursor. Propietario ve el historial de su empresa; otros roles solo el propio. Pedir otro usuario sin ser owner devuelve403. No se expone el directorio completo a lectores de Mis permisos.

Orden estable created_at DESC,id ASC; cursor keyset ligado a empresa/lector/rol/filtros/límite. Es estado de paginación sin firma y **no otorga autoridad**. RLS y predicados actuales aplican incluso si se fabrica. Cursor inválido400, contexto distinto409. Revalidación final de empresa/usuario/membresía/rol descarta una lectura cuando el acceso cambió durante la consulta. Búsqueda parametrizada con comodines %, _ y barra inversa literales. No hay conteo total ni snapshot histórico entre peticiones.

`GET /qms-access/grants` conserva array y límite100 por compatibilidad. La interfaz de permisos ya utiliza el contrato paginado, permite buscar/filtrar y revocar un grant antiguo tras navegar. Las páginas no calculan autoridad efectiva: esa consulta sigue usando todos los grants aplicables.

Catálogos owner GET /organization/members y /organization/units conservan sus cuerpos y añaden X-Tenant-ID + private,no-store para correlación. El historial y endpoint legacy también usan private,no-store. La UI rechaza catálogos de otra empresa, valida identidad y filas, aborta lecturas atrasadas, limpia contexto ante denegación y vuelve a primera página al filtrar.

## Comandos e interfaz

Conceder responsabilidad consulta el conjunto activo exacto miembro/unidad/capability con limit1, independientemente de las20 filas visibles. No se cambia la restricción de autoconcesión ni la política del auditor técnico. Revocación exige confirmación y conserva el emisor original. Se valida el resultado contra el comando y actor; una respuesta5xx/red/2xx incongruente bloquea reenvío hasta Refresh explícito. Un cambio confirmado conserva el aviso aun si falla la lectura posterior.

Filtros, etiquetas de estados, paginación y maquetación móvil comparten los tokens existentes; sin dependencias nuevas. Los colores no son la única señal de estado. Loading/error/empty y reduced motion conservan los componentes del producto.

## Validación ejecutada

- 42 integraciones HTTP/SQL con PostgreSQL desechable tmpfs PASS:155 grants empresaA/1B, empates de timestamp, filtros, todas las páginas, lectura por rol, cursor falsificado/contexto cambiado, suspensión/revocación concurrente, grant antiguo y ledger atómico; cabeceras de ambos catálogos. No usa DB cliente.
- 23 regresiones de grants PASS; roundtrip vacío y rechazo de downgrade con historia PASS.
- 50 unitarias API PASS;491 integraciones omitidas en corrida sin harness, que no se cuentan como ejecutadas.
- API Ruff/formato y mypy src+tests74archivos PASS.64 unitarias web, lint y typecheck PASS. Build producción PASS antes de últimos cambios exclusivos de pruebas/documentación.
- 16 browser PASS con identidad y API en memoria:owner/admin/member/auditor, grant+revoke, resultado perdido tras persistencia simulada, filtros/páginas/denegación/contexto.375/1440px y temas claro/oscuro afirmados; axeAA/overflow PASS en cuatro estados acotados. No sustituye backend real, OIDC ni certificación WCAG.
- Gitleaks fuente0hallazgos, ShellCheckharnessPASS, OpenGrep6reglas/2archivos Python/0hallazgos. Revisión independiente de solo lectura no halló P1/P2 en el diff inspeccionado; no afirma seguridad completa ni escaneo actualizado de vulnerabilidades de dependencias.

El primer fallo API era una expectativa de fixture de búsqueda con guion bajo; los primeros fallos browser fueron preview iniciado antes de copiar assets, selector ARIA exacto con texto de opciones y aserción del último request que incluía catálogos. Se corrigieron sin relajar permisos. Darktheme se volvió a ejecutar con clave real pm-theme y aserción del atributo; la pasada previa sin esa comprobación no se usa como evidencia final.

## Límites y continuidad

A02 cierra la truncación del historial de grants en la interfaz, **no** el catálogo de miembros/unidades del owner, que todavía carga la primera página100. Altas de autoridad para empresas grandes, lectura intratenant general, Workflow, onboarding y entitlements siguen pendientes. No se añade índice ni prueba de carga de gran escala; valorar planes/índices con datos representativos antes de afirmar rendimiento.

No hay despliegue ni migración local de esta entrega. El runtime de desarrollo sigue PR39/DB0048; PR41 y A02 son ramas revisables. El incidente de disco local y su recuperación se documentan aparte. CI del head final y revisión humana siguen requisitos previos a merge.

CP-QMS-ACCESS-HISTORY-00-20261114T162818Z preserva505fuentes/Git antes de modificar. CP-PARALLEL-AUDIT-WIP-00-20261114T183858Z preserva509fuentes/Git durante relevo; cifrados, restauración de fuentes por SHA256 y bundle verify PASS. Backup y claves fuera del árbol; no sustituyen respaldo DB.
