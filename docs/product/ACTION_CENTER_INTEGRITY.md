# Centro de Acciones — integridad de la cola ·16 noviembre2026

Rama codex/action-center-eligibility sobre PR55/820e482. No reestructura los
módulos QMS ni crea otra tabla de tareas. Conserva contrato GET /action-center,
los identificadores de destinos y el frontend existente.

## Comportamiento entregado

- Acciones CAPA en progreso aparecen con su estado real. Las abiertas en
  planificación siguen permitiendo preparar el plan.
- Acciones de CAPA canceladas/cerradas o que ya pasaron a revisión de eficacia no
  se ofrecen como trabajo ejecutable o verificación pendiente.
- Primero se determina elegibilidad; después se ordena y limita. Una tarea propia
  no desaparece por existir251 tareas anteriores asignadas a otras personas.
- Los resúmenes cuentan todos los registros elegibles, incluso fuentes ausentes
  de una página de un solo elemento. No representan un muestreo de250 por fuente.
- Consulta y resumen comparten una sentencia/snapshot SQL. Solo se materializan
  los elementos de la página (máximo200), no todo el conjunto en Python.
- Revisión independiente y acceso al contexto de destino siguen exigidos. Las
  tareas personales requieren autoridad para ejecutarlas; la supervisión de solo
  lectura conserva su vista de equipo sin adquirir autoridad de ejecución.
- Filtro de unidad exacto: excluye Workflow porque sus instancias son de empresa,
  sin unidad de negocio. Las unidades de asignación no se convierten en alcance.
- Los permisos efectivos siguen en API/PostgreSQL FORCE RLS. No hay nuevas
  capacidades, roles, migraciones, concesiones ni dependencias.

## Validación

| Comprobación | Resultado |
| --- | --- |
| HTTP + PostgreSQL desechable, schema0049 |18PASS; casos de251 registros, cuatro fuentes, roles, grants, estados e aislamiento |
| Regresión Workflow en PostgreSQL desechable |31PASS; downgrade con historia denegado como se esperaba |
| API unitarias |93PASS;530 casos DB omitidos sin harness, no declarados PASS |
| Ruff/formato y mypy |PASS;127 archivos formateados,78 fuentes analizadas |
| ShellCheck, diff whitespace |PASS |
| Gitleaks árbol |0hallazgos |
| OpenGrep acotado |6reglas/2archivos,0hallazgos |
| Runtime local0048 real, dos perfiles |10comprobaciones de lectura PASS;0mutaciones de negocio |

Los18 casos incluyen elegibilidad por usuario/rol/unidad, revocación de una
asignación, exclusión del auditor de ejecución personal, contexto completo para
abrir controles/evidencia, separación revisor/remitente, padres terminales,
resúmenes independientes del límite y aislamiento/suspensión de empresa.
Navegador real poblado con6acciones y navegación al expediente/acción CAPA exactos PASS, con destino destacado. Captura local artifacts/previews/2026-11-16/action-center-current.png. No se afirma ensayo de carga ni prueba completa de todos los botones.

La nueva suite se añade al job process-integrity y al checkpoint completo:

```sh
# CI construye la imagen endurecida por defecto.
./scripts/run-action-center-integrity.sh
# Reutilización explícita de la imagen existente para el harness local aislado:
PMC_TEST_REUSE_POSTGRES_IMAGE=1 ./scripts/run-action-center-integrity.sh
```

La fixture compartida comprueba que las URLs pertenecen exclusivamente a la DB
pmcloud_tenant_suspension. Contenedor/credenciales aleatorios, datos sintéticos,
tmpfs512m y retirada del contenedor propio al salir. Nunca usar DB de desarrollo
o clientes. Los errores iniciales de tipado/import de fixture de desarrollo se
corrigieron sin omitir pruebas ni relajar permisos; la primera corrida funcional
completó11 casos y la ampliada18.

## Demo local y recuperación

Runtime PR39/DB0048 + fix de formulario de procesos de PR55 + estos dos módulos.
Solo se recreó API con una capa pequeña; web, identidad, storage y DB permanecen
en sus versiones. Imagen previa: pmcloud-api:before-action-center-20261116.
Rootfs read-only, cap_drop y no-new-privileges conservados. Rollback local:
retaggear esa imagen como pmcloud-api:latest y recrear solo API con el mismo
Compose/env protegido. No exige restauración DB porque no hay cambios de negocio
ni migración. No atribuir0049/A02 al runtime0048.

CP-ACTION-CENTER-RESUME-00-20261116T211102Z preservó546fuentes/Git cifrados;
CP-ACTION-CENTER-02-20261116T212202Z preservó549fuentes/Git. Descifrado/restauración,
SHA256 y bundle verify PASS, backups fuera del árbol y claves separadas. El backup
DB de la demo CP-DEMO-SANDBOX-DB-06-20261116T195500Z permanece sin restaurarlo sobre
la base real. El respaldo final de entrega se sella aparte.

## Seguimiento CI de la demo

PR55/48741ce falló calidad porque unittest se ejecutaba en Python global sinhttpx.
Se corrigieron quality.yml y checkpoint.sh para usar el entorno backend bloqueado
por uv, sin instalar paquetes adicionales ni saltar casos.49unittest PASS local;
en820e482 calidad43957691112 y CodeQL43957691140 PASS. Security43957691134 estaba
en ejecución en ese corte; el run previo43944268386 falló solo gate final.
No se inventa conteo actualizado de CVE sin verificar su artefacto. PM NO GO sigue
vigente; ninguna de estas correcciones autoriza merge o producción.

Pendientes: aceptación de usuarios, visuales responsive poblados/screen reader,
escala/performance, resolución de vendors y demás dominios funcionales/comerciales.
La cola no corrigió por sí sola la publicación auditor-only. La entrega posterior
WORKFLOW_EXECUTOR_VALIDATION.md cierra esa validación API; la defensa SQL completa
sigue pendiente. Ninguna de ellas amplía autorizaciones.
