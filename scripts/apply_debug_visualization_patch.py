#!/usr/bin/env python3
"""Expose Godot's native runtime collision/path/navigation debug hints in GameView.

This patch adds a small first tranche of independent toggles. The runtime flags
are handled by SceneDebugger and SceneTree; it does not add scripts to projects.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "godot-source"
GAME_H = ROOT / "editor/run/game_view_plugin.h"
GAME_CPP = ROOT / "editor/run/game_view_plugin.cpp"
SCENE_H = ROOT / "scene/debugger/scene_debugger.h"
SCENE_CPP = ROOT / "scene/debugger/scene_debugger.cpp"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one patch anchor, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    for path in (GAME_H, GAME_CPP, SCENE_H, SCENE_CPP):
        if not path.is_file():
            raise SystemExit(f"Godot 4.7.2 source file not found: {path}")

    # Keep the enum values aligned between editor and runtime message handler.
    replace_once(
        GAME_H,
        "\tvoid set_debug_mute_audio(bool p_enabled);",
        "\tvoid set_debug_mute_audio(bool p_enabled);\n"
        "\tvoid set_debug_visualization(int p_kind, bool p_enabled);",
    )
    replace_once(
        GAME_H,
        "\t\tPREVIEW_DEBUG_MUTE_AUDIO,\n\t};",
        "\t\tPREVIEW_DEBUG_MUTE_AUDIO,\n"
        "\t\tPREVIEW_DEBUG_COLLISIONS,\n"
        "\t\tPREVIEW_DEBUG_PATHS,\n"
        "\t\tPREVIEW_DEBUG_NAVIGATION,\n"
        "\t};",
    )

    replace_once(
        GAME_CPP,
        "void GameViewDebugger::set_debug_mute_audio(bool p_enabled) {\n"
        "\tmute_audio = p_enabled;\n"
        "\tEditorDebuggerNode::get_singleton()->set_debug_mute_audio(p_enabled);\n"
        "}\n",
        "void GameViewDebugger::set_debug_mute_audio(bool p_enabled) {\n"
        "\tmute_audio = p_enabled;\n"
        "\tEditorDebuggerNode::get_singleton()->set_debug_mute_audio(p_enabled);\n"
        "}\n\n"
        "void GameViewDebugger::set_debug_visualization(int p_kind, bool p_enabled) {\n"
        "\tArray message;\n"
        "\tmessage.append(p_kind);\n"
        "\tmessage.append(p_enabled);\n"
        "\tbool sent = false;\n"
        "\tfor (Ref<EditorDebuggerSession> &session : sessions) {\n"
        "\t\tif (session->is_active()) {\n"
        "\t\t\tsession->send_message(\"scene:debug_visualization\", message);\n"
        "\t\t\tsent = true;\n"
        "\t\t}\n"
        "\t}\n"
        "\tif (!sent) {\n"
        "\t\tWARN_PRINT(\"[Preview Debugger] Cannot change runtime visualization: no active debug session.\");\n"
        "\t}\n"
        "}\n",
    )

    # Add checkable entries to the existing preview menu inserted by the prior patch.
    replace_once(
        GAME_CPP,
        "\tmenu->add_item(TTRC(\"Toggle Game Audio Mute\"), PREVIEW_DEBUG_MUTE_AUDIO);\n",
        "\tmenu->add_item(TTRC(\"Toggle Game Audio Mute\"), PREVIEW_DEBUG_MUTE_AUDIO);\n"
        "\tmenu->add_check_item(TTRC(\"Show Collision Shapes\"), PREVIEW_DEBUG_COLLISIONS);\n"
        "\tmenu->set_item_tooltip(menu->get_item_index(PREVIEW_DEBUG_COLLISIONS), TTRC(\"Uses Godot's native runtime collision debug drawing.\"));\n"
        "\tmenu->add_check_item(TTRC(\"Show Path Debugging\"), PREVIEW_DEBUG_PATHS);\n"
        "\tmenu->set_item_tooltip(menu->get_item_index(PREVIEW_DEBUG_PATHS), TTRC(\"Uses Godot's native runtime path debug drawing.\"));\n"
        "\tmenu->add_check_item(TTRC(\"Show Navigation Debugging\"), PREVIEW_DEBUG_NAVIGATION);\n"
        "\tmenu->set_item_tooltip(menu->get_item_index(PREVIEW_DEBUG_NAVIGATION), TTRC(\"Uses Godot's native runtime navigation debug drawing.\"));\n",
    )

    # Add three independent flags to GameView's own state.
    replace_once(
        GAME_H,
        "\tbool debug_mute_audio = false;",
        "\tbool debug_mute_audio = false;\n"
        "\tbool debug_visual_collisions = false;\n"
        "\tbool debug_visual_paths = false;\n"
        "\tbool debug_visual_navigation = false;",
    )

    # Dispatch toggles through the debugger protocol to the running game.
    replace_once(
        GAME_CPP,
        "\t\tcase PREVIEW_DEBUG_MUTE_AUDIO: {\n"
        "\t\t\tif (active_sessions > 0) {\n"
        "\t\t\t\t_debug_mute_audio_button_pressed();\n"
        "\t\t\t\tprint_line(debug_mute_audio ? \"[Preview Debugger] Game audio muted.\" : \"[Preview Debugger] Game audio unmuted.\");\n"
        "\t\t\t} else {\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] Audio control requires a running game.\");\n"
        "\t\t\t}\n"
        "\t\t} break;\n",
        "\t\tcase PREVIEW_DEBUG_MUTE_AUDIO: {\n"
        "\t\t\tif (active_sessions > 0) {\n"
        "\t\t\t\t_debug_mute_audio_button_pressed();\n"
        "\t\t\t\tprint_line(debug_mute_audio ? \"[Preview Debugger] Game audio muted.\" : \"[Preview Debugger] Game audio unmuted.\");\n"
        "\t\t\t} else {\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] Audio control requires a running game.\");\n"
        "\t\t\t}\n"
        "\t\t} break;\n"
        "\t\tcase PREVIEW_DEBUG_COLLISIONS: {\n"
        "\t\t\tdebug_visual_collisions = !debug_visual_collisions;\n"
        "\t\t\tdebugger->set_debug_visualization(0, debug_visual_collisions);\n"
        "\t\t\tgame_window_options_menu->get_popup()->set_item_checked(game_window_options_menu->get_popup()->get_item_index(PREVIEW_DEBUG_COLLISIONS), debug_visual_collisions);\n"
        "\t\t\tprint_line(debug_visual_collisions ? \"[Preview Debugger] Collision shapes enabled.\" : \"[Preview Debugger] Collision shapes disabled.\");\n"
        "\t\t} break;\n"
        "\t\tcase PREVIEW_DEBUG_PATHS: {\n"
        "\t\t\tdebug_visual_paths = !debug_visual_paths;\n"
        "\t\t\tdebugger->set_debug_visualization(1, debug_visual_paths);\n"
        "\t\t\tgame_window_options_menu->get_popup()->set_item_checked(game_window_options_menu->get_popup()->get_item_index(PREVIEW_DEBUG_PATHS), debug_visual_paths);\n"
        "\t\t\tprint_line(debug_visual_paths ? \"[Preview Debugger] Path visualization enabled.\" : \"[Preview Debugger] Path visualization disabled.\");\n"
        "\t\t} break;\n"
        "\t\tcase PREVIEW_DEBUG_NAVIGATION: {\n"
        "\t\t\tdebug_visual_navigation = !debug_visual_navigation;\n"
        "\t\t\tdebugger->set_debug_visualization(2, debug_visual_navigation);\n"
        "\t\t\tgame_window_options_menu->get_popup()->set_item_checked(game_window_options_menu->get_popup()->get_item_index(PREVIEW_DEBUG_NAVIGATION), debug_visual_navigation);\n"
        "\t\t\tprint_line(debug_visual_navigation ? \"[Preview Debugger] Navigation visualization enabled.\" : \"[Preview Debugger] Navigation visualization disabled.\");\n"
        "\t\t} break;\n",
    )

    # Ensure runtime flags are reset when the game session ends.
    replace_once(
        GAME_CPP,
        "\t\tgame_size_label->set_text(\"\");",
        "\t\tdebug_visual_collisions = false;\n"
        "\t\tdebug_visual_paths = false;\n"
        "\t\tdebug_visual_navigation = false;\n"
        "\t\tmenu = game_window_options_menu->get_popup();\n"
        "\t\tmenu->set_item_checked(menu->get_item_index(PREVIEW_DEBUG_COLLISIONS), false);\n"
        "\t\tmenu->set_item_checked(menu->get_item_index(PREVIEW_DEBUG_PATHS), false);\n"
        "\t\tmenu->set_item_checked(menu->get_item_index(PREVIEW_DEBUG_NAVIGATION), false);\n"
        "\t\tgame_size_label->set_text(\"\");",
    )

    replace_once(
        SCENE_H,
        "\tstatic Error _msg_debug_mute_audio(const Array &p_args);",
        "\tstatic Error _msg_debug_mute_audio(const Array &p_args);\n"
        "\tstatic Error _msg_debug_visualization(const Array &p_args);",
    )
    replace_once(
        SCENE_CPP,
        "Error SceneDebugger::_msg_debug_mute_audio(const Array &p_args) {\n"
        "\tERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);\n"
        "\tbool do_mute = p_args[0];\n"
        "\tAudioServer::get_singleton()->set_debug_mute(do_mute);\n"
        "\treturn OK;\n"
        "}\n",
        "Error SceneDebugger::_msg_debug_mute_audio(const Array &p_args) {\n"
        "\tERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);\n"
        "\tbool do_mute = p_args[0];\n"
        "\tAudioServer::get_singleton()->set_debug_mute(do_mute);\n"
        "\treturn OK;\n"
        "}\n\n"
        "Error SceneDebugger::_msg_debug_visualization(const Array &p_args) {\n"
        "\tERR_FAIL_COND_V(p_args.size() < 2, ERR_INVALID_DATA);\n"
        "\tconst int kind = int(p_args[0]);\n"
        "\tconst bool enabled = bool(p_args[1]);\n"
        "\tswitch (kind) {\n"
        "\t\tcase 0: SceneTree::get_singleton()->set_debug_collisions_hint(enabled); break;\n"
        "\t\tcase 1: SceneTree::get_singleton()->set_debug_paths_hint(enabled); break;\n"
        "\t\tcase 2: SceneTree::get_singleton()->set_debug_navigation_hint(enabled); break;\n"
        "\t\tdefault: ERR_FAIL_V_MSG(ERR_INVALID_PARAMETER, \"Unknown debug visualization kind.\");\n"
        "\t}\n"
        "\treturn OK;\n"
        "}\n",
    )
    replace_once(
        SCENE_CPP,
        '\tmessage_handlers["debug_mute_audio"] = _msg_debug_mute_audio;',
        '\tmessage_handlers["debug_mute_audio"] = _msg_debug_mute_audio;\n'
        '\tmessage_handlers["debug_visualization"] = _msg_debug_visualization;',
    )

    # Validate critical links so an incomplete patch fails in Actions, not in an APK.
    combined = GAME_H.read_text(encoding="utf-8") + GAME_CPP.read_text(encoding="utf-8") + SCENE_H.read_text(encoding="utf-8") + SCENE_CPP.read_text(encoding="utf-8")
    for token in (
        "set_debug_visualization(int p_kind, bool p_enabled)",
        "scene:debug_visualization",
        "PREVIEW_DEBUG_COLLISIONS", "PREVIEW_DEBUG_PATHS", "PREVIEW_DEBUG_NAVIGATION",
        "set_debug_collisions_hint(enabled)", "set_debug_paths_hint(enabled)",
        "set_debug_navigation_hint(enabled)", 'message_handlers["debug_visualization"]',
        "[Preview Debugger] Collision shapes enabled.",
    ):
        if token not in combined:
            raise SystemExit(f"Post-patch verification failed: missing {token}")
    print("Applied native preview debug toggles for collisions, paths, and navigation; status is reported to Output and invalid protocol messages return debugger errors.")


if __name__ == "__main__":
    main()
