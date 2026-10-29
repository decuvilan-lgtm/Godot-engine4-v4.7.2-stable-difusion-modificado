"""Source-contract tests for the Linux-to-Android Live Link emitter."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "scripts/live_link_addon/plugin.gd").read_text(encoding="utf-8")

class LiveLinkEmitterContractTests(unittest.TestCase):
    def test_emitter_role_is_separate_from_target_and_controller(self):
        self.assertIn('_role.add_item("Este editor envía cambios al Android", 2)', SOURCE)
        self.assertIn('selected_role = "agent"', SOURCE)
        self.assertIn('func _is_agent() -> bool:', SOURCE)
        self.assertIn('func _is_target() -> bool:\n    return str(ProjectSettings.get_setting(SETTING_ROLE, "target")) == "target"', SOURCE)
        self.assertIn('_role.set_item_disabled(2, true)', SOURCE)

    def test_sender_requires_a_valid_android_project_id_and_project_scoped_room(self):
        self.assertIn('id_regex.compile("^[0-9]{4}$")', SOURCE)
        self.assertIn('room = "project-" + target_id', SOURCE)
        self.assertIn('"live_link_emitter/target_project_id"', SOURCE)

    def test_sender_uses_explicit_baseline_and_conflict_aware_operations(self):
        self.assertIn("_show_baseline_confirmation", SOURCE)
        self.assertIn("ambos proyectos", SOURCE.lower())
        self.assertIn('"base_sha256": old_digest', SOURCE)
        self.assertIn('"target_platform": "android_editor"', SOURCE)
        self.assertIn('"policy_version": 1', SOURCE)
        self.assertIn('"operation": "delete"', SOURCE)
        self.assertIn('_sender_baseline[path] = str(_sender_inflight.get("sha256", ""))', SOURCE)

    def test_sender_excludes_project_identity_and_generated_or_private_paths(self):
        excluded = SOURCE.split("func _sender_path_is_excluded(relative_path: String) -> bool:", 1)[1].split("\\nfunc ", 1)[0]
        self.assertIn('lower == "project.godot"', excluded)
        self.assertIn('lower.begins_with(".git/")', excluded)
        self.assertIn('lower.begins_with(".godot/")', excluded)
        self.assertIn('addons/live_link/', excluded)

    def test_disconnect_does_not_claim_an_unknown_operation_failed_or_retry_it(self):
        self.assertIn("su resultado es desconocido", SOURCE)
        self.assertIn("_sender_inflight.clear()", SOURCE)
        self.assertIn("_sender_queue.clear()", SOURCE)

if __name__ == "__main__":
    unittest.main()