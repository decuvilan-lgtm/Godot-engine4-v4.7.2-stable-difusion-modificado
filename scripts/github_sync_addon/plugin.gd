@tool
extends EditorPlugin

const PLUGIN_PATH := "res://addons/github_sync/plugin.cfg"
const TERRAIN_PLUGIN_PATH := "res://addons/terrain_3d/plugin.cfg"
const MANIFEST_DIR := "github_sync_manifests"
const STAGE_DIR := "github_sync_stage"
const RESCUE_DIR := "github_sync_rescue"

var sync_button: Button
var sync_dialog: ConfirmationDialog
var repo_input: LineEdit
var ref_input: LineEdit
var status_label: Label
var preview_dialog: ConfirmationDialog
var preview_label: RichTextLabel
var request: HTTPRequest
var zip_path := "user://github_sync_download.zip"
var staged_root := "user://github_sync_stage"
var active_repo := ""
var active_ref := ""
var upstream_files: Dictionary = {}
var operations: Array[Dictionary] = []
var baseline: Dictionary = {}
var project_root := ""
var project_key := ""

func _enter_tree() -> void:
	project_root = ProjectSettings.globalize_path("res://").trim_suffix("/")
	project_key = str(hash(project_root))
	sync_button = Button.new()
	sync_button.text = "Sincronizar GitHub"
	sync_button.tooltip_text = "Actualizar este proyecto desde un repositorio público de GitHub. No sube archivos."
	sync_button.pressed.connect(_open_sync_dialog)
	add_control_to_container(EditorPlugin.CONTAINER_TOOLBAR, sync_button)
	_build_dialogs()

func _exit_tree() -> void:
	if request and is_instance_valid(request):
		request.request_completed.disconnect(_on_zip_downloaded)
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
	info.text = "Solo lee GitHub. Antes de escribir muestra los cambios; los archivos locales modificados se rescatan fuera del proyecto."
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
	request = HTTPRequest.new()
	request.timeout = 90.0
	request.download_file = zip_path
	add_child(request)
	request.request_completed.connect(_on_zip_downloaded)
	var url := "https://api.github.com/repos/%s/zipball" % active_repo
	if not active_ref.is_empty():
		url += "/" + active_ref.uri_encode()
	var headers := PackedStringArray(["Accept: application/vnd.github+json", "User-Agent: Godot-GitHub-Sync"])
	var err := request.request(url, headers)
	if err != OK:
		request.queue_free()
		request = null
		status_label.text = "No se pudo iniciar la descarga (error %d)." % err
		sync_dialog.popup_centered()

func _on_zip_downloaded(result: int, response_code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	if request:
		request.queue_free()
		request = null
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200 or not FileAccess.file_exists(zip_path):
		status_label.text = "GitHub no entregó el ZIP (HTTP %d). Revisa conexión, repositorio y referencia." % response_code
		sync_dialog.popup_centered()
		return
	var err := _stage_archive()
	if err != OK:
		status_label.text = "No se pudo preparar el ZIP (error %d). No se modificó el proyecto." % err
		sync_dialog.popup_centered()
		return
	_build_change_plan()
	_show_preview()

func _stage_archive() -> int:
	var zip := ZIPReader.new()
	var err := zip.open(zip_path)
	if err != OK:
		return err
	var entries := zip.get_files()
	if entries.is_empty():
		zip.close()
		return ERR_FILE_CORRUPT
	var archive_root := entries[0].get_slice("/", 0)
	var stage_absolute := ProjectSettings.globalize_path(staged_root)
	DirAccess.make_dir_recursive_absolute(stage_absolute)
	_remove_tree(staged_root)
	DirAccess.make_dir_recursive_absolute(stage_absolute)
	upstream_files.clear()
	for entry in entries:
		if entry.ends_with("/"):
			continue
		var relative := entry.trim_prefix(archive_root + "/")
		if relative == entry:
			relative = entry
		if relative.is_empty() or relative.begins_with("/") or relative.contains("\\"):
			continue
		var invalid := false
		for segment in relative.split("/"):
			if segment == ".." or segment == "." or segment.is_empty():
				invalid = true
				break
		if invalid or relative.begins_with(".git/") or relative.begins_with(".godot/") or relative.begins_with("__MACOSX/"):
			continue
		if relative == ".DS_Store":
			continue
		var bytes := zip.read_file(entry)
		if bytes.is_empty() and zip.get_files().has(entry):
			# Empty source files are valid; the write below preserves them.
			pass
		var target := staged_root.path_join(relative)
		var target_abs := ProjectSettings.globalize_path(target)
		DirAccess.make_dir_recursive_absolute(target_abs.get_base_dir())
		var file := FileAccess.open(target, FileAccess.WRITE)
		if file == null:
			zip.close()
			return FileAccess.get_open_error()
		file.store_buffer(bytes)
		file.close()
		# Keep the injected editor plugin out of the upstream manifest so a sync cannot overwrite itself.
		if not relative.begins_with("addons/github_sync/") and not relative.begins_with("addons/terrain_3d/"):
			upstream_files[relative] = _sha256(bytes)
	zip.close()
	if not upstream_files.has("project.godot"):
		return ERR_FILE_MISSING_DEPENDENCIES
	# Keep the sync plugin enabled when upstream changes project.godot. Hash the normalized staged
	# config so the plugin's own enabled entry does not appear as a local conflict on every sync.
	var staged_project := staged_root.path_join("project.godot")
	var config_err := _ensure_sync_plugin_enabled(staged_project)
	if config_err != OK:
		return config_err
	upstream_files["project.godot"] = FileAccess.get_sha256(staged_project)
	return OK

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
	var path := _manifest_path()
	if not FileAccess.file_exists(path):
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if parsed is Dictionary and parsed.get("files", null) is Dictionary:
		baseline = parsed.files

func _build_change_plan() -> void:
	_load_baseline()
	operations.clear()
	for relative in upstream_files.keys():
		var local_path := project_root.path_join(relative)
		var local_exists := FileAccess.file_exists(local_path)
		var local_hash := FileAccess.get_sha256(local_path) if local_exists else ""
		var old_hash := str(baseline.get(relative, ""))
		var new_hash := str(upstream_files[relative])
		if not local_exists:
			operations.append({"kind": "add", "path": relative, "modified": false})
		elif local_hash != new_hash:
			operations.append({"kind": "update", "path": relative, "modified": old_hash.is_empty() or local_hash != old_hash})
	# Deletion is allowed only for files tracked by a previous successful sync.
	for relative in baseline.keys():
		if upstream_files.has(relative):
			continue
		var local_path := project_root.path_join(str(relative))
		if FileAccess.file_exists(local_path):
			var local_hash := FileAccess.get_sha256(local_path)
			operations.append({"kind": "delete", "path": str(relative), "modified": local_hash != str(baseline[relative])})

func _show_preview() -> void:
	var adds := 0
	var updates := 0
	var deletes := 0
	var rescued := 0
	var lines := PackedStringArray()
	for operation in operations:
		match operation.kind:
			"add":
				adds += 1
			"update":
				updates += 1
			"delete":
				deletes += 1
		if operation.modified:
			rescued += 1
		if lines.size() < 80:
			var marker := "A" if operation.kind == "add" else ("D" if operation.kind == "delete" else "U")
			lines.append("%s  %s%s" % [marker, operation.path, "  [copia de rescate]" if operation.modified else ""])
	var summary := "Repositorio: %s\nReferencia: %s\n\nAñadir: %d   Actualizar: %d   Eliminar: %d\nArchivos locales que se rescatarán fuera del proyecto: %d\n\n" % [active_repo, active_ref if not active_ref.is_empty() else "(rama predeterminada)", adds, updates, deletes, rescued]
	summary += "\n".join(lines)
	if operations.size() > lines.size():
		summary += "\n… y %d cambios más." % (operations.size() - lines.size())
	if operations.is_empty():
		summary += "\nEl proyecto ya coincide con el repositorio."
		preview_dialog.ok_button_text = "Cerrar"
		preview_dialog.get_ok_button().disabled = true
	else:
		preview_dialog.ok_button_text = "Aplicar cambios"
		preview_dialog.get_ok_button().disabled = false
	preview_label.text = summary
	preview_dialog.popup_centered(Vector2i(540, 420))

func _apply_changes() -> void:
	if operations.is_empty():
		return
	var stamp := Time.get_datetime_string_from_system().replace(":", "-").replace(" ", "_")
	var rescue_root := OS.get_user_data_dir().path_join(RESCUE_DIR).path_join(project_key).path_join(stamp)
	var transaction_root := OS.get_user_data_dir().path_join("github_sync_transactions").path_join(project_key).path_join(stamp)
	var rescued_any := false

	# Back up every touched existing file before the first mutation. This makes a failed
	# write recoverable; only locally modified files are retained in the permanent rescue folder.
	for operation in operations:
		var relative: String = operation.path
		var local_path := project_root.path_join(relative)
		if not FileAccess.file_exists(local_path):
			continue
		var transaction_copy := transaction_root.path_join(relative)
		DirAccess.make_dir_recursive_absolute(transaction_copy.get_base_dir())
		if DirAccess.copy_absolute(local_path, transaction_copy) != OK:
			_remove_tree(transaction_root)
			_show_error("No se pudo preparar una copia de seguridad. No se modificó ningún archivo: " + relative)
			return
		if operation.modified:
			var rescue_copy := rescue_root.path_join(relative)
			DirAccess.make_dir_recursive_absolute(rescue_copy.get_base_dir())
			if DirAccess.copy_absolute(local_path, rescue_copy) != OK:
				_remove_tree(transaction_root)
				_remove_tree(rescue_root)
				_show_error("No se pudo rescatar el archivo local. No se modificó ningún archivo: " + relative)
				return
			rescued_any = true

	for operation in operations:
		var relative: String = operation.path
		var local_path := project_root.path_join(relative)
		var operation_error := OK
		if operation.kind == "delete":
			operation_error = DirAccess.remove_absolute(local_path)
		else:
			var staged_path := staged_root.path_join(relative)
			var bytes := FileAccess.get_file_as_bytes(staged_path)
			DirAccess.make_dir_recursive_absolute(local_path.get_base_dir())
			var file := FileAccess.open(local_path, FileAccess.WRITE)
			if file == null:
				operation_error = FileAccess.get_open_error()
			else:
				file.store_buffer(bytes)
				operation_error = file.get_error()
				file.close()
		if operation_error != OK:
			_rollback_operations(transaction_root)
			_remove_tree(transaction_root)
			_show_error("Falló la escritura de '%s' (error %d). Se intentó restaurar el estado anterior." % [relative, operation_error])
			return

	if not _save_manifest():
		_rollback_operations(transaction_root)
		_remove_tree(transaction_root)
		_show_error("No se pudo guardar el historial. Se intentó restaurar el estado anterior.")
		return
	_remove_tree(transaction_root)
	EditorInterface.get_resource_filesystem().scan()
	var done := "Sincronización completada. No se subió ningún archivo."
	if rescued_any:
		done += "\nCopias de rescate de archivos locales modificados: " + rescue_root
	_show_notice(done)

func _rollback_operations(transaction_root: String) -> void:
	for operation in operations:
		var relative: String = operation.path
		var local_path := project_root.path_join(relative)
		var transaction_copy := transaction_root.path_join(relative)
		if FileAccess.file_exists(transaction_copy):
			DirAccess.make_dir_recursive_absolute(local_path.get_base_dir())
			DirAccess.copy_absolute(transaction_copy, local_path)
		elif operation.kind == "add" and FileAccess.file_exists(local_path):
			DirAccess.remove_absolute(local_path)

func _save_manifest() -> bool:
	var folder := "user://%s" % MANIFEST_DIR
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(folder))
	var file := FileAccess.open(_manifest_path(), FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify({"repository": active_repo, "ref": active_ref, "files": upstream_files}, "\t"))
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
	var dialog := AcceptDialog.new()
	dialog.title = "Error de sincronización"
	dialog.dialog_text = message
	add_child(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()

func _show_notice(message: String) -> void:
	var dialog := AcceptDialog.new()
	dialog.title = "Sincronización de GitHub"
	dialog.dialog_text = message
	add_child(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()
