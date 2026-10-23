import tempfile
import unittest
from pathlib import Path

from github_sync_core import Change, SyncError, git_blob_sha1
from github_sync_review import create_review_snapshot, validate_review_snapshot


class ReviewSnapshotTests(unittest.TestCase):
    def make_project(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name) / "project"
        root.mkdir()
        (root / "project.godot").write_text("config")
        return temp, root

    def test_snapshot_is_pinned_and_deterministic(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        changes = [
            Change("z.txt", "add", git_blob_sha1(b"z"), None, 1),
            Change("a.txt", "delete", None, git_blob_sha1(b"a"), 1),
        ]
        snapshot = create_review_snapshot(root, "https://github.com/owner/repo", "main", "a" * 40, changes)
        self.assertEqual([row["path"] for row in snapshot["changes"]], ["a.txt", "z.txt"])
        self.assertEqual(snapshot["counts"]["add"], 1)
        self.assertEqual(snapshot["counts"]["delete"], 1)
        validate_review_snapshot(snapshot, root, "https://github.com/owner/repo", "main", "a" * 40)

    def test_snapshot_rejects_changed_context(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        snapshot = create_review_snapshot(root, "https://github.com/owner/repo", "main", "a" * 40, [])
        with self.assertRaisesRegex(SyncError, "stale"):
            validate_review_snapshot(snapshot, root, "https://github.com/owner/repo", "main", "b" * 40)

    def test_snapshot_rejects_tampered_top_level_context_and_counts(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        snapshot = create_review_snapshot(
            root, "https://github.com/owner/repo", "main", "a" * 40,
            [Change("new.txt", "add", git_blob_sha1(b"new"), None, 3)],
        )
        tampered_repo = dict(snapshot)
        tampered_repo["repository_url"] = "https://github.com/other/repo"
        with self.assertRaisesRegex(SyncError, "context or counts"):
            validate_review_snapshot(tampered_repo, root, "https://github.com/owner/repo", "main", "a" * 40)
        tampered_counts = dict(snapshot)
        tampered_counts["counts"] = dict(snapshot["counts"])
        tampered_counts["counts"]["add"] = 0
        with self.assertRaisesRegex(SyncError, "context or counts"):
            validate_review_snapshot(tampered_counts, root, "https://github.com/owner/repo", "main", "a" * 40)

    def test_snapshot_rejects_duplicate_paths_and_noncanonical_url(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        row = Change("same.txt", "add", git_blob_sha1(b"x"), None, 1)
        with self.assertRaisesRegex(SyncError, "Duplicate"):
            create_review_snapshot(root, "https://github.com/owner/repo", "main", "a" * 40, [row, row])
        with self.assertRaises(SyncError):
            create_review_snapshot(root, "https://github.com/owner/repo/issues/1", "main", "a" * 40, [])


if __name__ == "__main__":
    unittest.main()
