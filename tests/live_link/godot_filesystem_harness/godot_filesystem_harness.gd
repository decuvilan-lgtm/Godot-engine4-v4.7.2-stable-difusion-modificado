@tool
extends EditorPlugin

const PROJECT_ID := "12345678abcdef9012345678abcdef90"
const TEST_ROOT := "LiveLinkHarness"

var _failed := false


func _enter_tree() -> void:
    call_deferred("_run_after_editor_startup")


func _run_after_editor_startup() -> void:
    # Avoid calling ResourceFilesystem.scan() while the editor is still
    # initializing enabled plugins during its first scan.
    await get_tree().process_frame
    ProjectSettings.set_setting("live_link/project_id", PROJECT_ID)
    var receiver: Variant = get_tree().get_first_node_in_group("live_link_receiver")
    if receiver == null:
        _check(false, "active Live Link receiver found in editor tree")
        _finish()
        return

    var root := ProjectSettings.globalize_path("res://" + TEST_ROOT)
    if DirAccess.make_dir_recursive_absolute(root) != OK:
        _check(false, "test directory created")
        _finish()
        return

    _test_create_and_empty_file(receiver)
    _test_update_and_conflict(receiver)
    _test_rename_and_delete(receiver)
    _test_recovery_after_original_moved(receiver)
    _finish()


func _test_create_and_empty_file(receiver: Variant) -> void:
    var relative := TEST_ROOT + "/created.txt"
    var absolute := ProjectSettings.globalize_path("res://" + relative)
    var bytes := "created by Godot integration test".to_utf8_buffer()
    var data := _operation_data(receiver, "harness-create", bytes, "")
    var status: String = receiver._apply_validated_operation(data, "create", relative, absolute)
    _check(status == "applied", "create operation reports applied")
    _check(FileAccess.file_exists(absolute), "created file exists")
    _check(FileAccess.get_file_as_string(absolute) == bytes.get_string_from_utf8(), "created file content matches")

    var empty_relative := TEST_ROOT + "/empty.txt"
    var empty_absolute := ProjectSettings.globalize_path("res://" + empty_relative)
    var empty_bytes := PackedByteArray()
    var empty_data := _operation_data(receiver, "harness-empty", empty_bytes, "")
    status = receiver._apply_validated_operation(empty_data, "create", empty_relative, empty_absolute)
    _check(status == "applied", "empty-file create reports applied")
    _check(FileAccess.file_exists(empty_absolute), "empty file exists")
    _check(FileAccess.get_file_as_string(empty_absolute).is_empty(), "empty file remains empty")


func _test_update_and_conflict(receiver: Variant) -> void:
    var relative := TEST_ROOT + "/updated.txt"
    var absolute := ProjectSettings.globalize_path("res://" + relative)
    _write_text(absolute, "before")
    var base_hash := FileAccess.get_sha256(absolute)
    var next_bytes := "after".to_utf8_buffer()
    var data := _operation_data(receiver, "harness-update", next_bytes, base_hash)
    var status: String = receiver._apply_validated_operation(data, "update", relative, absolute)
    _check(status == "applied", "update operation reports applied")
    _check(FileAccess.get_file_as_string(absolute) == "after", "updated content matches")

    var wrong_bytes := "must not replace current file".to_utf8_buffer()
    var conflict_data := _operation_data(receiver, "harness-conflict", wrong_bytes, "0".repeat(64))
    status = receiver._apply_validated_operation(conflict_data, "update", relative, absolute)
    _check(status == "conflict", "stale base hash reports conflict")
    _check(FileAccess.get_file_as_string(absolute) == "after", "conflict leaves current content unchanged")


func _test_rename_and_delete(receiver: Variant) -> void:
    var source_relative := TEST_ROOT + "/rename-source.txt"
    var source_absolute := ProjectSettings.globalize_path("res://" + source_relative)
    _write_text(source_absolute, "rename me")
    var destination_relative := TEST_ROOT + "/renamed.txt"
    var rename_data := _operation_data(receiver, "harness-rename", PackedByteArray(), FileAccess.get_sha256(source_absolute))
    rename_data["destination_path"] = destination_relative
    var status: String = receiver._apply_validated_operation(rename_data, "rename", source_relative, source_absolute)
    var destination_absolute := ProjectSettings.globalize_path("res://" + destination_relative)
    _check(status == "applied", "rename operation reports applied")
    _check(not FileAccess.file_exists(source_absolute), "rename removes original path")
    _check(FileAccess.get_file_as_string(destination_absolute) == "rename me", "renamed content is preserved")

    var delete_relative := TEST_ROOT + "/delete-me.txt"
    var delete_absolute := ProjectSettings.globalize_path("res://" + delete_relative)
    _write_text(delete_absolute, "delete me")
    var delete_data := _operation_data(receiver, "harness-delete", PackedByteArray(), FileAccess.get_sha256(delete_absolute))
    status = receiver._apply_validated_operation(delete_data, "delete", delete_relative, delete_absolute)
    _check(status == "applied", "delete operation reports applied")
    _check(not FileAccess.file_exists(delete_absolute), "delete removes source file")


func _test_recovery_after_original_moved(receiver: Variant) -> void:
    var relative := TEST_ROOT + "/recover-me.txt"
    var absolute := ProjectSettings.globalize_path("res://" + relative)
    var rollback := absolute + ".live_link_rollback_deadbeef"
    var temporary := absolute + ".live_link_tmp_cafebabe"
    _write_text(rollback, "recover original")
    _write_text(temporary, "uncommitted replacement")
    if FileAccess.file_exists(absolute):
        DirAccess.remove_absolute(absolute)
    _check(receiver._write_transaction_journal(absolute, rollback, temporary, ""), "recovery journal written")
    receiver._recover_interrupted_file_transactions()
    _check(FileAccess.file_exists(absolute), "recovery restores original path")
    _check(FileAccess.get_file_as_string(absolute) == "recover original", "recovery restores original bytes")
    _check(not FileAccess.file_exists(temporary), "recovery removes uncommitted temporary file")
    _check(not FileAccess.file_exists(receiver._transaction_journal_path()), "recovery clears completed journal")


func _operation_data(receiver: Variant, operation_id: String, bytes: PackedByteArray, base_hash: String) -> Dictionary:
    return {
        "operation_id": operation_id,
        "content_base64": Marshalls.raw_to_base64(bytes) if not bytes.is_empty() else "",
        "sha256": receiver._sha256_bytes(bytes),
        "base_sha256": base_hash
    }


func _write_text(path: String, value: String) -> void:
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        _check(false, "fixture file opened for writing: " + path)
        return
    file.store_string(value)
    file.close()


func _check(condition: bool, label: String) -> void:
    if not condition:
        _failed = true
        push_error("LIVE_LINK_FS_TEST_FAIL: " + label)


func _finish() -> void:
    if _failed:
        push_error("LIVE_LINK_FS_TESTS_FAILED")
    else:
        print("LIVE_LINK_FS_TESTS_PASSED")
