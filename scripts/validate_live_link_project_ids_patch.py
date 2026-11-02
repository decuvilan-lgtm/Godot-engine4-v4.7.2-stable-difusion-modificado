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
require("bool live_link_id_is_valid = live_link_project_id.length() == 4;" in source and "live_link_project_id[i] <" in source and "live_link_project_id[i] >" in source, "only four decimal digits are displayed")
require('const String duplicate_suffix = "  ⚠ DUPLICATE ID";' in source and "duplicate_count > 1" in source, "duplicate local IDs are visibly flagged in Project Manager")
print("NOTE: automatic reassignment is not performed; users must resolve a displayed duplicate before connecting.")
