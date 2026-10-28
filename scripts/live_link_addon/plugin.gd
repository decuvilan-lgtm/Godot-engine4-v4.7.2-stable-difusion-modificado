@tool
extends EditorPlugin

const SETTING_URL := "live_link/relay_url"
const SETTING_ROOM := "live_link/room"
const SETTING_TOKEN := "live_link/token"
const SETTING_ROLE := "live_link/role"
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
var _connected := false
var _connecting := false
var _join: Dictionary = {}
var _last_frame := 0
var _remote_size := Vector2i(720, 1280)
var _last_pos := Vector2.ZERO

func _enter_tree() -> void:
    _setting(SETTING_URL, "wss://your-relay.example/ws", TYPE_STRING)
    _setting(SETTING_ROOM, "godot-room-1", TYPE_STRING)
    _setting(SETTING_ROLE, "target", TYPE_STRING)
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
    var connect_button := Button.new()
    connect_button.text = "Conectar"
    connect_button.pressed.connect(_connect_clicked)
    _panel.add_child(connect_button)
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
    note.text = "La entrada remota puede ejecutar acciones en el otro editor. Conecta solo equipos propios y usa WSS. Esta opción no comparte archivos ni sustituye el guardado."
    note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    _panel.add_child(note)

func _field(caption: String, control: Control) -> Control:
    var box := VBoxContainer.new()
    var label := Label.new()
    label.text = caption
    box.add_child(label)
    box.add_child(control)
    return box

func _connect_clicked() -> void:
    var url := _url.text.strip_edges()
    var room := _room.text.strip_edges()
    var token := _token.text
    var local_ws_regex := RegEx.new()
    local_ws_regex.compile("^ws://(127\\.0\\.0\\.1|localhost)(:[0-9]{1,5})?(/[^\\s]*)?$")
    var is_local_ws := local_ws_regex.search(url) != null
    if not (url.begins_with("wss://") or is_local_ws):
        _status.text = "Usa WSS; WS solo se permite para localhost exacto."
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
