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
