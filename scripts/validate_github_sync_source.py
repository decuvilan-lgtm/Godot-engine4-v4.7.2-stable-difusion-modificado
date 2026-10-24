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
    ("MAX_ARCHIVE_FILES := 6000", "archive entry count is bounded"),
    ("MAX_FILE_BYTES := 16 * 1024 * 1024", "single-file extraction size is bounded"),
    ("MAX_TOTAL_BYTES := 100 * 1024 * 1024", "total extracted data is bounded"),
    ("if not _save_manifest()", "no-op sync updates the repository baseline"),
    ("api.github.com/repos/%s/zipball", "downloads a repository archive from GitHub"),
    ("_build_change_plan()", "previews the change set before writing"),
    ("_show_preview()", "presents the change preview"),
    ("_apply_changes()", "applies only after explicit confirmation"),
    ("func _cleanup_staging()", "removes temporary archive and extracted repository after sync"),
    ("DirAccess.remove_absolute(absolute_zip)", "deletes the downloaded ZIP from mobile storage"),
    ("GitHub is the source of truth", "applies GitHub files directly as the source of truth"),
    ("No se crearon copias.", "reports retryable sync failure without creating backups"),
    ("Deliberately create no backup or transaction copies", "documents the no-backup mobile-storage policy"),
    ("_save_manifest()", "persists baseline for later deletions"),
    ('str(parsed.get("repository", "")) == active_repo', "only same-repository baseline permits deletion"),
    ("MAX_ARCHIVE_BYTES", "limits downloaded archive size on mobile"),
    ("MAX_ARCHIVE_FILES", "limits archive entry count"),
    ("MAX_FILE_BYTES", "limits individual staged file size"),
    ("MAX_TOTAL_BYTES", "limits expanded staged content"),
    ("not entry.begins_with(archive_root + \"/\")", "rejects ZIP paths outside the GitHub archive root"),
    ("_ensure_sync_plugin_enabled(staged_project)", "keeps the editor plugin enabled when project.godot changes"),
    ('relative.begins_with("addons/github_sync/")', "sync cannot overwrite its own addon"),
    ('relative.begins_with("addons/terrain_3d/")', "sync cannot overwrite the terrain addon"),
    ("Copias de rescate" not in gd, "does not create permanent rescue copies"),
    ("transaction_root" not in gd, "does not create transaction backup copies"),
    ("DirAccess.copy_absolute" not in gd, "does not copy local files during synchronization"),
    ('"delete"', "handles files removed from upstream"),
    ("EditorInterface.get_resource_filesystem().scan()", "rescans the editor filesystem after synchronization"),
]:
    require(token in gd, label)
require("no se crearon copias" in gd.lower() and "never uploads local files" in config.read_text(encoding="utf-8").lower(),
        "one-way sync is documented as no-upload")
patcher_text = patcher.read_text(encoding="utf-8")
require("TERRAIN_DATA_GD" in patcher_text and "terrain_plugin_setting" in patcher_text and "editor_plugins" in patcher_text,
        "installer embeds and enables both custom editor addons")
require("before the editor process starts" in patcher_text and "MANAGER_SOURCE" in patcher_text,
        "existing projects are provisioned before the editor process starts")
print("Source-only checks passed; no C++ compilation, GDScript parse, APK, or device runtime is implied.")
