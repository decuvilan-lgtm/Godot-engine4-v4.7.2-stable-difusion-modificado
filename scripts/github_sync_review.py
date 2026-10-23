"""Review snapshot helpers for a future native Analyze → Review → Sync UI.

This module does not access the network or modify project files. It binds a
reviewable change list to the exact project, repository, ref and commit.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Iterable

from github_sync_core import Change, SyncError, normalize_repo_path


def _canonical_repo_url(url: str) -> str:
    value = (url or "").strip().rstrip("/")
    if not value.startswith("https://github.com/"):
        raise SyncError("Only canonical HTTPS GitHub repository URLs are supported.")
    parts = value.removeprefix("https://github.com/").split("/")
    if len(parts) != 2 or any(not part or part in (".", "..") for part in parts):
        raise SyncError("Repository URL must identify exactly owner/repository.")
    if any(ch in value for ch in "?#\\"):
        raise SyncError("Repository URL must not contain query, fragment, or backslash.")
    return value


def create_review_snapshot(project_root: Path, repository_url: str, ref_name: str,
                           commit_sha: str, changes: Iterable[Change]) -> dict:
    """Create deterministic review data, pinned to one project and remote commit."""
    root = project_root.resolve()
    if not (root / "project.godot").is_file():
        raise SyncError("Selected folder is not a Godot project.")
    repo = _canonical_repo_url(repository_url)
    if not ref_name or any(ch.isspace() for ch in ref_name):
        raise SyncError("A non-empty branch/tag/ref is required.")
    if len(commit_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in commit_sha):
        raise SyncError("Review requires a full 40-character commit SHA.")
    rows = []
    seen = set()
    for change in changes:
        path = normalize_repo_path(change.path)
        if path in seen:
            raise SyncError(f"Duplicate path in review plan: {path}")
        seen.add(path)
        if change.action not in {"add", "update", "delete", "unchanged", "local-only"}:
            raise SyncError(f"Unknown action in review plan: {change.action}")
        rows.append(asdict(change) | {"path": path})
    rows.sort(key=lambda item: item["path"])
    counts = {action: sum(1 for row in rows if row["action"] == action)
              for action in ("add", "update", "delete", "unchanged", "local-only")}
    identity = {
        "project_root": str(root),
        "repository_url": repo,
        "ref": ref_name,
        "commit_sha": commit_sha.lower(),
        "changes": rows,
    }
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return identity | {
        "counts": counts,
        "fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def validate_review_snapshot(snapshot: dict, project_root: Path, repository_url: str,
                             ref_name: str, commit_sha: str) -> None:
    """Fail closed if review context changed before sync confirmation."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("fingerprint"), str):
        raise SyncError("Review snapshot is missing its fingerprint.")
    expected = create_review_snapshot(
        project_root, repository_url, ref_name, commit_sha,
        [Change(**row) for row in snapshot.get("changes", [])],
    )
    if snapshot["fingerprint"] != expected["fingerprint"]:
        raise SyncError("Review plan was modified or is stale; analyze again before syncing.")
