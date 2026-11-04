# CAPA — contrato funcional y estado de implementación

Estado: contrato técnico actualizado el 1 de noviembre de 2026. **El registro de
borradores CAPA con origen NCR/riesgo/otro, el análisis por método, el plan,
la ejecución, la revisión de eficacia, el cierre y la cancelación controlada
están implementados y probados**, junto con referencias directas a documentos,
implementaciones de control y evidencia aceptada. El módulo funcional sigue
incompleto por otras integraciones, reportes y aceptación UX. Este documento fija criterios verificables a partir del
addon Odoo; las partes pendientes siguen siendo propuestas técnicas. QMS completo
es producto base, no un addon comercial.

## Hito implementado: registro de borradores (0026)

- API y UI para crear, listar, leer y editar borradores. Código manual único por
  tenant, proceso activo, origen NCR/riesgo exclusivo o `other`, snapshot del
  código/estado del origen, dueño opcional, plazo y método de causa raíz.
- `capa.read/manage/review` son grants explícitos por unidad. `capa.review`
  está reservado para el flujo futuro. Para leer una CAPA vinculada se exige
  además `ncr.read` o `risks.read`; una revocación oculta el registro. RLS
  forzado, claves compuestas y trigger protegen scope, actor, snapshots e
  inmutabilidad del origen. En este primer hito el origen queda congelado desde
  la creación, incluso mientras el registro sigue en borrador; la fuente Odoo
  permite cambiarlo en `draft`, por lo que esta diferencia necesita revisión
  antes de declarar paridad.
- Ediciones con bloqueo y versión esperada; auditoría atómica con hash del
  enunciado. Sin transición fuera de `draft` en API ni base de datos. No hay
  acciones ni evaluaciones de eficacia todavía.
- PostgreSQL desechable: 158 pruebas del conjunto (4 nuevas CAPA), migración
  head→0008→head y bloqueo de downgrade con historial. OIDC/API/proxy local
  verificó creación desde NCR, permisos, versión, auditoría y revocación de
  lectura del origen. Build/lint/tipos web PASS. Falta aceptación visual con
  usuario real y pruebas del ciclo CAPA completo.

## Hito implementado: inicio y edición del análisis (0027)

- Transición controlada `draft → analysis` con método elegido y bloqueado. El
  servidor crea cinco respuestas de 5 Why, seis categorías Ishikawa o cuatro
  dimensiones “es/no es” con cuatro atributos cada una; `other` usa estructura
  vacía y nombre del método separado. API y PostgreSQL exigen claves exactas,
  texto acotado y versión esperada. La pantalla ofrece formularios por método.
- Borradores anteriores se conservan. La base rechaza saltos directos de estado,
  modificación del método y escritura del análisis sin el comando controlado.
  Resumen, causa verificada, nombre del método y respuestas se auditan como
  hashes. El estado `analysis` aún permite guardar hallazgos incompletos.
- PostgreSQL desechable: 165 pruebas PASS (7 nuevas, incluida respuesta UTF-8
  larga protegida por migración0028); OIDC/API/proxy local
  confirmó inicio 5 Why, edición, versión obsoleta, método bloqueado y auditoría.
  Web lint/tipos/build PASS. Captura sintética del formulario real en
  `artifacts/capa-analysis-demo.png`; falta aceptación UX de usuario real.
- **Límite histórico de 0027:** Ishikawa guardaba un texto por categoría. La
  migración0029 conserva esos valores sin reescribirlos; la UI los convierte en
  una causa sin confirmar al editar. El gate de avance quedó implementado en
  0030; falta validar la experiencia de usuario y el resto del ciclo CAPA.

## Hito implementado: causas Ishikawa confirmables (0029)

- Cada una de las seis categorías acepta hasta10 causas con enunciado, evidencia,
  fundamento y marca de confirmación. Una causa confirmada requiere los tres
  textos. API y PostgreSQL validan estructura exacta, límites, tamaños y
  confirmación. El servidor crea listas vacías para nuevos análisis; los textos
  guardados con0027 siguen legibles y se convierten a causa no confirmada en el
  editor, sin migración de datos ni pérdida de historial.
- La UI agrupa categorías plegables y muestra conteos de causas/confirmadas.
  Las ediciones siguen bajo bloqueo, versión esperada, RLS, permisos de unidad y
  auditoría atómica con hash del análisis. El downgrade se bloquea si ya existe
  análisis estructurado que el formato anterior no podría conservar.
- PostgreSQL desechable: **167 pruebas PASS**, incluida confirmación válida,
  sustitución de análisis histórico de texto por causas estructuradas, rechazo
  por API y SQL de una confirmación sin evidencia y bloqueo de downgrade
  con datos. OIDC/API/proxy local PASS para varias causas y rechazo422; permisos
  temporales revocados. Web lint/tipos/build y12 pruebas PASS. Captura visual
  sintética `artifacts/capa-fishbone-ui.png`; falta aceptación UX con usuario real.

## Hito implementado: inicio del plan de acciones (0030)

- `analysis → action_planned` exige resumen de investigación, causa verificada y
  los datos específicos del método: 5 Why con primera respuesta y secuencia sin
  saltos; Ishikawa con causa confirmada respaldada; Es/No-Es con observado, no
  observado y distinción en las cuatro dimensiones; o nombre del método alterno.
  El plan requiere un alcance escrito. La transición conserva actor y fecha y
  bloquea la investigación; aún no permite crear acciones individuales.
- API y PostgreSQL comprueban el mismo gate. La base rechaza avance directo,
  modificación simultánea de hallazgos o sellos falsos. Versión esperada,
  `capa.manage` por unidad y auditoría atómica `capa.plan_started` con hash del
  texto del plan. El downgrade se niega con plan o historial incompatible.
- PostgreSQL desechable: **171 pruebas PASS** (cuatro casos por método);
  migración head→0008→head PASS antes de datos. OIDC/API/proxy local verificó
  inicio del plan, actor, versión, bloqueo posterior y auditoría. Web
  lint/tipos/build y 12 pruebas PASS. Falta aceptación visual del nuevo
  formulario con usuario real.

## Hito implementado: registro de acciones (0031)

- Un plan admite acciones identificadas con título, descripción, responsable
  activo y fecha límite. Crear y editar exige `capa.manage`, estado
  `action_planned`, versión esperada del plan y, al editar, versión de la acción.
  La base bloquea eliminación, cambios de identidad, origen ajeno y escritura
  fuera del comando controlado. Cada cambio incrementa la versión del padre
  dentro de la misma transacción y registra auditoría de la acción con hashes
  del título y la descripción.
- RLS forzado y clave compuesta mantienen el mismo tenant y unidad; leer
  acciones pasa por la visibilidad del CAPA y su origen. UI con formulario de
  asignación, edición y páginas de 50. Por ahora las acciones nacen `open` y
  no tienen transición de ejecución o verificación; esa es la etapa siguiente.
- PostgreSQL desechable: **172 pruebas PASS**; migración reversible antes de
  datos y downgrade bloqueado con acciones/historial. OIDC/API/proxy local PASS
  para alta, listado, edición, versiones obsoletas, auditoría y revocación de
  lectura del origen. Web lint/tipos/build PASS. Falta aceptación UX real.

## Hito implementado: ejecución y verificación de acciones (0032)

- `action_planned → implementation` exige al menos una acción abierta y fija
  actor/fecha. Durante ejecución, las acciones pasan por
  `open → in_progress → completed → verified`; se puede completar directamente
  desde `open`. Cancelar una acción no terminal exige motivo. El plan, origen y
  datos de asignación quedan bloqueados desde el inicio de implementación.
- `capa.manage` ejecuta y completa; `capa.review` verifica o cancela. Quien
  completó una acción no puede verificarla. Notas de verificación y motivos
  son obligatorios y se auditan mediante hashes. RLS permite que un revisor
  con lectura y `capa.review`, sin `capa.manage`, haga la verificación.
- PostgreSQL desechable: **173 pruebas PASS**, incluida separación de funciones,
  versiones padre/acción y rechazo de SQL directo. OIDC/API/proxy local PASS
  con revisor distinto, permisos temporales revocados al terminar. Web
  lint/tipos/build PASS. Falta aceptación visual y revisión de eficacia.

## Hito implementado: entrada a revisión de eficacia (0033)

- `implementation → effectiveness_review` exige al menos una acción completada
  o verificada y ninguna acción activa abierta o en progreso. Se registra
  persona/fecha; las acciones quedan bloqueadas para decidir la eficacia sobre
  una ejecución estable. API y PostgreSQL aplican el mismo gate.
- PostgreSQL desechable: **173 pruebas PASS**; el caso de ejecución cubre
  rechazo con acción pendiente, bloqueo SQL, inicio válido y bloqueo posterior.
  OIDC/API/proxy local PASS y permisos temporales revocados. La decisión
  efectiva/inefectiva y el cierre se añadieron en 0034.

## Hito implementado: decisión de eficacia y cierre (0034)

- Cada evaluación de eficacia se guarda en una tabla de solo anexión con ciclo,
  decisión, notas, revisor, fechas y conteos de acciones. API y PostgreSQL exigen
  `capa.review`, notas no vacías y separación de cualquier persona que completó
  una acción. La evaluación y el cambio de estado se ejecutan en una transacción
  y se auditan con hash de las notas.
- Una decisión efectiva habilita el cierre con notas y sello de revisor; una
  decisión inefectiva conserva el ciclo anterior, vuelve a `action_planned` y
  exige una acción nueva antes de reiniciar la ejecución. Historial paginado y
  formularios de decisión/cierre en la UI. `closed` es terminal.
- PostgreSQL desechable: **174 pruebas PASS**, incluidos dos ciclos con resultado
  ineficaz seguido de eficaz, rechazo de un revisor implementador, historial
  preservado y cierre. OIDC/API/proxy local PASS para eficacia y cierre con
  revisor distinto; permisos temporales revocados. Web lint/tipos/build PASS.
  Falta aceptación visual y validación funcional completa contra Odoo.

## Hito implementado: cancelación formal (0035)

- Un revisor con `capa.review` puede cancelar un CAPA desde cualquier estado
  abierto hasta `effective`, con motivo obligatorio, actor y fecha. `closed` y
  `cancelled` son terminales. La base conserva los sellos de las etapas ya
  alcanzadas y rechaza cambios adicionales o cancelación por SQL sin el comando
  y permiso adecuados. La UI presenta el motivo y la fecha tras cancelar.
- PostgreSQL desechable: **175 pruebas PASS**, incluido rechazo de motivo vacío,
  doble cancelación y modificación SQL del terminal; migraciones head→0008→head
  y downgrade bloqueado con historial. OIDC/API/proxy local PASS al cancelar
  un CAPA real de prueba y comprobar auditoría. Web lint/tipos, 12 pruebas y
  build PASS; `make up` y health PASS. Falta aceptación UX con usuario real.

## Hito implementado: referencia externa del origen (0036)

- El registro acepta una referencia externa opcional de hasta 160 caracteres.
  Puede corregirse en borrador y queda congelada al iniciar el análisis. Se
  conserva junto al snapshot del origen, sin reemplazar la referencia interna
  obligatoria cuando el origen es NCR o riesgo. La auditoría guarda un hash del
  texto, no su contenido. La UI permite registrarla y muestra el valor al leer.
- PostgreSQL desechable: **176 pruebas PASS**, incluida edición de borrador,
  rechazo API y SQL tras iniciar análisis y auditoría hasheada; downgrade
  bloqueado con referencias existentes. OIDC/API/proxy local PASS con referencia
  externa en CAPA sintética; health PASS. Falta aceptación UX con usuario real.

## Hito implementado: comando de edición de borrador (0037)

- Toda actualización de un CAPA que permanece en `draft` requiere el comando
  controlado `edit` y `capa.manage`. La API lo fija dentro de la transacción al
  guardar; PostgreSQL rechaza una modificación directa del borrador aunque
  se suministren versión y fecha plausibles. Los comandos de transición siguen
  separados del de edición. El downgrade se bloquea si existen CAPA o eventos
  de auditoría del módulo.
- PostgreSQL desechable: **176 pruebas PASS**, incluido rechazo de edición SQL
  de borrador sin comando; migración head→0008→head y downgrade bloqueado con
  historia de negocio. El ciclo OIDC/API/proxy se repitió tras el despliegue
  local de 0037.
- Los comandos de sesión son una frontera de confianza de la API: el rol de
  aplicación que ejecutara SQL arbitrario también podría fijarlos. RLS y
  capacidades limitan el alcance, pero este control no reemplaza prevención
  de inyección SQL ni una prueba de seguridad autenticada.

## Alcance funcional confirmado en la fuente Odoo

- Registro por empresa/organización/proceso con código, nombre, problema, dueño,
  fecha objetivo y método de causa raíz. El origen puede ser NCR, riesgo u otro
  tipo. Si el origen es NCR o riesgo, exactamente esa referencia es obligatoria;
  la otra debe estar vacía. Las referencias deben pertenecer a la misma empresa y
  organización. En el SaaS esto se traducirá a tenant y unidad, con claves
  compuestas y RLS. El proceso de origen puede ser distinto dentro de la unidad.
- El origen y su referencia quedan bloqueados tras `draft`; el método de causa
  raíz también queda bloqueado al iniciar el análisis. El nombre, problema y
  origen deben estar completos para pasar a `analysis`.
- Métodos: `5why`, `fishbone`, `is_is_not`, `other`. `5why` crea cinco casillas
  fijas exactamente una vez; para planificar se exige respuesta 1 y respuestas
  contiguas hasta la última utilizada. `fishbone` usa seis categorías fijas;
  requiere una causa confirmada con fundamento de evidencia y motivo. `is_is_not`
  crea cuatro dimensiones fijas (qué, dónde, cuándo y alcance), cada una con
  observado, no observado y distinción; cambio es opcional. `other` exige nombre
  del método. Todos exigen análisis resumido y causa raíz verificada antes de
  `action_planned`. Los textos de ayuda PMC serán originales.
- Acciones CAPA con título, descripción, dueño, plazo, fecha de finalización,
  estado `open/in_progress/completed/verified/cancelled` y notas de verificación.
  Se exige al menos una para iniciar `implementation`. Solo acciones activas
  completadas o verificadas permiten terminarla. Una acción iniciada no se
  elimina; verificación y cancelación tienen autoridad de revisión explícita.
- Flujo: `draft → analysis → action_planned → implementation →
  effectiveness_review → effective → closed`; una evaluación `ineffective`
  se conserva como evento y permite volver a `action_planned` para agregar o
  corregir acciones. No se cierra un resultado ineficaz. La revisión de eficacia
  exige notas cuando se marca efectiva o ineficaz. Los resultados previos no se
  sobrescriben. Cancelación mediante transición autorizada.

## Contrato de implementación para el SaaS

1. Incorporar `capa.read/manage/review` como permisos explícitos por unidad;
   seat, owner de tenant y asignación como dueño no otorgan aprobación. Crear
   desde NCR/riesgo requiere permiso de lectura del origen además de CAPA.
   Como control adicional del SaaS, el revisor de eficacia será una persona
   distinta de quien implementó la acción; esta separación no se deduce de las
   transiciones del modelo Odoo y deberá especificarse en el producto.
2. Representar CAPA, acciones, casillas de análisis y revisiones de eficacia
   con identidad tenant/unidad/proceso. Usar FK compuestas, RLS forzado,
   snapshots del código/estado de origen y rechazo de referencias ajenas,
   inactivas o inexistentes. Permitir fuente histórica cerrada de la misma unidad
   cuando se justifique; conservar referencia aun si cambia su estado.
3. Toda mutación exige versión esperada y bloqueo del padre; transiciones y
   condiciones previas se comprueban en API **y base de datos**. El cierre es
   terminal. Las acciones y análisis no se pueden mutar por SQL directo para
   saltar el flujo. No borrar historial de ineficacia o acciones completadas.
4. Auditoría atómica con actor, decisión, fecha, versión y request ID. Los
   enunciados, análisis, causas, respuestas, decisiones y notas narrativas se
   registran mediante hashes; no exponer resúmenes privados en listados de otros
   módulos, logs, URLs o eventos. Vincular documentación solo mediante revisión
   liberada, limpia y autorizada; nunca aceptar claves S3 ni adjuntos directos.
5. UI por etapas: registro/origen, análisis guiado, plan y acciones, ejecución,
   verificación de eficacia e historial. Mostrar estado y responsables claramente;
   búsquedas paginadas y estados de acceso revocado, conflicto de versión y
   validación incompleta sin pérdida silenciosa de datos.

## Evidencia implementada en la migración 0038

- Una CAPA en borrador, análisis, plan o implementación puede citar una revisión
  documental activa, liberada y con archivo limpio dentro de la misma unidad.
- El vínculo conserva código, nombre, revisión, versión y SHA-256 del archivo. Su
  retiro es lógico, requiere motivo y mantiene el registro visible y auditable.
- RLS exige lectura de CAPA y documentos; crear o retirar exige además
  `capa.manage`. El padre se bloquea y versiona en cada operación.
- PostgreSQL rechaza escrituras directas sin comando controlado, snapshots
  alterados, archivos inseguros, revisiones no liberadas y cambios desde revisión
  de eficacia. El downgrade se detiene si existe historia.
- La UI permite buscar documentos, seleccionar revisiones limpias/liberadas,
  paginar, reintentar errores y retirar con explicación. El E2E local comprobó
  OIDC, proxy web, PDF analizado, liberación independiente, auditoría y limpieza.

## Evidencia implementada en la migración 0039

- Una CAPA en borrador, análisis, plan o implementación puede vincular directamente
  implementaciones activas y evidencia aceptada independientemente dentro de la
  misma unidad. La selección de evidencia parte de su implementación para mantener
  visible la relación operativa.
- Cada vínculo conserva código, nombre y versión del objetivo. Su retiro es lógico,
  exige la versión esperada del CAPA y del vínculo, requiere una explicación y
  conserva snapshots e historial de auditoría.
- RLS exige `capa.read` y `control_instances.read`; crear o retirar exige además
  `capa.manage`. El asiento o rol del tenant no concede estas capacidades. El CAPA
  se bloquea y aumenta su versión en cada alta o retiro.
- PostgreSQL rechaza objetivos de otra unidad, implementaciones inactivas, evidencia
  no aceptada, snapshots alterados, escritura directa sin comando y cambios desde
  revisión de eficacia. El downgrade se detiene cuando existe historia.
- La UI separa trazabilidad directa de la heredada, permite buscar implementaciones,
  elegir evidencia aceptada, consultar estados actuales y retirar con motivo.
  PostgreSQL desechable: **183 pruebas PASS**; Ruff y mypy PASS. Web lint, tipos y
  **21 pruebas PASS**. Falta el recorrido OIDC/proxy y la aceptación UX final tras
  desplegar esta migración.

## Trazabilidad heredada de la fuente

La interfaz CAPA consulta las relaciones activas de la NCR o riesgo registrado como
origen y presenta las implementaciones de control y, cuando el origen es una NCR, la
evidencia aceptada relacionada. Las consultas reutilizan los endpoints protegidos de
la fuente, por lo que no amplían autoridad ni duplican snapshots. Esta vista es
trazabilidad derivada de solo lectura. Se mantiene separada de los vínculos CAPA
directos, versionados y retirables implementados en 0039.

## Pruebas de aceptación pendientes antes de declarar paridad funcional

- PostgreSQL desechable: RLS entre tenants/unidades, auditor solo lectura,
  fuentes mutuamente excluyentes, origen congelado, estructura fija de `5why`
  e `is_is_not`, gates de análisis/acciones/eficacia y bloqueo SQL directo.
- Concurrencia: edición frente a transición, finalización de acción frente a
  cierre de implementación y reapertura tras resultado ineficaz; versiones
  obsoletas deben devolver conflicto sin perder historial.
- Dos sesiones OIDC con permisos diferentes: autor, responsable de acción y
  revisor de eficacia. Rechazar auto-revisión, owner sin grant, revocación de
  acceso al origen y referencias fuera de unidad. Verificar proxy web y auditoría.
- Recorrido visual del ciclo completo y de resultados ineficaces. Downgrade de
  migraciones con historial auditado debe fallar antes de destruir datos.

## Fuentes originales consultadas

- [Modelo y transiciones CAPA](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/blob/main/addons/pm_qms_capa/models/capa.py)
- [Acciones CAPA](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/blob/main/addons/pm_qms_capa/models/capa_action.py)
- [Análisis 5 Why](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/blob/main/addons/pm_qms_capa/models/capa_why.py)
- [Análisis Fishbone](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/blob/main/addons/pm_qms_capa/models/capa_fishbone.py)
- [Análisis Is / Is Not](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/blob/main/addons/pm_qms_capa/models/capa_is_is_not.py)
- [Pruebas Odoo CAPA](https://github.com/Perfect-Match-Systems/Perfect-Match-QMS2026/blob/main/addons/pm_qms_capa/tests/test_capa.py)
