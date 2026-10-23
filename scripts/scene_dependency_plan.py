"""Dependency-closure planner for scene-aware Godot imports.

Source-level helper only: native Project Manager integration is a separate step.
It preserves res:// paths and fails closed on missing or unsafe dependencies.
"""
from __future__ import annotations
import re
from pathlib import PurePosixPath
from typing import Mapping

_EXT_RESOURCE = re.compile(r'^\[ext_resource\s+.*?\bpath\s*=\s*"?(res://[^"\s\]]+)"?', re.M)
_LOAD = re.compile(r'\b(?:load|preload)\s*\(\s*["\'](res://[^"\']+)["\']\s*\)')
# Resource properties outside ext_resource blocks can also point to files.
_PATH = re.compile(r'\bpath\s*=\s*["\'](res://[^"\']+)["\']')


class SceneImportError(ValueError):
    pass


def normalize_res_path(path: str) -> str:
    if not isinstance(path, str) or not path.startswith("res://"):
        raise SceneImportError(f"Not a project resource path: {path!r}")
    raw = path[6:]
    parts = raw.split("/")
    if not raw or any(p in ("", ".", "..") for p in parts) or "\\" in raw or "\0" in raw:
        raise SceneImportError(f"Unsafe project resource path: {path!r}")
    return "res://" + PurePosixPath(*parts).as_posix()


def dependencies_for_text(text: str) -> set[str]:
    """Collect explicit external resource paths and literal load/preload paths."""
    paths = set(_EXT_RESOURCE.findall(text))
    paths.update(_PATH.findall(text))
    paths.update(_LOAD.findall(text))
    return {normalize_res_path(path) for path in paths}


def plan_scene_import(selected: str, project_files: Mapping[str, str]) -> list[str]:
    """Return selected resource plus transitive text dependencies, stable sorted.

    project_files maps normalized res:// paths to UTF-8 text. Binary dependencies
    can be supplied as empty text and are included, but cannot expose dependencies
    without Godot's ResourceLoader and therefore require native traversal.
    """
    selected = normalize_res_path(selected)
    normalized = {normalize_res_path(k): v for k, v in project_files.items()}
    if selected not in normalized:
        raise SceneImportError(f"Selected scene is missing: {selected}")
    pending = [selected]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        text = normalized[current]
        for dependency in sorted(dependencies_for_text(text)):
            if dependency not in normalized:
                raise SceneImportError(f"Missing dependency {dependency} referenced by {current}")
            if dependency not in visited:
                pending.append(dependency)
    return sorted(visited)
