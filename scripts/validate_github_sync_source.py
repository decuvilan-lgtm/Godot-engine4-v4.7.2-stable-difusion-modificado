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
    ("transaction_root := OS.get_user_data_dir()", "creates transaction backups outside the project"),
    ("_save_manifest()", "persists baseline for later deletions"),
    ('str(parsed.get("repository", "")) == active_repo', "only same-repository baseline permits deletion"),
    ("MAX_ARCHIVE_BYTES", "limits downloaded archive size on mobile"),
    ("MAX_ARCHIVE_FILES", "limits archive entry count"),
    ("MAX_SINGLE_FILE_BYTES", "limits individual staged file size"),
    ("MAX_TOTAL_STAGED_BYTES", "limits expanded staged content"),
    ("not entry.begins_with(archive_root + \"/\")", "rejects ZIP paths outside the GitHub archive root"),
    ("_ensure_sync_plugin_enabled(staged_project)", "keeps the editor plugin enabled when project.godot changes"),
    ('relative.begins_with("addons/github_sync/")', "sync cannot overwrite its own addon"),
    ('relative.begins_with("addons/terrain_3d/")', "sync cannot overwrite the terrain addon"),
    ("RESCUE_DIR", "rescue directory is outside the project"),
    ("DirAccess.copy_absolute(local_path, rescue_copy)", "modified local files are copied to rescue before overwrite/delete"),
    ('"delete"', "handles files removed from upstream"),
    ("EditorInterface.get_resource_filesystem().scan()", "rescans the editor filesystem after synchronization"),
]:
    require(token in gd, label)
require("No sube archivos." in gd and "never uploads local files" in config.read_text(encoding="utf-8").lower(),
        "one-way sync is documented as no-upload")
patcher_text = patcher.read_text(encoding="utf-8")
require("TERRAIN_DATA_GD" in patcher_text and "terrain_plugin_setting" in patcher_text and "editor_plugins" in patcher_text,
        "installer embeds and enables both custom editor addons")
require("install custom addons before launching any existing project" in patcher_text and "MANAGER_SOURCE" in patcher_text,
        "existing projects are provisioned before the editor process starts")
print("Source-only checks passed; no C++ compilation, GDScript parse, APK, or device runtime is implied.")
