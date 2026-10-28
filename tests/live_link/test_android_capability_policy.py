"""Regression checks for the Android-only capability contract consumed by the future agent."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "scripts/live_link_addon/android_capabilities.json"
DOC_PATH = ROOT / "docs/CHATGPT_ANDROID_COMPATIBILITY.md"


class AndroidCapabilityPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.doc = DOC_PATH.read_text(encoding="utf-8")

    def test_targets_modified_android_editor_and_both_arm_abis(self):
        target = self.policy["target"]
        self.assertEqual(target["engine"], "Godot 4.7.2 modified Android editor")
        self.assertEqual(target["android_version"], 11)
        self.assertEqual(target["logical_resolution"], "720x1600")
        self.assertEqual(set(target["architectures"]), {"armeabi-v7a", "arm64-v8a"})

    def test_desktop_only_workflows_are_explicitly_disallowed(self):
        rules = self.policy["rules"]
        self.assertEqual(rules["platform_priority"], "android_only")
        self.assertTrue(rules["never_assume_desktop_editor_controls_exist_on_android"])
        self.assertTrue(rules["never_use_pc_only_workflows_as_required_steps"])
        self.assertTrue(rules["never_add_desktop_only_dependencies_to_android_runtime"])

    def test_uncertain_editor_apis_must_be_verified(self):
        checks = self.policy["must_verify_before_use"]
        self.assertTrue(any("EditorInterface" in item or "EditorPlugin" in item for item in checks))
        self.assertTrue(any("filesystem" in item.lower() for item in checks))
        self.assertIn("When capability is uncertain, inspect the repository/API and mark it unverified instead of assuming desktop parity.", self.policy["agent_behavior"])

    def test_mobile_policy_is_documented_and_not_misrepresented_as_live(self):
        self.assertIn("no se debe presentar esa integración como terminada", self.doc)
        self.assertIn("720×1600", self.doc)
        self.assertIn("ARM32", self.doc)
        self.assertIn("PC", self.doc)


if __name__ == "__main__":
    unittest.main()
