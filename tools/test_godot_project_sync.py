import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from godot_project_sync import (
    RelayClient, SameOriginRedirectHandler, SyncError, pull_snapshot, validate_manifest, validate_relative_path,
)


PROJECT_ID = "7f3d7b64-0a2e-4db3-9a5f-3c2d7b7bce11"
PAYLOAD = b"[gd_scene format=3]\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


class FakeClient:
    def __init__(self, manifest, content=PAYLOAD):
        self.manifest = manifest
        self.content = content

    def get_manifest(self, project_id):
        return self.manifest

    def download_file(self, project_id, path, expected_size, expected_sha256):
        return self.content


def manifest(path="project.godot"):
    return {
        "project": {"id": PROJECT_ID, "slug": "fixture", "display_name": "Fixture"},
        "head_revision": 4,
        "files": [{"path": path, "sha256": DIGEST, "byte_size": len(PAYLOAD)}],
    }


class SyncValidationTests(unittest.TestCase):
    def test_accepts_normal_relative_path(self):
        self.assertEqual(validate_relative_path("scenes/main.tscn").as_posix(), "scenes/main.tscn")

    def test_rejects_traversal_and_absolute_paths(self):
        for path in ("../outside", "a/../../b", "/etc/passwd", "a\\b", "a//b"):
            with self.subTest(path=path), self.assertRaises(SyncError):
                validate_relative_path(path)

    def test_rejects_cache_and_credentials(self):
        for path in (".git/config", ".godot/imported/a", ".env", "keys/game.keystore"):
            with self.subTest(path=path), self.assertRaises(SyncError):
                validate_relative_path(path)

    def test_rejects_file_directory_collisions(self):
        data = manifest()
        data["files"].append({
            "path": "project.godot/child.txt",
            "sha256": DIGEST,
            "byte_size": len(PAYLOAD),
        })
        with self.assertRaises(SyncError):
            validate_manifest(data)

    def test_rejects_bad_hash_and_oversized_file(self):
        data = manifest()
        data["files"][0]["sha256"] = "not-a-hash"
        with self.assertRaises(SyncError):
            validate_manifest(data)
        data = manifest()
        data["files"][0]["byte_size"] = 32 * 1024 * 1024 + 1
        with self.assertRaises(SyncError):
            validate_manifest(data)

    def test_rejects_non_https_relay(self):
        with self.assertRaises(SyncError):
            RelayClient("http://example.test", "token")
        with self.assertRaises(SyncError):
            RelayClient("https://user:pass@example.test", "token")

    def test_rejects_cross_origin_or_tls_downgrade_redirects(self):
        class Request:
            full_url = "https://relay.example.test/v1/projects"

        handler = SameOriginRedirectHandler()
        with self.assertRaises(SyncError):
            handler.redirect_request(Request(), None, 302, "Found", {}, "https://attacker.example/file")
        with self.assertRaises(SyncError):
            handler.redirect_request(Request(), None, 302, "Found", {}, "http://relay.example.test/file")

    def test_pull_creates_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "snapshot"
            result = pull_snapshot(FakeClient(manifest()), PROJECT_ID, destination)
            self.assertEqual(result, destination)
            self.assertEqual((destination / "project.godot").read_bytes(), PAYLOAD)

    def test_pull_refuses_to_overwrite_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "project"
            destination.mkdir()
            marker = destination / "keep.txt"
            marker.write_text("untouched", encoding="utf-8")
            with self.assertRaises(SyncError):
                pull_snapshot(FakeClient(manifest()), PROJECT_ID, destination)
            self.assertEqual(marker.read_text(encoding="utf-8"), "untouched")

    def test_pull_cleans_staging_after_hash_failure(self):
        bad = FakeClient(manifest(), b"tampered")
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "snapshot"
            with self.assertRaises(SyncError):
                pull_snapshot(bad, PROJECT_ID, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_manifest_project_mismatch_is_rejected(self):
        data = manifest()
        data["project"]["id"] = "different"
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SyncError):
            pull_snapshot(FakeClient(data), PROJECT_ID, Path(tmp) / "snapshot")


if __name__ == "__main__":
    unittest.main()
