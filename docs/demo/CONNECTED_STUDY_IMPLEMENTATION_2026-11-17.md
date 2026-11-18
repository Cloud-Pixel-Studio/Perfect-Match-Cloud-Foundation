# Implementación de la demo conectada

## Resultado y alcance

La demo aislada `demo.3-238-70-198.sslip.io` incorpora casos `EST-*` mediante las APIs HTTPS existentes. El marketing sigue público; el panel usa OIDC, capacidades explícitas y aislamiento de empresa. No se cambiaron backend, migraciones, permisos, contratos API ni imágenes durante esta ampliación. La corrección OIDC y el perfil completo pertenecen al PR62 anterior.

La lectura final real devolvió PASS con 6 procesos, 8 documentos, 6 controles, 3 implementaciones, 8 riesgos/oportunidades, 6 NCR, 4 CAPA, 3 programas, 4 planes y 4 workflows. Se comprobaron 12 definiciones de actividad, 12 requisitos, 4 evidencias aceptadas, 52 vínculos activos, 24 registros dependientes de planes y 8 descargas SHA-256. Los conteos se refieren a esta ampliación, no al total del producto ni a funciones nuevas.

Los PDF actuales y la copia histórica existen en `infrastructure/demo/study-assets`, con manifiesto portable. El ZIP de Descargas contiene 14 entradas, guía y resultados sin contraseñas; integridad ZIP y ocho hashes comprobados. Las credenciales permanecen en el Markdown privado fuera del repositorio.

## Recuperación y preservación

- Antes de cargar: CP-CONNECTED-DEMO-00-20261117T223449Z, fuentes/Git y715 archivos restaurados por hash/modo; CP-CONNECTED-DATA-00, PostgreSQL cifrado.
- Después de cargar: CP-CONNECTED-DATA-06, PostgreSQL cifrado, 57 tablas restauradas en contenedor temporal sin red y tmpfs. Conteos y hashes ordenados coinciden. Ambas copias DB están también fuera de la VM con claves separadas, SHA256/decrypt/tamper verificados.
- Los dumps no se incorporan al repositorio ni se guardan en claro. Restauración DB comprobada con `--no-owner --no-privileges`: no acredita restauración de ACL, roles, objetos S3 o Keycloak.
- Datos LAB/QA y los datos de otra empresa conservados. El cargador agrega ausentes y no sobrescribe existentes. Una repetición no repara automáticamente toda carga parcial: el verificador debe rechazar escenarios incompletos o modificados.
- WIP anterior de frontend y archivos generados permanece fuera de este cambio. La instalación antigua `/opt/pmcloud` permanece intacta; solo la demo aislada recibió datos.

## Verificación y fallos resueltos

- 12 tests de la ampliación PASS; suite raíz completa102 PASS usando el wrapper del proyecto y venv API. Ruff y formato de los dos Python nuevos PASS. No cambian dependencias ni aplicación; no se atribuye un build frontend nuevo a cambios de datos.
- SAST estricto del cargador:6 reglas/1 archivo/0 hallazgos, sin avisos; análisis del directorio:6reglas/3Python/0hallazgos (otros formatos no analizados). Gitleaks staged:113KB/0 secretos. PDF marcados binarios con atributos acotados para conservar bytes y hashes; diffcheck PASS.
- Verificador ejecutado sobre HTTPS real después de la corrección final: PASS. Comprueba padres, códigos, hijos, referencias, documentos/descargas y hitos de CAPA002/NCR002 cerrados y WF003 completado.
- Revisión independiente encontró que un PASS basado en padres ocultaba hijos o hitos finales faltantes. Se añadieron validaciones y regresiones; la última ventana CAPA cerrada/NCR pendiente reprodujo `StudyFailure not raised` antes del fix y pasó después. Seguimiento separado:12 PASS, sin nuevos P0/P1/P2 en el alcance leído; no equivale a revisión integral ni aprobación de producción.
- Primer intento de implementación de controles:422 por omitir alcance en query; corregido el adaptador. Otra evidencia:409 al intentar usar documento de otro proceso; se respetó la regla y se vinculó una revisión del mismo proceso mediante API. No se relajaron validaciones ni se modificaron registros por SQL.
- Preparación de ejemplos de revisión: un422 por límite de listado CAPA se corrigió a50; la revisión ya liberada se preservó. Doc005 corrigió un alias mediante nueva revisión2.0 y retiro lógico del vínculo anterior del caso abierto; el histórico del caso cerrado permanece intacto.
- Navegador real confirma ocho tareas, CAPA001 con acciones y trazabilidad directa/heredada, documentos con revisiones3.0draft/2.0active/1.0superseded y auditorías con equipo/agenda. Capturas locales ignoradas en `artifacts/previews/2026-11-17-connected-demo`. El clic Download PDF no acreditó una nueva descarga en la carpeta local; no se registra como PASS de descarga UI. Las ocho descargas HTTP sí coinciden por hash.
- Pruebas previas de cuenta completa acreditaron rechazo de autoaprobación, autogrant y empresa ajena. Esta ampliación no repite todos esos negativos ni toda la regresión del SaaS.

## Límites que permanecen

Auditorías: solo planificación; revisión humana de independencia/competencia pendiente, `ready_for_execution=false`, sin ejecución/hallazgos/informe/certificación inventados. El PDF005 histórico en CAPA002 ilustra preservación de referencias y no prueba por sí mismo eficacia documental. La guía explica el soporte específico del caso.

El manifiesto refleja las revisiones vigentes de esta demo. Una carga vacía crea una primera emisión; las revisiones pedagógicas adicionales se crearon por operaciones separadas y no las recrea este cargador. Los cambios de práctica posteriores pueden hacer fallar la comparación con el baseline sin justificar ningún reset.

Persisten seis HIGH conocidos del Keycloak evaluado. No se reducen gates, no se autoriza producción y no se afirma paridad Odoo ni certificación ISO/NIST/WCAG. El PR se prepara contra `codex/demo-account-switch`, sin merge ni despliegue de producción.
