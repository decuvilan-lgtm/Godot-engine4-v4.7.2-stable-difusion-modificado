#!/usr/bin/env python3
"""Source-only checks for the GitHub sync addon and its installer patch."""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]

def require(ok: bool, message: str) -> None:
    if not ok:
        print("FAIL: " + message, file=sys.stderr)
        raise SystemExit(1)
    print("PASS: " + message)

patcher = ROOT / "scripts/apply_github_sync_patch.py"
addon = ROOT / "scripts/github_sync_addon/plugin.gd"
config = ROOT / "scripts/github_sync_addon/plugin.cfg"
require(patcher.is_file() and addon.is_file() and config.is_file(), "sync patcher and addon sources exist")
ast.parse(patcher.read_text(encoding="utf-8"), filename=str(patcher))
ast.parse((ROOT / "scripts/apply_github_import_patch.py").read_text(encoding="utf-8"), filename="apply_github_import_patch.py")
require(True, "sync patcher and existing source patcher have valid Python syntax")
gd = addon.read_text(encoding="utf-8")
for token, label in [
    ("Sincronizar GitHub", "visible in-editor sync button"),
    ("HTTPRequest", "network requests use Godot HTTPRequest"),
    ("api.github.com/repos/%s/zipball", "downloads a repository archive from GitHub"),
    ("_build_change_plan()", "previews the change set before writing"),
    ("_show_preview()", "presents the change preview"),
    ("_apply_changes()", "applies only after explicit confirmation"),
    ("_rollback_operations(transaction_root)", "attempts rollback when applying changes fails"),
    ("transaction_root = OS.get_user_data_dir()", "creates transaction backups outside the project"),
    ("_save_manifest()", "persists baseline for later deletions"),
    ("_ensure_sync_plugin_enabled(staged_project)", "keeps the editor plugin enabled when project.godot changes"),
    ('relative.begins_with("addons/github_sync/")', "sync cannot overwrite its own addon"),
    ("RESCUE_DIR", "rescue directory is outside the project"),
    ("DirAccess.copy_absolute(local_path, rescue_copy)", "modified local files are copied to rescue before overwrite/delete"),
    ('"delete"', "handles files removed from upstream"),
    ("EditorInterface.get_resource_filesystem().scan()", "rescans the editor filesystem after synchronization"),
]:
    require(token in gd, label)
require("never uploads" in gd.lower() or "never uploads" in config.read_text(encoding="utf-8").lower(),
        "one-way sync is documented as no-upload")
patcher_text = patcher.read_text(encoding="utf-8")
require("GitHubSyncAddonData::PLUGIN_GD" in patcher_text and "editor_plugins" in patcher_text,
        "installer embeds and enables the plugin for ZIP-installed projects")
print("Source-only checks passed; no C++ compilation, GDScript parse, APK, or device runtime is implied.")
