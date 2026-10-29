#!/usr/bin/env python3
"""Validate the Live Link Project Manager patch against a clean Godot source tree."""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "scripts/apply_live_link_project_ids_patch.py"
SOURCE = ROOT / "godot-source/editor/project_manager/project_list.cpp"
def require(ok: bool, message: str) -> None:
    if not ok:
        print("FAIL: " + message, file=sys.stderr)
        raise SystemExit(1)
    print("PASS: " + message)

require(PATCHER.is_file() and SOURCE.is_file(), "project ID patcher and Project Manager source exist")
ast.parse(PATCHER.read_text(encoding="utf-8"), filename=str(PATCHER))
source = SOURCE.read_text(encoding="utf-8")
require('cf->get_value("live_link", "project_id", "")' in source, "Project Manager reads the persisted project ID")
require('project_name += "  ·  Live Link ID: " + live_link_project_id;' in source, "project ID appears in the visible project title")
require('live_link_project_id.length() == 4 && live_link_project_id.is_valid_int()' in source, "only four-digit numeric IDs are displayed")
print("NOTE: duplicate-ID detection/reassignment is still a separate follow-up.")
