#!/usr/bin/env python3
"""Patch Godot 4.7.2 GameView with a compact, real preview-debug menu."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "godot-source"
HEADER = ROOT / "editor/run/game_view_plugin.h"
SOURCE = ROOT / "editor/run/game_view_plugin.cpp"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one patch anchor, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if not HEADER.is_file() or not SOURCE.is_file():
        raise SystemExit("Godot source not found: expected godot-source/editor/run/game_view_plugin.{h,cpp}")

    replace_once(
        HEADER,
        "\t\tWINDOW_HDR_OUTPUT_ERROR,\n\t};",
        "\t\tWINDOW_HDR_OUTPUT_ERROR,\n"
        "\t\tPREVIEW_DEBUG_SEPARATOR,\n"
        "\t\tPREVIEW_DEBUG_PAUSE_TOGGLE,\n"
        "\t\tPREVIEW_DEBUG_NEXT_FRAME,\n"
        "\t\tPREVIEW_DEBUG_STOP,\n"
        "\t\tPREVIEW_DEBUG_MUTE_AUDIO,\n"
        "\t};",
    )

    replace_once(
        SOURCE,
        "\t\tcase WINDOW_REQUEST_HDR_OUTPUT: {\n"
        "\t\t\tdebugger->toggle_hdr_output_requested();\n"
        "\t\t} break;\n"
        "\t}\n"
        "\t_update_embed_menu_options();",
        "\t\tcase WINDOW_REQUEST_HDR_OUTPUT: {\n"
        "\t\t\tdebugger->toggle_hdr_output_requested();\n"
        "\t\t} break;\n"
        "\t\tcase PREVIEW_DEBUG_PAUSE_TOGGLE: {\n"
        "\t\t\tif (active_sessions > 0) {\n"
        "\t\t\t\t_toggle_suspend_button();\n"
        "\t\t\t\tprint_line(suspend_button->is_pressed() ? \"[Preview Debugger] Game paused.\" : \"[Preview Debugger] Game resumed.\");\n"
        "\t\t\t} else {\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] Cannot pause: no game is running.\");\n"
        "\t\t\t}\n"
        "\t\t} break;\n"
        "\t\tcase PREVIEW_DEBUG_NEXT_FRAME: {\n"
        "\t\t\tif (active_sessions > 0 && suspend_button->is_pressed()) {\n"
        "\t\t\t\tdebugger->next_frame();\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] Requested one frame.\");\n"
        "\t\t\t} else {\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] Step frame requires a running, paused game.\");\n"
        "\t\t\t}\n"
        "\t\t} break;\n"
        "\t\tcase PREVIEW_DEBUG_STOP: {\n"
        "\t\t\tif (active_sessions > 0) {\n"
        "\t\t\t\t_stop_pressed();\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] Stop requested.\");\n"
        "\t\t\t} else {\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] No running game to stop.\");\n"
        "\t\t\t}\n"
        "\t\t} break;\n"
        "\t\tcase PREVIEW_DEBUG_MUTE_AUDIO: {\n"
        "\t\t\tif (active_sessions > 0) {\n"
        "\t\t\t\t_debug_mute_audio_button_pressed();\n"
        "\t\t\t\tprint_line(debug_mute_audio ? \"[Preview Debugger] Game audio muted.\" : \"[Preview Debugger] Game audio unmuted.\");\n"
        "\t\t\t} else {\n"
        "\t\t\t\tprint_line(\"[Preview Debugger] Audio control requires a running game.\");\n"
        "\t\t\t}\n"
        "\t\t} break;\n"
        "\t}\n"
        "\t_update_embed_menu_options();",
    )

    replace_once(
        SOURCE,
        "\tmenu->add_radio_check_item(TTRC(\"Stretch to Fit\"), WINDOW_SIZE_MODE_STRETCH);\n"
        "\tmenu->set_item_tooltip(menu->get_item_index(WINDOW_SIZE_MODE_STRETCH), TTRC(\"Embedded game size stretches to fit the Game Workspace.\"));\n\n",
        "\tmenu->add_radio_check_item(TTRC(\"Stretch to Fit\"), WINDOW_SIZE_MODE_STRETCH);\n"
        "\tmenu->set_item_tooltip(menu->get_item_index(WINDOW_SIZE_MODE_STRETCH), TTRC(\"Embedded game size stretches to fit the Game Workspace.\"));\n\n"
        "\tmenu->add_separator(TTRC(\"Preview Debugger\"), PREVIEW_DEBUG_SEPARATOR);\n"
        "\tmenu->add_item(TTRC(\"Pause / Resume Game\"), PREVIEW_DEBUG_PAUSE_TOGGLE);\n"
        "\tmenu->add_item(TTRC(\"Step One Frame (while paused)\"), PREVIEW_DEBUG_NEXT_FRAME);\n"
        "\tmenu->add_item(TTRC(\"Stop Game\"), PREVIEW_DEBUG_STOP);\n"
        "\tmenu->add_item(TTRC(\"Toggle Game Audio Mute\"), PREVIEW_DEBUG_MUTE_AUDIO);\n\n",
    )

    replace_once(
        SOURCE,
        "\tnext_frame_button->set_disabled(!suspend_button->is_pressed());\n\n\tmenu = game_window_options_menu->get_popup();",
        "\tnext_frame_button->set_disabled(!suspend_button->is_pressed());\n\n"
        "\tmenu = game_window_options_menu->get_popup();\n"
        "\tint debug_pause_index = menu->get_item_index(PREVIEW_DEBUG_PAUSE_TOGGLE);\n"
        "\tint debug_step_index = menu->get_item_index(PREVIEW_DEBUG_NEXT_FRAME);\n"
        "\tint debug_stop_index = menu->get_item_index(PREVIEW_DEBUG_STOP);\n"
        "\tint debug_mute_index = menu->get_item_index(PREVIEW_DEBUG_MUTE_AUDIO);\n"
        "\tif (debug_pause_index >= 0) {\n"
        "\t\tmenu->set_item_disabled(debug_pause_index, empty);\n"
        "\t\tmenu->set_item_text(debug_pause_index, suspend_button->is_pressed() ? TTR(\"Resume Game\") : TTR(\"Pause Game\"));\n"
        "\t}\n"
        "\tif (debug_step_index >= 0) {\n"
        "\t\tmenu->set_item_disabled(debug_step_index, empty || !suspend_button->is_pressed());\n"
        "\t}\n"
        "\tif (debug_stop_index >= 0) {\n"
        "\t\tmenu->set_item_disabled(debug_stop_index, empty);\n"
        "\t}\n"
        "\tif (debug_mute_index >= 0) {\n"
        "\t\tmenu->set_item_disabled(debug_mute_index, empty);\n"
        "\t\tmenu->set_item_text(debug_mute_index, debug_mute_audio ? TTR(\"Unmute Game Audio\") : TTR(\"Mute Game Audio\"));\n"
        "\t}\n\n",
    )

    # The preview toolbar is used on phones too; give its existing controls touch-sized hit areas.
    for button_name in ("suspend_button", "next_frame_button", "debug_mute_audio_button"):
        replace_once(
            SOURCE,
            f"\\t{button_name} = memnew(Button);\\n",
            f"\\t{button_name} = memnew(Button);\\n\\t{button_name}->set_custom_minimum_size(Size2(48, 48) * EDSCALE);\\n",
        )

    # Verify the resulting source still contains every real action and menu entry.
    patched_h = HEADER.read_text(encoding="utf-8")
    patched_cpp = SOURCE.read_text(encoding="utf-8")
    for token in (
        "PREVIEW_DEBUG_PAUSE_TOGGLE", "PREVIEW_DEBUG_NEXT_FRAME",
        "PREVIEW_DEBUG_STOP", "PREVIEW_DEBUG_MUTE_AUDIO",
        "debugger->next_frame()", "_stop_pressed()", "_debug_mute_audio_button_pressed()",
        "TTRC(\"Preview Debugger\")",
        "set_custom_minimum_size(Size2(48, 48) * EDSCALE)",
    ):
        if token not in patched_h + patched_cpp:
            raise SystemExit(f"Post-patch verification failed: missing {token}")
    print("Applied and verified compact GameView preview-debug menu patch.")


if __name__ == "__main__":
    main()
