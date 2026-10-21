#!/usr/bin/env python3
"""Apply the public GitHub repository import UI to the official Godot 4.7.2 source."""
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
    "ProjectDialog *project_dialog = nullptr;\n\tConfirmationDialog *github_import_dialog = nullptr;\n\tLineEdit *github_repo_url = nullptr;\n\tHTTPRequest *github_http_request = nullptr;\n\tString github_zip_path;\n\tString github_repo_name;")
replace_once(HEADER,
    "\tvoid _import_project();\n\tvoid _new_project();",
    "\tvoid _import_project();\n\tvoid _show_github_import_dialog();\n\tvoid _github_import_confirmed();\n\tvoid _github_download_completed(int p_result, int p_response_code, const PackedStringArray &p_headers, const PackedByteArray &p_body);\n\tvoid _new_project();")
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

void ProjectManager::_new_project() {""")
replace_once(SOURCE,
    "\t\t\thb->add_child(import_btn);\n\n\t\t\tscan_btn = memnew(Button);",
    """\t\t\thb->add_child(import_btn);

\t\t\tButton *github_import_btn = memnew(Button);
\t\t\tgithub_import_btn->set_text(TTRC("GitHub"));
\t\t\tgithub_import_btn->set_tooltip_text(TTRC("Download a project from a public GitHub repository."));
\t\t\tgithub_import_btn->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_show_github_import_dialog));
\t\t\thb->add_child(github_import_btn);

\t\t\tscan_btn = memnew(Button);""")
print("GitHub import patch applied successfully to project_manager.h and project_manager.cpp.")
