@tool
extends EditorPlugin

const PLUGIN_PATH := "res://addons/github_sync/plugin.cfg"
const TERRAIN_PLUGIN_PATH := "res://addons/terrain_3d/plugin.cfg"
const MANIFEST_DIR := "github_sync_manifests"
const MAX_TREE_FILES := 6000
const MAX_FILE_BYTES := 256 * 1024 * 1024
const MAX_TOTAL_BYTES := 1024 * 1024 * 1024

var sync_button: Button
var sync_dialog: ConfirmationDialog
var repo_input: LineEdit
var ref_input: LineEdit
var status_label: Label
var preview_dialog: ConfirmationDialog
var preview_label: RichTextLabel
var request: HTTPRequest
var staged_root := "user://github_sync_stage"
var active_repo := ""
var active_ref := ""
var remote_commit_sha := ""
var request_state := ""
var upstream_files: Dictionary = {}
var tree_entries: Dictionary = {}
var pending_downloads: Array[String] = []
var download_index := 0
var staged_bytes := 0
var legacy_baseline := false
var operations: Array[Dictionary] = []
var baseline: Dictionary = {}
var project_root := ""
var project_key := ""

func _enter_tree() -> void:
	project_root = ProjectSettings.globalize_path("res://").trim_suffix("/")
	var key_context := HashingContext.new()
	key_context.start(HashingContext.HASH_SHA256)
	key_context.update(project_root.to_utf8_buffer())
	project_key = key_context.finish().hex_encode().substr(0, 32)
	sync_button = Button.new()
	sync_button.text = "Sincronizar GitHub"
	sync_button.tooltip_text = "Actualizar este proyecto desde un repositorio público de GitHub. No sube archivos."
	sync_button.pressed.connect(_open_sync_dialog)
	add_control_to_container(EditorPlugin.CONTAINER_TOOLBAR, sync_button)
	_build_dialogs()

func _exit_tree() -> void:
	# A dismissed preview or editor shutdown must not leave temporary staging data on the phone.
	_cleanup_staging()
	if request and is_instance_valid(request):
		if request.request_completed.is_connected(_on_incremental_request_completed):
			request.request_completed.disconnect(_on_incremental_request_completed)
		request.queue_free()
	if sync_button:
		remove_control_from_container(EditorPlugin.CONTAINER_TOOLBAR, sync_button)
		sync_button.queue_free()
	if sync_dialog:
		sync_dialog.queue_free()
	if preview_dialog:
		preview_dialog.queue_free()

func _build_dialogs() -> void:
	sync_dialog = ConfirmationDialog.new()
	sync_dialog.title = "Sincronización unidireccional GitHub → proyecto"
	sync_dialog.ok_button_text = "Descargar y comparar"
	var root := VBoxContainer.new()
	root.custom_minimum_size = Vector2(420, 0)
	var info := Label.new()
	info.text = "Solo aplica los archivos de GitHub al proyecto. No crea copias ni sube archivos."
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(info)
	repo_input = LineEdit.new()
	repo_input.placeholder_text = "owner/repository o URL de GitHub"
	repo_input.clear_button_enabled = true
	root.add_child(repo_input)
	ref_input = LineEdit.new()
	ref_input.placeholder_text = "Rama, etiqueta o SHA (vacío = rama predeterminada)"
	ref_input.clear_button_enabled = true
	root.add_child(ref_input)
	status_label = Label.new()
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(status_label)
	sync_dialog.add_child(root)
	add_child(sync_dialog)
	sync_dialog.confirmed.connect(_start_download)

	preview_dialog = ConfirmationDialog.new()
	preview_dialog.title = "Revisar sincronización"
	preview_dialog.ok_button_text = "Aplicar cambios"
	preview_label = RichTextLabel.new()
	preview_label.custom_minimum_size = Vector2(440, 220)
	preview_label.fit_content = true
	preview_dialog.add_child(preview_label)
	add_child(preview_dialog)
	preview_dialog.confirmed.connect(_apply_changes)
	preview_dialog.canceled.connect(_on_preview_dismissed)
	preview_dialog.close_requested.connect(_on_preview_dismissed)

func _open_sync_dialog() -> void:
	status_label.text = "Los cambios locales nunca se suben a GitHub."
	sync_dialog.popup_centered(Vector2i(520, 240))

func _normalize_repository(value: String) -> String:
	var repo := value.strip_edges()
	for prefix in ["https://github.com/", "http://github.com/", "https://www.github.com/", "http://www.github.com/", "github.com/", "www.github.com/"]:
		if repo.begins_with(prefix):
			repo = repo.trim_prefix(prefix)
			break
	repo = repo.trim_suffix("/")
	repo = repo.trim_suffix(".git")
	var parts := repo.split("/", false)
	if parts.size() < 2:
		return ""
	if parts.size() > 2:
		# Accept repository pages such as /tree/main, but never use that suffix as the repository name.
		repo = parts[0] + "/" + parts[1]
		parts = repo.split("/", false)
	if parts.size() != 2 or parts[0].is_empty() or parts[1].is_empty():
		return ""
	var safe := "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
	for ch in parts[0]:
		if not safe.contains(ch) or ch == ".":
			return ""
	for ch in parts[1]:
		if not safe.contains(ch):
			return ""
	return parts[0] + "/" + parts[1]

func _start_download() -> void:
	active_repo = _normalize_repository(repo_input.text)
	active_ref = ref_input.text.strip_edges()
	if active_repo.is_empty():
		status_label.text = "Repositorio inválido. Usa owner/repository o una URL de GitHub."
		sync_dialog.popup_centered()
		return
	if active_ref.contains("..") or active_ref.contains("\\") or active_ref.contains("?") or active_ref.contains("#") or active_ref.begins_with("/"):
		status_label.text = "La referencia contiene caracteres no permitidos."
		sync_dialog.popup_centered()
		return
	if request and is_instance_valid(request):
		request.queue_free()
		request = null
	_cleanup_staging()
	_load_baseline()
	tree_entries.clear()
	upstream_files.clear()
	operations.clear()
	pending_downloads.clear()
	download_index = 0
	staged_bytes = 0
	remote_commit_sha = ""
	request = HTTPRequest.new()
	request.timeout = 90.0
	# GitHub documents a 7 MiB maximum for recursive tree responses; bound JSON in-memory use.
	request.body_size_limit = 8 * 1024 * 1024
	request.download_chunk_size = 16384
	request.request_completed.connect(_on_incremental_request_completed)
	add_child(request)
	status_label.text = "Consultando la referencia de GitHub…"
	if active_ref.is_empty():
		_start_request("repo", "https://api.github.com/repos/%s" % active_repo)
	else:
		_start_request("commit", "https://api.github.com/repos/%s/commits/%s" % [active_repo, active_ref.uri_encode()])

func _start_request(state: String, url: String, destination: String = "") -> void:
	if request == null or not is_instance_valid(request):
		_fail_sync("La solicitud de red dejó de estar disponible.")
		return
	request_state = state
	request.download_file = destination
	# JSON tree responses are capped at 8 MiB; changed file downloads may use the full 256 MiB file budget.
	request.body_size_limit = MAX_FILE_BYTES + 1024 * 1024 if not destination.is_empty() else 8 * 1024 * 1024
	var headers := PackedStringArray(["Accept: application/vnd.github+json", "User-Agent: Godot-GitHub-Sync"])
	var err := request.request(url, headers)
	if err != OK:
		_fail_sync("No se pudo iniciar la solicitud a GitHub (error %d)." % err)

func _incremental_headers() -> PackedStringArray:
	return PackedStringArray(["Accept: application/vnd.github+json", "User-Agent: Godot-GitHub-Sync"])

func _on_incremental_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		_fail_sync("Falló la solicitud a GitHub (HTTP %d, resultado %d). Revisa conexión, referencia o límites de la API." % [response_code, result])
		return
	match request_state:
		"repo":
			var repo_data = JSON.parse_string(body.get_string_from_utf8())
			if not repo_data is Dictionary or not repo_data.has("default_branch"):
				_fail_sync("GitHub no devolvió la rama predeterminada del repositorio.")
				return
			active_ref = str(repo_data.default_branch)
			_start_request("commit", "https://api.github.com/repos/%s/commits/%s" % [active_repo, active_ref.uri_encode()])
		"commit":
			var commit_data = JSON.parse_string(body.get_string_from_utf8())
			if not commit_data is Dictionary or not commit_data.has("sha"):
				_fail_sync("GitHub no devolvió un commit válido para esa referencia.")
				return
			remote_commit_sha = str(commit_data.sha)
			_start_request("tree", "https://api.github.com/repos/%s/git/trees/%s?recursive=1" % [active_repo, remote_commit_sha])
		"tree":
			_process_tree_response(body)
		"file":
			_finish_downloaded_file()
		_:
			_fail_sync("Estado de sincronización desconocido; no se modificó el proyecto.")

func _process_tree_response(body: PackedByteArray) -> void:
	var parsed = JSON.parse_string(body.get_string_from_utf8())
	if not parsed is Dictionary or not parsed.get("tree", null) is Array:
		_fail_sync("GitHub devolvió un árbol de archivos inválido.")
		return
	if bool(parsed.get("truncated", false)):
		_fail_sync("El árbol del repositorio supera el límite de la API. Se canceló para evitar una sincronización incompleta.")
		return
	var entries: Array = parsed.tree
	if entries.size() > MAX_TREE_FILES:
		_fail_sync("El repositorio supera el límite de %d entradas para proteger el teléfono." % MAX_TREE_FILES)
		return
	for entry in entries:
		if not entry is Dictionary or str(entry.get("type", "")) != "blob":
			continue
		var relative := str(entry.get("path", ""))
		if not _is_safe_relative_path(relative) or _is_ignored_path(relative):
			continue
		var blob_sha := str(entry.get("sha", ""))
		var size := int(entry.get("size", -1))
		if blob_sha.length() != 40 or size < 0:
			_fail_sync("GitHub devolvió metadatos inválidos para '%s'." % relative)
			return
		if size > MAX_FILE_BYTES:
			_fail_sync("'%s' supera el límite de %d MiB por archivo." % [relative, MAX_FILE_BYTES / (1024 * 1024)])
			return
		tree_entries[relative] = {"sha": blob_sha, "size": size}
	if not tree_entries.has("project.godot"):
		_fail_sync("El repositorio no contiene project.godot; no parece ser un proyecto Godot válido.")
		return
	_build_incremental_download_queue()
	_download_next_file()

func _is_safe_relative_path(relative: String) -> bool:
	if relative.is_empty() or relative.begins_with("/") or relative.contains("\\"):
		return false
	for segment in relative.split("/"):
		if segment.is_empty() or segment == "." or segment == "..":
			return false
	return true

func _is_ignored_path(relative: String) -> bool:
	return relative == ".DS_Store" or relative.begins_with(".git/") or relative == ".git" or relative.begins_with(".godot/") or relative == ".godot" or relative.begins_with("__MACOSX/") or relative.begins_with("addons/github_sync/") or relative.begins_with("addons/terrain_3d/")

func _build_incremental_download_queue() -> void:
	pending_downloads.clear()
	upstream_files.clear()
	legacy_baseline = false
	for value in baseline.values():
		if str(value).length() == 64:
			legacy_baseline = true
			break
	for relative in tree_entries.keys():
		var metadata: Dictionary = tree_entries[relative]
		var remote_sha := str(metadata.sha)
		upstream_files[relative] = remote_sha
		var local_path := project_root.path_join(relative)
		var local_exists := FileAccess.file_exists(local_path)
		var old_sha := str(baseline.get(relative, ""))
		var needs_legacy_compare := legacy_baseline and not old_sha.is_empty()
		var local_sha := _git_blob_sha1(local_path) if local_exists else ""
		if needs_legacy_compare:
			# Old manifests stored SHA-256, not Git blob IDs. One migration pass downloads
			# tracked files to compare content; successful manifests then use Git blob SHA-1.
			pending_downloads.append(relative)
		elif not local_exists or local_sha != remote_sha:
			if old_sha != remote_sha or not local_exists:
				pending_downloads.append(relative)
	# Only previously tracked files may be deleted; untracked local files are never inferred as upstream deletions.
	for relative in baseline.keys():
		if tree_entries.has(str(relative)):
			continue
		var local_path := project_root.path_join(str(relative))
		if FileAccess.file_exists(local_path):
			var local_hash := FileAccess.get_sha256(local_path)
			operations.append({"kind": "delete", "path": str(relative), "modified": legacy_baseline or local_hash != str(baseline[relative])})
	status_label.text = "Árbol comparado: %d archivos; descargando solo contenido necesario…" % tree_entries.size()

func _download_next_file() -> void:
	if download_index >= pending_downloads.size():
		_finish_incremental_plan()
		return
	var relative := pending_downloads[download_index]
	var metadata: Dictionary = tree_entries[relative]
	staged_bytes += int(metadata.size)
	if staged_bytes > MAX_TOTAL_BYTES:
		_fail_sync("Los archivos que cambiaron superan el límite temporal de %d MiB. No se modificó el proyecto." % (MAX_TOTAL_BYTES / (1024 * 1024)))
		return
	var destination := staged_root.path_join(relative)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(destination).get_base_dir())
	var encoded_parts := PackedStringArray()
	for part in relative.split("/"):
		encoded_parts.append(part.uri_encode())
	var url := "https://raw.githubusercontent.com/%s/%s/%s" % [active_repo, remote_commit_sha, "/".join(encoded_parts)]
	status_label.text = "Descargando %d/%d: %s" % [download_index + 1, pending_downloads.size(), relative]
	_start_request("file", url, destination)

func _finish_downloaded_file() -> void:
	var relative := pending_downloads[download_index]
	var staged_path := staged_root.path_join(relative)
	if not FileAccess.file_exists(staged_path):
		_fail_sync("GitHub no guardó el archivo descargado '%s'." % relative)
		return
	var staged_file := FileAccess.open(staged_path, FileAccess.READ)
	if staged_file == null:
		_fail_sync("No se pudo leer el archivo descargado '%s'." % relative)
		return
	var size := staged_file.get_length()
	staged_file.close()
	var metadata: Dictionary = tree_entries[relative]
	if size != int(metadata.size) or _git_blob_sha1(staged_path) != str(metadata.sha):
		_fail_sync("La verificación del archivo '%s' falló; se canceló la sincronización." % relative)
		return
	if relative == "project.godot":
		var config_error := _ensure_sync_plugin_enabled(staged_path)
		if config_error != OK:
			_fail_sync("No se pudo conservar la configuración de los complementos en project.godot (error %d)." % config_error)
			return
	_plan_downloaded_file(relative, staged_path)
	download_index += 1
	_download_next_file()

func _plan_downloaded_file(relative: String, staged_path: String) -> void:
	var local_path := project_root.path_join(relative)
	var local_exists := FileAccess.file_exists(local_path)
	var old_sha := str(baseline.get(relative, ""))
	var remote_sha := str(tree_entries[relative].sha)
	if not local_exists:
		operations.append({"kind": "add", "path": relative, "modified": false})
		return
	if relative == "project.godot":
		var local_config_hash := FileAccess.get_sha256(local_path)
		var staged_config_hash := FileAccess.get_sha256(staged_path)
		if local_config_hash == staged_config_hash:
			return
		if legacy_baseline and not old_sha.is_empty() and staged_config_hash == old_sha:
			return
		operations.append({"kind": "update", "path": relative, "modified": old_sha.is_empty() or local_config_hash != old_sha})
		return
	var local_sha := _git_blob_sha1(local_path)
	if local_sha == remote_sha:
		return
	if legacy_baseline and not old_sha.is_empty():
		# Legacy manifests store SHA-256 of the last synced bytes. If the upstream bytes
		# are unchanged, preserve local edits instead of rewriting an unchanged file.
		var downloaded_sha256 := FileAccess.get_sha256(staged_path)
		if downloaded_sha256 == old_sha:
			return
		operations.append({"kind": "update", "path": relative, "modified": FileAccess.get_sha256(local_path) != old_sha})
		return
	operations.append({"kind": "update", "path": relative, "modified": old_sha.is_empty() or local_sha != old_sha})

func _finish_incremental_plan() -> void:
	if request and is_instance_valid(request):
		request.queue_free()
		request = null
	_build_change_plan()
	_show_preview()

func _fail_sync(message: String) -> void:
	_log_sync(message, "error")
	if request and is_instance_valid(request):
		if request.request_completed.is_connected(_on_incremental_request_completed):
			request.request_completed.disconnect(_on_incremental_request_completed)
		request.queue_free()
		request = null
	_cleanup_staging()
	operations.clear()
	status_label.text = message
	sync_dialog.popup_centered(Vector2i(520, 240))

func _git_blob_sha1(path: String) -> String:
	if not FileAccess.file_exists(path):
		return ""
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	var size := file.get_length()
	if size > MAX_FILE_BYTES:
		file.close()
		return ""
	var context := HashingContext.new()
	if context.start(HashingContext.HASH_SHA1) != OK:
		file.close()
		return ""
	# Git hashes a blob as: "blob <byte-count>\\0" + file bytes.
	context.update(("blob %d" % size).to_utf8_buffer() + PackedByteArray([0]))
	while file.get_position() < size:
		var remaining := size - file.get_position()
		context.update(file.get_buffer(mini(remaining, 65536)))
	file.close()
	return context.finish().hex_encode()

func _ensure_sync_plugin_enabled(config_path: String) -> int:
	var config := ConfigFile.new()
	var err := config.load(config_path)
	if err != OK:
		return err
	# Preserve the display name chosen during import while accepting upstream project settings.
	var local_config := ConfigFile.new()
	if local_config.load(project_root.path_join("project.godot")) == OK and local_config.has_section_key("application", "config/name"):
		config.set_value("application", "config/name", local_config.get_value("application", "config/name"))
	var enabled: PackedStringArray = config.get_value("editor_plugins", "enabled", PackedStringArray())
	var changed := false
	if not enabled.has(PLUGIN_PATH):
		enabled.append(PLUGIN_PATH)
		changed = true
	if not enabled.has(TERRAIN_PLUGIN_PATH):
		enabled.append(TERRAIN_PLUGIN_PATH)
		changed = true
	if changed:
		config.set_value("editor_plugins", "enabled", enabled)
		return config.save(config_path)
	return OK

func _manifest_path() -> String:
	return "user://%s/%s.json" % [MANIFEST_DIR, project_key]

func _load_baseline() -> void:
	baseline = {}
	legacy_baseline = false
	var path := _manifest_path()
	if not FileAccess.file_exists(path):
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if parsed is Dictionary and parsed.get("files", null) is Dictionary and str(parsed.get("repository", "")) == active_repo:
		baseline = parsed.files
		for value in baseline.values():
			if str(value).length() == 64:
				legacy_baseline = true
				break

func _build_change_plan() -> void:
	# Deletions were planned from the prior successful manifest before downloading.
	# Keep only paths whose old manifest entry was present and which still exist locally.
	for relative in baseline.keys():
		if tree_entries.has(str(relative)):
			continue
		var local_path := project_root.path_join(str(relative))
		if FileAccess.file_exists(local_path):
			var already_planned := false
			for operation in operations:
				if operation.kind == "delete" and str(operation.path) == str(relative):
					already_planned = true
					break
			if not already_planned:
				operations.append({"kind": "delete", "path": str(relative), "modified": true})


func _show_preview() -> void:
	var adds := 0
	var updates := 0
	var deletes := 0
	var lines := PackedStringArray()
	for operation in operations:
		match operation.kind:
			"add":
				adds += 1
			"update":
				updates += 1
			"delete":
				deletes += 1
		if lines.size() < 80:
			var marker := "A" if operation.kind == "add" else ("D" if operation.kind == "delete" else "U")
			lines.append("%s  %s%s" % [marker, operation.path, "  [se reemplazará]" if operation.modified else ""])
	var summary := "Repositorio: %s\nReferencia: %s\n\nAñadir: %d   Actualizar: %d   Eliminar: %d\nLos archivos del repositorio reemplazarán sus versiones locales cuando corresponda.\n\n" % [active_repo, active_ref if not active_ref.is_empty() else "(rama predeterminada)", adds, updates, deletes]
	summary += "\n".join(lines)
	summary += "\n\nLas escenas .tscn se actualizan en su misma ruta; no se crean escenas duplicadas. Las conexiones serializadas en la versión de GitHub se conservan tal cual."
	if operations.size() > lines.size():
		summary += "\n… y %d cambios más." % (operations.size() - lines.size())
	if operations.is_empty():
		summary += "\nEl proyecto ya coincide con el repositorio."
		# Remember the latest repository/ref even when no writes are required.
		if not _save_manifest():
			summary += "\nAviso: no se pudo actualizar el historial local de sincronización."
		_cleanup_staging()
		preview_dialog.ok_button_text = "Cerrar"
		preview_dialog.get_ok_button().disabled = true
	else:
		preview_dialog.ok_button_text = "Aplicar cambios"
		preview_dialog.get_ok_button().disabled = false
	preview_label.text = summary
	preview_dialog.popup_centered(Vector2i(540, 420))

func _on_preview_dismissed() -> void:
	# The user may close the preview without applying. No staged duplicate files should remain.
	_cleanup_staging()
	operations.clear()

func _apply_changes() -> void:
	if operations.is_empty():
		return
	var possible_moves := _detect_possible_moves()
	_log_sync("Aplicando %d operaciones desde %s @ %s." % [operations.size(), active_repo, remote_commit_sha])
	for operation in operations:
		var relative: String = operation.path
		var local_path := project_root.path_join(relative)
		var operation_error := OK
		var connection_change := ""
		if operation.kind == "delete":
			operation_error = DirAccess.remove_absolute(local_path)
			if operation_error == OK:
				if possible_moves.has(relative):
					_log_sync("POSIBLE MOVIMIENTO/RENOMBRE: '%s' → '%s' (se elimina la ruta anterior y se instala la nueva)." % [relative, str(possible_moves[relative])])
				else:
					_log_sync("ELIMINADO: '%s' ya no existe en el repositorio." % relative)
		else:
			var staged_path := staged_root.path_join(relative)
			DirAccess.make_dir_recursive_absolute(local_path.get_base_dir())
			var incoming_connections := PackedStringArray()
			if relative.ends_with(".tscn") and FileAccess.file_exists(local_path):
				var previous_connections := _read_scene_connections(local_path)
				incoming_connections = _read_scene_connections(staged_path)
				if previous_connections != incoming_connections:
					connection_change = "CONEXIONES CAMBIADAS (%d antes, %d después)" % [previous_connections.size(), incoming_connections.size()]
			operation_error = _copy_file_streaming(staged_path, local_path)
			if operation_error == OK:
				if operation.kind == "add":
					var move_source := ""
					for old_path in possible_moves:
						if str(possible_moves[old_path]) == relative:
							move_source = str(old_path)
							break
					if not move_source.is_empty():
						_log_sync("AÑADIDO como posible movimiento: '%s' (origen: '%s')." % [relative, move_source])
					else:
						_log_sync("AÑADIDO: '%s'." % relative)
				else:
					_log_sync("SOBRESCRITO: '%s' en su ruta original." % relative)
				if relative.ends_with(".tscn"):
					if not connection_change.is_empty():
						_log_sync("%s en '%s'; revisa las conexiones en el editor/Debugger." % [connection_change, relative], "warning")
					else:
						_log_sync("Conexiones de '%s': sin cambios (%d conexiones serializadas)." % [relative, incoming_connections.size()])
		if operation_error != OK:
			_log_sync("Falló la aplicación de '%s' (error %d)." % [relative, operation_error], "error")
			_cleanup_staging()
			_show_error("Falló la aplicación de '%s' (error %d). No se crearon copias. Vuelve a sincronizar para aplicar de nuevo los archivos de GitHub." % [relative, operation_error])
			return
	if not _save_manifest():
		_cleanup_staging()
		_show_error("Los archivos se aplicaron, pero no se pudo actualizar el historial. Vuelve a sincronizar para recalcular los cambios.")
		return
	_cleanup_staging()
	EditorInterface.get_resource_filesystem().scan()
	_log_sync("Sincronización completada: %d operaciones aplicadas; temporales eliminados." % operations.size())
	_show_notice("Sincronización completada. Se aplicaron los cambios de GitHub directamente; los temporales se eliminaron y no se subió ningún archivo.")

func _detect_possible_moves() -> Dictionary:
	var deleted_by_sha: Dictionary = {}
	var moves: Dictionary = {}
	for operation in operations:
		if operation.kind == "delete":
			var old_sha := str(baseline.get(str(operation.path), ""))
			if not old_sha.is_empty():
				deleted_by_sha[old_sha] = str(operation.path)
	for operation in operations:
		if operation.kind != "add":
			continue
		var new_sha := str(upstream_files.get(str(operation.path), ""))
		if not new_sha.is_empty() and deleted_by_sha.has(new_sha):
			var old_path := str(deleted_by_sha[new_sha])
			if old_path != str(operation.path):
				moves[old_path] = str(operation.path)
				deleted_by_sha.erase(new_sha)
	return moves

func _read_scene_connections(scene_path: String) -> PackedStringArray:
	var connections := PackedStringArray()
	if not scene_path.ends_with(".tscn") or not FileAccess.file_exists(scene_path):
		return connections
	var file := FileAccess.open(scene_path, FileAccess.READ)
	if file == null:
		return connections
	while not file.eof_reached():
		var line := file.get_line().strip_edges()
		if line.begins_with("[connection "):
			connections.append(line)
	file.close()
	connections.sort()
	return connections

func _log_sync(message: String, severity: String = "info") -> void:
	var formatted := "[GitHub Sync] " + message
	match severity:
		"warning":
			push_warning(formatted)
		"error":
			push_error(formatted)
		_:
			print(formatted)

func _copy_file_streaming(source_path: String, destination_path: String) -> int:
	var source := FileAccess.open(source_path, FileAccess.READ)
	if source == null:
		return FileAccess.get_open_error()
	var expected_size := source.get_length()
	var destination := FileAccess.open(destination_path, FileAccess.WRITE)
	if destination == null:
		var open_error := FileAccess.get_open_error()
		source.close()
		return open_error
	while source.get_position() < expected_size:
		var chunk := source.get_buffer(mini(65536, expected_size - source.get_position()))
		if chunk.is_empty():
			destination.close()
			source.close()
			return FAILED
		destination.store_buffer(chunk)
		if destination.get_error() != OK:
			destination.close()
			source.close()
			return FAILED
	destination.close()
	source.close()
	return OK


func _cleanup_staging() -> void:
	_remove_tree(staged_root)

func _save_manifest() -> bool:
	var folder := "user://%s" % MANIFEST_DIR
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(folder))
	var file := FileAccess.open(_manifest_path(), FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify({
		"schema": 2,
		"repository": active_repo,
		"ref": active_ref,
		"commit": remote_commit_sha,
		"files": upstream_files
	}, "\t"))
	var save_error := file.get_error()
	file.close()
	return save_error == OK



func _sha256(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return context.finish().hex_encode()

func _remove_tree(path: String) -> void:
	var directory := DirAccess.open(path)
	if directory == null:
		return
	directory.list_dir_begin()
	var name := directory.get_next()
	while not name.is_empty():
		if name != "." and name != "..":
			var child := path.path_join(name)
			if directory.current_is_dir():
				_remove_tree(child)
				DirAccess.remove_absolute(ProjectSettings.globalize_path(child))
			else:
				DirAccess.remove_absolute(ProjectSettings.globalize_path(child))
		name = directory.get_next()
	directory.list_dir_end()

func _show_error(message: String) -> void:
	_log_sync(message, "error")
	var dialog := AcceptDialog.new()
	dialog.title = "Error de sincronización"
	dialog.dialog_text = message
	add_child(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()

func _show_notice(message: String) -> void:
	_log_sync(message)
	var dialog := AcceptDialog.new()
	dialog.title = "Sincronización de GitHub"
	dialog.dialog_text = message
	add_child(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()
