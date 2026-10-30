#!/usr/bin/env python3
"""Validate safe MCP addon embedding into desktop ZIP-installed projects."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1] / "godot-source"
HEADER = ROOT / "editor/github_sync_addon_data.h"
DIALOG = ROOT / "editor/project_manager/project_dialog.cpp"

def require(condition: bool, message: str) -> None:
    if not condition:
        print("FAIL: " + message, file=sys.stderr)
        raise SystemExit(1)
    print("PASS: " + message)

require(HEADER.is_file() and DIALOG.is_file(), "generated addon header and ProjectDialog source exist")
header = HEADER.read_text(encoding="utf-8")
dialog = DIALOG.read_text(encoding="utf-8")
match = re.search(r"MCP_FILE_COUNT = (\d+);", header)
require(match is not None and int(match.group(1)) > 0, "safe MCP addon files are embedded in the Linux build")
require("MCP_FILE_PATHS[]" in header and "MCP_FILE_CONTENTS[]" in header, "embedded file paths and contents are present")
require("execute_script_tool.gd" not in header, "arbitrary execute-script tool is absent from the packaged addon")
require("send_live_link_changes_tool.gd" in header and "get_live_link_status_tool.gd" in header, "MCP exposes typed Live Link status and send tools")
require("MCP_FILE_COUNT > 0" in dialog and "mcp_plugin_setting" in dialog, "Project Manager installs and enables the addon only when packaged")
require("#ifndef ANDROID_ENABLED" in dialog, "automatic MCP installation is limited to desktop editor builds")
print("PASS: desktop MCP addon embedding checks completed")
