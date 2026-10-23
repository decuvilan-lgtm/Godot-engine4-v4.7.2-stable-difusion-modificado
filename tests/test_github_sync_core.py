import json
import tempfile
import unittest
from pathlib import Path

from github_sync_core import (
    Change, SyncError, apply_plan, build_plan, git_blob_sha1,
    load_manifest, normalize_repo_path, project_manifest_path, safe_target,
)


def blob(data: bytes) -> str:
    return git_blob_sha1(data)


class GitHubSyncCoreTests(unittest.TestCase):
    def test_git_blob_hash_uses_git_header(self):
        self.assertEqual(blob(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        for value in ("../outside", "assets/../../outside", "/etc/passwd",
                      "C:/temp/file", "assets\\evil", ""):
            with self.subTest(value=value), self.assertRaises(SyncError):
                normalize_repo_path(value)

    def test_plan_add_update_delete_and_preserve_local_only(self):
        local = {
            "keep.txt": {"git_blob_sha": blob(b"same"), "size": 4},
            "change.txt": {"git_blob_sha": blob(b"local"), "size": 5},
            "removed.txt": {"git_blob_sha": blob(b"old"), "size": 3},
            "personal.png": {"git_blob_sha": blob(b"mine"), "size": 4},
        }
        remote = {
            "keep.txt": {"type": "blob", "sha": blob(b"same"), "size": 4},
            "change.txt": {"type": "blob", "sha": blob(b"remote"), "size": 6},
            "new.txt": {"type": "blob", "sha": blob(b"new"), "size": 3},
        }
        previous = {"tracked_files": {
            "keep.txt": {"sha": blob(b"same")},
            "change.txt": {"sha": blob(b"old")},
            "removed.txt": {"sha": blob(b"old")},
        }}
        plan = {item.path: item for item in build_plan(remote, local, previous)}
        self.assertEqual(plan["keep.txt"].action, "unchanged")
        self.assertEqual(plan["change.txt"].action, "update")
        self.assertEqual(plan["new.txt"].action, "add")
        self.assertEqual(plan["removed.txt"].action, "delete")
        self.assertEqual(plan["personal.png"].action, "local-only")

    def test_manifest_version_is_checked(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.json"
            path.write_text(json.dumps({"version": 999, "tracked_files": {}}))
            with self.assertRaises(SyncError):
                load_manifest(path)

    def test_apply_add_update_delete_and_preserve_untracked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "project"
            root.mkdir()
            (root / "project.godot").write_text("config")
            (root / "update.txt").write_bytes(b"old")
            (root / "delete.txt").write_bytes(b"gone")
            (root / "local-only.txt").write_bytes(b"mine")
            manifest_path = Path(td) / "metadata" / "manifest.json"
            old_manifest = {
                "version": 1,
                "project_root": str(root.resolve()),
                "repository_url": "https://github.com/example/project",
                "tracked_files": {
                    "update.txt": {"sha": blob(b"old")},
                    "delete.txt": {"sha": blob(b"gone")},
                },
            }
            manifest_path.parent.mkdir()
            manifest_path.write_text(json.dumps(old_manifest))
            plan = [
                Change("update.txt", "update", blob(b"new"), blob(b"old"), 3),
                Change("add.txt", "add", blob(b"added"), None, 5),
                Change("delete.txt", "delete", None, blob(b"gone"), 4),
                Change("local-only.txt", "local-only", None, blob(b"mine"), 4),
            ]
            payloads = {"update.txt": b"new", "add.txt": b"added"}
            result = apply_plan(
                root, plan, lambda p, expected: payloads[p], manifest_path,
                "https://github.com/example/project", "main", "a" * 40,
            )
            self.assertEqual((root / "update.txt").read_bytes(), b"new")
            self.assertEqual((root / "add.txt").read_bytes(), b"added")
            self.assertFalse((root / "delete.txt").exists())
            self.assertEqual((root / "local-only.txt").read_bytes(), b"mine")
            saved = json.loads(manifest_path.read_text())
            self.assertEqual(saved["commit_sha"], "a" * 40)
            self.assertEqual(result["changed_count"], 3)

    def test_bad_download_hash_leaves_project_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "project"
            root.mkdir()
            (root / "project.godot").write_text("config")
            (root / "file.txt").write_bytes(b"original")
            manifest_path = Path(td) / "meta" / "manifest.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(json.dumps({"version": 1, "project_root": str(root.resolve()),
                                                  "repository_url": "https://github.com/example/project",
                                                  "tracked_files": {}}))
            plan = [Change("file.txt", "update", blob(b"expected"),
                           blob(b"original"), 8)]
            with self.assertRaises(SyncError):
                apply_plan(root, plan, lambda _p, _s: b"tampered", manifest_path,
                           "https://github.com/example/project", "main", "b" * 40)
            self.assertEqual((root / "file.txt").read_bytes(), b"original")



    def test_each_project_gets_a_distinct_stable_manifest_path(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            metadata = base / "editor-metadata"
            project_a = base / "projects" / "A"
            project_b = base / "projects" / "B"
            project_a.mkdir(parents=True)
            project_b.mkdir(parents=True)
            first = project_manifest_path(metadata, project_a)
            second = project_manifest_path(metadata, project_b)
            self.assertNotEqual(first, second)
            self.assertEqual(first, project_manifest_path(metadata, project_a))
            self.assertEqual(first.name, "github_sync_manifest.json")

    def test_manifest_cannot_be_reused_for_another_project(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root_a = base / "project-a"
            root_b = base / "project-b"
            root_a.mkdir()
            root_b.mkdir()
            (root_a / "project.godot").write_text("a")
            (root_b / "project.godot").write_text("b")
            manifest_path = base / "metadata" / "manifest.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(json.dumps({
                "version": 1, "project_root": str(root_a.resolve()),
                "repository_url": "https://github.com/example/project",
                "tracked_files": {}
            }))
            with self.assertRaisesRegex(SyncError, "different local project"):
                apply_plan(root_b, [], lambda _p, _s: b"", manifest_path,
                           "https://github.com/example/project", "main", "c" * 40)

    def test_manifest_cannot_be_reused_for_another_repository(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "project"
            root.mkdir()
            (root / "project.godot").write_text("config")
            manifest_path = base / "metadata" / "manifest.json"
            manifest_path.parent.mkdir()
            manifest_path.write_text(json.dumps({
                "version": 1, "project_root": str(root.resolve()),
                "repository_url": "https://github.com/example/one",
                "tracked_files": {}
            }))
            with self.assertRaisesRegex(SyncError, "different GitHub repository"):
                apply_plan(root, [], lambda _p, _s: b"", manifest_path,
                           "https://github.com/example/two", "main", "d" * 40)


if __name__ == "__main__":
    unittest.main()
