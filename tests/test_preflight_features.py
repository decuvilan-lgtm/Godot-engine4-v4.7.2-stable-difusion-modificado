import unittest
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

    def test_grouping_deduplicates_same_path(self):
        first = classify_file_read_failure("res://bad.bin", FileReadFailure.IO_ERROR)
        second = classify_file_read_failure("res://bad.bin", FileReadFailure.TRUNCATED_CONTAINER)
        self.assertEqual(group_corrupt_findings([first, second]), [first])


if __name__ == "__main__":
    unittest.main()
