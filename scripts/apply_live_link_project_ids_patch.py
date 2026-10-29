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
    """\tif (cf_err == OK) {
\t\tcf_project_name = cf->get_value("application", "config/name", "");
\t\tif (!cf_project_name.is_empty()) {
\t\t\tproject_name = cf_project_name.xml_unescape();
\t\t}
\t\tconfig_version = (int)cf->get_value("", "config_version", 0);
\t}""",
    """\tString live_link_project_id;
\tif (cf_err == OK) {
\t\tcf_project_name = cf->get_value("application", "config/name", "");
\t\tif (!cf_project_name.is_empty()) {
\t\t\tproject_name = cf_project_name.xml_unescape();
\t\t}
\t\tconfig_version = (int)cf->get_value("", "config_version", 0);
\t\tlive_link_project_id = cf->get_value("live_link", "project_id", "");
\t\t// The ID is a public label, not a credential. Keep it visible in the project list.
\t\tbool live_link_id_is_valid = live_link_project_id.length() == 4;
\t\tfor (int i = 0; i < live_link_project_id.length(); i++) {
\t\t\tif (live_link_project_id[i] < '0' || live_link_project_id[i] > '9') {
\t\t\t\tlive_link_id_is_valid = false;
\t\t\t}
\t\t}
\t\tif (live_link_id_is_valid) {
\t\t\tproject_name += "  ·  Live Link ID: " + live_link_project_id;
\t\t}
\t}""")

replace_once(
    """\tfor (const String &path : sections) {
\t\tbool favorite = _config.get_value(path, "favorite", false);
\t\t_projects.push_back(load_project_data(path, favorite));
\t}""",
    """\tfor (const String &path : sections) {
\t\tbool favorite = _config.get_value(path, "favorite", false);
\t\t_projects.push_back(load_project_data(path, favorite));
\t}

\t// Four-digit IDs are labels, so detect local collisions instead of assuming uniqueness.
\tconst String id_marker = "  ·  Live Link ID: ";
\tconst String duplicate_suffix = "  ⚠ DUPLICATE ID";
\tfor (int i = 0; i < _projects.size(); i++) {
\t\tconst String &name = _projects[i].project_name;
\t\tint marker_pos = name.find(id_marker);
\t\tif (marker_pos < 0) {
\t\t\tcontinue;
\t\t}
\t\tString project_id = name.substr(marker_pos + id_marker.length());
\t\tint duplicate_count = 0;
\t\tfor (int j = 0; j < _projects.size(); j++) {
\t\t\tconst String &other_name = _projects[j].project_name;
\t\t\tint other_marker_pos = other_name.find(id_marker);
\t\t\tif (other_marker_pos >= 0 && other_name.substr(other_marker_pos + id_marker.length()) == project_id) {
\t\t\t\tduplicate_count++;
\t\t\t}
\t\t}
\t\tif (duplicate_count > 1) {
\t\t\t_projects.write[i].project_name += duplicate_suffix;
\t\t}
\t}""")

print("PASS: Project Manager displays valid four-digit IDs and flags local collisions.")
