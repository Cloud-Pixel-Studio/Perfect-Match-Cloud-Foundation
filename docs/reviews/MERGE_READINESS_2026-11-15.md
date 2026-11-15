# Auditoría de ramas y preparación de merge

Verificado: **2026-11-15T07:55:22-05:00 (America/New_York)**. Repositorio oficial Perfect-Match-Cloud-Foundation.

**Resultado: 0 PR listos para merge.** 47 ramas remotas, 36 PR abiertos; 35 drafts y PR13 listo para revisión pero bloqueado. No se fusionó, cerró, rebasó ni desplegó ninguna rama. La aprobación humana antes de merge se conserva.

Calidad: **33 PASS / 3 FAIL**. CodeQL: **35 PASS / 1 sin evidencia devuelta**. Security: **35 FAIL / 1 en curso**. No se devolvieron reviews APPROVED; hay **7 hilos sin resolver**. Un análisis CodeQL exitoso puede generar alertas: no equivale a triage cerrado.

Los 36 `git merge-tree --write-tree` terminaron 0 contra sus bases actuales, sin modificar checkout/refs. Esto prueba combinabilidad textual individual, no integración funcional, disponibilidad comercial ni validez de la combinación de todas las ramas. Una lectura inicial de GitHub mostró mergeability transitoria para PR52; reconsulta y simulación actual no reproducen conflicto.

## Bloqueos que requieren acción

- **PR13**: falla regresión visual y gate de seguridad.4 hilos abiertos: 1 P1 de reemplazo documental y 3 P2 del Centro de Acciones. El P1 tiene corrección y regresiones en PR47, todavía no integradas en PR13; los otros hilos necesitan revisión contra el head que se proponga entregar.
- **PR22**: Ruff detecta 2 archivos sin formato (`document_control.py` y su test). PR23 contiene el arreglo separado; no atribuir sus checks al head22.
- **PR43**: 2 alertas CodeQL sobre escritura de datos de red a archivos del harness. Requieren triage documentado; no se declara exposición ni falso positivo confirmado.
- **PR48**: Trivy filesystem falla y la generación de evidencia queda incompleta. No se devolvió corrida CodeQL para su head actual; no contarlo como PASS.
- **PR49**: Gitleaks falla; fallos posteriores de imágenes/SBOM son consecuentes a la interrupción anterior. Distinguir alerta de secreto real de falso positivo antes de remediar. Branding/marketing permanecen drafts separados.
- **PR50**: 1 alerta CodeQL sobre logging de datos sensibles. La línea revisada imprime contadores numéricos de findings, no Match ni valores; es candidata a falso positivo, pero falta triage independiente y cierre. Gate de seguridad sigue rojo.
- **PR51**: error de parseo de TypeScript en `apps/web/src/lib/dashboard-metrics.test.ts:18`, además de seguridad. Su body dice design-only; el head incorpora helpers/tests y se evalúa el código real.
- **PR52**: falla prueba de meses válidos. La expresión regular contiene `\\d` donde se esperan dígitos; `2026-01` se rechaza. También falla seguridad. El arreglo debe conservar el test y no cambiar el dato válido para hacer pasar la prueba.
- **PR53**: CI de seguridad aún en curso al corte; calidad y CodeQL PASS. Bootstrap del runtime candidato ya pasó en el job consultado. No asignar todavía cero CVE ni autorizar actualización de volúmenes reales.

## Inventario 1 a 1 de PR abiertos

PASS/FAIL se refiere al workflow devuelto para el **head exacto** indicado en el JSON. No se ejecutaron nuevamente todas las suites durante esta auditoría. Todos continúan bloqueados por al menos seguridad/CI incompleto y revisión requerida.

|PR / cambio|Rama base|Calidad|CodeQL|Security|Hilos pendientes|
|---|---|---|---|---|---|
|[13 — Establish secure multi-tenant QMS foundation](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/13)|`main`|PASS|PASS|FAIL|4|
|[19 — Integrate merged PR #15–#17 features back into QMS foundation (#13)](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/19)|PR13|PASS|PASS|FAIL|0|
|[20 — chore(agents): configure bounded Codex specialists and validate manifests](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/20)|PR19|PASS|PASS|FAIL|0|
|[21 — security(config): reject insecure public endpoints in production](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/21)|PR19|PASS|PASS|FAIL|0|
|[22 — chore(agents): UX/reliability specialists and external tooling evaluation](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/22)|PR20|FAIL|PASS|FAIL|0|
|[23 — style(ci): fix Ruff formatting in PMC-05 revision files](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/23)|PR22|PASS|PASS|FAIL|0|
|[24 — security(ci): generate deterministic CVE inventory from Trivy JSON](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/24)|PR23|PASS|PASS|FAIL|0|
|[25 — feat(web): present the QMS product with real workflows and a demo brief](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/25)|PR19|PASS|PASS|FAIL|0|
|[26 — fix(documents): recover creation references and accessible pagination](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/26)|PR25|PASS|PASS|FAIL|0|
|[27 — fix(documents): retain drafts and safely recover denied or conflicting actions](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/27)|PR26|PASS|PASS|FAIL|0|
|[28 — fix(security): prevent stale or partially written Trivy CVE evidence](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/28)|PR24|PASS|PASS|FAIL|0|
|[29 — fix(security): fail closed when Trivy scan target is absent](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/29)|PR28|PASS|PASS|FAIL|0|
|[30 — Connect nonconformities and risks to their corrective actions](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/30)|PR27|PASS|PASS|FAIL|0|
|[31 — Add internal audit programs and planning workspace](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/31)|PR30|PASS|PASS|FAIL|0|
|[32 — Add controlled, process-linked scope to internal-audit planning](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/32)|PR31|PASS|PASS|FAIL|0|
|[33 — Add controlled audit criteria and protect linked scope history](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/33)|PR32|PASS|PASS|FAIL|0|
|[34 — Add versioned audit planning team without implied execution access](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/34)|PR33|PASS|PASS|FAIL|0|
|[35 — Audit agenda: UTC scheduling, participant guards and recoverable history](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/35)|PR34|PASS|PASS|FAIL|0|
|[36 — Audit independence: immutable assessments and conservative preparation checks](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/36)|PR35|PASS|PASS|FAIL|0|
|[37 — Verify planned auditors’ scoped execution access](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/37)|PR36|PASS|PASS|FAIL|0|
|[38 — Organize audit detail into accessible focused views](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/38)|PR37|PASS|PASS|FAIL|0|
|[39 — Record audit-specific competence assessments with controlled evidence](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/39)|PR38|PASS|PASS|FAIL|0|
|[40 — docs: audit QMS access, company setup and Odoo option parity](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/40)|PR39|PASS|PASS|FAIL|0|
|[41 — fix: block suspended company access in API and PostgreSQL](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/41)|PR40|PASS|PASS|FAIL|0|
|[42 — Auditoría independiente de arquitectura, accesos y alcance SaaS](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/42)|PR41|PASS|PASS|FAIL|0|
|[43 — Auditoría independiente del recorrido comercial y de calidad](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/43)|PR41|PASS|PASS|FAIL|2|
|[44 — Historial completo y filtrable de responsabilidades QMS por empresa](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/44)|PR41|PASS|PASS|FAIL|0|
|[45 — Auditoría de operabilidad: evidencia por módulo y fallo del revisor documental](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/45)|PR41|PASS|PASS|FAIL|0|
|[46 — fix(web): announce QMS access history pagination accessibly](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/46)|PR44|PASS|PASS|FAIL|0|
|[47 — Corrige revisión documental mínima y sustitución atómica de versiones](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/47)|PR44|PASS|PASS|FAIL|0|
|[48 — brand: BEMS Quality identity, SVG assets and web-shell preview](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/48)|`main`|PASS|SIN EVIDENCIA|FAIL|0|
|[49 — brand: adapt existing product marketing site to BEMS Quality](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/49)|PR25|PASS|PASS|FAIL|0|
|[50 — Bind six-image security evidence and enforce production URL settings](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/50)|PR47|PASS|PASS|FAIL|1|
|[51 — design: BEMS Quality dashboard KPI and analytics proposal](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/51)|PR25|FAIL|PASS|FAIL|0|
|[52 — feat(kpi): guard ratio denominators and missing trend observations](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/52)|PR51|FAIL|PASS|FAIL|0|
|[53 — Evaluate pinned stable Keycloak 26.8.2 and SeaweedFS 4.53 in isolated CI](https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/53)|PR50|PASS|PASS|EN CURSO|0|

## Dependencias y duplicación

Cadena principal actual: `main ←13 ←19 ←25 ←26 ←27 ←30 ←31 ←32 ←33 ←34 ←35 ←36 ←37 ←38 ←39 ←40 ←41 ←44 ←47 ←50 ←53`. La flecha significa que el PR de la derecha apunta a la rama del anterior; no es una orden para fusionar todo sin validación.

Ramas laterales:20→19,21→19,22→20,23→22,24→23,28→24,29→28;42/43/45→41;46→44;49/51→25;52→51;48→main. Cada base exacta está en JSON.

PR21 y24/28/29 aportan trabajo reutilizado y ampliado en PR50. No volver a mezclar bases antiguas solo para cerrar esos PR: comparar diferencias residuales y proponer cierre por sustitución cuando un mantenedor lo apruebe. PR23 es un fix específico del head22, no prueba de que22 ya lo incorpore.

Las ramas con seis módulos PMC iniciales ya son ancestros de main; Design Studio/auditoría foundation/visual están en19 y sus descendientes, pero todavía no en main. WIP recovery conserva0041 no validada; no es una entrega candidata.

|Rama sin PR abierto|Situación comprobada|
|---|---|
|`codex/ai-design-studio`|already in PR19 and later ancestors; not in main|
|`codex/internal-audit-foundation`|already in PR19 and later ancestors; not in main|
|`codex/visual-completion`|already in PR19 and later ancestors; not in main|
|`codex/wip-audit-scope-recovery`|WIP recovery; no open PR, no validated delivery|
|`main`|base|
|`pmc/00-4-main-governance-enforcement`|already in main|
|`pmc/00-local-foundation`|already in main|
|`pmc/01-identity-multitenancy`|already in main|
|`pmc/02-audit-engine`|already in main|
|`pmc/03-organization-structure`|already in main|
|`pmc/04-workflow-engine`|already in main|

## Secuencia recomendada

1. Corregir los errores de calidad22/51/52 y hacer triage de Trivy/Gitleaks48/49/51/52 y de los 7 hilos. No silenciar scanners ni relajar HIGH/CRITICAL.
2. Terminar evaluación53 y verificar artefactos por SHA/digest/run. Propagar arreglos de47/50 y vendor aceptado a una candidata de integración preservando todas las ramas; no afirmar arreglado13 por existir47 separado.
3. Reconciliar branding48/49 y KPI51/52 con la candidata actual sin importar código antiguo innecesario. No publicar KPI conceptual como indicador real.
4. Repetir CI sobre la combinación exacta, revisar cambios y migraciones, comprobar respaldo/rollback y obtener aprobación independiente/humana. Integrar por dependencias con gates verdes; no merge masivo.
5. Main/prod conservan NO GO hasta seguridad, staging, operación/recuperación y alcance comercial aceptados. Un merge a rama de desarrollo y una salida comercial son decisiones distintas; este corte no autoriza ninguno.

## Evidencia y límites

Las URLs/IDs de runs, SHA de head/base, resultados de merge-tree y metadatos mínimos de revisión están en el JSON adjunto. Logs completos se guardan fuera de Git con0600; no se publican posibles valores sensibles ni se añaden allowlists. Las protecciones/rulesets del servidor y todas las alertas globales de Code Scanning no se enumeraron:0aprobaciones observadas se refiere a reviews devueltos por PR. Se inspeccionaron los hilos y los fallos concretos descritos; esta revisión de readiness no sustituye una revisión manual de cada línea de todos los PR ni aceptación funcional integral.

CP-MERGE-READINESS-00-20261115T125325Z:537 fuentes/Git cifrados fuera del árbol y restaurados por SHA256 / bundle verify PASS antes de escribir este informe. Se conserva el runtime y las DB reales; solo se actualiza documentación en rama de auditoría dedicada.

Checkpoint del informe: CP-MERGE-READINESS-06-20261115T125637Z; restauración cifrada de539 fuentes y Git verificada. Contadores/partición del inventario y Gitleaks del árbol PASS. No añade pruebas funcionales nuevas. Esta rama documental se crea después del corte y queda excluida de los36 PR evaluados.
