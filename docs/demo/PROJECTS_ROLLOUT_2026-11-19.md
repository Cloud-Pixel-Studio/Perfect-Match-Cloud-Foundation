# Demo: proyectos QMS y referencias por paso

Estado: preparación, sin actualización instalada todavía. El usuario autorizó19noviembre actualizar la demo al terminar y probar la entrega. Este documento se completará con la evidencia real de instalación; no aprueba producción ni fusiona la pila de PR.

La inspección SSH20noviembre02:03UTC encontró API account-switch-20261117, web d707210, esquema0049_tenant_suspension y57tablas. Los seis servicios demo y los cinco de la instalación anterior estaban saludables. La imagen guided-journeys-3aa7f95 existe pero no estaba instalada. Marketing/products devuelve200; sesión/API anónima401; administración/realm master404. La comprobación CUA mostró marketing público y accesoOIDC; no se había iniciado sesión en esa inspección.

Alcance preparado: actualizar únicamente API/web y ejecutar las migraciones aditivas0050/0051 sobre la base demo separada, después de respaldo cifrado y restauración aislada. Conservar proveedores, archivos privados, volúmenes, imágenes previas y /opt/pmcloud. No reiniciar bootstrap de identidades, resetear contraseñas, hacer downgrade con historial ni restaurar encima de datos vivos.

Cuenta de estudio prevista: pmc-demo-full en DEMO-PRACTICA. Los permisos projects.read/manage se asignarán explícitamente por otro owner mediante las APIs normales; la asignación de coordinador no concede acceso. Ejemplos previstos: seis proyectos correspondientes a los seis recorridos, con referencias a revisiones liberadas y evidencias aceptadas ya existentes. Las brechas de producto seguirán pendientes y el trabajo reportado seguirá sin verificación.

Recuperación, fuente final, imágenes, revisión, pruebas y capturas: pendientes de ejecución. No se atribuye PASS de restauración o despliegue a la inspección de solo lectura.

Respaldo previo completado: CP-QMS-DEMO-BASELINE-VERIFIED-20261120T052809Z, esquema0049 y57tablas. Restauración en PostgreSQL sinred con propietarios/ACL preservados, roles sin contraseñas, políticasRLS y secuencias comparadas; AES256GCM/decrypt/tamperPASS. Seis artefactos cifrados copiados fuera deVM ydescifrados/hash verificados conclave separada. No se restauró sobre la base activa. No prueba restauraciónS3/IdP ni reaplicación de contraseñas.

Dos ensayos previos se conservaron: coincidían datos, pero diferían la representación de ACL por defecto y el deparse de casts de políticas. Se corrigió la comparación siguiendo [acldefault de PostgreSQL18](https://www.postgresql.org/docs/18/functions-info.html), sin ignorar permisos. El SQL de las políticas fuente se reparsea solo en el clon dentro de una transacción revertida; se comprueban primero identidades/roles/comandos y un control negativo detecta ampliar un rol aPUBLIC. El ensayo final pasó. Un canalSSH del ensayo diagnóstico terminó sin devolver salida; se inspeccionaron sus artefactos conservados mediante una conexión normal nueva, sin repetir con el mismo ID ni modificar datos activos.
