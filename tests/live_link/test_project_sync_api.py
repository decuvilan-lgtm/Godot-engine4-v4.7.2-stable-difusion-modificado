import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "relay"))
from project_sync_api import safe_path, validate_manifest

class ManifestValidationTests(unittest.TestCase):
    def test_accepts_normal_manifest(self):
        ok, error = validate_manifest([{"path":"Scenes/main.tscn","sha256":"a"*64,"size":128}])
        self.assertTrue(ok, error)

    def test_rejects_traversal_and_internal_dirs(self):
        for path in ("../project.godot", "/tmp/a", "C:/temp/a", ".git/config", ".godot/imported/a", "Scenes\\escape"):
            self.assertFalse(safe_path(path), path)

    def test_rejects_duplicate_paths_and_hashes(self):
        item={"path":"a.txt","sha256":"b"*64,"size":1}
        self.assertFalse(validate_manifest([item,item])[0])
        self.assertFalse(validate_manifest([dict(item,sha256="not-hash")])[0])

    def test_rejects_boolean_size_and_unbounded_manifest(self):
        item={"path":"a.txt","sha256":"b"*64,"size":True}
        self.assertFalse(validate_manifest([item])[0])
        self.assertFalse(validate_manifest([{"path":str(i)+".txt","sha256":"b"*64,"size":1} for i in range(20001)])[0])

if __name__ == "__main__":
    unittest.main()
