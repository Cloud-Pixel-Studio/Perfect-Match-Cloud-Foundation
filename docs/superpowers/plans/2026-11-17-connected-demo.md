# Demo QMS con archivos y flujos conectados

Objetivo autorizado: ampliar la demo sintética de la VM para estudiar cada opción implementada y las relaciones entre procesos, documentos, controles/evidencia, riesgos, NCR, CAPA, workflows y planes de auditoría. Se conserva la cuenta pmc-demo-full como recorrido único; los actos independientes usan otro actor real de la demo.

Arquitectura: APIs HTTPS actuales y roles/capacidades existentes, sin modificar modelos, migraciones, licencias ni validaciones para fabricar estados. Fuentes de los contratos: scripts runtime existentes y schemas API. Nuevos registros EST-*; no sobrescribir LAB-* ni ediciones del usuario. EmpresaA primero, empresaB mantiene aislamiento y ejemplos propios. Las operaciones no implementadas se documentan como pendientes.

- [x] Preservar estado fuente y base antes de la nueva carga; cierre de cuenta ya probado por separado.
- [x] Revisar contratos de vínculos y versiones; definir tres escenarios: recepción/proveedor, control documental, auditoría planificada.
- [x] Crear ocho PDF españoles útiles, originales y ficticios, con referencias cruzadas; renderizar y validar archivos.
- [x] Implementar cargador idempotente limitado al hostname/demo aprobados, basado en el sandbox existente. No restaurar grants revocados ni sobreescribir ejemplos editados.
- [x] Crear procesos/propietarios y documentos en varios estados por flujos reales, con antivirus/storage privados y actor revisor independiente.
- [x] Conectar controles, implementación, actividades y evidencia documental aceptada; vincular riesgo→NCR→CAPA y acciones según contratos actuales.
- [x] Poblar planes de auditoría: programas, alcance, criterios, equipo, agenda y soporte de competencia donde exista. Nunca falsear ejecución/hallazgos/informe ni certificaciones.
- [x] Poblar workflows ejecutables y distintas etapas sin sustituir las aprobaciones QMS; mantener trabajo pendiente para el usuario.
- [x] Verificar inventario persistido, relaciones, descargas/hash, transiciones, negativas y protección de otra empresa; recorrer navegador con la cuenta completa.
- [x] Entregar mapa de estudio y archivos, actualizar checkpoint y preparar PR con evidencia saneada, conservar credenciales fuera de Git.
- [x] Publicar la rama y abrir el PR sin fusionar: https://github.com/Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation/pull/63 (borrador; CI exacto pendiente).

No se declara finalizada ninguna casilla hasta disponer de evidencia. Pruebas anteriores del despliegue o de account-switch no acreditan esta ampliación.

Evidencia: CONNECTED_STUDY_VALIDATION_2026-11-17.json y CONNECTED_STUDY_REVISIONS_2026-11-17.json. Navegador: ocho tareas y registros CAPA/documentos/planes confirmados; descarga UI nueva no acreditada en carpeta local, ocho descargas HTTP/hash sí. Negativas y aislamiento acreditados por pruebas previas de cuenta completa; esta ampliación no las repite todas. Doce tests específicos/102raíz y revisión independiente acotada. Ver informe de implementación para límites.
