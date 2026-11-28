# Paneles de control y Personas

## Referencia funcional

Se revisaron los modelos de persona y formación, los permisos y la navegación de `pm_qms_people` en el QMS propio de Odoo. La persona tiene un vínculo opcional a una cuenta, roles, contadores de formación vencida, cualificaciones próximas a vencer y acuses pendientes. Formación distingue el catálogo de cursos, las sesiones y los registros individuales. El plan del SaaS conserva esas distinciones y presenta el seguimiento desde la ficha de cada empleado.

## Áreas de trabajo

| Área | Quién accede | Alcance |
| --- | --- | --- |
| Mi perfil | Cada usuario autenticado | Identidad de su propia cuenta, empresa seleccionada, rol y preferencia de tema del navegador. |
| Control de empresa | Propietario o administrador de la empresa | Sedes y departamentos, asignaciones, permisos, puesta en marcha del QMS y bitácora. En iteraciones siguientes se incorporan marca, idioma, zona horaria, plantillas y avisos. |
| Personas y formación | Encargados con permisos de personas o formación por unidad | Empleados, foto privada, cursos, asignación por persona o rol, asistencia, resultados, evidencias, vencimientos y cualificaciones. Cada usuario accederá a su ficha propia según la política del tenant. |
| Operación del SaaS | Personal interno con identidad y permisos de plataforma | Alta, suspensión y reactivación de empresas, planes, seats, addons ISO, facturas, soporte, salud, despliegues, restauraciones y bitácora de plataforma. |

La ficha laboral y la cuenta de acceso tienen ciclos de vida independientes. Una persona puede figurar en el directorio y recibir formación sin consumir un seat. La vinculación a una cuenta, la invitación y los permisos de QMS son decisiones separadas. Las capacidades de administración de un cliente aplican a su empresa. El acceso de plataforma se gobierna con identidad, permisos y bitácora propios. Las pantallas de operación trabajan con metadatos comerciales y de servicio.

## Personalización

- Empresa puede definir el nombre visible, logo, combinación cromática, idioma, zona horaria, sedes, departamentos, responsables y plantillas. Los presets cromáticos mantienen el contraste definido por el sistema visual.
- Usuario puede elegir su tema personal y consultar su identidad y responsabilidades. La configuración del proveedor de identidad, aislamiento de datos, auditoría y seguridad se administra en la plataforma.
- Foto laboral requiere permisos por unidad y una política de autoservicio. Antes de persistirla se implementará validación de formato y dimensiones, recodificación sin metadatos, escaneo, almacenamiento privado, autorización individual en la lectura y seguimiento de cambios.

## Entrega actual

- **Mi perfil** y **Control de empresa** se integran en el SaaS autenticado. Control de empresa abre las pantallas operativas existentes según la autoridad de la sesión.
- `/design-studio/control-centers` ofrece datos sintéticos y permite ensayar la alta, edición, foto, archivo, restauración y cursos. También permite explorar personalización de empresa y el panel interno. Activar con `PMQMS_CONTROL_PREVIEW=1` en el proceso web de revisión. La ruta devuelve 404 de forma predeterminada. Los cambios de la vista previa se mantienen en memoria y se reinician al recargar.
- Siguientes entregas de Personas: ficha persistente y permisos por unidad, fotos privadas, catálogo y sesiones, asignaciones y resultados, y finalmente evaluaciones, evidencias, vencimientos y acuses. El registro de formación aportará evidencias de 7.2 y 7.3 con aprobación y trazabilidad.
