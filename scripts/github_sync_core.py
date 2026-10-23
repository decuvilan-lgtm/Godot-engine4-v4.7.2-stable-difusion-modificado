"""Reference core for GitHub project synchronization.

This module is deliberately independent of the editor UI. It provides the
algorithms and transactional filesystem layer that the Android Project Manager
integration must call; it is not itself the native UI integration.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping


MANIFEST_VERSION = 1
IGNORED_PARTS = {".git", ".godot", ".github"}
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
MANIFEST_NAME = "github_sync_manifest.json"


class SyncError(RuntimeError):
    """Raised when a sync cannot safely continue."""


def git_blob_sha1(data: bytes) -> str:
    """Return Git's canonical blob object ID for bytes."""
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def normalize_repo_path(raw: str) -> str:
    """Validate a remote repository path and return normalized POSIX form."""
    if not isinstance(raw, str) or not raw or "\0" in raw or "\\" in raw:
        raise SyncError("Invalid repository path.")
    if raw.startswith("/") or raw.startswith("~") or (len(raw) >= 2 and raw[1] == ":"):
        raise SyncError("Absolute paths are not allowed.")
    p = PurePosixPath(raw)
    if any(part in ("", ".", "..") for part in raw.split("/")):
        raise SyncError("Path traversal or empty path segment rejected.")
    if p.is_absolute() or not p.parts:
        raise SyncError("Invalid repository path.")
    return p.as_posix()


def safe_target(root: Path, relative: str) -> Path:
    """Resolve a target under root without following symlinks outside root."""
    rel = normalize_repo_path(relative)
    root_resolved = root.resolve()
    target = root_resolved.joinpath(*PurePosixPath(rel).parts)
    cursor = root_resolved
    for part in PurePosixPath(rel).parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise SyncError(f"Refusing to traverse symlink: {rel}")
    if target.is_symlink():
        raise SyncError(f"Refusing to replace symlink: {rel}")
    try:
        target.resolve(strict=False).relative_to(root_resolved)
    except ValueError as exc:
        raise SyncError(f"Path escapes project root: {rel}") from exc
    return target


def should_ignore(relative: str, extra_ignores: Iterable[str] = ()) -> bool:
    rel = PurePosixPath(relative)
    if any(part in IGNORED_PARTS for part in rel.parts):
        return True
    if rel.name in IGNORED_NAMES or rel.name == MANIFEST_NAME:
        return True
    return any(relative == rule or relative.startswith(rule.rstrip("/") + "/")
               for rule in extra_ignores)


def inventory_local(root: Path, extra_ignores: Iterable[str] = ()) -> dict[str, dict]:
    """Inventory regular files only; never traverse symlink directories."""
    root = root.resolve()
    found: dict[str, dict] = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        base_path = Path(base)
        dirs[:] = sorted(d for d in dirs if not (base_path / d).is_symlink())
        for name in sorted(files):
            path = base_path / name
            rel = path.relative_to(root).as_posix()
            if should_ignore(rel, extra_ignores) or path.is_symlink() or not path.is_file():
                continue
            data = path.read_bytes()
            found[rel] = {"git_blob_sha": git_blob_sha1(data), "size": len(data)}
    return found


@dataclass(frozen=True)
class Change:
    path: str
    action: str
    remote_sha: str | None = None
    local_sha: str | None = None
    size: int = 0
    reason: str = ""


def build_plan(
    remote_tree: Mapping[str, Mapping],
    local_inventory: Mapping[str, Mapping],
    previous_manifest: Mapping | None,
    extra_ignores: Iterable[str] = (),
) -> list[Change]:
    """Build deterministic add/update/delete/local-only/unchanged plan.

    remote_tree maps path to Git tree entries (type, sha, size, mode).
    The prior successful manifest is the authority for tracked remote deletes.
    """
    manifest = previous_manifest or {}
    old_files = manifest.get("tracked_files", {})
    remote: dict[str, Mapping] = {}
    for raw_path, item in remote_tree.items():
        path = normalize_repo_path(raw_path)
        if should_ignore(path, extra_ignores) or item.get("type") != "blob":
            continue
        sha = item.get("sha")
        if not isinstance(sha, str) or len(sha) != 40:
            raise SyncError(f"Invalid Git blob ID for {path}")
        remote[path] = item

    changes: list[Change] = []
    all_paths = sorted(set(remote) | set(local_inventory) | set(old_files))
    for path in all_paths:
        if should_ignore(path, extra_ignores):
            continue
        r = remote.get(path)
        l = local_inventory.get(path)
        old = old_files.get(path)
        if r is not None:
            rsha = str(r["sha"])
            lsha = l.get("git_blob_sha") if l else None
            size = int(r.get("size") or 0)
            if l is None:
                changes.append(Change(path, "add", rsha, None, size, "Present in remote, absent locally."))
            elif lsha == rsha:
                changes.append(Change(path, "unchanged", rsha, str(lsha), size,
                                      "Local Git blob matches remote."))
            else:
                old_sha = old.get("sha") if old is not None else None
                if old_sha is None or lsha != old_sha:
                    # Never replace untracked or locally edited content silently.
                    changes.append(Change(
                        path, "local-only", None, str(lsha), int(l.get("size") or 0),
                        "CONFLICT: local bytes differ from the last synced version (or no version is tracked); preserved.",
                    ))
                else:
                    changes.append(Change(path, "update", rsha, str(lsha), size,
                                          "Remote changed since last sync; local bytes still match the last synced version."))
        elif old is not None:
            old_sha = old.get("sha")
            local_sha = str(l.get("git_blob_sha")) if l else None
            if l is not None and local_sha != old_sha:
                # Remote removal is authoritative, but preserve edited bytes outside the project.
                changes.append(Change(
                    path, "archive", None, local_sha, int(l.get("size") or 0),
                    "Remote deleted this tracked file; local edits will be moved outside the project to a recovery folder.",
                ))
            else:
                changes.append(Change(path, "delete", None, local_sha,
                                      int(old.get("size") or 0),
                                      "Previously tracked file was deleted remotely and local bytes still match the last synced version."))
        elif l is not None:
            changes.append(Change(path, "local-only", None,
                                  str(l.get("git_blob_sha")), int(l.get("size") or 0),
                                  "Not tracked by the last sync and absent from remote; left untouched."))
    return changes


def project_manifest_path(metadata_root: Path, project_root: Path) -> Path:
    """Return a stable, separate manifest location for one canonical project root."""
    canonical_root = str(project_root.resolve())
    identity = hashlib.sha256(canonical_root.encode("utf-8")).hexdigest()
    return metadata_root.resolve() / "github_sync" / identity / MANIFEST_NAME


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"version": MANIFEST_VERSION, "tracked_files": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SyncError(f"Cannot read sync manifest: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != MANIFEST_VERSION:
        raise SyncError("Unsupported or invalid sync manifest version.")
    if not isinstance(value.get("tracked_files"), dict):
        raise SyncError("Invalid tracked_files manifest field.")
    return value


def write_json_atomic(path: Path, value: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".manifest-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def apply_plan(
    root: Path,
    changes: Iterable[Change],
    content_provider: Callable[[str, str], bytes],
    manifest_path: Path,
    repo_url: str,
    ref_name: str,
    commit_sha: str,
    extra_ignores: Iterable[str] = (),
) -> dict:
    """Apply a reviewed plan with staging, backups, verification and rollback.

    content_provider(path, expected_blob_sha) fetches the exact blob content.
    Call only after the caller revalidates the remote commit and user confirms
    the destructive operation counts.
    """
    # Materialize once: the plan is consumed for validation and again when
    # writing the successful manifest. A generator must not silently empty it.
    changes = list(changes)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not (root / "project.godot").is_file():
        raise SyncError("Selected folder is not a Godot project (project.godot missing).")
    manifest = load_manifest(manifest_path)
    project_identity = str(root.resolve())
    # A non-empty legacy manifest without an identity cannot safely authorize
    # deletes: it may have been copied from another project.
    if manifest.get("tracked_files") and not manifest.get("project_root"):
        raise SyncError("Existing sync manifest has no project identity; analyze again to create a project-bound manifest.")
    recorded_root = manifest.get("project_root")
    if recorded_root and str(Path(recorded_root).resolve()) != project_identity:
        raise SyncError("Sync manifest belongs to a different local project. Refusing to apply this plan.")
    recorded_repo = manifest.get("repository_url")
    if recorded_repo and recorded_repo.rstrip("/") != repo_url.rstrip("/"):
        raise SyncError("Sync manifest belongs to a different GitHub repository. Re-link and analyze before syncing.")
    selected = [c for c in changes if c.action in ("add", "update", "delete", "archive")]
    tracked_before_sync = manifest.get("tracked_files", {})
    for c in selected:
        normalized_path = normalize_repo_path(c.path)
        if normalized_path != c.path:
            raise SyncError(f"Plan contains a non-normalized path: {c.path}")
        if should_ignore(c.path, extra_ignores):
            raise SyncError(f"Plan includes an excluded path: {c.path}")
        if c.action == "delete" and c.path not in tracked_before_sync:
            raise SyncError(f"Refusing to delete a file not tracked by the previous successful sync: {c.path}")
        target = safe_target(root, c.path)
        if c.action == "add" and target.exists():
            raise SyncError(f"Local file appeared after analysis; refusing to overwrite it: {c.path}")
        if c.action == "update":
            prior = tracked_before_sync.get(c.path)
            if prior is None or not prior.get("sha"):
                raise SyncError(f"Refusing to overwrite an existing file that was never tracked by a successful sync: {c.path}")
            if c.local_sha != prior.get("sha"):
                raise SyncError(f"Local file has edits since the last successful sync; conflict preserved: {c.path}")
            if not target.is_file() or c.local_sha is None:
                raise SyncError(f"Local file changed after analysis; re-analyze before syncing: {c.path}")
            if git_blob_sha1(target.read_bytes()) != c.local_sha:
                raise SyncError(f"Local file changed after analysis; re-analyze before syncing: {c.path}")
        if c.action == "delete":
            prior = tracked_before_sync.get(c.path)
            if prior is None:
                raise SyncError(f"Refusing to delete a file not tracked by the previous successful sync: {c.path}")
            if target.exists() and c.local_sha is not None:
                if prior.get("sha") != c.local_sha:
                    raise SyncError(f"Refusing to delete locally edited tracked file; conflict preserved: {c.path}")
                if not target.is_file() or git_blob_sha1(target.read_bytes()) != c.local_sha:
                    raise SyncError(f"Tracked file changed after analysis; re-analyze before deleting: {c.path}")

    txid = uuid.uuid4().hex
    transaction_root = manifest_path.parent / ("sync-recovery-" + txid)
    staged = transaction_root / "staged"
    backup = transaction_root / "backup"
    staged.mkdir(parents=True, exist_ok=False)
    backup.mkdir(parents=True, exist_ok=True)
    journal: list[dict] = []
    staged_hashes: dict[str, str] = {}
    committed = False

    try:
        # Download and verify all replacement bytes before touching project files.
        for c in selected:
            if c.action in ("add", "update"):
                data = content_provider(c.path, str(c.remote_sha))
                if not isinstance(data, bytes) or git_blob_sha1(data) != c.remote_sha:
                    raise SyncError(f"Downloaded blob hash mismatch: {c.path}")
                stage_path = safe_target(staged, c.path)
                stage_path.parent.mkdir(parents=True, exist_ok=True)
                stage_path.write_bytes(data)
                staged_hashes[c.path] = c.remote_sha or ""

        # Journal the complete intended transaction before mutation.
        for c in selected:
            target = safe_target(root, c.path)
            existed = target.exists()
            # Downloads may take time: re-check the reviewed local state immediately
            # before backing up and applying any mutation.
            if c.action == "add" and existed:
                raise SyncError(f"Local file appeared during sync; refusing to overwrite it: {c.path}")
            if c.action == "update":
                if not target.is_file() or c.local_sha is None or git_blob_sha1(target.read_bytes()) != c.local_sha:
                    raise SyncError(f"Local file changed during sync; re-analyze before syncing: {c.path}")
            if c.action == "delete" and c.local_sha is not None and existed:
                if not target.is_file() or git_blob_sha1(target.read_bytes()) != c.local_sha:
                    raise SyncError(f"Tracked file changed during sync; re-analyze before deleting: {c.path}")
            journal.append({"path": c.path, "action": c.action, "existed": existed})
            if existed:
                if not target.is_file():
                    raise SyncError(f"Target is not a regular file: {c.path}")
                backup_path = safe_target(backup, c.path)
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_path)
        write_json_atomic(transaction_root / "journal.json", {
            "transaction_id": txid, "commit": commit_sha, "operations": journal
        })

        # Apply. Remote-deleted tracked files are removed; unrelated local-only files survive.
        for c in selected:
            target = safe_target(root, c.path)
            if c.action == "delete":
                if target.exists():
                    target.unlink()
            elif c.action == "archive":
                archive_target = manifest_path.parent / "preserved-remote-deletions" / txid / c.path
                archive_target.parent.mkdir(parents=True, exist_ok=True)
                if not target.is_file() or c.local_sha is None or git_blob_sha1(target.read_bytes()) != c.local_sha:
                    raise SyncError(f"Locally edited file changed during sync: {c.path}")
                if archive_target.exists():
                    raise SyncError(f"Archive destination already exists: {c.path}")
                os.replace(target, archive_target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(safe_target(staged, c.path), target)

        # Verify every affected path before making the new manifest authoritative.
        for c in selected:
            target = safe_target(root, c.path)
            if c.action in ("delete", "archive"):
                if target.exists():
                    raise SyncError(f"Remote-deleted file still exists in project: {c.path}")
                if c.action == "archive":
                    archive_target = manifest_path.parent / "preserved-remote-deletions" / txid / c.path
                    if not archive_target.is_file() or git_blob_sha1(archive_target.read_bytes()) != c.local_sha:
                        raise SyncError(f"Archived file verification failed: {c.path}")
            else:
                if not target.is_file() or git_blob_sha1(target.read_bytes()) != c.remote_sha:
                    raise SyncError(f"Post-sync verification failed: {c.path}")

        remote_tracked = {}
        for c in changes:
            if c.action in ("add", "update", "unchanged") and c.remote_sha:
                remote_tracked[c.path] = {"sha": c.remote_sha, "size": c.size}
        new_manifest = {
            "version": MANIFEST_VERSION,
            "project_root": project_identity,
            "repository_url": repo_url,
            "ref": ref_name,
            "commit_sha": commit_sha,
            "tracked_files": remote_tracked,
            "ignore_rules": sorted(set(extra_ignores)),
            "last_successful_sync_unix": int(time.time()),
            "previous_transaction_id": txid,
        }
        write_json_atomic(manifest_path, new_manifest)
        committed = True
        return {"transaction_id": txid, "manifest": new_manifest,
                "changed_count": len(selected), "recovery_path": str(transaction_root)}
    except Exception as exc:
        rollback_errors = []
        for item in reversed(journal):
            try:
                target = safe_target(root, item["path"])
                backup_path = safe_target(backup, item["path"])
                if item.get("action") == "archive" and item.get("existed"):
                    archived = manifest_path.parent / "preserved-remote-deletions" / txid / item["path"]
                    if archived.is_file():
                        archived.unlink()
                if item["existed"] and backup_path.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_path, target)
                elif not item["existed"] and target.exists():
                    if target.is_file():
                        target.unlink()
                    else:
                        raise SyncError(f"Rollback target became a directory: {item['path']}")
            except Exception as rollback_exc:
                rollback_errors.append(f"{item['path']}: {rollback_exc}")
        detail = f"Sync failed and rollback was attempted: {exc}"
        if rollback_errors:
            detail += " | Rollback needs manual recovery: " + "; ".join(rollback_errors)
        raise SyncError(detail) from exc
    finally:
        # Keep transaction recovery data when anything failed or until a future
        # explicit cleanup policy is implemented. Never delete recovery on failure.
        if committed:
            pass
