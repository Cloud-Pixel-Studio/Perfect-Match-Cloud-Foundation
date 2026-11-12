# CAPA desde no conformidades y riesgos

12 noviembre2026. Rama `codex/capa-origin-workflow`, basada en
`codex/document-command-feedback@ba884bcba9e75422218a7b1f409d6d0a7b88876e`.

## Resultado implementado

NCR y riesgos muestran sus CAPA de origen, con código, título, estado, fecha y
un enlace al registro exacto del workspace CAPA existente. Un formulario breve
crea una CAPA con empresa/unidad/proceso/origen fijos; el responsable se asigna
en CAPA. No se reimplementa el ciclo de causa, plan, acciones y eficacia.

El panel compartido incluye paginación de20 con lectura de21 para detectar la
siguiente página, skeleton, vacío, error, actualización explícita y estados
accesibles. Usa tokens y temas existentes; respeta reduced-motion. Las fuentes
canceladas conservan su historial pero no ofrecen creación. Código manual:
la numeración automática sigue pendiente.

## Contratos y seguridad

- GET `/capas` añade filtros UUID opcionales `source_ncr_id` y `source_risk_id`.
  No cambia la respuesta ni el comportamiento de las consultas sin filtro.
  Conserva q literal, source_type, limit y offset. Ambos orígenes o un tipo
  incompatible devuelven422; un origen no visible devuelve404.
- Exige `capa.read` y lectura NCR/riesgo en la unidad. Consulta el origen con
  empresa y unidad explícitas y conserva PostgreSQL/RLS. No trata owner/seat
  como autoridad QMS. La UI rechaza filas que no coinciden con el origen.
- POST utiliza la creación existente y sus validaciones de proceso, origen,
  permisos y código único. No cambian permisos, modelos, esquema, migraciones,
  autenticación, licencias, dependencias ni configuración productiva.
- La creación UI requiere capa.read/manage, lectura de origen y processes.read.
  El servidor sigue siendo la autoridad. No hay reenvío automático.503/409/422
  conservan el borrador;401/403/404 borran el panel y recargan capacidades/datos
  de la unidad y sesión. Respuestas2xx ambiguas bloquean un segundo envío con
  explicación persistente hasta revisar el registro principal.
- Cada ámbito/registro/proceso remonta el panel. AbortController y generaciones
  descartan respuestas tardías. Busy compartido evita editar origen y crear CAPA
  simultáneamente. Los enlaces conservan pm_source/pm_record/pm_unit autorizados.

## Evidencia

| Comprobación | Resultado observado |
| --- | --- |
| Ruff/formato y mypy API+tests | PASS,58 archivos tipados y99 de formato. |
| Pytest sin PostgreSQL |50PASS,299SKIP,2warnings preexistentes deStarlette/AnyIO. |
| Suite PostgreSQL desechable |199/199PASS, incluidas14 nuevas por origen. |
| Migraciones en DB desechable | head→0008→headPASS antes de datos; downgrade destructivo tras historial bloqueadoPASS. No se migró la DB local del SaaS. |
| Frontend | ESLint,TypeScript,59unitarias ybuildPASS. |
| Playwright Darwin |50/50PASS sin reintentos ni actualización de snapshots. |
| Playwright Linux |50/50PASS sin reintentos ni actualización de snapshots; Playwright1.64.1 por digest2f05f8a. |
| Secretos | Gitleaks árbol/historialPASS. |
| Dependencias/licencias | PolíticaPASS; audit0High/Critical y1Moderate preexistente; Trivy repositorio0High/Critical. No dependencias nuevas. |
| Análisis estático |6 reglas OpenGrep,0 hallazgos en API. Parser parcial preexistente encontrol_definitions.py:223; no acredita análisis TypeScript completo. |
| Revisión independiente | Lectura deAPI/UI por otro agente. Se corrigió recarga de capacidades y bloqueo/explicación de creación incierta. No equivale a aprobación humana o auditoría completa. |

Las14 pruebas DB cubren orígenes exactos, búsqueda literal, paginación, filtros
incompatibles, IDs desconocidos, unidades y empresas distintas aun con grants
válidos, revocación y trazabilidad de NCR cancelada. Primera ejecución198PASS/1FAIL:
el fixture de cancelación no tenía ncr.review; se concedió correctamente solo en
la DB desechable y la repetición final pasó199/199. No se relajó la autorización.

Navegador:14 casos nuevos,13 con respuestas simuladas y toda escritura QMS
interceptada;1live lee DEMO-NCR-001 y abre DEMO-CAPA-001 sin escrituras. Los fixtures
comprueban creación de ambos orígenes,201 exacto,503 con borrador,202 incierto,403 con revocación,
permisos, paginación, respuesta obsoleta, API antigua, fuente cancelada y375/1440px con axe.
Las36 regresiones existentes conservan productos, galería, administración,
documentos y otros módulos. No se usa una escritura simulada como prueba de
persistencia: la creación real queda cubierta separadamente por integración DB.
Verificación adicional en el navegador de la sesión: el demo NCR abrió su CAPA
persistida. No se crearon datos QMS en el runtime local.

## Recuperación y entrega

CP inicial **CP-CAPA-ORIGIN-00-20261112T154919Z**:410 archivos más Git cifrados
fuera del repositorio, restauración aislada por hash y bundle verifyPASS. Clave
0600 separada. Sin copia de datos de clientes ni restauración DB declarada.
Checkpoint final **CP-CAPA-ORIGIN-06-20261112T212240Z**; resultados de restauración en su manifiesto público. PR se registra tras sincronizar.

Preview local3000/API8000 actualizado mediante capas pequeñas. Imágenes previas
retenidas en tags `pmcloud-{api,web}:before-capa-origin-20261112`; sin modificar
Dockerfiles ni volúmenes. No es un despliegue productivo.

## Límites y siguientes verticales

Este hito cierra la brecha de navegación/creación inversa NCR/riesgo→CAPA; no
prueba paridad integral con Odoo. Faltan adjuntos genéricos, autonumeración,
reportes y aceptación con usuarios. Auditoría interna0040 sigue parcial sinUI;
no aplicar el borrador0041. KPI, revisión por la dirección, formación,
calibración, calidad cliente/proveedor, costos, importación y licenciamiento
por empresa/seats/ISO siguen pendientes según la comparativa12nov.

Se mantiene la propuesta Básico1empresa+3seats+1ISO, sin precio ni edición
confirmados. CI del head nuevo requiere lectura propia. Release sigue bloqueado
por imágenes proveedoras y requisitos operativos; no trasladar al head actual
el PASS/FAIL delPR27. Sin merge o despliegue automático.
