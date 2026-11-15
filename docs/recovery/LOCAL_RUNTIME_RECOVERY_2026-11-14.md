# Recuperación del entorno local · 14 noviembre de 2026

El disco de datos de Colima pmqms (48 GiB) se llenó. PostgreSQL registró PANIC/No space left on device y no pudo escribir postmaster.pid; API /health devolvió503. El runtime corresponde a desarrollo, PR39/DB0048. No se atribuyen a este runtime las correcciones de PR41/A02.

Se verificó PMC_ENVIRONMENT=development, el perfil y capacidad libre del host. Liberar88.52MB de caché de build descartable no resolvió el arranque. No se ejecutaron docker system/image/volume prune, reset, clean ni restauración sobre la DB existente.

CP-LOCAL-VM-DISK-00-20261114T205033Z cifró la configuración Colima fuera de Git y verificó descifrado idéntico. Se detuvo exclusivamente el perfil pmqms y se arrancó con disk52GiB, manteniendo4CPU/6GiB de memoria, volúmenes y datos. PostgreSQL volvió healthy/pg_isready accepting; /var/lib/docker mostró3.8GiB libres y /health volvió200 tras cargar ClamAV. La ampliación no se revierte reduciendo el disco.

CP-LOCAL-RECOVERED-DB-06-20261114T205600Z: respaldo posterior cifrado y restauración en PostgreSQL aislado tmpfs512m PASS. Esquema0048_audit_competence,57tablas de usuario; comparación de esquema/filas/roles/ACL/secuencias conforme al procedimiento existente. No se aplicó migración ni mutación de negocio. Dump, claves y manifest privado quedan fuera de Git. El respaldo previo CP-TENANT-SUSPENSION-DB-00-20261114T155635Z se conserva; no fue restaurado sobre la DB real.

El escaso espacio libre del host/VM exige capacidad y retención planificadas antes de nuevos builds grandes. No se eliminaron respaldos, imágenes anteriores o volúmenes de pruebas no identificados. Las auditorías continuaron usando DB sintéticas tmpfs; la recuperación del runtime no convierte esos tests en pruebas sobre datos de cliente.

La auditoría de flujo conserva el fallo inicial de infraestructura y añade la comprobación posterior por separado en PR43. Sin cambio de producción, merge ni nuevos permisos.
