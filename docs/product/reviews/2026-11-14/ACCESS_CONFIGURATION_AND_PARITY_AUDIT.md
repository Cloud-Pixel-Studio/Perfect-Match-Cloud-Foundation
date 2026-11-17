# Estado, accesos, configuración y paridad de Perfect Match QMS

Cierre: 14 de noviembre de 2026 UTC / Nueva York. Inicio y checkpoint: 13 de noviembre local.
Estado: auditoría, sin cambios de permisos, datos de clientes, producción ni interfaz.
Producto verificado: SaaS PR39, `f8562540773e4d7294ff09b5abc603aa80add027`, DB0048.
GitHub PR39 sigue abierto, borrador y sin fusionar. El código local0049 es WIP no activado.
Referencia funcional: Odoo `d89330cc1a8e9a2ea16992c9b49394f1dc481b7f`, misma punta actual de main consultada en GitHub.

## 1. Dónde estamos

Tenemos una aplicación propia con aislamiento empresarial, identidad OIDC,
estructura organizativa, responsabilidades explícitas, procesos, documentos y
revisiones controladas, controles/actividades/evidencia, riesgos, NCR, CAPA,
Centro de Acciones y bitácora. La web comercial, marca y temas visuales existen.
Esto no equivale a QMS completo, producto listo para producción ni certificación.

En auditorías internas funcionan programas, planificación, alcance, criterios,
equipo, agenda UTC, revisión de independencia, diagnóstico de autoridad y
evaluación de competencia específica del auditor. Faltan preparar formalmente la
ejecución, iniciar, evidencias, hallazgos, hallazgo→NCR, reporting y cierre.
Los botones locales Ready/Start están en un borrador sin backend0049 ni pruebas:
no cuentan como disponibles y no se activaron durante esta revisión.

Siguen pendientes verticales de KPI, revisión por dirección, personas/formación,
calibración, calidad cliente/proveedor, costos de calidad, importación general,
perfil ISO y licencia/suscripción comercial. La evaluación puntual del auditor
no sustituye People & Competency. Los módulos QMS son parte del producto base;
los addons comerciales previstos son las normas/ediciones ISO.

## 2. Qué significan las secciones confusas

| Nombre actual | Qué hace realmente | Ejemplo | Ubicación recomendada, no implementada |
| --- | --- | --- | --- |
| Workflows | Plantillas versionadas de pasos, responsables y transiciones; instancias que ejecutan una versión publicada | Una solicitud interna pasa de revisión a autorización y finalización | El constructor en Configuración de empresa → Flujos de trabajo; al usuario operativo sus tareas en Centro de Acciones |
| Permissions | Responsabilidades QMS explícitas por persona y unidad; consulta de accesos propios para los demás roles | María puede leer documentos de Sede Norte; Luis puede aprobar allí | Mis accesos en perfil/Mi trabajo; administración de responsabilidades en Configuración, solo owner actual |
| Audit trail | Bitácora técnica de quién cambió qué y cuándo; lectura, sin borrar ni modificar historia | Se registra quién aprobó una revisión o retiró un permiso | Trazabilidad / Registro de cambios, con permiso específico a diseñar |
| Internal audits | Programa y expedientes de auditoría de calidad | Planificar auditoría de compras, criterios, equipo y agenda | Calidad → Auditorías internas |
| Organization | Sedes/departamentos/equipos y asignaciones de miembros ya existentes | La empresa tiene una sede y dos departamentos | Configuración de empresa → Estructura |

Workflows NO es actualmente el configurador de las aprobaciones de documentos,
NCR o CAPA. Esos módulos tienen sus propios comandos y reglas. La referencia de
una instancia genérica es texto libre, no una relación gobernada con QMS.
Un paso de tipo approval no añade por sí solo firma, validación documental ni
separación autor/aprobador. Una transición genérica no libera documentos.

## 3. Roles y autorizaciones actuales

Una empresa es un tenant independiente. Sedes, departamentos y equipos son
unidades dentro de esa empresa. Cambiar de empresa no mezcla registros ni
convierte dos empresas en una suscripción. Un seat habilita participación
comercial futura; no otorga automáticamente responsabilidad QMS.

| Acción | Owner de empresa | Admin de empresa | Member | Auditor (rol técnico actual) |
| --- | --- | --- | --- | --- |
| Ver Mis accesos | Sí | Sí, solo propios | Sí, propios | Sí, propios |
| Conceder/revocar responsabilidad QMS ajena | Sí; no a sí mismo | No | No | No |
| Configurar estructura/asignaciones | Sí | Sí | No | No |
| Leer estructura/directorio por API | Sí | Sí | Sí, aunque Organization se oculta en menú | Sí |
| Leer bitácora técnica de toda la empresa | Sí | Sí | No | Sí, aunque carezca de grants QMS |
| Ver catálogo/instancias/historia Workflows | Sí | Sí | Sí, ámbito empresarial | Sí, ámbito empresarial |
| Crear/publicar/iniciar/cancelar Workflows | Sí | Sí | No | No |
| Ejecutar un paso Workflow | Solo si está asignado | Solo si está asignado | Solo si está asignado | No, aunque lo asignen |
| Operar módulos QMS | Solo con grants explícitos por unidad | Solo con grants explícitos por unidad | Solo con grants explícitos por unidad | Lectura explícita; excepción audits.execute, sin pantalla disponible en0048 |

El rol auditor técnico no debe confundirse con una asignación de auditor interno
en un expediente. Ser líder de una unidad o responsable de un proceso no eleva
al usuario a owner/admin. No existe una consola platform_admin comercial en
esta navegación; el admin de una empresa no administra todas las empresas.

Los permisos efectivos se revalidan en API y PostgreSQL; ocultar un enlace no
es una medida suficiente. Los grants son de unidad exacta, sin comodines ni
herencia implícita de la sede padre. La navegación usa familias de capabilities
para reducir opciones, pero no representa por sí sola todo el contexto.

## 4. Hallazgos y acciones recomendadas

P2 aquí significa prioridad media dentro de esta revisión de ingeniería, sin
CVSS ni certificación de riesgo. No se detectó ni se afirma un escape entre
empresas. Una política de lectura amplia dentro de una empresa requiere una
decisión de producto; no se debe etiquetar automáticamente como explotación.

| ID | Prioridad / naturaleza | Hallazgo | Evidencia / medida recomendada |
| --- | --- | --- | --- |
| A01 | P2 seguridad | Suspensión empresarial incompleta para sesiones seleccionadas: organización, workflows y bitácora no comprueban todos Tenant.status | `organization_service.py:23`, `workflow_service.py:36`, `auth.py:68`; RLS0003/0004/0005. Cerrar actor y RLS de manera coherente, con regresión de sesiones vigentes. Reproducción HTTP sintética confirma lectura/edición de estructura y lectura de bitácora después de deshabilitar; reproducción de servicio/RLS confirma inicio de workflow. |
| A02 | P2 operativo | Grants de acceso limitados a100; la paginación visual solo recorre ese subconjunto | `qms_access.py:213`, `qms-access-workspace.tsx:88`. Añadir paginación/búsqueda de servidor y permitir encontrar todos los grants activos para revocación. |
| A03 | P2 política / minimización | Todos los miembros pueden consultar estructura, nombres, roles y asignaciones del tenant; Mis accesos carga también directorio empresarial | `organization.py:287`, UI QMSAccess:57. Reducir consultas de Mis accesos y diseñar directorios mínimos de selección por caso; no romper pickers operativos. |
| A04 | P2 política / alcance | Rol auditor ve bitácora de toda la empresa sin separación por unidad/capability QMS | `audit.py:76`, RLS0003:48. Separar auditor interno de calidad de auditor de seguridad y definir permiso de lectura de trazabilidad. |
| A05 | P2 operativo | Se permite configurar/publicar un paso cuyo único ejecutor es un usuario con rol auditor; ejecución lo rechaza | `workflow_service.py:479,591,678`, UI:219. Validar elegibilidad real del responsable antes de publicar; reproducción de servicio/RLS confirma publicación y rechazo403 al ejecutor. |
| A06 | P2 defensa en profundidad | La política UPDATE de workflow_instances no reproduce en SQL todas las reglas de actor, transición y versión que valida la API | RLS0005:319. Usuarios HTTP no reciben credenciales SQL; no se demuestra bypass HTTP. Incorporar protección SQL de comandos, versiones y eventos antes de prometer misma profundidad que dominios QMS nuevos. |
| A07 | P2 arranque comercial | No hay invitación/alta de empresa o segundo owner; owner único no puede autoconcederse grants | Bootstrap local es development-only y no onboarding. Diseñar alta controlada/dual sin eliminar la prohibición de self-grant. |
| A08 | P3 UX | Permissions aparece en Administration para todos; Workflows mezcla constructor y tareas y llama read-only al member que sí puede ejecutar | Separar Mis accesos, Mis tareas y Configuración. Nombres descriptivos: Flujos de trabajo y Registro de cambios. |
| A09 | P3 UX/fiabilidad | Workflows tiene listas/historia limitadas a100; editor parcial; error incierto dice que no se guardó y puede mantener datos viejos | Incorporar paginación, limpieza/reconciliación y mensajes que no inviten a repetir una operación de resultado desconocido. |
| A11 | P3 higiene HTTP | Respuesta API directa de bitácora no declara Cache-Control private,no-store | Observado en reproducción HTTP; el proxy reenvía cabeceras upstream. No prueba que un navegador o proxy concreto la almacenara. Añadir y verificar política coherente de caché. |
| A10 | P3 funcional | API de controles soporta evidencia requerida/no aplicable, pero UI solo avanza por camino principal | `controls-workspace.tsx:248`. Completar decisiones explícitas y justificación, preservando reglas API/DB. |

No se cambió ninguna política de acceso durante esta auditoría. Para A03/A04,
falta definir qué lectura departamental necesita el cliente y cómo se concede;
la propuesta no equivale a permiso nuevo ni a aprobación del usuario.

## 5. Qué configura una empresa y qué pertenece a la plataforma

| Ámbito | Configuración / operación prevista | Estado real |
| --- | --- | --- |
| Perfil de empresa | Nombre comercial/legal, datos y alcance del sistema | Empresa seleccionable; edición comercial completa pendiente |
| Estructura empresarial | Sedes, departamentos, equipos y asignaciones | Implementado; owner/admin editan |
| Personas y accesos | Invitaciones, membresías, responsabilidades por unidad | Grants implementados; invitaciones y administración de membresías pendientes |
| Procesos/documentos/controles | Responsables, contenido, requisitos, revisiones y decisiones autorizadas | Implementado por dominio/estado; no todos los casos Odoo completos |
| Flujos de trabajo | Definir pasos/responsables, validar, publicar nuevas versiones | Implementado con brechas descritas; nunca editar versiones ya publicadas |
| Configuración de calidad futura | Matrices de competencia, catálogos de equipos, KPI y periodicidades | Verticales pendientes; no mostrar botones como funcionales |
| Suscripción propia | Consultar/solicitar plan, seats e ISO de ESA empresa | Pendiente de implementación comercial |
| Plataforma Perfect Match | Aprovisionar/suspender empresas, catálogo global, planes/precios, soporte autorizado, observabilidad | Operación del proveedor; no debe exponerse al admin del cliente |
| Seguridad e infraestructura | Claves, secretos, DB, backups, antivirus, storage, despliegues, configuración OIDC y agentes | Solo operador autorizado; fuera de la configuración normal del cliente |

No son interruptores configurables para un usuario: aislamiento entre empresas,
validación de permisos, CSRF, escaneo de archivos, integridad de hashes,
prohibición de alterar historia, separación de aprobación exigida por cada
dominio y límites de la licencia. Los cambios de esas reglas requieren versión
de producto, revisión de seguridad y pruebas. Tampoco se permite que cada empresa
modifique el catálogo global de normas o marque una certificación como obtenida.

## 6. Empezar un QMS desde cero

Tres recorridos de producto distintos, sin borrar trabajo existente:

1. **Construcción manual, parcialmente posible hoy tras aprovisionamiento.**
   Crear empresa/membresías mediante alta controlada (falta UX comercial), definir
   alcance/sedes, habilitar responsables, crear procesos, elaborar documentos,
   configurar controles y requisitos, aportar evidencia y usar revisores
   independientes. Después operar riesgos/NCR/CAPA y planificar auditorías.
   Las verticales pendientes impiden describirlo como QMS completo terminado.
2. **Implementación guiada por norma/sector, pendiente.** Un asistente recoge
   contexto, alcance, procesos y objetivos; solo un pack revisado y con derechos
   contratados genera un proyecto, actividades y evidencia esperada. Revisión
   humana de aplicabilidad, responsables, hitos, brechas y preparación. No debe
   inventar documentos aprobados ni reutilizar automáticamente datos demo.
3. **Migración de un sistema existente, pendiente.** Importar registros y archivos
   con validación, relaciones, responsables, trazabilidad y reconciliación. Una
   importación no convierte archivos en revisiones aprobadas ni transfiere por
   sí sola firmas o vigencia de otro sistema.

El asistente comercial debe resolver el primer owner/segundo autorizador sin
autoconceder permisos; crear empresa y miembros antes de ofrecer catálogos que
exijan esos contextos. No exigir un workflow genérico para aprobar el primer
documento: el módulo documental ya tiene su aprobación controlada.

La idea de plan básico del usuario es1 empresa + 3 seats + 1 addon ISO. No se confirmó
precio ni edición normativa ni se implementaron sus límites. Sedes dentro de
la misma empresa son unidades; una segunda empresa es otro espacio/suscripción
según la regla comercial que se implemente, sin mezcla de datos.

## 7. Conteo Odoo frente a SaaS

Leer `ODOO_SAAS_OPTION_BY_OPTION.md` para todas las filas numeradas y
`OPTION-INVENTORY.json` para fuentes, métodos, ubicaciones y apariciones XML.

- 20 addons funcionales de Odoo; los directorios AI/Portal sin implementación se excluyen.
- 109 IDs de menú tras overrides:83 entradas con acción activas,23 agrupadores,3 desactivadas.
- De83 entradas activas:6 tienen entrada operativa comparable,15 adaptación parcial,62 sin equivalente entregado.
- 249 botones de negocio únicos por modelo+método, derivados de261 apariciones XML;5 cancelaciones especiales excluidas.
- De249:51 acciones comparables presentes;19 parciales;2 WIP no disponibles;177 sin equivalente entregado.

Los menús y botones se solapan: NO sumarlos. Un botón de navegación no equivale
a una vertical completa. Los CRUD genéricos, campos, filtros, métodos no
expuestos como botón, herencia resuelta en runtime y aceptación funcional están
fuera del conteo. Por eso estos números no son un porcentaje de producto
terminado ni una verificación exhaustiva de cada requisito de paridad.

La clasificación histórica de20 bloques sigue siendo11con contraparte parcial
y9sin vertical equivalente; no es lo mismo que este nuevo conteo de botones.
No se ejecutó Odoo ni se verificó una instalación de cliente.

### Conteo por módulo de origen de cada botón

E=comparable, P=parcial, W=borrador no disponible, F=sin equivalente. La autoría del primer XML cargado determina el módulo del botón; no es un conteo de entidades completas.

| Nº | Módulo Odoo | Total | E | P | W | F |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Base QMS y controles | 8 | 5 | 2 | 0 | 1 |
| 2 | Documentos | 11 | 10 | 1 | 0 | 0 |
| 3 | Evidencias | 5 | 0 | 4 | 0 | 1 |
| 4 | Riesgos | 5 | 5 | 0 | 0 | 0 |
| 5 | No conformidades | 7 | 7 | 0 | 0 | 0 |
| 6 | CAPA y acciones | 15 | 14 | 1 | 0 | 0 |
| 7 | Auditorías internas | 18 | 7 | 1 | 2 | 8 |
| 8 | KPI y objetivos | 12 | 0 | 0 | 0 | 12 |
| 9 | Revisión por dirección | 10 | 0 | 0 | 0 | 10 |
| 10 | Implementación guiada | 21 | 0 | 3 | 0 | 18 |
| 11 | Mappings / pack calidad | 8 | 0 | 0 | 0 | 8 |
| 12 | ISO9001 y transición | 27 | 0 | 0 | 0 | 27 |
| 13 | Importación | 2 | 0 | 0 | 0 | 2 |
| 14 | Personas / formación | 4 | 0 | 0 | 0 | 4 |
| 15 | Equipos / calibración | 15 | 0 | 0 | 0 | 15 |
| 16 | Licencia comercial | 4 | 0 | 0 | 0 | 4 |
| 17 | Dashboard / accesos | 22 | 3 | 4 | 0 | 15 |
| 18 | Cliente / proveedor /8D/SCAR | 47 | 0 | 0 | 0 | 47 |
| 19 | Centro de Acciones | 3 | 0 | 3 | 0 | 0 |
| 20 | Costos de calidad | 5 | 0 | 0 | 0 | 5 |
| | **Total** | **249** | **51** | **19** | **2** | **177** |

## 8. Pruebas y límites

- Checkpoint previo `CP-PRODUCT-ACCESS-AUDIT-00-20261114T015214Z`:497 archivos de fuente/Git cifrados, restaurados y cotejados; bundle verificado. Backups/claves fuera del árbol. No se afirma restauración DB nueva porque no se cambió la DB local.
- PostgreSQL desechable:23 pruebas de permisos QMS,31 workflows y17 organización PASS; no se usó la DB de desarrollo ni clientes.
- Navegación:9 pruebas unitarias PASS. `git diff --check` PASS.
- Primer intento de harness falló por docker fuera de PATH; se corrigió usando el wrapper original. Primer arranque de organización falló por conexión de bootstrap; un contenedor nuevo completó17pruebas. Fallos de entorno conservados en logs, sin cambios de producto.
- Los errores al intentar downgrade con historia son la denegación esperada de los harness; los scripts de access/workflow terminaron correctamente y organización imprime downgrade denied as designed.
- Reproducción HTTP de suspensión CONFIRMA hallazgo: tras deshabilitar, lectura de estructura200, PATCH200 persistido y bitácora200. QMS lista200 vacía, detalle404 y capabilities vacías; /tenant/context403 limpia selección y posterior estructura409. No es un PASS de suspensión.
- Reproducción de Workflows CONFIRMA hallazgos: publica un paso con único auditor y luego rechaza transición403; tras deshabilitar la empresa el servicio/RLS sigue leyendo definiciones e iniciando instancias. No se afirma bypass HTTP Workflow por esta prueba de servicio.
- Los dos primeros intentos del helper HTTP fallaron: override de sesión de prueba incorrecto, y expectativa403 incorrecta para listado QMS filtrado por RLS. Se preservaron registros; helper final usa expire_on_commit=False como fábrica real, crea proceso sintético y comprueba lista vacía/detalle404. No se alteró el producto para lograr el resultado.
- No se hicieron249 recorridos browser ni nuevas pruebas de todas las verticales. Las pruebas anteriores de PR39 no se transfieren al WIP0049. Ningún PASS aislado permite afirmar que toda autorización está cerrada.
- No hubo cambios de backend/modelos/auth/permisos ni despliegue. Esta entrega es un diagnóstico y catálogo; las correcciones A01–A11 siguen pendientes.

## 9. Orden recomendado

1. Cerrar suspensión de empresa, revisión integral de accesos y las brechas del motor Workflow; separar lectura de trazabilidad por función.
2. Diseñar y construir alta comercial de empresa/personas y asistente de arranque; navegación por tarea y configuración empresarial claramente separadas.
3. Terminar ready/start y después ejecución/evidencia/hallazgos/reporting de auditorías; integrar seguimiento con NCR/CAPA/Centro de Acciones.
4. Entregar las verticales pendientes y packs/versiones revisados, con los mismos controles y pruebas de aislamiento.
5. Suscripción/entitlements por empresa/seats/ISO, aceptación con usuarios y gates de seguridad, restauración y operación antes de producción.

Este orden es recomendación de ingeniería. No se añadió una decisión comercial
ni se alteraron los permisos existentes para resolver visualmente una brecha.
