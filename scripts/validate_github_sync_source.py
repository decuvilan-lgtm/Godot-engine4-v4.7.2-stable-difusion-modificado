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
    ("MAX_TREE_FILES := 6000", "tree entry count is bounded"),
    ("MAX_FILE_BYTES := 256 * 1024 * 1024", "single-file download size is bounded at 256 MiB"),
    ("MAX_TOTAL_BYTES := 1024 * 1024 * 1024", "total staged downloads are bounded at 1 GiB"),
    ("api.github.com/repos/%s/git/trees/%s?recursive=1", "enumerates repository tree instead of downloading a ZIP"),
    ("raw.githubusercontent.com/%s/%s/%s", "downloads changed file content pinned to a commit SHA"),
    ("bool(parsed.get(\"truncated\", false))", "rejects truncated GitHub trees instead of silently syncing partial data"),
    ("_build_incremental_download_queue()", "queues only missing or changed files"),
    ("_git_blob_sha1", "verifies Git blob IDs against downloaded file contents"),
    ("legacy_baseline", "migrates old SHA-256 manifests without trusting them as Git blob IDs"),
    ("_build_change_plan()", "plans tracked deletions before preview"),
    ("_show_preview()", "presents the change preview"),
    ("_apply_changes()", "applies only after explicit confirmation"),
    ("_copy_file_streaming(staged_path, local_path)", "applies large files with bounded memory and replaces their original paths"),
    ("func _log_sync(message: String", "routes sync events to Output and warnings/errors to the debugger"),
    ('"ARCHIVO ACTUALIZADO', "logs successful file overwrites to Output"),
    ("func _detect_possible_moves()", "detects probable moves/renames from matching blob IDs"),
    ("func _read_scene_connections(scene_path: String)", "compares serialized .tscn signal connections before replacement"),
    ("REVISAR CONEXIONES DE ESCENA", "warns in debugger when serialized scene connections change"),
    ("Las escenas .tscn se actualizan en su misma ruta", "documents in-place scene replacement and serialized connections"),
    ("func _cleanup_staging()", "removes temporary staged changed files"),
    ("preview_dialog.canceled.connect(_on_preview_dismissed)", "cleans staged files when the user cancels preview"),
    ("preview_dialog.close_requested.connect(_on_preview_dismissed)", "cleans staged files when the preview window is closed"),
    ("_cleanup_staging()\n\tif request and is_instance_valid(request):", "cleans staging when the plugin unloads"),
    ("Se aplicaron los cambios de GitHub directamente", "applies GitHub files directly as the source of truth"),
    ("No se crearon copias de respaldo.", "reports retryable sync failure without creating backups"),
    ("No crea copias ni sube archivos.", "documents the no-backup mobile-storage policy"),
    ("_save_manifest()", "persists baseline for later deletions"),
    ('str(parsed.get("repository", "")) == active_repo', "only same-repository baseline permits deletion"),
    ("_ensure_sync_plugin_enabled(staged_path)", "keeps editor plugins enabled when project.godot changes"),
    ('relative.begins_with("addons/github_sync/")', "sync cannot overwrite its own addon"),
    ('relative.begins_with("addons/terrain_3d/")', "sync cannot overwrite the terrain addon"),
    ('"delete"', "handles files removed from upstream"),
    ("EditorInterface.get_resource_filesystem().scan()", "rescans the editor filesystem after synchronization"),
]:

    require(token in gd, label)
require("zipball" not in gd.lower() and "ZIPReader" not in gd, "incremental sync does not download or extract repository ZIPs")
require("Copias de rescate" not in gd, "does not create permanent rescue copies")
require("transaction_root" not in gd, "does not create transaction backup copies")
require("DirAccess.copy_absolute" not in gd, "does not copy local files during synchronization")
require("DirAccess.copy_absolute" not in gd, "does not copy local files during synchronization")
require("no se crearon copias" in gd.lower() and "never uploads local files" in config.read_text(encoding="utf-8").lower(),
        "one-way sync is documented as no-upload")
patcher_text = patcher.read_text(encoding="utf-8")
require("TERRAIN_DATA_GD" in patcher_text and "terrain_plugin_setting" in patcher_text and "editor_plugins" in patcher_text,
        "installer embeds and enables both custom editor addons")
require("before the editor process starts" in patcher_text and "MANAGER_SOURCE" in patcher_text,
        "existing projects are provisioned before the editor process starts")
print("Source-only checks passed; no C++ compilation, GDScript parse, APK, or device runtime is implied.")
