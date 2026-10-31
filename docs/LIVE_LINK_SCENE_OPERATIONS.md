# Live Link — protocolo de edición semántica en vivo

**Estado:** primera implementación en la rama; pendiente de validación en Godot headless y en Android físico.  
**Rama:** `feature/live-editor-link`  
**Objetivo:** ejecutar cambios sobre la escena abierta del editor Godot Android, en vez de usar la transferencia de archivos como mecanismo principal.

## 1. Contrato de producto

La edición debe ser visible incrementalmente en la sesión abierta. Si el agente crea un nodo, mueve un objeto o cambia una propiedad, el Android debe aplicar la operación a su escena activa y actualizar SceneTree, Inspector y viewport sin reiniciar el editor, reimportar el proyecto ni reconstruir un APK.

La sincronización de archivos puede transportar recursos externos auxiliares (texturas, audio, mallas importadas), pero no reemplaza las operaciones del editor.

## 2. Roles

- **Godot Linux / agente de trabajo:** solicita operaciones semánticas sobre un proyecto Android seleccionado por ID.
- **Godot Android / receptor:** valida la identidad y el contexto de la escena, solicita aprobación según la política de seguridad y ejecuta la operación en el editor real.
- **Transporte:** entrega mensajes autenticados y correlacionados. Un relay solo transporta; no es la autoridad que modifica la escena.
- **ChatGPT / herramienta:** debe tener un conector autorizado para invocar las operaciones. Tener un ID o un archivo MCP local no da acceso automáticamente.

El ID de cuatro dígitos identifica el proyecto, no autentica ni conecta.

## 3. Sobre de mensaje versionado

Cada solicitud incluye, como mínimo:

```json
{
  "type": "scene_operation",
  "protocol_version": 1,
  "operation_id": "op-unique-id",
  "project_id": "0427",
  "scene_id": "res://scenes/house.tscn",
  "expected_scene_revision": 12,
  "target_node_id": "stable-node-id-or-null",
  "operation": "set_transform",
  "arguments": {
    "position": [2.0, 0.0, -1.0]
  },
  "approval": "required"
}
```

El ejemplo ilustra el contrato, no es todavía un mensaje aceptado por el código actual. Las revisiones de escena detectan solicitudes obsoletas; los IDs de nodo deben mantenerse estables durante la sesión y no depender solo del nombre visible.

Respuesta correlacionada:

```json
{
  "type": "scene_operation_result",
  "protocol_version": 1,
  "operation_id": "op-unique-id",
  "project_id": "0427",
  "status": "applied",
  "scene_revision": 13,
  "message": ""
}
```

Estados mínimos: `applied`, `rejected`, `conflict`, `invalid`, `failed`, `unknown`. Un timeout no se debe tratar como fallo seguro: consultar el estado antes de repetir una operación no idempotente.

## 4. Operaciones iniciales (MVP)

1. `create_node`: crear `Node3D`, `MeshInstance3D`, `CSGBox3D`, `DirectionalLight3D` o `Camera3D` bajo un padre validado.
2. `set_transform`: cambiar posición, rotación y escala de un `Node3D`.
3. `set_property`: cambiar visibilidad o tamaño de un `CSGBox3D`, con validación de tipo y rango.
4. `delete_node`: eliminar un nodo descendiente, con confirmación y registro Undo/Redo.

Guardar la escena sigue siendo una acción separada del editor y no se ejecuta automáticamente. Materiales, recursos externos y creación de geometría más avanzada quedan para fases posteriores.

## 5. Ejecución dentro de Godot

El receptor no debe escribir a mano el archivo `.tscn` para simular una edición. Debe operar sobre el árbol de escena y los recursos vivos a través de las APIs del editor, preferiblemente con `EditorInterface`, selección del editor, escena editada y `EditorUndoRedoManager` cuando corresponda. Debe marcar la escena como modificada y actualizar el viewport/Inspector de forma nativa.

Antes de codificar, verificar en Godot 4.7.2 las firmas y disponibilidad reales de las APIs de `EditorInterface`, `EditorUndoRedoManager`, `EditorPlugin` y la escena editada. Si una operación requiere acceso que un addon no expone, añadir una API nativa estrecha al editor C++/Android en vez de fingir que el addon controla todo.

No permitir que una solicitud remota invoque GDScript arbitrario, comandos de shell ni nombres de métodos arbitrarios. Cada tipo de operación tiene un esquema explícito, tipos permitidos y límites.

## 6. Seguridad y consistencia

- Verificar ID de proyecto, escena abierta, revisión y nodo destino antes de ejecutar.
- Validar tipos, valores finitos, nombres y límites; rechazar NaN/Infinity y rutas fuera del proyecto.
- Requerir aprobación en el Android para cambios destructivos y conservar un registro de operaciones.
- Aplicar cada operación en el hilo principal del editor; no mutar el SceneTree desde un callback de red en un hilo secundario.
- Usar UndoRedo para permitir deshacer cuando sea compatible.
- Responder solo después de que la operación haya terminado; diferenciar aplicada en memoria de guardada en disco.
- Rechazar revisiones obsoletas y devolver contexto suficiente para reconciliar, sin sobrescribir silenciosamente cambios locales.
- No exponer el relay sin autenticación/TLS. El ID de proyecto no es un secreto.

## 7. Plan de implementación y pruebas

### Fase A — inspección de API
Crear una prueba/harness de editor Godot 4.7.2 que compruebe cómo obtener la escena abierta, añadir un nodo, cambiar su transformación, eliminarlo, marcar la escena como modificada y deshacer la acción. Confirmar que la operación actualiza SceneTree y viewport sin guardar/recargar.

### Fase B — motor de operaciones local
Implementar un despachador con allowlist de operaciones y validación estricta, independiente del transporte. El harness crea un suelo y cuatro paredes, mueve una pared, verifica propiedades y deshace una operación.

### Fase C — transporte y aprobación
Añadir el mensaje versionado y ACK correlacionado, manteniendo el canal de archivos actual separado. Probar duplicados, operación obsoleta, desconexión, rechazo y reintento seguro.

### Fase D — Android real
Aplicar una secuencia sobre una escena abierta en el editor modificado del teléfono: cada pared debe aparecer al llegar la operación; mover una pared desde Linux debe actualizar su posición sin reiniciar ni importar una escena nueva.

### Criterio de aceptación
La prueba no se considera aprobada por transmitir JSON, pasar pruebas estáticas o guardar un archivo. Debe demostrar mutación de la escena viva en el editor Android real, con confirmación visible y sin recargar el proyecto.

## 8. Diferencia frente al código existente

El código actual de Live Link implementa operaciones de **archivos** (`create/update/rename/delete`) y su aprobación/validación. Eso es útil para transportar recursos, pero no ejecuta cambios semánticos en la escena abierta. El tipo `project_operation` sigue reservado a archivos. Se añadió un canal separado `scene_operation` / `scene_operation_result`, con validación de allowlist, correlación de ACK, control de duplicados/TTL y una notificación `scene_state` para informar escena abierta y revisión. El emisor MCP expone `send_live_scene_operation`; el receptor Android muestra una confirmación y aplica las operaciones mediante `EditorPlugin.get_undo_redo()`.

No se debe afirmar que la edición semántica en vivo funciona hasta implementar y probar el contrato descrito. No generar APK ni fusionar PR #2 sin autorización explícita.


## 9. Estado de la primera implementación (2026-10-31)

- Relay: valida y enruta `scene_operation`, `scene_operation_result` y `scene_state` entre los roles agent/target; los ACK se vinculan al tipo de operación pendiente para evitar respuestas cruzadas.
- Linux/MCP: se añadió la herramienta tipada `send_live_scene_operation`, sin habilitar ejecución arbitraria de GDScript.
- Android: el addon incluye motor de operaciones, confirmación explícita y uso del historial Undo/Redo del editor. La revisión se incrementa también ante cambios locales registrados en el historial.
- Operaciones de geometría inicial: nodos CSGBox3D, posición/rotación/escala y tamaño, suficientes para prototipar suelo y paredes.
- No implementado: sincronización bidireccional de cada edición desde Android hacia Linux, asignación de materiales/texturas, guardado remoto automático y transporte seguro accesible desde ChatGPT cloud.
- Validado en CI con Godot 4.7.2 headless: carga del addon y harness que crea una escena real, crea un CSGBox3D, cambia posición/rotación/escala/tamaño, lo elimina y comprueba que Undo lo restaura. También pasaron 58 pruebas Python de relay/contratos y la sintaxis de los empaquetadores MCP.
- Pendiente: build nativo Linux con el MCP empaquetado, conexión física entre los dos editores, viewport Android real y conexión autorizada desde ChatGPT cloud. No se debe afirmar que el enlace funciona end-to-end hasta esas pruebas.
