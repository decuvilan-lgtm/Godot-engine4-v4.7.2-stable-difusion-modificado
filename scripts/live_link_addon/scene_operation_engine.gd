extends RefCounted
class_name LiveLinkSceneOperationEngine

const ALLOWED_CLASSES := ["Node3D", "MeshInstance3D", "CSGBox3D", "DirectionalLight3D", "Camera3D"]

static func validate_request(data: Dictionary, project_id: String, scene_root: Node, current_revision: int) -> Dictionary:
    if str(data.get("project_id", "")) != project_id:
        return {"ok": false, "status": "rejected", "message": "El ID del proyecto no coincide."}
    if not is_instance_valid(scene_root) or not scene_root.is_inside_tree():
        return {"ok": false, "status": "rejected", "message": "No hay una escena abierta en el editor."}
    if str(data.get("scene_path", "")) != str(scene_root.scene_file_path):
        return {"ok": false, "status": "rejected", "message": "La escena activa no coincide con la solicitud."}
    if typeof(data.get("expected_scene_revision", null)) != TYPE_INT or int(data.expected_scene_revision) != current_revision:
        return {"ok": false, "status": "conflict", "message": "La revisión de escena está desactualizada."}
    if typeof(data.get("operation_id", null)) != TYPE_STRING or not _valid_id(str(data.operation_id)):
        return {"ok": false, "status": "invalid", "message": "ID de operación inválido."}
    var operation := str(data.get("operation", ""))
    var args: Variant = data.get("arguments", {})
    if not args is Dictionary:
        return {"ok": false, "status": "invalid", "message": "Los argumentos deben ser un objeto."}
    if operation not in ["create_node", "set_transform", "set_property", "delete_node"]:
        return {"ok": false, "status": "rejected", "message": "Operación no permitida."}
    if JSON.stringify(args).length() > 4096:
        return {"ok": false, "status": "invalid", "message": "Los argumentos superan el límite."}
    return {"ok": true, "operation": operation, "arguments": args}


static func apply_request(plugin: EditorPlugin, data: Dictionary, scene_root: Node) -> Dictionary:
    var operation := str(data.operation)
    var args: Dictionary = data.arguments
    var undo_redo := plugin.get_undo_redo()
    if operation == "create_node":
        var parent_path := str(args.get("parent_path", ""))
        var parent: Node = scene_root if parent_path.is_empty() else scene_root.get_node_or_null(NodePath(parent_path))
        var node_name := str(args.get("name", ""))
        var node_class := str(args.get("class", ""))
        if parent == null or not parent.is_inside_tree() or not node_name.is_valid_identifier() or parent.has_node(NodePath(node_name)) or node_class not in ALLOWED_CLASSES or not ClassDB.can_instantiate(node_class):
            return {"ok": false, "status": "invalid", "message": "Padre, nombre o clase de nodo no válidos."}
        var node := ClassDB.instantiate(node_class) as Node
        if node == null:
            return {"ok": false, "status": "failed", "message": "No se pudo crear el nodo."}
        node.name = node_name
        undo_redo.create_action("Live Link: crear " + node_name)
        undo_redo.add_do_method(parent, "add_child", node)
        undo_redo.add_do_method(node, "set_owner", scene_root)
        undo_redo.add_undo_method(parent, "remove_child", node)
        undo_redo.add_do_reference(node)
        undo_redo.commit_action()
        return {"ok": true, "status": "applied", "message": "Nodo creado."}
    var target_path := str(data.get("target_node_path", ""))
    var target := scene_root.get_node_or_null(NodePath(target_path))
    if target == null or target == scene_root or not scene_root.is_ancestor_of(target):
        return {"ok": false, "status": "invalid", "message": "El nodo destino no existe o no se puede modificar."}
    if operation == "set_transform":
        if not target is Node3D:
            return {"ok": false, "status": "invalid", "message": "El destino no es un Node3D."}
        var raw: Variant = args.get("position", null)
        if not raw is Array or raw.size() != 3:
            return {"ok": false, "status": "invalid", "message": "La posición debe tener tres componentes."}
        for value in raw:
            if typeof(value) not in [TYPE_INT, TYPE_FLOAT] or not is_finite(float(value)) or absf(float(value)) > 1000000.0:
                return {"ok": false, "status": "invalid", "message": "La posición contiene un valor no permitido."}
        var next_position := Vector3(float(raw[0]), float(raw[1]), float(raw[2]))
        undo_redo.create_action("Live Link: mover " + target.name)
        undo_redo.add_do_property(target, "position", next_position)
        undo_redo.add_undo_property(target, "position", target.position)
        undo_redo.commit_action()
        return {"ok": true, "status": "applied", "message": "Transformación actualizada."}
    if operation == "set_property":
        if str(args.get("property", "")) != "visible" or typeof(args.get("value", null)) != TYPE_BOOL or not "visible" in target:
            return {"ok": false, "status": "invalid", "message": "Propiedad no permitida."}
        undo_redo.create_action("Live Link: cambiar visibilidad")
        undo_redo.add_do_property(target, "visible", args.value)
        undo_redo.add_undo_property(target, "visible", target.visible)
        undo_redo.commit_action()
        return {"ok": true, "status": "applied", "message": "Propiedad actualizada."}
    if operation == "delete_node":
        var parent := target.get_parent()
        if parent == null:
            return {"ok": false, "status": "invalid", "message": "El nodo no tiene padre."}
        undo_redo.create_action("Live Link: eliminar " + target.name)
        undo_redo.add_do_method(parent, "remove_child", target)
        undo_redo.add_undo_method(parent, "add_child", target)
        undo_redo.add_undo_method(target, "set_owner", scene_root)
        undo_redo.add_do_reference(target)
        undo_redo.commit_action()
        return {"ok": true, "status": "applied", "message": "Nodo eliminado."}
    return {"ok": false, "status": "rejected", "message": "Operación no implementada."}


static func _valid_id(value: String) -> bool:
    if value.is_empty() or value.length() > 100:
        return false
    for c in value:
        if not (c.is_ascii_alphanumeric() or c in ["_", ".", ":", "-"]):
            return false
    return true
