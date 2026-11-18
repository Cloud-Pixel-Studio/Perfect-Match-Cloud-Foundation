# Archivos de estudio sintéticos

Ocho PDF originales de dos páginas y una copia histórica, sin datos de clientes, enlaces externos, JavaScript ni credenciales. `manifest.json` identifica código, revisión, tamaño y SHA-256. Los originales fueron renderizados y revisados; la corrección de EST-DOC-005 conserva el PDF histórico.

Guía: [Recorrido conectado](../../../docs/demo/CONNECTED_STUDY_GUIDE.md).

Desde la raíz, con las dependencias de desarrollo de API instaladas:

```sh
apps/api/.venv/bin/python infrastructure/demo/connected_study.py \
  --env-file /ruta/privada/demo.env \
  --assets infrastructure/demo/study-assets \
  --verify --report-file /ruta/privada/resultado.json
```

El verificador solo acepta el hostname y la base de la demo autorizada. La configuración debe tener modo 0600. No publicar ese archivo ni sus valores.

`--apply` requiere el manifiesto de recuperación CP-CONNECTED-DATA-00 restaurado y verificado; escribe a través de las APIs existentes y preserva registros existentes. Una interrupción puede dejar un escenario parcial: verificar, inspeccionar y corregir mediante operaciones autorizadas, sin borrar ni restablecer trabajo del usuario. La carga base libera los ocho documentos; las revisiones pedagógicas adicionales fueron creadas y comprobadas por separado en la demo y no son recreadas por este cargador.

Los PDF son copias de estudio; su vigencia operativa depende del registro controlado dentro del SaaS. Se aplica la licencia del repositorio.
