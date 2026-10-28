# Live Link — protocolo propuesto de sincronización entre editores

**Estado: diseño, no implementado.** La transmisión de pantalla/entrada del addon actual no sincroniza archivos. Este documento define una primera versión segura para discutir e implementar por separado.

## Objetivo

Permitir que el editor Linux y el editor Android trabajen sobre el mismo proyecto, y que los cambios hechos desde cualquiera de los dos extremos se reflejen en el otro sin usar GitHub como transporte obligatorio para cada cambio.

## Separar tres canales

1. **Control remoto:** eventos de entrada y pantalla en tiempo real. No es un mecanismo de guardado.
2. **Estado efímero del editor:** selección, escena abierta, pestaña activa y vista. No debe sobrescribir recursos del proyecto ni el estado de otro usuario sin una política explícita.
3. **Archivos del proyecto:** cambios persistentes de recursos y escenas, con versiones, hashes y resolución de conflictos.

## Protocolo inicial de archivos (propuesto)

- Cada editor se registra con un ID de sesión aleatorio, versión de protocolo y capacidades.
- El proyecto se identifica por un UUID local persistente, no solo por el nombre de carpeta.
- Cada cambio se representa como operación: `create`, `update`, `delete`, `rename`; contiene ruta relativa normalizada, hash SHA-256, tamaño, versión base y sesión de origen.
- Solo se aceptan rutas relativas dentro del proyecto. Rechazar rutas absolutas, `..`, rutas con separadores ambiguos, enlaces simbólicos que escapen de la raíz y archivos que excedan límites configurados.
- Enviar archivos por fragmentos con tamaño máximo, hash verificado antes de confirmar y escritura temporal seguida de reemplazo atómico cuando la plataforma lo permita.
- No sobrescribir un archivo local si su hash actual difiere del hash base que el emisor esperaba. En ese caso crear un conflicto explícito con ambas versiones y permitir comparar/guardar una copia; nunca descartar silenciosamente el trabajo.
- Los borrados son tombstones versionados, no eliminaciones inmediatas en el otro extremo. Un borrado solo se aplica si el receptor sigue en la versión base esperada y el usuario confirmó la política de borrado.
- Mantener un registro pequeño de operaciones confirmadas para reanudar tras desconexión. Las operaciones duplicadas deben ser idempotentes.
- Usar WSS, token de sesión de vida corta, autorización por proyecto/sala y límites de frecuencia/tamaño. Nunca registrar tokens ni contenido sensible en logs.
- Excluir por defecto `.git/`, `.godot/`, cachés, temporales, archivos generados y carpetas configuradas por el usuario. No sincronizar claves o secretos sin opt-in explícito.
- Si un recurso se está editando en ambos extremos, no fusionar texto ni escenas automáticamente en la primera versión. Marcar conflicto y preservar ambas copias.
- Los cambios sincronizados deben pasar por el mecanismo de guardado/importación de Godot y notificar al editor para refrescar el FileSystem. Deben validarse escenas, recursos, UID y referencias antes de declarar éxito.

## Criterios de aceptación antes de habilitarlo

- Crear/editar/renombrar/borrar un archivo en Linux se refleja en Android; lo mismo en sentido inverso.
- Pruebas de desconexión a mitad de transferencia, reconexión, operación duplicada, archivos grandes, rutas maliciosas, conflicto simultáneo y borrado concurrente.
- Nunca perder silenciosamente una versión; mostrar claramente conflictos y errores.
- El proyecto sigue abriendo después de sincronizar escenas y recursos.
- GitHub Sync continúa siendo independiente y unidireccional.
- Pruebas de almacenamiento y rendimiento en Android ARM32/ARM64 y en el LG K51 antes de activarlo por defecto.

## Decisión pendiente

Antes de implementar, decidir si la primera versión será **sesión compartida con un editor autoritativo** (más sencilla y segura) o **edición bidireccional con conflictos** (más potente, bastante más compleja). No afirmar que ambos extremos se sincronizan hasta superar todos los criterios anteriores.
