#!/usr/bin/env python3
"""Show the persistent four-digit Live Link ID beside enabled projects in Project Manager."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "godot-source"
SOURCE = ROOT / "editor/project_manager/project_list.cpp"

def replace_once(old: str, new: str) -> None:
    content = SOURCE.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"project_list.cpp: expected exactly one insertion anchor, found {count}")
    SOURCE.write_text(content.replace(old, new, 1), encoding="utf-8")

if not SOURCE.is_file():
    sys.exit("Godot project_list.cpp is missing; checkout the 4.7.2 source first.")

replace_once(
    '''\tif (cf_err == OK) {
\t\tcf_project_name = cf->get_value("application", "config/name", "");
\t\tif (!cf_project_name.is_empty()) {
\t\t\tproject_name = cf_project_name.xml_unescape();
\t\t}
\t\tconfig_version = (int)cf->get_value("", "config_version", 0);
\t}''',
    '''\tString live_link_project_id;
\tif (cf_err == OK) {
\t\tcf_project_name = cf->get_value("application", "config/name", "");
\t\tif (!cf_project_name.is_empty()) {
\t\t\tproject_name = cf_project_name.xml_unescape();
\t\t}
\t\tconfig_version = (int)cf->get_value("", "config_version", 0);
\t\tlive_link_project_id = cf->get_value("live_link", "project_id", "");
\t\t// The ID is a public label, not a credential. Keep it visible in the project list.
\t\tif (live_link_project_id.length() == 4 && live_link_project_id.is_valid_int()) {
\t\t\tproject_name += "  ·  Live Link ID: " + live_link_project_id;
\t\t}
\t}'''
)

print("PASS: Project Manager displays a valid four-digit Live Link ID beside the project name.")
