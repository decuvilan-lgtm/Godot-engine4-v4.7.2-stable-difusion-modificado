import unittest
from pathlib import Path
from scene_dependency_plan import plan_scene_import, SceneImportError
from corrupt_file_classifier import (
    FileReadFailure, classify_file_read_failure, group_corrupt_findings,
)


class SceneDependencyPlanTests(unittest.TestCase):
    def test_transitive_dependencies_and_cycles_are_deduplicated(self):
        files = {
            "res://Main.tscn": '[ext_resource type="PackedScene" path="res://scenes/A.tscn" id="1"]',
            "res://scenes/A.tscn": '[ext_resource type="PackedScene" path="res://scenes/B.tscn" id="1"]\n[ext_resource type="Resource" path="res://shared.tres" id="2"]',
            "res://scenes/B.tscn": '[ext_resource type="PackedScene" path="res://Main.tscn" id="1"]',
            "res://shared.tres": '[gd_resource type="Resource" format=3]',
        }
        self.assertEqual(plan_scene_import("res://Main.tscn", files), sorted(files))

    def test_inherited_scene_and_resource_path_properties_are_dependencies(self):
        files = {
            "res://scenes/child.tscn": (
                '[gd_scene load_steps=2 format=3]\n'
                '[ext_resource type="PackedScene" path = "res://scenes/base.tscn" id="1"]\n'
                '[node name="Child" instance=ExtResource("1")]\n'
                '[node name="Sprite" type="Sprite2D" parent="."]\n'
                'owner = NodePath("..")\n'
                'signal connected()\n'
            ),
            "res://scenes/base.tscn": '[gd_scene format=3]\n[node name="Base" type="Node2D"]\n',
        }
        self.assertEqual(
            plan_scene_import("res://scenes/child.tscn", files),
            ["res://scenes/base.tscn", "res://scenes/child.tscn"],
        )

    def test_missing_dependency_fails_closed(self):
        with self.assertRaisesRegex(SceneImportError, "Missing dependency"):
            plan_scene_import("res://Main.tscn", {
                "res://Main.tscn": '[ext_resource type="PackedScene" path="res://Missing.tscn" id="1"]'
            })

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(SceneImportError):
            plan_scene_import("res://../outside.tscn", {})

    def test_literal_load_and_preload_dependencies_are_followed(self):
        files = {
            "res://Main.tscn": '[gd_scene format=3]\n[ext_resource type="Script" path="res://scripts/main.gd" id="1"]',
            "res://scripts/main.gd": 'const DATA = preload("res://data/settings.tres")\nfunc get_scene(): return load("res://scenes/Optional.tscn")',
            "res://data/settings.tres": '[gd_resource type="Resource" format=3]',
            "res://scenes/Optional.tscn": '[gd_scene format=3]',
        }
        self.assertEqual(plan_scene_import("res://Main.tscn", files), sorted(files))

    def test_backslash_and_empty_path_segments_are_rejected(self):
        for path in ("res://assets\\\\evil.tres", "res://assets//file.tres"):
            with self.subTest(path=path), self.assertRaises(SceneImportError):
                plan_scene_import(path, {})


class CorruptFileClassifierTests(unittest.TestCase):
    def test_only_explicit_low_level_failures_create_findings(self):
        self.assertIsNotNone(classify_file_read_failure("res://broken.res", FileReadFailure.TRUNCATED_CONTAINER))
        for normal_error in ("syntax_error", "missing_resource", "runtime_error", "parse_error"):
            self.assertIsNone(classify_file_read_failure("res://script.gd", normal_error))

    def test_grouping_deduplicates_and_sorts_paths(self):
        later = classify_file_read_failure("res://z/bad.bin", FileReadFailure.IO_ERROR)
        first = classify_file_read_failure("res://a/bad.bin", FileReadFailure.TRUNCATED_CONTAINER)
        duplicate = classify_file_read_failure("res://z/bad.bin", FileReadFailure.TRUNCATED_CONTAINER)
        self.assertEqual(group_corrupt_findings([later, first, duplicate]), [first, later])


class GitHubImportPatchSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.import_patch = (root / "scripts" / "apply_github_import_patch.py").read_text(encoding="utf-8")
        cls.build_workflow = (root / ".github" / "workflows" / "build-godot-android-source.yml").read_text(encoding="utf-8")

    def test_keyboard_done_routes_to_search_fallback(self):
        self.assertIn('connect("text_submitted", callable_mp(this, &ProjectManager::_github_import_submitted))', self.import_patch)
        self.assertIn('_github_import_submitted(const String &p_text)', self.import_patch)
        self.assertIn('_github_force_search();', self.import_patch)

    def test_pasted_owner_repo_query_is_scoped_to_owner(self):
        self.assertIn('query = parts[1] + " user:" + parts[0];', self.import_patch)
        self.assertIn('search_url = "https://api.github.com/search/repositories?q="', self.import_patch)

    def test_search_pagination_and_download_are_guarded(self):
        self.assertIn('per_page=20&page=', self.import_patch)
        self.assertIn('MIN(5, MAX(1, (github_search_total_count + 19) / 20))', self.import_patch)
        self.assertIn('p_response_code != 200', self.import_patch)
        self.assertIn('!FileAccess::exists(github_zip_path)', self.import_patch)

    def test_android_build_applies_native_github_review_ui(self):
        self.assertIn('Apply native GitHub analysis and review UI', self.build_workflow)
        self.assertIn('scripts/apply_github_sync_ui_patch.py', self.build_workflow)


if __name__ == "__main__":
    unittest.main()
