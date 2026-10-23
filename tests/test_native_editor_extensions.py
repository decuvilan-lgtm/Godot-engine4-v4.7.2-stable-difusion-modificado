from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeEditorExtensionTests(unittest.TestCase):
    def test_dependency_tool_uses_native_loader_and_safe_paths(self):
        patcher = (ROOT / "scripts/extend_safe_mcp_scene_tools.py").read_text(encoding="utf-8")
        self.assertIn("ResourceLoader.get_dependencies(current)", patcher)
        self.assertIn("is_safe_project_path(dependency)", patcher)
        self.assertIn('"truncated": not pending.is_empty()', patcher)
        self.assertIn("does not import or rewrite them", patcher)
        self.assertIn("ZipFile(archive_path", patcher)
        self.assertLess(patcher.index('if "InspectSceneDependenciesTool"'), patcher.index("TOOL.write_text"))

    def test_android_and_standalone_addon_jobs_apply_extension(self):
        workflow = (ROOT / ".github/workflows/build-godot-android-source.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("run: python scripts/extend_safe_mcp_scene_tools.py"), 2)
        self.assertLess(
            workflow.index("name: Add native scene dependency inspection tool"),
            workflow.index("name: Embed MCP addon source files in Android editor assets"),
        )
        standalone = workflow.index("name: Package and validate safe MCP addon")
        self.assertGreater(workflow.index("name: Add native scene dependency inspection tool", standalone), standalone)

    def test_mobile_github_panel_has_touch_sized_controls(self):
        patcher = (ROOT / "scripts/apply_github_sync_ui_patch.py").read_text(encoding="utf-8")
        self.assertIn("Size2(0, 380) * EDSCALE", patcher)
        self.assertIn("Size2(0, 44) * EDSCALE", patcher)
        self.assertIn("Size2(0, 48) * EDSCALE", patcher)
        self.assertIn("Size2(0, 180) * EDSCALE", patcher)
        self.assertIn("GitHub: analizar y revisar", patcher)

    def test_existing_unsafe_execution_tool_stays_disabled(self):
        packager = (ROOT / "scripts/package_safe_mcp_android.py").read_text(encoding="utf-8")
        self.assertIn("Remove it rather than pretending it is a sandbox", packager)
        self.assertIn("ExecuteScriptTool", packager)
        self.assertIn("project deletion/removal is permanently blocked", packager)


if __name__ == "__main__":
    unittest.main()
