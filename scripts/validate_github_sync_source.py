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
    ("_build_incremental_download_queue()", "queues missing files and any local content that differs from GitHub"),
    ("_git_blob_sha1", "verifies Git blob IDs against downloaded file contents"),
    ('digest.length() != 40 and digest.length() != 64', "accepts only supported Git SHA-1 or legacy SHA-256 manifest hashes"),
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
    ("Los cambios de GitHub se aplicaron.", "applies GitHub files directly as the source of truth"),
    ("Los respaldos previos se conservan en:", "preserves the backup location if applying a later operation fails"),
    ("se guardan fuera del proyecto", "explains that replaced/deleted local files are backed up outside the project"),
    ("_save_manifest()", "persists baseline for later deletions"),
    ('str(parsed.get("repository", "")) == active_repo', "only same-repository baseline permits deletion"),
    ("if not local_exists or local_sha != remote_sha:", "always compares local bytes directly to GitHub even when the previous upstream baseline is unchanged"),
    ("GitHub is the source of truth", "explicitly treats GitHub as authoritative over local edits"),
    ("GitHub is authoritative.", "stages project.godot exactly as downloaded from GitHub"),
    ('relative.begins_with("addons/github_sync/")', "sync cannot overwrite its own addon"),
    ('relative.begins_with("addons/terrain_3d/")', "sync cannot overwrite the terrain addon"),
    ('"delete"', "handles files removed from upstream"),
    ("EditorInterface.get_resource_filesystem().scan()", "rescans the editor filesystem after synchronization"),
    ("call_deferred(\"_auto_organize_project_scenes\")", "starts automatic scene organization on project load"),
    ("func _auto_organize_project_scenes() -> void:", "discovers all project scenes at startup"),
    ('await get_tree().process_frame', "waits for the initial editor filesystem scan"),
    ('dir_path: String = pending_dirs.pop_back()', "walks project directories recursively"),
    ('elif entry.ends_with(".tscn")', "collects every scene resource, including unreferenced child scenes"),
    ("packed_scene.get_state()", "reads serialized scene hierarchy without flattening nodes"),
    ("state.get_node_count()", "iterates scene nodes and descendants"),
    ("state.get_node_instance(node_index)", "traverses nested instanced-scene dependencies"),
    ("EditorInterface.open_scene_from_path(scene_path)", "opens scene resources as independent editor tabs"),
    ('EditorInterface.open_scene_from_path(main_scene)', "restores the configured main scene as the active tab"),
    ("Escenas que no se pudieron abrir", "reports unreadable scenes separately from script errors"),
    ("func _organize_synced_scenes(initial_paths: PackedStringArray, open_all_project_scenes: bool = false)", "organizes changed scenes into separate editor tabs"),
    ("state.get_node_instance(node_index)", "traverses nested instanced-scene dependencies"),
    ("EditorInterface.open_scene_from_path(scene_path)", "opens valid imported scenes as tabs without merging their nodes"),
    ("Escenas que no se pudieron abrir", "reports only unreadable scene resources after synchronization"),
]:

    require(token in gd, label)
require("zipball" not in gd.lower() and "ZIPReader" not in gd, "incremental sync does not download or extract repository ZIPs")
require("func _backup_local_changes() -> String:" in gd, "backs up local files before destructive updates/deletions")
require('const BACKUP_DIR := "github_sync_backups"' in gd and 'user://%s/%s/%s' in gd, "stores backups outside the project in per-project, per-session folders")
require("backup_error := _backup_local_changes()" in gd and "No se aplicó ningún cambio" in gd, "aborts before project mutation if backups cannot be prepared")
require("MAX_TOTAL_BYTES" in gd and "MAX_FILE_BYTES" in gd and "files_to_backup" in gd, "bounds backup sizes to protect device storage")
require("not _is_safe_relative_path(relative) or _is_ignored_path(relative)" in gd, "rejects unsafe manifest paths before backups or file mutations")
require('expected_hash.length() == 64 else _git_blob_sha1(local_path)' in gd, "compares deletion candidates using the same hash algorithm as their manifest")
require("never uploads local files" in config.read_text(encoding="utf-8").lower(), "one-way sync remains documented as no-upload")
patcher_text = patcher.read_text(encoding="utf-8")
require("TERRAIN_DATA_GD" in patcher_text and "terrain_plugin_setting" in patcher_text and "editor_plugins" in patcher_text,
        "installer embeds and enables both custom editor addons")
require("before the editor process starts" in patcher_text and "MANAGER_SOURCE" in patcher_text,
        "existing projects are provisioned before the editor process starts")
print("Source-only checks passed; no C++ compilation, GDScript parse, APK, or device runtime is implied.")
