# Recuperación de sesión y contexto en la bandeja

## Cambio terminado

Completa el WIP local preservado de ActionCenter. Ante401, tanto el resumen como la bandeja completa retiran tareas y métricas y muestran una acción explícita para entrar de nuevo.403 indica pérdida de acceso; errores de red/servidor o respuestas inválidas muestran indisponibilidad y permiten reintentar. Nunca se muestran cuerpos de error del servidor.

Las lecturas usan el proxy existente, credenciales same-origin y `cache: no-store`. El contrato de visualización se valida antes de renderizar: scope solicitado, fechas, métricas, lista, tipos y enums. Las respuestas fuera de orden y las de componentes desmontados se ignoran. Overview y ActionCenter se vuelven a montar con la combinación actor/empresa/rol, impidiendo reutilizar una cola del contexto anterior.

El enlace de recuperación hace una navegación completa al login OIDC existente. Una excepción ESLint de una sola línea explica por qué no se usa navegación SPA/prefetch sobre ese GET que establece estado de autenticación. No cambia autenticación, autorización, sesiones API, capacidades, modelos, licencias ni datos de la demo.

## Evidencia

- Baseline frontend:118 pruebas PASS. Final:136 PASS, incluidas18 del nuevo lector. El primer intento falló por módulo aún no implementado; después las tres regresiones de arrays como enums reprodujeron el defecto encontrado por revisión y pasaron tras exigir cadenas.
- Lint con cero avisos, typecheck y build frontend PASS. El primer lint detectó el anchor nativo; se documentó la excepción específica requerida por el flujo OIDC, sin desactivar reglas globales. El build final se usó como aplicación standalone para el recorrido local.
- Diez regresiones Playwright nuevas enumeradas y typechecked: dos presentaciones ×401/403/500, respuesta200malformada y respuesta tardía de otra empresa. La de respuesta tardía espera el fin de la respuesta antigua y dos frames de render antes de afirmar que no reaparece. **Ejecución automatizada de esas diez pruebas pendiente de CI**, no PASS local.
- Navegador CUA sobre build real y API sintética en loopback: colaA visible →401 elimina cola/métricas y ofrece Sign in again; enlace navega a la ruta real del proxy en fixture; bandeja completa403 elimina cola, reintento200 recupera; cambioA→B muestra únicamente tareaB. Capturas locales ignoradas en `artifacts/previews/2026-11-17-action-recovery/verified-*.png`.
- El fixture no usa secretos ni clientes y no modifica el producto: solo prueba la presentación. Su redirect de login es simulado; no acredita un nuevo login OIDC real ni aislamiento de DB. Servidores de prueba propios cerrados después del recorrido; la VM y los túneles previos no se tocaron.
- Revisor independiente solo lectura:133 unitarias y diffcheck PASS al revisar; encontró dosP2 (enums con coerción y aserción de carrera prematura), corregidos en una pasada. Sin P0/P1 identificados en ese alcance. No equivale a aprobación humana o revisión de todo el SaaS.
- Sin cambios de dependencias. Las seis reglas SAST actuales son Python y no cubren este TypeScript; no atribuirles un PASS de seguridad de este cambio. ESLint y CodeQL/CI conservan sus responsabilidades. Los seis HIGH conocidos de Keycloak siguen pendientes.

## Preservación, publicación y pendientes

CP-ACTION-RECOVERY-00-20261118T021932Z conserva732fuentes/Git y WIP anteriores, con restauración/hash/modos/bundle/decrypt/tamper verificados. No fue necesario modificar ni respaldar de nuevo la base de datos porque este slice solo cambia frontend. `apps/web/AGENTS.md`, generado por Next y preexistente, permanece preservado fuera del commit. `next-env.d.ts` volvió al contenido del HEAD al regenerar tipos; no se descartó manualmente.

Rama `codex/action-session-recovery`, base1672dd2/PR63. No merge ni despliegue a producción. **La demo pública aún conserva su imagen web anterior**; instalar este cambio requiere el siguiente paso de validación e integración de demo. No confundir las capturas del fixture con una actualización remota.

Auditorías ready/start quedan para un slice independiente: API y trigger solo permiten draft→planned/cancelled y planned→cancelled. Sus revisiones humanas se vinculan a la versión exacta del plan; una transición ingenua invalidaría esos dictámenes. Deben diseñarse versión congelada y validación atómica antes de activar esos comandos.

Publicado en [PR64](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/64), borrador contraPR63. CP-ACTION-RECOVERY-06-20261118T081525Z:737fuentes/Git restaurados conhashes/modos/bundle ydecrypt/tamperPASS. Commitlocaloriginalb8cd07f preservado yárbolpublicadoidéntico. No merge; CIexacto y10browserautomatizados pendientes.
