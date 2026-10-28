"""Regression checks for Live Link's explicit project identity/activation gate.

These are source-contract checks, not a substitute for executing the UI on Android.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "scripts/live_link_addon/plugin.gd").read_text(encoding="utf-8")


class ProjectIdentityGateTests(unittest.TestCase):
    def test_connection_starts_disabled_and_requires_explicit_enable(self):
        self.assertIn('_connect_button.disabled = true', SOURCE)
        connect = SOURCE.split("func _connect_clicked() -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn("if not _connection_enabled:", connect)
        self.assertIn("Primero revela el código y habilita la conexión.", connect)
        self.assertIn("if not _code_copied:", SOURCE)
        self.assertIn("Primero copia el código y compártelo en el chat.", SOURCE)

    def test_reveal_generates_fresh_random_project_id(self):
        reveal = SOURCE.split("func _reveal_project_code() -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn("Crypto.new()", reveal)
        self.assertIn("generate_random_bytes(16).hex_encode()", reveal)
        self.assertIn("ProjectSettings.set_setting(SETTING_PROJECT_ID, project_id)", reveal)
        self.assertIn("ProjectSettings.save() != OK", reveal)
        self.assertIn("_connection_enabled = false", reveal)
        self.assertIn("_connect_button.disabled = true", reveal)

    def test_reveal_does_not_connect_or_copy_automatically(self):
        reveal = SOURCE.split("func _reveal_project_code() -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertNotIn("_connect_clicked()", reveal)
        self.assertNotIn("DisplayServer.clipboard_set", reveal)
        self.assertIn("_project_code_label.visible = true", reveal)

    def test_copy_button_is_unlocked_only_after_reveal(self):
        build = SOURCE.split("func _build_ui() -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        reveal = SOURCE.split("func _reveal_project_code() -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn('copy_button.disabled = true', build)
        self.assertIn('copy_button.name = "CopyProjectCodeButton"', build)
        self.assertIn('child.disabled = false', reveal)

    def test_connected_session_cannot_rotate_identifier_underneath_it(self):
        reveal = SOURCE.split("func _reveal_project_code() -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn("if _connected or _connecting:", reveal)
        self.assertIn("Desconecta primero", reveal)

    def test_relay_url_validation_checks_private_ipv4_octets_and_ports(self):
        helper = SOURCE.split("func _is_allowed_relay_url(url: String) -> bool:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn("_is_private_ipv4(lan_match.get_string(1))", helper)
        self.assertIn("_valid_port(lan_match, 3)", helper)
        self.assertIn("return port >= 1 and port <= 65535", SOURCE)
        self.assertIn("octet > 255", SOURCE)
        self.assertIn("octets[1] >= 16 and octets[1] <= 31", SOURCE)
        self.assertIn('if not _is_allowed_relay_url(url):', SOURCE)


    def test_secure_relay_validation_checks_dns_labels_and_port(self):
        helper = SOURCE.split("func _is_valid_dns_host(host: String) -> bool:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn("host.length() > 253", helper)
        self.assertIn("label.length() > 63", helper)
        self.assertIn('label.begins_with("-")', helper)
        self.assertIn('label.ends_with("-")', helper)
        self.assertIn("code != 45", helper)
        relay = SOURCE.split("func _is_allowed_relay_url(url: String) -> bool:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn("_is_valid_dns_host(secure_match.get_string(1))", relay)
        self.assertIn("_valid_port(secure_match, 3)", relay)

    def test_plain_ws_is_limited_to_loopback_or_private_lan(self):
        helper = SOURCE.split("func _is_allowed_relay_url(url: String) -> bool:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn('local_regex.compile("^ws://', helper)
        self.assertIn('lan_regex.compile("^ws://', helper)
        self.assertIn('secure_regex.compile("^wss://', helper)
        self.assertNotIn('url.begins_with("wss://") or is_local_ws or is_lan_ws', SOURCE)

    def test_remote_file_changes_require_explicit_user_approval(self):
        apply = SOURCE.split("func _apply_project_operation(data: Dictionary) -> void:", 1)[1].split(
            "\\nfunc _approve_pending_project_operation", 1
        )[0]
        self.assertIn("_approval_dialog.popup_centered()", apply)
        self.assertIn("_pending_project_operation = data.duplicate(true)", apply)
        self.assertIn("return", apply)
        self.assertIn("_approval_dialog.confirmed.connect(_approve_pending_project_operation)", SOURCE)
        self.assertIn("_approval_dialog.canceled.connect(_reject_pending_project_operation)", SOURCE)
        approve = SOURCE.split("func _approve_pending_project_operation() -> void:", 1)[1].split(
            "\\nfunc _reject_pending_project_operation", 1
        )[0]
        self.assertIn("_apply_validated_operation(data, operation, relative_path, absolute_path)", approve)
        reject = SOURCE.split("func _reject_pending_project_operation() -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn('"status":"rejected"', reject)

    def test_remote_approval_dialog_contract(self):
        apply = SOURCE.split("func _apply_project_operation(data: Dictionary) -> void:", 1)[1].split(
            "\\nfunc _approve_pending_project_operation", 1
        )[0]
        self.assertIn("_approval_dialog.popup_centered()", apply)
        self.assertIn("_pending_project_operation = data.duplicate(true)", apply)
        self.assertIn("_approval_dialog.confirmed.connect(_approve_pending_project_operation)", SOURCE)
        self.assertIn("_approval_dialog.canceled.connect(_reject_pending_project_operation)", SOURCE)
        approve = SOURCE.split("func _approve_pending_project_operation() -> void:", 1)[1].split(
            "\\nfunc _reject_pending_project_operation", 1
        )[0]
        self.assertIn("_apply_validated_operation(data, operation, relative_path, absolute_path)", approve)
        reject = SOURCE.split("func _reject_pending_project_operation() -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn('"status":"rejected"', reject)

    def test_relay_binds_only_to_loopback_by_default(self):
        server = (ROOT / "relay" / "server.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("HOST", "127.0.0.1")', server)
        self.assertNotIn('os.environ.get("HOST", "0.0.0.0")', server)

    def test_receiver_enforces_android_policy_envelope(self):
        apply = SOURCE.split("func _apply_project_operation(data: Dictionary) -> void:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn('data.get("target_platform", "")) != "android_editor"', apply)
        self.assertIn('data.get("policy_version", -1)) != 1', apply)

    def test_receiver_rejects_unsafe_paths_and_protected_directories(self):
        safe = SOURCE.split("func _safe_relative_path(value: Variant) -> bool:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn('path.begins_with("/")', safe)
        self.assertIn('path.contains("\\\\")', safe)
        self.assertIn('part == ".."', safe)
        self.assertIn('part.to_lower() == ".git"', safe)
        self.assertIn('part.to_lower() == ".godot"', safe)

    def test_path_gate_checks_symlink_entries_even_when_targets_do_not_exist(self):
        project_path = SOURCE.split("func _project_absolute_path(relative_path: String) -> String:", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn("parent_dir.is_link(current.get_file())", project_path)
        self.assertNotIn(
            "if FileAccess.file_exists(current) or DirAccess.dir_exists_absolute(current):",
            project_path,
        )

    def test_updates_deletes_and_renames_require_base_hash(self):
        apply = SOURCE.split("func _apply_validated_operation(", 1)[1].split(
            "\nfunc ", 1
        )[0]
        self.assertIn('operation in ["update", "rename", "delete"]', apply)
        self.assertIn('base_hash.is_empty()', apply)
        self.assertIn('FileAccess.get_sha256(absolute_path).to_lower() != base_hash.to_lower()', apply)

    def test_delete_creates_backup_before_removing_source(self):
        apply = SOURCE.split("func _apply_validated_operation(", 1)[1].split(
            "\nfunc ", 1
        )[0]
        backup = apply.index('_backup_project_file(absolute_path, relative_path')
        remove = apply.index('DirAccess.remove_absolute(absolute_path)')
        self.assertLess(backup, remove)


if __name__ == "__main__":
    unittest.main()
