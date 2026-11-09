#!/usr/bin/env python3
"""Apply public GitHub import and shared-project add-on installation to Godot 4.7.2."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "godot-source"
HEADER = ROOT / "editor/project_manager/project_manager.h"
SOURCE = ROOT / "editor/project_manager/project_manager.cpp"

def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path.relative_to(ROOT)}: expected one anchor, found {count}: {old[:90]!r}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")

if not HEADER.is_file() or not SOURCE.is_file():
    sys.exit("Godot source tree not found; run this script from the repository workflow.")

replace_once(HEADER,
    "class HFlowContainer;\nclass LineEdit;",
    "class HFlowContainer;\nclass HTTPRequest;\nclass LineEdit;")
replace_once(HEADER,
    "ProjectDialog *project_dialog = nullptr;",
    "ProjectDialog *project_dialog = nullptr;\n\tConfirmationDialog *github_import_dialog = nullptr;\n\tLineEdit *github_repo_url = nullptr;\n\tHTTPRequest *github_http_request = nullptr;\n\tString github_zip_path;\n\tString github_repo_name;\n\tHTTPRequest *shared_sync_http_request = nullptr;\n\tString shared_sync_project_path;\n\tString shared_sync_stage_path;\n\tVector<String> shared_sync_files;\n\tint shared_sync_file_index = 0;")
replace_once(HEADER,
    "\tvoid _import_project();\n\tvoid _new_project();",
    "\tvoid _import_project();\n\tvoid _show_github_import_dialog();\n\tvoid _github_import_confirmed();\n\tvoid _github_download_completed(int p_result, int p_response_code, const PackedStringArray &p_headers, const PackedByteArray &p_body);\n\tvoid _install_shared_sync_addon();\n\tvoid _download_next_shared_sync_addon_file();\n\tvoid _shared_sync_addon_file_completed(int p_result, int p_response_code, const PackedStringArray &p_headers, const PackedByteArray &p_body);\n\tvoid _finish_shared_sync_addon_install();\n\tvoid _new_project();")
replace_once(SOURCE,
    '#include "scene/gui/separator.h"\n#include "scene/main/scene_tree.h"',
    '#include "scene/gui/separator.h"\n#include "scene/main/http_request.h"\n#include "scene/main/scene_tree.h"')
replace_once(SOURCE,
    """void ProjectManager::_import_project() {
\tproject_dialog->set_mode(ProjectDialog::MODE_IMPORT);
\tproject_dialog->ask_for_path_and_show();
}

void ProjectManager::_new_project() {""",
    """void ProjectManager::_import_project() {
\tproject_dialog->set_mode(ProjectDialog::MODE_IMPORT);
\tproject_dialog->ask_for_path_and_show();
}

void ProjectManager::_show_github_import_dialog() {
\tif (!github_import_dialog) {
\t\tgithub_import_dialog = memnew(ConfirmationDialog);
\t\tgithub_import_dialog->set_title(TTRC("Import from GitHub"));
\t\tgithub_import_dialog->set_ok_button_text(TTRC("Download"));

\t\tVBoxContainer *container = memnew(VBoxContainer);
\t\tcontainer->add_theme_constant_override("separation", 8 * EDSCALE);
\t\tgithub_import_dialog->add_child(container);

\t\tLabel *help = memnew(Label);
\t\thelp->set_text(TTRC("Enter a public GitHub repository URL or owner/repository."));
\t\thelp->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
\t\tcontainer->add_child(help);

\t\tgithub_repo_url = memnew(LineEdit);
\t\tgithub_repo_url->set_placeholder(TTRC("https://github.com/owner/repository"));
\t\tgithub_repo_url->set_clear_button_enabled(true);
\t\tcontainer->add_child(github_repo_url);

\t\tadd_child(github_import_dialog);
\t\tgithub_import_dialog->connect("confirmed", callable_mp(this, &ProjectManager::_github_import_confirmed));
\t}
\tgithub_import_dialog->popup_centered(Size2i(520 * EDSCALE, 0));
}

void ProjectManager::_github_import_confirmed() {
\tif (github_http_request) {
\t\t_show_error(TTR("A GitHub download is already in progress."));
\t\treturn;
\t}

\tString repository = github_repo_url->get_text().strip_edges();
\trepository = repository.trim_prefix("https://github.com/");
\trepository = repository.trim_prefix("http://github.com/");
\trepository = repository.trim_suffix("/");
\trepository = repository.trim_suffix(".git");
\tPackedStringArray parts = repository.split("/", false);
\tif (parts.size() != 2 || parts[0].is_empty() || parts[1].is_empty() || parts[0].contains_char(' ') || parts[1].contains_char(' ')) {
\t\t_show_error(TTR("Invalid repository. Use a public GitHub URL such as https://github.com/owner/repository."));
\t\treturn;
\t}

\tgithub_repo_name = parts[1];
\tgithub_zip_path = OS::get_singleton()->get_cache_path().path_join("godot_github_import.zip");
\tDirAccess::remove_absolute(github_zip_path);

\tgithub_http_request = memnew(HTTPRequest);
\tgithub_http_request->set_download_file(github_zip_path);
\tgithub_http_request->set_timeout(60.0);
\tadd_child(github_http_request);
\tgithub_http_request->connect("request_completed", callable_mp(this, &ProjectManager::_github_download_completed));

\tPackedStringArray headers;
\theaders.push_back("Accept: application/vnd.github+json");
\theaders.push_back("User-Agent: Godot-Project-Manager");
\tError err = github_http_request->request("https://api.github.com/repos/" + parts[0] + "/" + parts[1] + "/zipball", headers);
\tif (err != OK) {
\t\tgithub_http_request->queue_free();
\t\tgithub_http_request = nullptr;
\t\t_show_error(TTR("Could not start the GitHub download. Check your internet connection."));
\t}
}

void ProjectManager::_github_download_completed(int p_result, int p_response_code, const PackedStringArray &p_headers, const PackedByteArray &p_body) {
\tif (github_http_request) {
\t\tgithub_http_request->queue_free();
\t\tgithub_http_request = nullptr;
\t}
\tif (p_result != HTTPRequest::RESULT_SUCCESS || p_response_code != 200 || !FileAccess::exists(github_zip_path)) {
\t\t_show_error(vformat(TTR("GitHub download failed (HTTP %d). Check the repository URL and make sure it is public."), p_response_code));
\t\treturn;
\t}
\t_install_project(github_zip_path, github_repo_name);
}

void ProjectManager::_install_shared_sync_addon() {
    if (shared_sync_http_request) {
        _show_error(TTR("A shared sync add-on download is already in progress."));
        return;
    }
    Vector<ProjectList::Item> selected = project_list->get_selected_projects();
    if (selected.size() != 1) {
        _show_error(TTR("Select exactly one project before installing Shared Sync."));
        return;
    }
    shared_sync_project_path = selected[0].path;
    const String project_config = shared_sync_project_path.path_join("project.godot");
    if (!FileAccess::exists(project_config)) {
        _show_error(TTR("The selected project does not contain project.godot."));
        return;
    }
    if (FileAccess::exists(shared_sync_project_path.path_join("addons/godot_project_sync/plugin.gd")) || FileAccess::exists(shared_sync_project_path.path_join("addons/godot_ai_bridge/plugin.gd")) || FileAccess::exists(shared_sync_project_path.path_join("addons/godot_command_center/plugin.gd"))) {
        _show_error(TTR("Shared Project Sync is already installed. Existing add-on files were not overwritten."));
        return;
    }
    shared_sync_files.clear();
    shared_sync_files.push_back("godot_project_sync/plugin.gd");
    shared_sync_files.push_back("godot_project_sync/plugin.cfg");
    shared_sync_files.push_back("godot_project_sync/README.md");
    shared_sync_files.push_back("godot_ai_bridge/plugin.gd");
    shared_sync_files.push_back("godot_ai_bridge/plugin.cfg");
    shared_sync_files.push_back("godot_command_center/plugin.gd");
    shared_sync_files.push_back("godot_command_center/plugin.cfg");
    shared_sync_file_index = 0;
    shared_sync_stage_path = OS::get_singleton()->get_cache_path().path_join("godot_shared_project_sync_addon");
    if (DirAccess::make_dir_recursive_absolute(shared_sync_stage_path) != OK) {
        _show_error(TTR("Could not create a temporary folder for the Shared Sync add-on."));
        return;
    }
    shared_sync_http_request = memnew(HTTPRequest);
    shared_sync_http_request->set_timeout(60.0);
    shared_sync_http_request->set_max_redirects(0);
    shared_sync_http_request->connect("request_completed", callable_mp(this, &ProjectManager::_shared_sync_addon_file_completed));
    add_child(shared_sync_http_request);
    _download_next_shared_sync_addon_file();
}

void ProjectManager::_download_next_shared_sync_addon_file() {
    if (!shared_sync_http_request) {
        return;
    }
    if (shared_sync_file_index >= shared_sync_files.size()) {
        _finish_shared_sync_addon_install();
        return;
    }
    const String filename = shared_sync_files[shared_sync_file_index];
    const String url = "https://raw.githubusercontent.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/main/addons/" + filename;
    PackedStringArray headers;
    headers.push_back("User-Agent: Godot-Shared-Project-Sync");
    Error err = shared_sync_http_request->request(url, headers, HTTPClient::METHOD_GET);
    if (err != OK) {
        shared_sync_http_request->queue_free();
        shared_sync_http_request = nullptr;
        _show_error(TTR("Could not start downloading the Shared Sync add-on."));
    }
}

void ProjectManager::_shared_sync_addon_file_completed(int p_result, int p_response_code, const PackedStringArray &p_headers, const PackedByteArray &p_body) {
    if (!shared_sync_http_request) {
        return;
    }
    if (p_result != HTTPRequest::RESULT_SUCCESS || p_response_code != 200 || p_body.is_empty()) {
        shared_sync_http_request->queue_free();
        shared_sync_http_request = nullptr;
        _show_error(vformat(TTR("Shared Sync add-on download failed (HTTP %d). No project files were enabled."), p_response_code));
        return;
    }
    const String filename = shared_sync_files[shared_sync_file_index];
    const String stage_file = shared_sync_stage_path.path_join(filename);
    if (DirAccess::make_dir_recursive_absolute(stage_file.get_base_dir()) != OK) {
        shared_sync_http_request->queue_free();
        shared_sync_http_request = nullptr;
        _show_error(TTR("Could not create a temporary add-on subfolder."));
        return;
    }
    Ref<FileAccess> file = FileAccess::open(stage_file, FileAccess::WRITE);
    if (file.is_null()) {
        shared_sync_http_request->queue_free();
        shared_sync_http_request = nullptr;
        _show_error(TTR("Could not write a temporary Shared Sync add-on file."));
        return;
    }
    file->store_buffer(p_body);
    file->flush();
    file->close();
    shared_sync_file_index++;
    _download_next_shared_sync_addon_file();
}

void ProjectManager::_finish_shared_sync_addon_install() {
    if (shared_sync_http_request) {
        shared_sync_http_request->queue_free();
        shared_sync_http_request = nullptr;
    }
    const String addon_dir = shared_sync_project_path.path_join("addons");
    if (DirAccess::make_dir_recursive_absolute(addon_dir) != OK) {
        _show_error(TTR("Could not create the Shared Sync add-on folder in the selected project."));
        return;
    }
    for (const String &filename : shared_sync_files) {
        const String staged = shared_sync_stage_path.path_join(filename);
        const PackedByteArray bytes = FileAccess::get_file_as_bytes(staged);
        if (bytes.is_empty()) {
            _show_error(TTR("A downloaded Shared Sync add-on file is empty or unavailable."));
            return;
        }
        const String destination = addon_dir.path_join(filename);
        if (DirAccess::make_dir_recursive_absolute(destination.get_base_dir()) != OK) {
            _show_error(TTR("Could not create an add-on folder in the selected project."));
            return;
        }
        Ref<FileAccess> output = FileAccess::open(destination, FileAccess::WRITE);
        if (output.is_null()) {
            _show_error(TTR("Could not install the Shared Sync add-on into the selected project."));
            return;
        }
        output->store_buffer(bytes);
        output->flush();
        output->close();
    }
    ConfigFile config;
    const String config_path = shared_sync_project_path.path_join("project.godot");
    if (config.load(config_path) != OK) {
        _show_error(TTR("The add-on files were installed, but project.godot could not be read. Enable the plugin manually in Project Settings."));
        return;
    }
    Variant existing = config.get_value("editor_plugins", "enabled", PackedStringArray());
    PackedStringArray enabled;
    if (existing.get_type() == Variant::PACKED_STRING_ARRAY) {
        enabled = existing;
    } else if (existing.get_type() == Variant::ARRAY) {
        Array values = existing;
        for (int i = 0; i < values.size(); i++) {
            enabled.push_back(String(values[i]));
        }
    }
    PackedStringArray plugin_paths;
    plugin_paths.push_back("res://addons/godot_project_sync/plugin.cfg");
    plugin_paths.push_back("res://addons/godot_ai_bridge/plugin.cfg");
    plugin_paths.push_back("res://addons/godot_command_center/plugin.cfg");
    for (const String &plugin_path : plugin_paths) {
        if (enabled.find(plugin_path) == -1) {
            enabled.push_back(plugin_path);
        }
    }
    config.set_value("editor_plugins", "enabled", enabled);
    if (config.save(config_path) != OK) {
        _show_error(TTR("The add-on was installed, but project.godot could not be updated. Enable Shared Sync manually in Project Settings > Plugins."));
        return;
    }
    _show_error(TTR("Shared Project Sync, AI Bridge and Command Center were installed and enabled. Pair Command Center only on the Web editor for remote AI commands."));
}

void ProjectManager::_new_project() {""")
replace_once(SOURCE,
    "\t\t\thb->add_child(import_btn);\n\n\t\t\tscan_btn = memnew(Button);",
    """\t\t\thb->add_child(import_btn);

\t\t\tButton *github_import_btn = memnew(Button);
\t\t\tgithub_import_btn->set_text(TTRC("GitHub"));
\t\t\tgithub_import_btn->set_tooltip_text(TTRC("Download a project from a public GitHub repository."));
\t\t\tgithub_import_btn->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_show_github_import_dialog));
\t\t\thb->add_child(github_import_btn);

\t\t\tButton *shared_sync_btn = memnew(Button);
\t\t\tshared_sync_btn->set_text(TTRC("Shared Sync"));
\t\t\tshared_sync_btn->set_tooltip_text(TTRC("Install the shared project synchronization dock in the selected project."));
\t\t\tshared_sync_btn->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_install_shared_sync_addon));
\t\t\thb->add_child(shared_sync_btn);

\t\t\tscan_btn = memnew(Button);""")
print("GitHub import and shared-project add-on installers applied successfully to project_manager.h and project_manager.cpp.")
