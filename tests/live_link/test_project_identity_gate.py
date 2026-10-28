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


if __name__ == "__main__":
    unittest.main()
