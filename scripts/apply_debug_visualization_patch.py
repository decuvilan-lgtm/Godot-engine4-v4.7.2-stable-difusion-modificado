#!/usr/bin/env python3
"""Add one native runtime collision-shape toggle to Godot's preview debugger.

This patch deliberately implements only collision-shape visualization. Paths,
navigation and other visualization options are not exposed until their own
implementation and validation pass.
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

    replace_once(
        GAME_H,
        "\tvoid set_debug_mute_audio(bool p_enabled);",
        "\tvoid set_debug_mute_audio(bool p_enabled);\n"
        "\tvoid set_debug_collision_shapes(bool p_enabled);",
    )
    replace_once(
        GAME_H,
        "\t\tPREVIEW_DEBUG_MUTE_AUDIO,\n\t};",
        "\t\tPREVIEW_DEBUG_MUTE_AUDIO,\n"
        "\t\tPREVIEW_DEBUG_COLLISIONS,\n"
        "\t};",
    )
    replace_once(
        GAME_H,
        "\tbool debug_mute_audio = false;",
        "\tbool debug_mute_audio = false;\n"
        "\tbool debug_visual_collisions = false;",
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
        "void GameViewDebugger::set_debug_collision_shapes(bool p_enabled) {\n"
        "\tArray message;\n"
        "\tmessage.append(p_enabled);\n"
        "\tbool sent = false;\n"
        "\tfor (Ref<EditorDebuggerSession> &session : sessions) {\n"
        "\t\tif (session->is_active()) {\n"
        "\t\t\tsession->send_message(\"scene:debug_collision_shapes\", message);\n"
        "\t\t\tsent = true;\n"
        "\t\t}\n"
        "\t}\n"
        "\tif (!sent) {\n"
        "\t\tWARN_PRINT(\"[Preview Debugger] Collision visualization needs an active debug session.\");\n"
        "\t}\n"
        "}\n",
    )

    replace_once(
        GAME_CPP,
        "\tmenu->add_item(TTRC(\"Toggle Game Audio Mute\"), PREVIEW_DEBUG_MUTE_AUDIO);\n",
        "\tmenu->add_item(TTRC(\"Toggle Game Audio Mute\"), PREVIEW_DEBUG_MUTE_AUDIO);\n"
        "\tmenu->add_check_item(TTRC(\"Show Collision Shapes\"), PREVIEW_DEBUG_COLLISIONS);\n"
        "\tmenu->set_item_tooltip(menu->get_item_index(PREVIEW_DEBUG_COLLISIONS), TTRC(\"Show Godot's native runtime collision-shape debug drawing. Requires a running debug session.\"));\n",
    )

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
        "\t\t\tif (active_sessions > 0) {\n"
        "\t\t\t\tdebug_visual_collisions = !debug_visual_collisions;\n"
        "\t\t\t\tdebugger->set_debug_collision_shapes(debug_visual_collisions);\n"
        "\t\t\t\tgame_window_options_menu->get_popup()->set_item_checked(game_window_options_menu->get_popup()->get_item_index(PREVIEW_DEBUG_COLLISIONS), debug_visual_collisions);\n"
        "\t\t\t\tprint_line(debug_visual_collisions ? \"[Preview Debugger] Collision shapes enabled.\" : \"[Preview Debugger] Collision shapes disabled.\");\n"
        "\t\t\t} else {\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] Collision visualization requires a running debug game.\");\n"
        "\t\t\t}\n"
        "\t\t} break;\n",
    )

    replace_once(
        GAME_CPP,
        "\t\tgame_size_label->set_text(\"\");",
        "\t\tdebug_visual_collisions = false;\n"
        "\t\tmenu = game_window_options_menu->get_popup();\n"
        "\t\tconst int collision_item_index = menu->get_item_index(PREVIEW_DEBUG_COLLISIONS);\n"
        "\t\tif (collision_item_index >= 0) {\n"
        "\t\t\tmenu->set_item_checked(collision_item_index, false);\n"
        "\t\t}\n"
        "\t\tgame_size_label->set_text(\"\");",
    )

    replace_once(
        SCENE_H,
        "\tstatic Error _msg_debug_mute_audio(const Array &p_args);",
        "\tstatic Error _msg_debug_mute_audio(const Array &p_args);\n"
        "\tstatic Error _msg_debug_collision_shapes(const Array &p_args);",
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
        "Error SceneDebugger::_msg_debug_collision_shapes(const Array &p_args) {\n"
        "\tERR_FAIL_COND_V(p_args.size() != 1, ERR_INVALID_DATA);\n"
        "\tERR_FAIL_COND_V(p_args[0].get_type() != Variant::BOOL, ERR_INVALID_DATA);\n"
        "\tSceneTree *scene_tree = SceneTree::get_singleton();\n"
        "\tERR_FAIL_NULL_V(scene_tree, ERR_UNCONFIGURED);\n"
        "\tconst bool requested = p_args[0];\n"
        "\t// Force a state transition so physics debug-change callbacks refresh existing shapes.\n"
        "\tscene_tree->set_debug_collisions_hint(!requested);\n"
        "\tscene_tree->set_debug_collisions_hint(requested);\n"
        "\tconst bool active = scene_tree->is_debugging_collisions_hint();\n"
        "\tERR_FAIL_COND_V_MSG(active != requested, ERR_UNAVAILABLE, \"Collision visualization is unavailable in this build or physics backend.\");\n"
        "\treturn OK;\n"
        "}\n",
    )
    replace_once(
        SCENE_CPP,
        '\tmessage_handlers["debug_mute_audio"] = _msg_debug_mute_audio;',
        '\tmessage_handlers["debug_mute_audio"] = _msg_debug_mute_audio;\n'
        '\tmessage_handlers["debug_collision_shapes"] = _msg_debug_collision_shapes;',
    )

    combined = GAME_H.read_text(encoding="utf-8") + GAME_CPP.read_text(encoding="utf-8") + SCENE_H.read_text(encoding="utf-8") + SCENE_CPP.read_text(encoding="utf-8")
    for token in (
        "set_debug_collision_shapes(bool p_enabled)",
        "scene:debug_collision_shapes",
        "PREVIEW_DEBUG_COLLISIONS",
        "set_debug_collisions_hint(requested)",
        "set_debug_collisions_hint(!requested)",
        "p_args[0].get_type() != Variant::BOOL",
        "active != requested",
        "Collision visualization is unavailable in this build or physics backend.",
        'message_handlers["debug_collision_shapes"]',
        "[Preview Debugger] Collision shapes enabled.",
        "Collision visualization requires a running debug game.",
    ):
        if token not in combined:
            raise SystemExit(f"Post-patch verification failed: missing {token}")
    if "PREVIEW_DEBUG_PATHS" in combined or "PREVIEW_DEBUG_NAVIGATION" in combined:
        raise SystemExit("Only collision visualization may be exposed in this implementation step.")

    print("Applied and statically verified the collision-shape preview toggle and debugger protocol handler; no paths/navigation toggles are exposed yet.")


if __name__ == "__main__":
    main()
