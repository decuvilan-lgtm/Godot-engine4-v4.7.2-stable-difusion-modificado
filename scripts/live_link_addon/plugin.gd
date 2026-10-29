@tool
extends EditorPlugin

const SETTING_URL := "live_link/relay_url"
const SETTING_ROOM := "live_link/room"
const SETTING_TOKEN := "live_link/token"
const SETTING_ROLE := "live_link/role"
const SETTING_PROJECT_ID := "live_link/project_id"
const BACKUP_ROOT := "user://live_link_backups"
const MAX_OPERATION_BYTES := 5 * 1024 * 1024
const FRAME_MS := 400
const MAX_W := 720
const MAX_H := 1280

var _ws := WebSocketPeer.new()
var _panel: VBoxContainer
var _status: Label
var _screen: TextureRect
var _room: LineEdit
var _url: LineEdit
var _token: LineEdit
var _role: OptionButton
var _project_code_label: Label
var _enable_button: Button
var _connect_button: Button
var _connection_enabled := false
var _code_copied := false
var _connected := false
var _connecting := false
var _join: Dictionary = {}
var _last_frame := 0
var _remote_size := Vector2i(720, 1280)
var _last_pos := Vector2.ZERO
var _approval_dialog: ConfirmationDialog
var _pending_project_operation: Dictionary = {}

func _enter_tree() -> void:
    _setting(SETTING_URL, "wss://your-relay.example/ws", TYPE_STRING)
    _setting(SETTING_ROOM, "godot-room-1", TYPE_STRING)
    _setting(SETTING_ROLE, "target", TYPE_STRING)
    _ensure_project_id()
    _recover_interrupted_file_transactions()
    _build_ui()
    add_control_to_dock(DOCK_SLOT_RIGHT_UL, _panel)
    set_process(true)
    set_process_input(true)

func _exit_tree() -> void:
    if _ws.get_ready_state() != WebSocketPeer.STATE_CLOSED:
        _ws.close()
    if is_instance_valid(_panel):
        remove_control_from_docks(_panel)
        _panel.queue_free()

func _setting(key: String, value: Variant, kind: int) -> void:
    if not ProjectSettings.has_setting(key):
        ProjectSettings.set_setting(key, value)
    ProjectSettings.set_initial_value(key, value)
    ProjectSettings.add_property_info({"name": key, "type": kind})

func _build_ui() -> void:
    _panel = VBoxContainer.new()
    _panel.name = "Live Link"
    _panel.custom_minimum_size = Vector2(300, 0)
    var title := Label.new()
    title.text = "Live Link · editor remoto experimental"
    title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    _panel.add_child(title)
    var project_label := Label.new()
    project_label.text = "Identificación del proyecto"
    project_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    _panel.add_child(project_label)
    var reveal_button := Button.new()
    reveal_button.text = "1. Revelar código identificador"
    reveal_button.pressed.connect(_reveal_project_code)
    _panel.add_child(reveal_button)
    _project_code_label = Label.new()
    _project_code_label.text = ""
    _project_code_label.visible = false
    _project_code_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    _panel.add_child(_project_code_label)
    var copy_button := Button.new()
    copy_button.text = "Copiar código"
    copy_button.pressed.connect(_copy_project_code)
    copy_button.disabled = true
    copy_button.name = "CopyProjectCodeButton"
    _panel.add_child(copy_button)
    _enable_button = Button.new()
    _enable_button.text = "2. Habilitar conexión (sin activarla)"
    _enable_button.disabled = true
    _enable_button.pressed.connect(_enable_connection)
    _panel.add_child(_enable_button)
    _url = LineEdit.new()
    _url.text = str(ProjectSettings.get_setting(SETTING_URL))
    _url.placeholder_text = "wss://servidor/ws"
    _panel.add_child(_field("Relay seguro (WSS)", _url))
    _room = LineEdit.new()
    _room.text = str(ProjectSettings.get_setting(SETTING_ROOM))
    _panel.add_child(_field("Sala privada", _room))
    _token = LineEdit.new()
    _token.secret = true
    var settings := EditorInterface.get_editor_settings()
    if settings.has_setting(SETTING_TOKEN):
        _token.text = str(settings.get_setting(SETTING_TOKEN))
    else:
        _token.text = OS.get_environment("LIVE_LINK_TOKEN")
    _panel.add_child(_field("Token compartido", _token))
    _role = OptionButton.new()
    _role.add_item("Este editor comparte pantalla", 0)
    _role.add_item("Este editor controla al remoto", 1)
    _role.select(1 if str(ProjectSettings.get_setting(SETTING_ROLE)) == "controller" else 0)
    _panel.add_child(_field("Modo", _role))
    _connect_button = Button.new()
    _connect_button.text = "3. Activar conexión"
    _connect_button.disabled = true
    _connect_button.pressed.connect(_connect_clicked)
    _panel.add_child(_connect_button)
    _status = Label.new()
    _status.text = "Desconectado"
    _status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    _panel.add_child(_status)
    _screen = TextureRect.new()
    _screen.custom_minimum_size = Vector2(300, 430)
    _screen.size_flags_vertical = Control.SIZE_EXPAND_FILL
    _screen.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    _screen.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
    _screen.mouse_filter = Control.MOUSE_FILTER_STOP
    _screen.focus_mode = Control.FOCUS_ALL
    _screen.gui_input.connect(_screen_input)
    _panel.add_child(_screen)
    var note := Label.new()
    note.text = "El código identifica este proyecto, pero no es una contraseña. Para evitar servicios externos, puedes alojar relay/server.py en un equipo de tu misma Wi-Fi y usar ws://IP_PRIVADA:8765/ws con el mismo token. WS de LAN no está cifrado: nunca lo expongas a Internet. Para conexiones remotas usa WSS. El cliente de ChatGPT aún requiere una integración externa."
    note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    _panel.add_child(note)

    _approval_dialog = ConfirmationDialog.new()
    _approval_dialog.title = "Confirmar cambio remoto"
    _approval_dialog.ok_button_text = "Aplicar cambio"
    _approval_dialog.cancel_button_text = "Rechazar"
    _approval_dialog.confirmed.connect(_approve_pending_project_operation)
    _approval_dialog.canceled.connect(_reject_pending_project_operation)
    add_child(_approval_dialog)

func _field(caption: String, control: Control) -> Control:
    var box := VBoxContainer.new()
    var label := Label.new()
    label.text = caption
    box.add_child(label)
    box.add_child(control)
    return box

func _reveal_project_code() -> void:
    # Cada revelado crea un identificador nuevo. Así dos copias de un proyecto
    # no conservan accidentalmente el mismo destino. El ID no es un secreto.
    if _connected or _connecting:
        _status.text = "Desconecta primero para generar un nuevo código."
        return
    var crypto := Crypto.new()
    var project_id := crypto.generate_random_bytes(16).hex_encode()
    ProjectSettings.set_setting(SETTING_PROJECT_ID, project_id)
    if ProjectSettings.save() != OK:
        _status.text = "No se pudo guardar el identificador del proyecto."
        return
    _connection_enabled = false
    _code_copied = false
    _connect_button.disabled = true
    _enable_button.disabled = true
    _project_code_label.text = "Código de este proyecto: " + project_id
    _project_code_label.visible = true
    for child in _panel.find_children("CopyProjectCodeButton", "Button", true, false):
        child.disabled = false
    _status.text = "Código nuevo revelado. Cópialo y compártelo para identificar este destino."




func _copy_project_code() -> void:
    var project_id := str(ProjectSettings.get_setting(SETTING_PROJECT_ID, ""))
    if not project_id.is_empty():
        DisplayServer.clipboard_set(project_id)
        _code_copied = true
        _enable_button.disabled = false
        _status.text = "Código copiado. Ahora puedes habilitar la conexión; todavía no está activa."


func _enable_connection() -> void:
    if not _code_copied:
        _status.text = "Primero copia el código y compártelo en el chat."
        return
    _connection_enabled = true
    _connect_button.disabled = false
    _enable_button.disabled = true
    _status.text = "Conexión habilitada, pero todavía desconectada. Pulsa «Activar conexión» cuando estés listo."



func _valid_port(match: RegExMatch, port_group: int) -> bool:
    var port_text := match.get_string(port_group)
    if port_text.is_empty():
        return true
    var port := int(port_text)
    return port >= 1 and port <= 65535


func _is_private_ipv4(host: String) -> bool:
    var parts := host.split(".")
    if parts.size() != 4:
        return false
    var octets: Array[int] = []
    for part in parts:
        if part.is_empty() or not part.is_valid_int() or (part.length() > 1 and part.begins_with("0")):
            return false
        var octet := int(part)
        if octet < 0 or octet > 255:
            return false
        octets.append(octet)
    return octets[0] == 10 or (octets[0] == 192 and octets[1] == 168) or (octets[0] == 172 and octets[1] >= 16 and octets[1] <= 31)


func _is_valid_dns_host(host: String) -> bool:
    if host.is_empty() or host.length() > 253 or host.begins_with(".") or host.ends_with("."):
        return false
    var labels := host.split(".")
    for label in labels:
        if label.is_empty() or label.length() > 63 or label.begins_with("-") or label.ends_with("-"):
            return false
        for i in range(label.length()):
            var code := label.unicode_at(i)
            var is_letter_or_digit := (code >= 48 and code <= 57) or (code >= 65 and code <= 90) or (code >= 97 and code <= 122)
            if not is_letter_or_digit and code != 45:
                return false
    return true


func _is_allowed_relay_url(url: String) -> bool:
    var local_regex := RegEx.new()
    local_regex.compile("^ws://(127\\.0\\.0\\.1|localhost)(:([0-9]{1,5}))?(/[^\\s]*)?$")
    var local_match = local_regex.search(url)
    if local_match != null:
        return _valid_port(local_match, 3)
    var lan_regex := RegEx.new()
    lan_regex.compile("^ws://((?:10\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3})|(?:192\\.168\\.[0-9]{1,3}\\.[0-9]{1,3})|(?:172\\.(?:1[6-9]|2[0-9]|3[0-1])\\.[0-9]{1,3}\\.[0-9]{1,3}))(:([0-9]{1,5}))?(/[^\\s]*)?$")
    var lan_match = lan_regex.search(url)
    if lan_match != null:
        return _is_private_ipv4(lan_match.get_string(1)) and _valid_port(lan_match, 3)
    var secure_regex := RegEx.new()
    secure_regex.compile("^wss://([A-Za-z0-9.-]+)(:([0-9]{1,5}))?(/[^\\s]*)?$")
    var secure_match = secure_regex.search(url)
    return secure_match != null and _is_valid_dns_host(secure_match.get_string(1)) and _valid_port(secure_match, 3)

func _connect_clicked() -> void:
    if not _connection_enabled:
        _status.text = "Primero revela el código y habilita la conexión."
        return
    var url := _url.text.strip_edges()
    var room := _room.text.strip_edges()
    var token := _token.text
    if not _is_allowed_relay_url(url):
        _status.text = "URL no válida: usa WSS remoto o WS solo para localhost/IP privada de LAN con puerto válido."
        return
    var room_regex := RegEx.new()
    room_regex.compile("^[A-Za-z0-9_.:-]{1,80}$")
    if room_regex.search(room) == null:
        _status.text = "Sala no válida. Usa letras, números, guion bajo, punto, dos puntos o guion."
        return
    if token.is_empty():
        _status.text = "Falta el token."
        return
    ProjectSettings.set_setting(SETTING_URL, url)
    ProjectSettings.set_setting(SETTING_ROOM, room)
    ProjectSettings.set_setting(SETTING_ROLE, "controller" if _role.selected == 1 else "target")
    ProjectSettings.save()
    var settings := EditorInterface.get_editor_settings()
    settings.set_setting(SETTING_TOKEN, token)
    settings.save()
    if _ws.get_ready_state() != WebSocketPeer.STATE_CLOSED:
        _ws.close()
    _ws = WebSocketPeer.new()
    _connected = false
    _connecting = true
    _join = {"type":"join", "room":room, "role":str(ProjectSettings.get_setting(SETTING_ROLE)), "token":token}
    var err := _ws.connect_to_url(url)
    if err != OK:
        _connecting = false
        _join.clear()
        _status.text = "Error de conexión: " + error_string(err)
        return
    _status.text = "Conectando…"

func _process(_delta: float) -> void:
    if _ws.get_ready_state() == WebSocketPeer.STATE_CLOSED:
        if _connecting or _connected:
            _connecting = false
            _connected = false
            _join.clear()
            _status.text = "Conexión cerrada o rechazada por el relay. Revisa URL, token y sala; pulsa Conectar para reintentar."
        return
    _ws.poll()
    if _ws.get_ready_state() == WebSocketPeer.STATE_OPEN and not _join.is_empty():
        _ws.send_text(JSON.stringify(_join))
        _join.clear()
    while _ws.get_available_packet_count() > 0:
        var data: Variant = JSON.parse_string(_ws.get_packet().get_string_from_utf8())
        if data is Dictionary:
            _message(data)
    if not _connected or _ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
        return
    if _is_target() and Time.get_ticks_msec() - _last_frame >= FRAME_MS:
        _last_frame = Time.get_ticks_msec()
        _send_frame()

func _message(data: Dictionary) -> void:
    match str(data.get("type", "")):
        "joined":
            _connecting = false
            _connected = true
            _status.text = "Conectado a sala " + str(data.get("room", ""))
        "peer_joined":
            _status.text = "Editor remoto conectado."
        "peer_left":
            _status.text = "Editor remoto desconectado."
        "screen_frame":
            if _is_controller():
                _show_frame(data)
        "remote_input":
            if _is_target() and str(data.get("from_role", "")) == "controller":
                _dispatch(data.get("event", {}))
        "project_operation":
            if _is_target() and str(data.get("from_role", "")) == "agent":
                _apply_project_operation(data)


func _ensure_project_id() -> void:
    var current := str(ProjectSettings.get_setting(SETTING_PROJECT_ID, ""))
    var valid := RegEx.new()
    valid.compile("^[a-fA-F0-9-]{16,64}$")
    if valid.search(current) == null:
        var crypto := Crypto.new()
        current = crypto.generate_random_bytes(16).hex_encode()
        ProjectSettings.set_setting(SETTING_PROJECT_ID, current)
        ProjectSettings.save()


func _safe_relative_path(value: Variant) -> bool:
    if not value is String:
        return false
    var path := str(value)
    if path.is_empty() or path.length() > 1024 or path.begins_with("/") or path.contains("\\") or path.contains(":"):
        return false
    var parts := path.split("/", true)
    if parts.is_empty():
        return false
    for part in parts:
        if part.is_empty() or part == "." or part == ".." or part.to_lower() == ".git" or part.to_lower() == ".godot":
            return false
    return true


func _project_absolute_path(relative_path: String) -> String:
    var root := ProjectSettings.globalize_path("res://").simplify_path().trim_suffix("/")
    var absolute := (root.path_join(relative_path)).simplify_path()
    if not absolute.begins_with(root + "/"):
        return ""
    var current := root
    for part in relative_path.split("/", false):
        current = current.path_join(part)
        # Check the directory entry itself, not only whether its target exists.
        # A dangling symlink can make file_exists/dir_exists return false while
        # still occupying this path; reject links before any read/write/rename.
        var parent_dir := DirAccess.open(current.get_base_dir())
        if parent_dir != null and parent_dir.is_link(current.get_file()):
            return ""
    return absolute


func _sha256_bytes(bytes: PackedByteArray) -> String:
    var context := HashingContext.new()
    if context.start(HashingContext.HASH_SHA256) != OK:
        return ""
    if context.update(bytes) != OK:
        return ""
    return context.finish().hex_encode()


func _transaction_journal_path() -> String:
    var project_id := str(ProjectSettings.get_setting(SETTING_PROJECT_ID, ""))
    return BACKUP_ROOT.path_join(project_id).path_join("active_transaction.json")


func _clear_transaction_journal() -> void:
    var journal := _transaction_journal_path()
    if FileAccess.file_exists(journal):
        DirAccess.remove_absolute(ProjectSettings.globalize_path(journal))


func _write_transaction_journal(original_path: String, rollback_path: String, temp_path: String, backup_path: String) -> bool:
    var journal := _transaction_journal_path()
    if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(journal.get_base_dir())) != OK:
        return false
    var file := FileAccess.open(journal, FileAccess.WRITE)
    if file == null:
        return false
    file.store_string(JSON.stringify({
        "original": original_path,
        "rollback": rollback_path,
        "temporary": temp_path,
        "backup": ProjectSettings.globalize_path(backup_path) if not backup_path.is_empty() else ""
    }))
    file.flush()
    var write_error := file.get_error()
    file.close()
    return write_error == OK


func _recover_interrupted_file_transactions() -> void:
    # One journal per project avoids recursively scanning large mobile projects on startup.
    var journal := _transaction_journal_path()
    if not FileAccess.file_exists(journal):
        return
    var file := FileAccess.open(journal, FileAccess.READ)
    if file == null:
        push_error("Live Link could not read its recovery journal.")
        return
    var parsed: Variant = JSON.parse_string(file.get_as_text())
    file.close()
    if not parsed is Dictionary:
        push_error("Live Link recovery journal is invalid; leaving it for manual inspection.")
        return
    var root := ProjectSettings.globalize_path("res://").simplify_path().trim_suffix("/") + "/"
    var original := str(parsed.get("original", ""))
    var rollback := str(parsed.get("rollback", ""))
    var temporary := str(parsed.get("temporary", ""))
    var backup := str(parsed.get("backup", ""))
    var relative_original := original.trim_prefix(root)
    var backup_root := ProjectSettings.globalize_path(BACKUP_ROOT.path_join(str(ProjectSettings.get_setting(SETTING_PROJECT_ID, "")))).simplify_path().trim_suffix("/") + "/"
    if not _safe_relative_path(relative_original) or not rollback.begins_with(original + ".live_link_rollback_") or not temporary.begins_with(original + ".live_link_tmp_") or (not backup.is_empty() and not backup.begins_with(backup_root)):
        push_error("Live Link recovery journal paths failed validation; leaving it for manual inspection.")
        return
    if FileAccess.file_exists(rollback):
        if not FileAccess.file_exists(original) and not DirAccess.dir_exists_absolute(original):
            if DirAccess.rename_absolute(rollback, original) != OK:
                if backup.is_empty() or not FileAccess.file_exists(backup) or DirAccess.copy_absolute(backup, original) != OK:
                    push_error("Live Link could not restore interrupted replacement: " + original)
                    return
                DirAccess.remove_absolute(rollback)
        else:
            DirAccess.remove_absolute(rollback)
    elif not FileAccess.file_exists(original) and not DirAccess.dir_exists_absolute(original) and not backup.is_empty() and FileAccess.file_exists(backup):
        if DirAccess.copy_absolute(backup, original) != OK:
            push_error("Live Link could not restore file from backup: " + original)
            return
    if FileAccess.file_exists(temporary):
        DirAccess.remove_absolute(temporary)
    _clear_transaction_journal()


func _backup_project_file(absolute_path: String, relative_path: String, operation_id: String) -> String:
    var source := FileAccess.open(absolute_path, FileAccess.READ)
    if source == null:
        return ""
    var bytes := source.get_buffer(source.get_length())
    source.close()
    var safe_id := operation_id.sha256_text().substr(0, 12)
    var backup_relative := str(ProjectSettings.get_setting(SETTING_PROJECT_ID)) + "/" + str(Time.get_unix_time_from_system()) + "_" + safe_id + "/" + relative_path
    var backup_path := BACKUP_ROOT.path_join(backup_relative)
    var backup_absolute := ProjectSettings.globalize_path(backup_path)
    var parent := backup_absolute.get_base_dir()
    if DirAccess.make_dir_recursive_absolute(parent) != OK:
        return ""
    var output := FileAccess.open(backup_path, FileAccess.WRITE)
    if output == null:
        return ""
    output.store_buffer(bytes)
    output.flush()
    var write_error := output.get_error()
    output.close()
    if write_error != OK or not FileAccess.file_exists(backup_path):
        return ""
    return backup_path


func _apply_project_operation(data: Dictionary) -> void:
    var project_id := str(ProjectSettings.get_setting(SETTING_PROJECT_ID, ""))
    var op_id := str(data.get("operation_id", ""))
    var operation := str(data.get("operation", ""))
    var relative_path := str(data.get("path", ""))
    var status := "rejected"
    var detail := "Operación inválida."
    if not _pending_project_operation.is_empty():
        detail = "Ya hay una operación esperando aprobación; esta operación no se ha aplicado."
    elif str(data.get("target_platform", "")) != "android_editor" or int(data.get("policy_version", -1)) != 1:
        detail = "La operación no declara la política de compatibilidad Android requerida."
    elif str(data.get("project_id", "")) != project_id:
        detail = "El ID de proyecto no coincide con este proyecto Godot."
    elif op_id.is_empty() or op_id.length() > 100 or not _safe_relative_path(relative_path):
        detail = "ID de operación o ruta no válida."
    elif operation not in ["create", "update", "rename", "delete"]:
        detail = "Tipo de operación no permitido."
    else:
        var absolute_path := _project_absolute_path(relative_path)
        if absolute_path.is_empty():
            detail = "La ruta sale del proyecto o contiene un enlace simbólico."
        else:
            var approval_text := "Proyecto: " + project_id + "\nOperación: " + operation + "\nArchivo: " + relative_path
            if operation == "rename":
                var destination := str(data.get("destination_path", ""))
                if not _safe_relative_path(destination):
                    detail = "La ruta de destino no es válida."
                else:
                    var destination_absolute := _project_absolute_path(destination)
                    if destination_absolute.is_empty():
                        detail = "El destino sale del proyecto o contiene un enlace simbólico."
                    elif FileAccess.file_exists(destination_absolute) or DirAccess.dir_exists_absolute(destination_absolute):
                        detail = "El destino ya existe; no se ha aplicado ningún cambio."
                    else:
                        approval_text += "\nDestino: " + destination
            if operation != "rename" or approval_text.contains("\nDestino: "):
                _pending_project_operation = data.duplicate(true)
                _approval_dialog.dialog_text = approval_text + "\n\nSolo se aplicará si confirmas. Revisa todas las rutas antes de continuar."
                _approval_dialog.popup_centered()
                _status.text = "Esperando aprobación para " + operation + ": " + relative_path
                return
    _send({"type":"project_result", "project_id":project_id, "operation_id":op_id, "status":status, "message":detail})


func _approve_pending_project_operation() -> void:
    if _pending_project_operation.is_empty():
        return
    var data := _pending_project_operation
    _pending_project_operation = {}
    var project_id := str(ProjectSettings.get_setting(SETTING_PROJECT_ID, ""))
    var op_id := str(data.get("operation_id", ""))
    var operation := str(data.get("operation", ""))
    var relative_path := str(data.get("path", ""))
    var status := "rejected"
    var detail := "Operación inválida."
    if str(data.get("project_id", "")) != project_id:
        detail = "El ID de proyecto cambió antes de la aprobación."
    elif not _safe_relative_path(relative_path):
        detail = "La ruta dejó de ser válida."
    else:
        var absolute_path := _project_absolute_path(relative_path)
        if absolute_path.is_empty():
            detail = "La ruta sale del proyecto o contiene un enlace simbólico."
        else:
            status = _apply_validated_operation(data, operation, relative_path, absolute_path)
            detail = "Operación completada." if status == "applied" else "No se aplicó: conflicto, archivo inválido o error de escritura."
    _send({"type":"project_result", "project_id":project_id, "operation_id":op_id, "status":status, "message":detail})
    _status.text = detail


func _reject_pending_project_operation() -> void:
    if _pending_project_operation.is_empty():
        return
    var data := _pending_project_operation
    _pending_project_operation = {}
    _send({"type":"project_result", "project_id":str(ProjectSettings.get_setting(SETTING_PROJECT_ID, "")), "operation_id":str(data.get("operation_id", "")), "status":"rejected", "message":"Operación rechazada por el usuario en Godot."})
    _status.text = "Operación remota rechazada."


func _apply_validated_operation(data: Dictionary, operation: String, relative_path: String, absolute_path: String) -> String:
    var exists := FileAccess.file_exists(absolute_path)
    var base_hash := str(data.get("base_sha256", ""))
    if operation == "create" and exists:
        return "conflict"
    if operation in ["update", "rename", "delete"]:
        if not exists or base_hash.is_empty() or FileAccess.get_sha256(absolute_path).to_lower() != base_hash.to_lower():
            return "conflict"
    if operation == "delete":
        if _backup_project_file(absolute_path, relative_path, str(data.get("operation_id", ""))).is_empty():
            return "failed"
        # Detect edits made after the initial conflict check and backup read.
        if not FileAccess.file_exists(absolute_path) or FileAccess.get_sha256(absolute_path).to_lower() != base_hash.to_lower():
            return "conflict"
        if DirAccess.remove_absolute(absolute_path) != OK:
            return "failed"
        EditorInterface.get_resource_filesystem().scan()
        return "applied"
    if operation == "rename":
        var destination := str(data.get("destination_path", ""))
        if not _safe_relative_path(destination):
            return "rejected"
        var destination_absolute := _project_absolute_path(destination)
        if destination_absolute.is_empty() or FileAccess.file_exists(destination_absolute) or DirAccess.dir_exists_absolute(destination_absolute):
            return "conflict"
        if _backup_project_file(absolute_path, relative_path, str(data.get("operation_id", ""))).is_empty():
            return "failed"
        # Recheck both sides after backup creation to avoid overwriting a concurrent change.
        if not FileAccess.file_exists(absolute_path) or FileAccess.get_sha256(absolute_path).to_lower() != base_hash.to_lower():
            return "conflict"
        destination_absolute = _project_absolute_path(destination)
        if destination_absolute.is_empty() or FileAccess.file_exists(destination_absolute) or DirAccess.dir_exists_absolute(destination_absolute):
            return "conflict"
        if DirAccess.make_dir_recursive_absolute(destination_absolute.get_base_dir()) != OK:
            return "failed"
        if DirAccess.rename_absolute(absolute_path, destination_absolute) != OK:
            return "failed"
        EditorInterface.get_resource_filesystem().scan()
        return "applied"
    var content_text := str(data.get("content_base64", ""))
    var content := Marshalls.base64_to_raw(content_text)
    if content.is_empty() and content_text != "":
        return "rejected"
    if content.size() > MAX_OPERATION_BYTES or _sha256_bytes(content).to_lower() != str(data.get("sha256", "")).to_lower():
        return "rejected"
    var backup_path := ""
    if operation == "update":
        backup_path = _backup_project_file(absolute_path, relative_path, str(data.get("operation_id", "")))
        if backup_path.is_empty():
            return "failed"
    if DirAccess.make_dir_recursive_absolute(absolute_path.get_base_dir()) != OK:
        return "failed"
    var temp_absolute := absolute_path + ".live_link_tmp_" + str(data.get("operation_id", "")).sha256_text().substr(0, 8)
    var temp_file := FileAccess.open(temp_absolute, FileAccess.WRITE)
    if temp_file == null:
        return "failed"
    temp_file.store_buffer(content)
    temp_file.flush()
    var write_error := temp_file.get_error()
    temp_file.close()
    if write_error != OK or FileAccess.get_sha256(temp_absolute).to_lower() != str(data.get("sha256", "")).to_lower():
        DirAccess.remove_absolute(temp_absolute)
        return "failed"
    # Revalidate the target immediately before the transaction to narrow the TOCTOU window.
    if operation == "update":
        if not FileAccess.file_exists(absolute_path) or FileAccess.get_sha256(absolute_path).to_lower() != base_hash.to_lower():
            DirAccess.remove_absolute(temp_absolute)
            return "conflict"
    elif operation == "create" and (FileAccess.file_exists(absolute_path) or DirAccess.dir_exists_absolute(absolute_path)):
        DirAccess.remove_absolute(temp_absolute)
        return "conflict"
    var rollback_absolute := absolute_path + ".live_link_rollback_" + str(data.get("operation_id", "")).sha256_text().substr(0, 8)
    if not _write_transaction_journal(absolute_path, rollback_absolute, temp_absolute, backup_path):
        DirAccess.remove_absolute(temp_absolute)
        return "failed"
    if exists:
        if FileAccess.file_exists(rollback_absolute) or DirAccess.dir_exists_absolute(rollback_absolute):
            DirAccess.remove_absolute(temp_absolute)
            _clear_transaction_journal()
            return "failed"
        # Keep a recoverable sibling instead of deleting the original before install.
        if DirAccess.rename_absolute(absolute_path, rollback_absolute) != OK:
            DirAccess.remove_absolute(temp_absolute)
            _clear_transaction_journal()
            return "failed"
    if DirAccess.rename_absolute(temp_absolute, absolute_path) != OK:
        if exists and (FileAccess.file_exists(rollback_absolute) or DirAccess.dir_exists_absolute(rollback_absolute)):
            if DirAccess.rename_absolute(rollback_absolute, absolute_path) != OK and not backup_path.is_empty():
                DirAccess.copy_absolute(ProjectSettings.globalize_path(backup_path), absolute_path)
        DirAccess.remove_absolute(temp_absolute)
        if FileAccess.file_exists(absolute_path):
            _clear_transaction_journal()
        return "failed"
    if exists and FileAccess.file_exists(rollback_absolute):
        DirAccess.remove_absolute(rollback_absolute)
    _clear_transaction_journal()
    EditorInterface.get_resource_filesystem().scan()
    return "applied"

func _send_frame() -> void:
    var image := get_tree().root.get_texture().get_image()
    if image == null or image.is_empty():
        return
    if image.get_width() > MAX_W or image.get_height() > MAX_H:
        var scale := minf(float(MAX_W) / image.get_width(), float(MAX_H) / image.get_height())
        image.resize(maxi(1, int(image.get_width() * scale)), maxi(1, int(image.get_height() * scale)))
    var jpg := image.save_jpg_to_buffer(0.50)
    if not jpg.is_empty():
        _send({"type":"screen_frame","width":image.get_width(),"height":image.get_height(),"data":Marshalls.raw_to_base64(jpg)})

func _show_frame(data: Dictionary) -> void:
    var raw := Marshalls.base64_to_raw(str(data.get("data", "")))
    var image := Image.new()
    if raw.is_empty() or image.load_jpg_from_buffer(raw) != OK:
        return
    _remote_size = Vector2i(int(data.get("width", image.get_width())), int(data.get("height", image.get_height())))
    var texture := _screen.texture as ImageTexture
    if texture == null or texture.get_size() != Vector2(image.get_size()):
        _screen.texture = ImageTexture.create_from_image(image)
    else:
        texture.update(image)

func _screen_input(event: InputEvent) -> void:
    if not _is_controller() or not _connected or _screen.texture == null:
        return
    var p := Vector2.ZERO
    var kind := ""
    var button := MOUSE_BUTTON_LEFT
    var pressed := false
    var mask := 0
    if event is InputEventMouseMotion:
        p = event.position
        kind = "mouse_motion"
        mask = event.button_mask
    elif event is InputEventMouseButton:
        p = event.position
        kind = "mouse_button"
        button = event.button_index
        pressed = event.pressed
    elif event is InputEventScreenTouch:
        p = event.position
        kind = "mouse_button"
        pressed = event.pressed
    elif event is InputEventScreenDrag:
        p = event.position
        kind = "mouse_motion"
        mask = MOUSE_BUTTON_MASK_LEFT
    else:
        return
    var size := Vector2(_remote_size)
    var scale := minf(_screen.size.x / maxf(1.0, size.x), _screen.size.y / maxf(1.0, size.y))
    var drawn := size * scale
    var mapped := (p - (_screen.size - drawn) * 0.5) / maxf(scale, 0.0001)
    if mapped.x < 0.0 or mapped.y < 0.0 or mapped.x >= size.x or mapped.y >= size.y:
        return
    _send({"type":"remote_input","event":{"kind":kind,"x":mapped.x/size.x,"y":mapped.y/size.y,"button_index":button,"pressed":pressed,"button_mask":mask}})
    _screen.accept_event()

func _input(event: InputEvent) -> void:
    if not _is_controller() or not _connected or not is_instance_valid(_screen) or not _screen.has_focus():
        return
    if event is InputEventKey:
        _send({"type":"remote_input","event":{"kind":"key","keycode":event.keycode,"physical_keycode":event.physical_keycode,"unicode":event.unicode,"pressed":event.pressed,"echo":event.echo,"shift":event.shift_pressed,"ctrl":event.ctrl_pressed,"alt":event.alt_pressed,"meta":event.meta_pressed}})
        get_viewport().set_input_as_handled()

func _dispatch(event: Variant) -> void:
    if not event is Dictionary:
        return
    var kind := str(event.get("kind", ""))
    # Keyboard events have no normalized pointer coordinates. Validate pointer
    # coordinates only for pointer events, otherwise every key event is dropped.
    var pos := Vector2.ZERO
    if kind == "mouse_motion" or kind == "mouse_button":
        var nx := float(event.get("x", -1.0))
        var ny := float(event.get("y", -1.0))
        if not is_finite(nx) or not is_finite(ny) or nx < 0.0 or nx > 1.0 or ny < 0.0 or ny > 1.0:
            return
        var viewport_size := get_tree().root.get_visible_rect().size
        pos = Vector2(nx * viewport_size.x, ny * viewport_size.y)
    match kind:
        "mouse_motion":
            var motion := InputEventMouseMotion.new()
            motion.position = pos
            motion.global_position = pos
            motion.button_mask = int(event.get("button_mask", 0))
            Input.parse_input_event(motion)
        "mouse_button":
            var mouse := InputEventMouseButton.new()
            mouse.position = pos
            mouse.global_position = pos
            mouse.button_index = int(event.get("button_index", MOUSE_BUTTON_LEFT))
            mouse.pressed = bool(event.get("pressed", false))
            Input.parse_input_event(mouse)
        "key":
            var key := InputEventKey.new()
            key.keycode = int(event.get("keycode", 0))
            key.physical_keycode = int(event.get("physical_keycode", 0))
            key.unicode = int(event.get("unicode", 0))
            key.pressed = bool(event.get("pressed", false))
            key.echo = bool(event.get("echo", false))
            key.shift_pressed = bool(event.get("shift", false))
            key.ctrl_pressed = bool(event.get("ctrl", false))
            key.alt_pressed = bool(event.get("alt", false))
            key.meta_pressed = bool(event.get("meta", false))
            Input.parse_input_event(key)

func _is_controller() -> bool:
    return str(ProjectSettings.get_setting(SETTING_ROLE, "target")) == "controller"

func _is_target() -> bool:
    return not _is_controller()

func _send(data: Dictionary) -> void:
    if _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _ws.send_text(JSON.stringify(data))
