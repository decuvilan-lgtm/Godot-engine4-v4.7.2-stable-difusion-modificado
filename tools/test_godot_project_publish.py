import hashlib
import tempfile
import unittest
from pathlib import Path

from godot_project_publish import (
    PublishError, build_plan, publish_project, scan_project, validate_manifest,
)

PROJECT_ID = "7f3d7b64-0a2e-4db3-9a5f-3c2d7b7bce11"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeClient:
    def __init__(self, files=None):
        self.files = dict(files or {})
        self.uploads = []
        self.revision = 1

    def get_manifest(self, project_id):
        return {"project": {"id": project_id, "slug": "fixture", "display_name": "Fixture"},
                "head_revision": self.revision,
                "files": [{"path": p, "sha256": v[0], "byte_size": v[1]} for p, v in sorted(self.files.items())]}

    def upload_file(self, project_id, path, data, digest, base_sha):
        current = self.files.get(path)
        current_sha = current[0] if current else None
        if current_sha != base_sha:
            raise PublishError("HTTP 409 conflict")
        self.files[path] = (digest, len(data))
        self.revision += 1
        self.uploads.append(path)
        return {"sha256": digest, "revision": self.revision}


class PublishTests(unittest.TestCase):
    def make_project(self, root: Path):
        (root / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        (root / "main.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")

    def test_scan_excludes_cache_and_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            (root / ".godot").mkdir()
            (root / ".godot" / "cache.bin").write_bytes(b"x")
            (root / ".env").write_text("SECRET=x")
            result = scan_project(root)
            self.assertEqual(set(result), {"project.godot", "main.tscn"})

    def test_rejects_symlinked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            outside = root.parent / (root.name + "-outside")
            outside.write_text("no")
            try:
                (root / "leak.txt").symlink_to(outside)
                self.assertNotIn("leak.txt", scan_project(root))
            finally:
                outside.unlink(missing_ok=True)

    def test_three_way_plan_uploads_only_local_changes(self):
        local = {"a": {"sha256": "new"}}
        remote = {"a": {"sha256": "old"}, "b": {"sha256": "remote"}}
        state = {"files": {"a": {"local_sha256": "old", "remote_sha256": "old"},
                           "b": {"local_sha256": "", "remote_sha256": "remote"}}}
        plan = build_plan(local, remote, state)
        self.assertEqual(plan["upload"], ["a"])
        self.assertEqual(plan["remote_only"], ["b"])
        self.assertEqual(plan["conflicts"], [])

    def test_conflicting_edits_are_blocked(self):
        local = {"a": {"sha256": "local"}}
        remote = {"a": {"sha256": "remote"}}
        state = {"files": {"a": {"local_sha256": "base", "remote_sha256": "base"}}}
        self.assertEqual(build_plan(local, remote, state)["conflicts"], ["a"])

    def test_first_publish_uploads_only_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            self.make_project(root)
            remote = {"project.godot": (sha(b"config_version=5\n"), len(b"config_version=5\n"))}
            client = FakeClient(remote)
            state = Path(tmp) / "state.json"
            plan = publish_project(client, PROJECT_ID, root, state, apply=True)
            self.assertEqual(plan["upload"], ["main.tscn"])
            self.assertEqual(client.uploads, ["main.tscn"])
            self.assertTrue(state.exists())

    def test_dry_run_does_not_upload_or_write_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            self.make_project(root)
            client = FakeClient()
            state = Path(tmp) / "state.json"
            plan = publish_project(client, PROJECT_ID, root, state, apply=False)
            self.assertEqual(len(plan["upload"]), 2)
            self.assertEqual(client.uploads, [])
            self.assertFalse(state.exists())

    def test_excludes_nested_environment_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            (root / ".env.production").mkdir()
            (root / ".env.production" / "credentials.txt").write_text("secret", encoding="utf-8")
            self.assertEqual(set(scan_project(root)), {"project.godot", "main.tscn"})

    def test_local_deletion_never_deletes_remote_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            self.make_project(root)
            remote_bytes = b"old remote content"
            remote_sha = sha(remote_bytes)
            client = FakeClient({"removed_locally.txt": (remote_sha, len(remote_bytes))})
            state = Path(tmp) / "state.json"
            state.write_text(__import__("json").dumps({"project_id": PROJECT_ID, "files": {
                "removed_locally.txt": {"local_sha256": remote_sha, "remote_sha256": remote_sha}
            }}), encoding="utf-8")
            plan = publish_project(client, PROJECT_ID, root, state, apply=True)
            self.assertEqual(plan["upload"], ["main.tscn", "project.godot"])
            self.assertIn("removed_locally.txt", client.files)

    def test_changed_local_file_updates_with_remote_base_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            self.make_project(root)
            old = b"old scene"
            (root / "main.tscn").write_bytes(b"new scene")
            project_bytes = b"config_version=5\n"
            client = FakeClient({"project.godot": (sha(project_bytes), len(project_bytes)),
                                 "main.tscn": (sha(old), len(old))})
            state = Path(tmp) / "state.json"
            state.write_text(__import__("json").dumps({"project_id": PROJECT_ID, "files": {
                "project.godot": {"local_sha256": sha(project_bytes), "remote_sha256": sha(project_bytes)},
                "main.tscn": {"local_sha256": sha(old), "remote_sha256": sha(old)}
            }}), encoding="utf-8")
            plan = publish_project(client, PROJECT_ID, root, state, apply=True)
            self.assertEqual(plan["upload"], ["main.tscn"])
            self.assertEqual(client.files["main.tscn"][0], sha(b"new scene"))

    def test_remote_only_difference_stays_visible(self):
        local = {"a": {"sha256": "local"}}
        remote = {"a": {"sha256": "web"}}
        state = {"files": {"a": {"local_sha256": "local", "remote_sha256": "web"}}}
        self.assertEqual(build_plan(local, remote, state)["remote_only"], ["a"])

    def test_local_edit_during_upload_remains_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            self.make_project(root)
            scene = root / "main.tscn"
            original = scene.read_bytes()
            class EditingClient(FakeClient):
                def upload_file(self, project_id, path, data, digest, base_sha):
                    result = super().upload_file(project_id, path, data, digest, base_sha)
                    if path == "main.tscn":
                        scene.write_bytes(b"edited during transfer")
                    return result
            client = EditingClient()
            state_path = Path(tmp) / "state.json"
            publish_project(client, PROJECT_ID, root, state_path, apply=True)
            state = __import__("json").loads(state_path.read_text(encoding="utf-8"))
            next_plan = build_plan(scan_project(root),
                                   {p: {"sha256": v[0], "byte_size": v[1]} for p, v in client.files.items()},
                                   state)
            self.assertIn("main.tscn", next_plan["upload"])
            self.assertNotEqual(scene.read_bytes(), original)

    def test_manifest_must_match_destination(self):
        payload = {"project": {"id": "wrong"}, "head_revision": 0, "files": []}
        with self.assertRaises(PublishError):
            validate_manifest(payload, PROJECT_ID)


if __name__ == "__main__":
    unittest.main()
