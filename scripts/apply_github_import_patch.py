#!/usr/bin/env python3
"""Apply the public GitHub repository import UI to the official Godot 4.7.2 source."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "godot-source"
HEADER = ROOT / "editor/project_manager/project_manager.h"
SOURCE = ROOT / "editor/project_manager/project_manager.cpp"
PROJECT_DIALOG = ROOT / "editor/project_manager/project_dialog.cpp"

def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path.relative_to(ROOT)}: expected one anchor, found {count}: {old[:90]!r}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")

if not HEADER.is_file() or not SOURCE.is_file() or not PROJECT_DIALOG.is_file():
    sys.exit("Godot source tree not found; run this script from the repository workflow.")

replace_once(HEADER,
    "class HFlowContainer;\nclass LineEdit;",
    "class Button;\nclass HFlowContainer;\nclass HTTPRequest;\nclass LineEdit;\nclass OptionButton;")
replace_once(HEADER,
    "ProjectDialog *project_dialog = nullptr;",
    "ProjectDialog *project_dialog = nullptr;\n\tConfirmationDialog *github_import_dialog = nullptr;\n\tLineEdit *github_repo_url = nullptr;\n\tLineEdit *github_repo_ref = nullptr;\n\tHTTPRequest *github_http_request = nullptr;\n\tHTTPRequest *github_search_request = nullptr;\n\tConfirmationDialog *github_results_dialog = nullptr;\n\tOptionButton *github_repo_results = nullptr;\n\tString github_zip_path;\n\tString github_repo_name;\n\tString github_search_query;\n\tint github_search_page = 1;\n\tint github_search_total_count = 0;\n\tButton *github_search_more_btn = nullptr;\n\tConfirmationDialog *mcp_install_dialog = nullptr;")
replace_once(HEADER,
    "\tvoid _import_project();\n\tvoid _new_project();",
    "\tvoid _import_project();\n\tvoid _show_github_import_dialog();\n\tvoid _github_import_confirmed();\n\tvoid _github_import_submitted(const String &p_text);\n\tvoid _github_search_button_pressed();\n\tvoid _github_start_search(int p_page);\n\tvoid _github_search_next_page();\n\tvoid _github_search_completed(int p_result, int p_response_code, const PackedStringArray &p_headers, const PackedByteArray &p_body);\n\tvoid _github_search_result_confirmed();\n\tvoid _github_download_completed(int p_result, int p_response_code, const PackedStringArray &p_headers, const PackedByteArray &p_body);\n\tvoid _show_mcp_install_dialog();\n\tvoid _install_mcp_addon_confirmed();\n\tvoid _new_project();")
replace_once(SOURCE,
    '#include "scene/gui/separator.h"\n#include "scene/main/scene_tree.h"',
    '#include "core/io/json.h"\n#include "scene/gui/separator.h"\n#include "scene/main/http_request.h"\n#include "scene/main/scene_tree.h"\n#include "platform/android/file_access_android.h"\n#include "modules/zip/zip_reader.h"')
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
\t\tgithub_import_dialog->set_ok_button_text(TTRC("Search / Download"));

\t\tVBoxContainer *container = memnew(VBoxContainer);
\t\tcontainer->add_theme_constant_override("separation", 8 * EDSCALE);
\t\tgithub_import_dialog->add_child(container);

\t\tLabel *help = memnew(Label);
\t\thelp->set_text(TTRC("Search public repositories by name or account, or enter a direct GitHub URL / owner/repository."));
\t\thelp->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
\t\tcontainer->add_child(help);

\t\tgithub_repo_url = memnew(LineEdit);
\t\tgithub_repo_url->set_placeholder(TTRC("e.g. godot mcp, owner/repo, or GitHub URL"));
\t\tgithub_repo_url->set_clear_button_enabled(true);
\t\tcontainer->add_child(github_repo_url);
\t\tgithub_repo_url->connect("text_submitted", callable_mp(this, &ProjectManager::_github_import_submitted));

\t\tgithub_repo_ref = memnew(LineEdit);
\t\tgithub_repo_ref->set_placeholder(TTRC("Optional branch, tag, or commit SHA (default branch if empty)"));
\t\tgithub_repo_ref->set_clear_button_enabled(true);
\t\tcontainer->add_child(github_repo_ref);

\t\tButton *github_search_btn = memnew(Button);
\t\tgithub_search_btn->set_text(TTRC("Buscar en GitHub"));
\t\tgithub_search_btn->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_github_search_button_pressed));
\t\tcontainer->add_child(github_search_btn);

\t\tadd_child(github_import_dialog);
\t\tgithub_import_dialog->connect("confirmed", callable_mp(this, &ProjectManager::_github_import_confirmed));

\t\tgithub_results_dialog = memnew(ConfirmationDialog);
\t\tgithub_results_dialog->set_title(TTRC("GitHub search results"));
\t\tgithub_results_dialog->set_ok_button_text(TTRC("Import selected"));
\t\tVBoxContainer *results_container = memnew(VBoxContainer);
\t\tLabel *results_help = memnew(Label);
\t\tresults_help->set_text(TTRC("Choose a public repository to download and import."));
\t\tresults_container->add_child(results_help);
\t\tgithub_repo_results = memnew(OptionButton);
\t\tresults_container->add_child(github_repo_results);
\t\tgithub_search_more_btn = memnew(Button);
\t\tgithub_search_more_btn->set_text(TTRC(\"Recargar siguientes 20\"));
\t\tgithub_search_more_btn->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_github_search_next_page));
\t\tresults_container->add_child(github_search_more_btn);
\t\tgithub_results_dialog->add_child(results_container);
\t\tadd_child(github_results_dialog);
\t\tgithub_results_dialog->connect("confirmed", callable_mp(this, &ProjectManager::_github_search_result_confirmed));
\t}
\tgithub_import_dialog->popup_centered_clamped(Size2i(680 * EDSCALE, 560 * EDSCALE), 0.95);
}

void ProjectManager::_github_import_submitted(const String &p_text) {
\tif (github_repo_url) {
\t\tgithub_repo_url->release_focus();
\t}
\t_github_import_confirmed();
}

// The explicit Search button must search even when the input looks like a direct
// repository URL. This is the recovery path when URL-based import does not work.
void ProjectManager::_github_search_button_pressed() {
\tif (github_search_request) {
\t\t_show_error(TTR("A GitHub search is already in progress."));
\t\treturn;
\t}
\tif (github_http_request) {
\t\t_show_error(TTR("A GitHub download is already in progress."));
\t\treturn;
\t}
\tString query = github_repo_url ? github_repo_url->get_text().strip_edges() : String();
\tif (query.is_empty()) {
\t\t_show_error(TTR("Enter a repository name, owner/repository, or GitHub URL to search."));
\t\treturn;
\t}
\tconst bool github_url = query.begins_with("https://github.com/") || query.begins_with("http://github.com/") || query.begins_with("https://www.github.com/") || query.begins_with("http://www.github.com/") || query.begins_with("github.com/") || query.begins_with("www.github.com/");
\tif (query.begins_with("https://www.github.com/")) {
\t\tquery = query.trim_prefix("https://www.github.com/");
\t} else if (query.begins_with("http://www.github.com/")) {
\t\tquery = query.trim_prefix("http://www.github.com/");
\t} else if (query.begins_with("https://github.com/")) {
\t\tquery = query.trim_prefix("https://github.com/");
\t} else if (query.begins_with("http://github.com/")) {
\t\tquery = query.trim_prefix("http://github.com/");
\t} else if (query.begins_with("www.github.com/")) {
\t\tquery = query.trim_prefix("www.github.com/");
\t} else if (query.begins_with("github.com/")) {
\t\tquery = query.trim_prefix("github.com/");
\t} else if (query.contains("://") || query.begins_with("www.")) {
\t\t_show_error(TTR("Use a github.com repository link or enter a search query."));
\t\treturn;
\t}
\t// Browser-copied GitHub links often include a tab, branch path, query, or fragment.
\t// For search fallback, reduce these links to owner/repository; direct import stays strict.
\tif (github_url) {
\t\tint query_pos = query.find("?");
\t\tint fragment_pos = query.find("#");
\t\tif (query_pos >= 0) {
\t\t\tquery = query.substr(0, query_pos);
\t\t}
\t\tif (fragment_pos >= 0) {
\t\t\tquery = query.substr(0, fragment_pos);
\t\t}
\t\tquery = query.trim_suffix("/");
\t\tquery = query.trim_suffix(".git");
\t\tPackedStringArray url_parts = query.split("/", false);
\t\tif (url_parts.size() < 2 || url_parts[0].is_empty() || url_parts[1].is_empty()) {
\t\t\t_show_error(TTR("For a GitHub link, include an account and repository name."));
\t\t\treturn;
\t\t}
\t\tquery = url_parts[0] + "/" + url_parts[1];
\t} else if (query.contains("/") && (query.contains("?") || query.contains("#"))) {
\t\t_show_error(TTR("For owner/repository searches, remove query parameters and fragments."));
\t\treturn;
\t}
\tif (query.contains("/")) {
\t\tPackedStringArray parts = query.split("/", false);
\t\tif (parts.size() != 2 || parts[0].is_empty() || parts[1].is_empty() || parts[0].contains(" ") || parts[1].contains(" ")) {
\t\t\t_show_error(TTR("For a repository search, use owner/repository without extra path segments."));
\t\t\treturn;
\t\t}
\t}
\tgithub_search_query = query;
\tgithub_search_page = 1;
\tgithub_search_total_count = 0;
\tif (github_import_dialog) {
\t\tgithub_import_dialog->hide();
\t}
\t_github_start_search(1);
}

void ProjectManager::_github_import_confirmed() {
\tif (github_http_request) {
\t\t_show_error(TTR("A GitHub download is already in progress."));
\t\treturn;
\t}

\tString repository = github_repo_url->get_text().strip_edges();
	repository = repository.strip_edges();
	// Accept only github.com repository URLs or the exact owner/repository form.
	// Reject lookalike hosts, extra path segments, query strings, and fragments.
	if (repository.begins_with("https://github.com/")) {
		repository = repository.trim_prefix("https://github.com/");
	} else if (repository.begins_with("http://github.com/")) {
		repository = repository.trim_prefix("http://github.com/");
	} else if (repository.begins_with("github.com/")) {
		repository = repository.trim_prefix("github.com/");
	} else if (repository.contains("://") || repository.begins_with("www.")) {
		_show_error(TTR("Use github.com/owner/repository or enter owner/repository. Other hosts are not supported."));
		return;
	}
	repository = repository.trim_suffix("/");
	repository = repository.trim_suffix(".git");
	if (repository.contains("?") || repository.contains("#")) {
		_show_error(TTR("Remove query parameters or fragments. Enter only the repository URL."));
		return;
	}
	if (!repository.contains("/")) {
		if (github_search_request) {
			_show_error(TTR("A GitHub search is already in progress."));
			return;
		}
		github_search_query = repository;
		github_search_page = 1;
		github_search_total_count = 0;
		_github_start_search(1);
		return;
	}

	PackedStringArray parts = repository.split("/", false);
	if (parts.size() != 2 || parts[0].is_empty() || parts[1].is_empty()) {
		_show_error(TTR("Invalid repository. Use https://github.com/owner/repository or owner/repository."));
		return;
	}
	const String owner_allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-";
	const String repo_allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.";
	for (int i = 0; i < parts[0].length(); i++) {
		if (!owner_allowed.contains_char(parts[0][i])) {
			_show_error(TTR("The GitHub account name contains unsupported characters."));
			return;
		}
	}
	for (int i = 0; i < parts[1].length(); i++) {
		if (!repo_allowed.contains_char(parts[1][i])) {
			_show_error(TTR("The repository name contains unsupported characters."));
			return;
		}
	}
	if (parts[0].begins_with("-") || parts[0].ends_with("-") || parts[1] == "." || parts[1] == "..") {
		_show_error(TTR("The GitHub account or repository name is invalid."));
		return;
	}

\tString requested_ref = github_repo_ref ? github_repo_ref->get_text().strip_edges() : String();
\tif (!requested_ref.is_empty()) {
\t\tif (requested_ref.begins_with("/") || requested_ref.contains("\\\\") || requested_ref.contains("..") || requested_ref.contains(" ") || requested_ref.contains("?") || requested_ref.contains("#")) {
\t\t\t_show_error(TTR("The branch, tag, or commit reference contains unsupported characters."));
\t\t\treturn;
\t\t}
\t\tfor (int i = 0; i < requested_ref.length(); i++) {
\t\t\tconst char32_t c = requested_ref[i];
\t\t\tconst bool allowed = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '/';
\t\t\tif (!allowed) {
\t\t\t\t_show_error(TTR("Use only letters, numbers, slash, dot, underscore, and hyphen in the branch or tag."));
\t\t\t\treturn;
\t\t\t}
\t\t}
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
\tString archive_url = "https://api.github.com/repos/" + parts[0] + "/" + parts[1] + "/zipball";
\tif (!requested_ref.is_empty()) {
\t\tarchive_url += "/" + requested_ref.uri_encode();
\t}
\tError err = github_http_request->request(archive_url, headers);
\tif (err != OK) {
\t\tgithub_http_request->queue_free();
\t\tgithub_http_request = nullptr;
\t\t_show_error(TTR("Could not start the GitHub download. Check your internet connection."));
\t}
}

void ProjectManager::_github_start_search(int p_page) {
	if (github_search_request) {
		return;
	}
	github_search_page = CLAMP(p_page, 1, 5); // GitHub repository search exposes at most 100 results.
	github_search_request = memnew(HTTPRequest);
	github_search_request->set_timeout(30.0);
	add_child(github_search_request);
	github_search_request->connect("request_completed", callable_mp(this, &ProjectManager::_github_search_completed));
	PackedStringArray search_headers;
	search_headers.push_back("Accept: application/vnd.github+json");
	search_headers.push_back("User-Agent: Godot-Project-Manager");
	String search_url = "https://api.github.com/search/repositories?q=" + github_search_query.uri_encode() + "&sort=stars&order=desc&per_page=20&page=" + itos(github_search_page);
	if (github_search_more_btn) {
		github_search_more_btn->set_disabled(true);
	}
	Error search_error = github_search_request->request(search_url, search_headers);
	if (search_error != OK) {
		github_search_request->queue_free();
		github_search_request = nullptr;
		if (github_search_more_btn) {
			github_search_more_btn->set_disabled(false);
		}
		_show_error(TTR("Could not start GitHub repository search. Check your internet connection."));
	}
}

void ProjectManager::_github_search_next_page() {
	if (github_search_request || github_search_query.is_empty()) {
		return;
	}
	const int max_page = MIN(5, MAX(1, (github_search_total_count + 19) / 20));
	const int next_page = github_search_page >= max_page ? 1 : github_search_page + 1;
	_github_start_search(next_page);
}

void ProjectManager::_github_search_completed(int p_result, int p_response_code, const PackedStringArray &p_headers, const PackedByteArray &p_body) {
	if (github_search_request) {
		github_search_request->queue_free();
		github_search_request = nullptr;
	}
	if (github_search_more_btn) {
		github_search_more_btn->set_disabled(false);
	}
	if (p_result != HTTPRequest::RESULT_SUCCESS || p_response_code != 200) {
		_show_error(vformat(TTR("GitHub search failed (HTTP %d). Check your connection or try a more specific query."), p_response_code));
		return;
	}
	Variant parsed = JSON::parse_string(String::utf8((const char *)p_body.ptr(), p_body.size()));
	if (parsed.get_type() != Variant::DICTIONARY) {
		_show_error(TTR("GitHub returned an invalid search response."));
		return;
	}
	Dictionary response = parsed;
	github_search_total_count = int(response.get("total_count", 0));
	Array items = response.get("items", Array());
	github_repo_results->clear();
	int added = 0;
	for (int i = 0; i < items.size() && added < 20; i++) {
		if (items[i].get_type() != Variant::DICTIONARY) {
			continue;
		}
		Dictionary item = items[i];
		String full_name = item.get("full_name", String());
		String html_url = item.get("html_url", String());
		if (full_name.is_empty() || !html_url.begins_with("https://github.com/")) {
			continue;
		}
		github_repo_results->add_item(full_name);
		added++;
	}
	if (added == 0) {
		if (github_search_page > 1 && github_search_total_count > 0) {
			github_search_page = 1;
			_github_start_search(1);
			return;
		}
		_show_error(TTR("No public repositories matched that search. Try another name or owner."));
		return;
	}
	const int max_page = MIN(5, MAX(1, (github_search_total_count + 19) / 20));
	if (github_search_more_btn) {
		github_search_more_btn->set_text(github_search_page >= max_page ? TTR("Volver a los primeros 20") : TTR("Recargar siguientes 20"));
	}
	github_results_dialog->popup_centered_clamped(Size2i(680 * EDSCALE, 560 * EDSCALE), 0.95);
}

void ProjectManager::_github_search_result_confirmed() {
	if (!github_repo_results || github_repo_results->get_item_count() == 0 || github_repo_results->get_selected() < 0) {
		_show_error(TTR("Select a repository from the GitHub search results."));
		return;
	}
	github_repo_url->set_text(github_repo_results->get_item_text(github_repo_results->get_selected()));
	_github_import_confirmed();
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


void ProjectManager::_show_mcp_install_dialog() {
    Vector<ProjectList::Item> selected = project_list->get_selected_projects();
    if (selected.size() != 1) {
        _show_error(TTR("Select exactly one existing project before installing MCP."));
        return;
    }
    const String project_path = selected[0].path;
    if (!FileAccess::exists(project_path.path_join("project.godot"))) {
        _show_error(TTR("The selected folder is not a valid Godot project."));
        return;
    }
    if (DirAccess::dir_exists_absolute(project_path.path_join("addons/godot_mcp_android"))) {
        _show_error(TTR("This project already has addons/godot_mcp_android. It was left untouched; move or back it up before reinstalling."));
        return;
    }
    if (!mcp_install_dialog) {
        mcp_install_dialog = memnew(ConfirmationDialog);
        mcp_install_dialog->set_title(TTRC("Install Godot MCP"));
        mcp_install_dialog->set_text(TTR("Copy the bundled MCP addon into the selected project and enable it in project.godot? Existing addon folders will never be overwritten. The server is configured to listen on this device only."));
        mcp_install_dialog->set_ok_button_text(TTRC("Install and Enable"));
        add_child(mcp_install_dialog);
        mcp_install_dialog->connect("confirmed", callable_mp(this, &ProjectManager::_install_mcp_addon_confirmed));
    }
    mcp_install_dialog->popup_centered(Size2i(560 * EDSCALE, 0));
}

void ProjectManager::_install_mcp_addon_confirmed() {
    Vector<ProjectList::Item> selected = project_list->get_selected_projects();
    if (selected.size() != 1) {
        _show_error(TTR("Select exactly one project and try again."));
        return;
    }
    const String project_path = selected[0].path;
    const String project_file = project_path.path_join("project.godot");
    const String addon_target = project_path.path_join("addons/godot_mcp_android");
    if (!FileAccess::exists(project_file)) {
        _show_error(TTR("The selected folder is not a valid Godot project."));
        return;
    }
    if (DirAccess::dir_exists_absolute(addon_target)) {
        _show_error(TTR("The MCP addon folder already exists. No files were overwritten."));
        return;
    }

    ConfigFile config;
    if (config.load(project_file) != OK) {
        _show_error(TTR("Could not read project.godot; no MCP files were copied."));
        return;
    }
    PackedStringArray enabled;
    Variant enabled_value = config.get_value("editor_plugins", "enabled", PackedStringArray());
    if (enabled_value.get_type() == Variant::PACKED_STRING_ARRAY) {
        enabled = enabled_value;
    } else if (enabled_value.get_type() == Variant::ARRAY) {
        Array enabled_array = enabled_value;
        for (const Variant &entry : enabled_array) {
            enabled.push_back(String(entry));
        }
    }
    const String plugin_path = "res://addons/godot_mcp_android/plugin.cfg";
    if (!enabled.has(plugin_path)) {
        enabled.push_back(plugin_path);
    }

    const String addons_dir = project_path.path_join("addons");
    const String addon_staging = addons_dir.path_join(".godot_mcp_android_install_tmp");
    if (DirAccess::dir_exists_absolute(addon_staging)) {
        _show_error(TTR("A previous MCP install staging folder exists. Inspect it manually before retrying; nothing was deleted."));
        return;
    }
    Error mkdir_error = DirAccess::make_dir_recursive_absolute(addons_dir);
    if (mkdir_error != OK) {
        _show_error(TTR("Could not create the project's addons folder."));
        return;
    }

    // Android APK assets are not the same namespace as res:// in the editor build.
    // Read the single bundled ZIP directly through Android's AssetManager.
    FileAccessAndroid bundled_asset;
    if (bundled_asset.open_internal("mcp-addon.zip", FileAccess::READ) != OK) {
        _show_error(TTR("The MCP ZIP is missing from this APK. Rebuild the editor before installing MCP."));
        return;
    }
    const String zip_path = OS::get_singleton()->get_cache_path().path_join("godot_mcp_android_bundle.zip");
    Ref<FileAccess> zip_output = FileAccess::open(zip_path, FileAccess::WRITE);
    if (zip_output.is_null()) {
        bundled_asset.close();
        _show_error(TTR("Could not prepare the MCP bundle in app cache."));
        return;
    }
    uint8_t buffer[16384];
    uint64_t remaining = bundled_asset.get_length();
    while (remaining > 0) {
        const uint64_t requested = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
        uint64_t bytes_read = bundled_asset.get_buffer(buffer, requested);
        if (bytes_read == 0) {
            zip_output.unref();
            bundled_asset.close();
            _show_error(TTR("The bundled MCP ZIP could not be read completely."));
            return;
        }
        if (!zip_output->store_buffer(buffer, bytes_read)) {
            zip_output.unref();
            bundled_asset.close();
            _show_error(TTR("Could not copy the MCP bundle into app cache."));
            return;
        }
        remaining -= bytes_read;
    }
    zip_output.unref();
    bundled_asset.close();

    Ref<ZIPReader> zip;
    zip.instantiate();
    if (zip->open(zip_path) != OK) {
        _show_error(TTR("The bundled MCP ZIP could not be opened."));
        return;
    }
    PackedStringArray archive_files = zip->get_files();
    bool plugin_cfg_written = false;
    bool extraction_failed = false;
    for (int i = 0; i < archive_files.size(); i++) {
        String archive_path = archive_files[i];
        if (archive_path.ends_with("/")) {
            continue;
        }
        if (!archive_path.begins_with("godot_mcp_android/") || archive_path.begins_with("/") || archive_path.contains_char('\\\\')) {
            extraction_failed = true;
            break;
        }
        PackedStringArray segments = archive_path.split("/", true);
        for (int j = 0; j < segments.size(); j++) {
            if (segments[j] == "." || segments[j] == "..") {
                extraction_failed = true;
                break;
            }
        }
        if (extraction_failed) {
            break;
        }
        String relative_path = archive_path.trim_prefix("godot_mcp_android/");
        if (relative_path.is_empty()) {
            extraction_failed = true;
            break;
        }
        String destination = addon_staging.path_join(relative_path);
        Error parent_error = DirAccess::make_dir_recursive_absolute(destination.get_base_dir());
        if (parent_error != OK) {
            extraction_failed = true;
            break;
        }
        Ref<FileAccess> output = FileAccess::open(destination, FileAccess::WRITE);
        if (output.is_null()) {
            extraction_failed = true;
            break;
        }
        PackedByteArray contents = zip->read_file(archive_path, true);
        if (contents.is_empty() || !output->store_buffer(contents.ptr(), contents.size())) {
            output.unref();
            extraction_failed = true;
            break;
        }
        output.unref();
        if (relative_path == "plugin.cfg") {
            plugin_cfg_written = true;
        }
    }
    zip->close();
    if (extraction_failed || !plugin_cfg_written || !FileAccess::exists(addon_staging.path_join("plugin.cfg"))) {
        _show_error(TTR("MCP extraction failed validation. No plugin was enabled; inspect the temporary staging folder before retrying."));
        return;
    }
    Error rename_error = DirAccess::rename_absolute(addon_staging, addon_target);
    if (rename_error != OK) {
        _show_error(TTR("MCP files were staged but could not be moved into place. No plugin was enabled; inspect the temporary staging folder."));
        return;
    }

    config.set_value("editor_plugins", "enabled", enabled);
    Error save_error = config.save(project_file);
    if (save_error != OK) {
        _show_error(TTR("The MCP addon files were copied, but project.godot could not be saved. The plugin remains disabled; check project permissions."));
        return;
    }
    project_list->refresh_project(project_path);
    _show_error(TTR("MCP addon installed and enabled for the selected project. Open the project to start the plugin."));
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

\t\t\tButton *mcp_install_btn = memnew(Button);
\t\t\tmcp_install_btn->set_text(TTRC(\"Install MCP\"));
\t\t\tmcp_install_btn->set_tooltip_text(TTRC(\"Install and enable the bundled safe MCP addon in the selected project.\"));
\t\t\tmcp_install_btn->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_show_mcp_install_dialog));
\t\t\thb->add_child(mcp_install_btn);

\t\t\tscan_btn = memnew(Button);""")
# Keep Android's media scanner from indexing images bundled in projects installed
# from ZIP archives (including public GitHub repositories).
replace_once(PROJECT_DIALOG,
    """\t\t\tif (create_dir->is_pressed()) {
\t\t\t\tRef<DirAccess> d = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
\t\t\t\tif (!d->dir_exists(path) && d->make_dir(path) != OK) {
\t\t\t\t\t_set_message(TTRC("Couldn't create project directory, check permissions."), MESSAGE_ERROR);
\t\t\t\t\treturn;
\t\t\t\t}
\t\t\t}

\t\t\tret = unzGoToFirstFile(pkg);""",
    """\t\t\tif (create_dir->is_pressed()) {
\t\t\t\tRef<DirAccess> d = DirAccess::create(DirAccess::ACCESS_FILESYSTEM);
\t\t\t\tif (!d->dir_exists(path) && d->make_dir(path) != OK) {
\t\t\t\t\t_set_message(TTRC("Couldn't create project directory, check permissions."), MESSAGE_ERROR);
\t\t\t\t\treturn;
\t\t\t\t}
\t\t\t}

\t\t\t// Prevent Android Gallery from indexing images bundled in installed projects.
\t\t\t// Create .nomedia before extracting any assets so it covers all subdirectories.
\t\t\tif (mode == MODE_INSTALL) {
\t\t\t\tString no_media_path = path.path_join(\".nomedia\");
\t\t\t\tif (!FileAccess::exists(no_media_path)) {
\t\t\t\t\tRef<FileAccess> no_media = FileAccess::open(no_media_path, FileAccess::WRITE);
\t\t\t\t\tif (no_media.is_null()) {
\t\t\t\t\t\t_set_message(TTRC(\"Couldn't protect the imported project from Android Gallery indexing. Check project-folder permissions.\"), MESSAGE_ERROR);
\t\t\t\t\t\tunzClose(pkg);
\t\t\t\t\t\treturn;
\t\t\t\t\t}
\t\t\t\t\tno_media->store_string(\"Godot project assets are not gallery media.\");
\t\t\t\t\tno_media.unref();
\t\t\t\t}
\t\t\t}

\t\t\tret = unzGoToFirstFile(pkg);""")


# Extend the remote-debugger channel so physics, navigation, avoidance, and path
# overlays can be toggled in the running game without restarting the preview.
SCENE_DEBUGGER_HEADER = ROOT / "scene/debugger/scene_debugger.h"
SCENE_DEBUGGER_SOURCE = ROOT / "scene/debugger/scene_debugger.cpp"
EDITOR_DEBUGGER_HEADER = ROOT / "editor/debugger/editor_debugger_node.h"
EDITOR_DEBUGGER_SOURCE = ROOT / "editor/debugger/editor_debugger_node.cpp"
SCRIPT_DEBUGGER_HEADER = ROOT / "editor/debugger/script_editor_debugger.h"
SCRIPT_DEBUGGER_SOURCE = ROOT / "editor/debugger/script_editor_debugger.cpp"
for required in (SCENE_DEBUGGER_HEADER, SCENE_DEBUGGER_SOURCE, EDITOR_DEBUGGER_HEADER,
                 EDITOR_DEBUGGER_SOURCE, SCRIPT_DEBUGGER_HEADER, SCRIPT_DEBUGGER_SOURCE):
    if not required.is_file():
        sys.exit(f"Godot debugger source not found; cannot wire live preview overlays: {required}")

replace_once(EDITOR_DEBUGGER_HEADER,
    "void set_debug_mute_audio(bool p_mute);",
    "void set_debug_collisions(bool p_enabled);\n\tvoid set_debug_navigation(bool p_enabled);\n\tvoid set_debug_avoidance(bool p_enabled);\n\tvoid set_debug_mute_audio(bool p_mute);")
replace_once(EDITOR_DEBUGGER_SOURCE,
    "void EditorDebuggerNode::set_debug_mute_audio(bool p_mute) {",
    """void EditorDebuggerNode::set_debug_fps(bool p_enabled) {
\t_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
\t\tdbg->set_debug_fps(p_enabled);
\t});
}

void EditorDebuggerNode::set_debug_collisions(bool p_enabled) {
\t_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
\t\tdbg->set_debug_collisions(p_enabled);
\t});
}

void EditorDebuggerNode::set_debug_navigation(bool p_enabled) {
\t_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
\t\tdbg->set_debug_navigation(p_enabled);
\t});
}

void EditorDebuggerNode::set_debug_avoidance(bool p_enabled) {
\t_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
\t\tdbg->set_debug_avoidance(p_enabled);
\t});
}

void EditorDebuggerNode::set_debug_mute_audio(bool p_mute) {""")

replace_once(SCRIPT_DEBUGGER_HEADER,
    "void set_debug_mute_audio(bool p_mute);",
    "void set_debug_collisions(bool p_enable);\n\tvoid set_debug_navigation(bool p_enable);\n\tvoid set_debug_avoidance(bool p_enable);\n\tvoid set_debug_mute_audio(bool p_mute);")
# Android can deliver a delayed stack-frame selection after the preview has stopped.
# The upstream ERR_FAIL_COND_V reports this expected stale UI event as an ERROR.
# Keep the same safe return behavior without polluting Output or obscuring real failures.
replace_once(SCRIPT_DEBUGGER_SOURCE,
    "bool ScriptEditorDebugger::request_stack_dump(const int &p_frame) {\n\tERR_FAIL_COND_V(!is_session_active() || p_frame < 0, false);",
    "bool ScriptEditorDebugger::request_stack_dump(const int &p_frame) {\n\tif (!is_session_active() || p_frame < 0) {\n\t\treturn false;\n\t}")

replace_once(SCRIPT_DEBUGGER_SOURCE,
    "void ScriptEditorDebugger::set_debug_mute_audio(bool p_mute) {",
    """void ScriptEditorDebugger::set_debug_fps(bool p_enable) {
\tArray msg = { p_enable };
\t_put_msg("scene:set_debug_fps", msg);
}

void ScriptEditorDebugger::set_debug_collisions(bool p_enable) {
\tArray msg = { p_enable };
\t_put_msg("scene:set_debug_collisions", msg);
}

void ScriptEditorDebugger::set_debug_navigation(bool p_enable) {
\tArray msg = { p_enable };
\t_put_msg("scene:set_debug_navigation", msg);
}

void ScriptEditorDebugger::set_debug_avoidance(bool p_enable) {
\tArray msg = { p_enable };
\t_put_msg("scene:set_debug_avoidance", msg);
}

void ScriptEditorDebugger::set_debug_mute_audio(bool p_mute) {""")

replace_once(SCENE_DEBUGGER_HEADER,
    "static Error _msg_debug_mute_audio(const Array &p_args);",
    "static Error _msg_debug_mute_audio(const Array &p_args);\n\tstatic Error _msg_set_debug_collisions(const Array &p_args);\n\tstatic Error _msg_set_debug_navigation(const Array &p_args);\n\tstatic Error _msg_set_debug_avoidance(const Array &p_args);\n\tstatic void _create_runtime_debug_overlay();\n\tstatic void _runtime_debug_button_pressed();\n\tstatic void _runtime_debug_item_pressed(int p_id);\n\tstatic void _runtime_fps_timer_timeout();")
replace_once(SCENE_DEBUGGER_SOURCE,
    '#include "servers/rendering/rendering_server.h"',
    '#include "core/templates/list.h"\n#include "scene/2d/path_2d.h"\n#include "scene/3d/path_3d.h"\n#include "scene/gui/button.h"\n#include "scene/gui/popup_menu.h"\n#include "scene/gui/label.h"\n#include "scene/main/timer.h"\n#include "core/config/engine.h"\n#include "scene/main/canvas_layer.h"\n#include "servers/rendering/rendering_server.h"\n#include "servers/navigation_2d/navigation_server_2d.h"\n#include "servers/navigation_3d/navigation_server_3d.h"')
replace_once(SCENE_DEBUGGER_SOURCE,
    "Error SceneDebugger::_msg_debug_mute_audio(const Array &p_args) {",
    """Error SceneDebugger::_msg_set_debug_collisions(const Array &p_args) {
\tERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);
\tSceneTree *tree = SceneTree::get_singleton();
\tERR_FAIL_NULL_V(tree, ERR_UNCONFIGURED);
\ttree->set_debug_collisions_hint(bool(p_args[0]));
\treturn OK;
}

Error SceneDebugger::_msg_set_debug_navigation(const Array &p_args) {
\tERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);
\tconst bool enabled = p_args[0];
\tSceneTree::get_singleton()->set_debug_navigation_hint(enabled);
#ifndef NAVIGATION_2D_DISABLED
\tNavigationServer2D::get_singleton()->set_debug_navigation_enabled(enabled);
#endif
#ifndef NAVIGATION_3D_DISABLED
\tNavigationServer3D::get_singleton()->set_debug_navigation_enabled(enabled);
#endif
\treturn OK;
}

Error SceneDebugger::_msg_set_debug_avoidance(const Array &p_args) {
\tERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);
\tconst bool enabled = p_args[0];
#ifndef NAVIGATION_2D_DISABLED
\tNavigationServer2D::get_singleton()->set_debug_avoidance_enabled(enabled);
#endif
#ifndef NAVIGATION_3D_DISABLED
\tNavigationServer3D::get_singleton()->set_debug_avoidance_enabled(enabled);
#endif
\treturn OK;
}


Error SceneDebugger::_msg_set_debug_fps(const Array &p_args) {
\tERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);
\t_create_runtime_debug_overlay();
\tSceneTree *tree = SceneTree::get_singleton();
\tERR_FAIL_NULL_V(tree, ERR_UNCONFIGURED);
\tWindow *root = tree->get_root();
\tERR_FAIL_NULL_V(root, ERR_UNCONFIGURED);
\tLabel *fps_label = Object::cast_to<Label>(root->get_node_or_null(NodePath("__GodotPreviewDebugOverlay/FPSLabel")));
\tTimer *fps_timer = Object::cast_to<Timer>(root->get_node_or_null(NodePath("__GodotPreviewDebugOverlay/FPSTimer")));
\tERR_FAIL_NULL_V(fps_label, ERR_DOES_NOT_EXIST);
\tERR_FAIL_NULL_V(fps_timer, ERR_DOES_NOT_EXIST);
\tif (bool(p_args[0])) {
\t\tfps_label->show();
\t\tfps_timer->start();
\t\t_runtime_fps_timer_timeout();
\t} else {
\t\tfps_timer->stop();
\t\tfps_label->hide();
\t}
\treturn OK;
}

Error SceneDebugger::_msg_debug_mute_audio(const Array &p_args) {""")
replace_once(SCENE_DEBUGGER_SOURCE,
    'message_handlers["debug_mute_audio"] = _msg_debug_mute_audio;',
    'message_handlers["debug_mute_audio"] = _msg_debug_mute_audio;\n\tmessage_handlers["set_debug_collisions"] = _msg_set_debug_collisions;\n\tmessage_handlers["set_debug_navigation"] = _msg_set_debug_navigation;\n\tmessage_handlers["set_debug_avoidance"] = _msg_set_debug_avoidance;\n\t_create_runtime_debug_overlay();')



# Make the two remaining preview overlays react to menu changes while the game is
# already running. Canvas redraw is a RenderingServer runtime flag. Path2D nodes
# need an explicit redraw after changing SceneTree's hint; Path3D relies on the
# engine's existing path debug rendering implementation.
replace_once(EDITOR_DEBUGGER_HEADER,
    "void set_debug_avoidance(bool p_enabled);",
    "void set_debug_avoidance(bool p_enabled);\n\tvoid set_debug_paths(bool p_enabled);\n\tvoid set_debug_canvas_item_redraw(bool p_enabled);\n\tvoid set_debug_fps(bool p_enabled);")
replace_once(EDITOR_DEBUGGER_SOURCE,
    "void EditorDebuggerNode::set_debug_collisions(bool p_enabled) {",
    """void EditorDebuggerNode::set_debug_paths(bool p_enabled) {
\t_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
\t\tdbg->set_debug_paths(p_enabled);
\t});
}

void EditorDebuggerNode::set_debug_canvas_item_redraw(bool p_enabled) {
\t_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
\t\tdbg->set_debug_canvas_item_redraw(p_enabled);
\t});
}

void EditorDebuggerNode::set_debug_collisions(bool p_enabled) {""")
replace_once(SCRIPT_DEBUGGER_HEADER,
    "void set_debug_avoidance(bool p_enable);",
    "void set_debug_avoidance(bool p_enable);\n\tvoid set_debug_paths(bool p_enable);\n\tvoid set_debug_canvas_item_redraw(bool p_enable);\n\tvoid set_debug_fps(bool p_enable);")
replace_once(SCRIPT_DEBUGGER_SOURCE,
    "void ScriptEditorDebugger::set_debug_collisions(bool p_enable) {",
    """void ScriptEditorDebugger::set_debug_paths(bool p_enable) {
\tArray msg = { p_enable };
\t_put_msg("scene:set_debug_paths", msg);
}

void ScriptEditorDebugger::set_debug_canvas_item_redraw(bool p_enable) {
\tArray msg = { p_enable };
\t_put_msg("scene:set_debug_canvas_item_redraw", msg);
}

void ScriptEditorDebugger::set_debug_collisions(bool p_enable) {""")
replace_once(SCENE_DEBUGGER_HEADER,
    "static Error _msg_set_debug_avoidance(const Array &p_args);",
    "static Error _msg_set_debug_avoidance(const Array &p_args);\n\tstatic Error _msg_set_debug_paths(const Array &p_args);\n\tstatic Error _msg_set_debug_canvas_item_redraw(const Array &p_args);\n\tstatic Error _msg_set_debug_fps(const Array &p_args);")
replace_once(SCENE_DEBUGGER_SOURCE,
    "Error SceneDebugger::_msg_debug_mute_audio(const Array &p_args) {",
    """Error SceneDebugger::_msg_set_debug_paths(const Array &p_args) {
\tERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);
\tSceneTree *tree = SceneTree::get_singleton();
\tERR_FAIL_NULL_V(tree, ERR_UNCONFIGURED);
\tconst bool enabled = bool(p_args[0]);
\ttree->set_debug_paths_hint(enabled);
\t// The hint alone is not a runtime toggle in Godot. Refresh each existing
\t// Path2D/Path3D debug renderer explicitly so both 2D and 3D paths update now.
\tList<Node *> pending;
\tif (tree->get_root()) {
\t\tpending.push_back(tree->get_root());
\t}
\twhile (!pending.is_empty()) {
\t\tNode *node = pending.front()->get();
\t\tpending.pop_front();
\t\tif (Path2D *path_2d = Object::cast_to<Path2D>(node)) {
\t\t\tpath_2d->debug_update_runtime();
\t\t}
\t\tif (Path3D *path_3d = Object::cast_to<Path3D>(node)) {
\t\t\tpath_3d->debug_update_runtime(enabled);
\t\t}
\t\tfor (int i = 0; i < node->get_child_count(); i++) {
\t\t\tpending.push_back(node->get_child(i));
\t\t}
\t}
\treturn OK;
}

Error SceneDebugger::_msg_set_debug_canvas_item_redraw(const Array &p_args) {
\tERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);
\tRenderingServer::get_singleton()->canvas_item_set_debug_redraw(bool(p_args[0]));
\treturn OK;
}

Error SceneDebugger::_msg_debug_mute_audio(const Array &p_args) {""")
replace_once(SCENE_DEBUGGER_SOURCE,
    'message_handlers["set_debug_avoidance"] = _msg_set_debug_avoidance;',
    'message_handlers["set_debug_avoidance"] = _msg_set_debug_avoidance;\n\tmessage_handlers["set_debug_paths"] = _msg_set_debug_paths;\n\tmessage_handlers["set_debug_canvas_item_redraw"] = _msg_set_debug_canvas_item_redraw;\n\tmessage_handlers["set_debug_fps"] = _msg_set_debug_fps;')
# Runtime overlay owns these toggles; no COL button is placed in EditorRunBar.


# Runtime path toggling must refresh Godot's actual built-in Path2D/Path3D
# debug renderers; merely changing SceneTree::debug_paths_hint is insufficient.
PATH2D_HEADER = ROOT / "scene/2d/path_2d.h"
PATH2D_SOURCE = ROOT / "scene/2d/path_2d.cpp"
PATH3D_HEADER = ROOT / "scene/3d/path_3d.h"
PATH3D_SOURCE = ROOT / "scene/3d/path_3d.cpp"
for required in (PATH2D_HEADER, PATH2D_SOURCE, PATH3D_HEADER, PATH3D_SOURCE):
    if not required.is_file():
        sys.exit(f"Godot path-debug source not found: {required.relative_to(ROOT)}")

replace_once(PATH2D_HEADER,
    "Ref<Curve2D> get_curve() const;",
    "Ref<Curve2D> get_curve() const;\n\tvoid debug_update_runtime();")
replace_once(PATH2D_SOURCE,
    "void Path2D::set_curve(const Ref<Curve2D> &p_curve) {",
    """void Path2D::debug_update_runtime() {
#ifdef DEBUG_ENABLED
    if (is_inside_tree()) {
        _debug_update();
    }
#endif
}

void Path2D::set_curve(const Ref<Curve2D> &p_curve) {""")
replace_once(PATH3D_HEADER,
    "Ref<StandardMaterial3D> get_debug_material();",
    "Ref<StandardMaterial3D> get_debug_material();\n\tvoid debug_update_runtime(bool p_enabled);")
replace_once(PATH3D_SOURCE,
    "void Path3D::set_debug_custom_color(const Color &p_color) {",
    """void Path3D::debug_update_runtime(bool p_enabled) {
    if (!p_enabled) {
        if (debug_instance.is_valid()) {
            RS::get_singleton()->instance_set_visible(debug_instance, false);
        }
        return;
    }

    // Paths created while debugging was off have no RenderingServer instance yet.
    if (!debug_instance.is_valid()) {
        debug_instance = RS::get_singleton()->instance_create();
        set_notify_transform(true);
    }
    _update_debug_mesh();
}

void Path3D::set_debug_custom_color(const Color &p_color) {""")

print("GitHub import and Android Gallery protection patches applied successfully.")


# Android immersive preview mode: hide editor chrome, use the whole display area,
# and keep a small floating return control so the running game is not stopped.
EDITOR_NODE_HEADER = ROOT / "editor/editor_node.h"
EDITOR_NODE_SOURCE = ROOT / "editor/editor_node.cpp"
if not EDITOR_NODE_HEADER.is_file() or not EDITOR_NODE_SOURCE.is_file():
    sys.exit("Godot EditorNode source not found; cannot add immersive preview mode.")

replace_once(EDITOR_NODE_HEADER,
    "class EditorTitleBar;\n",
    "class EditorTitleBar;\nclass CanvasLayer;\nclass Button;\n")
replace_once(EDITOR_NODE_HEADER,
    "class Button;\n",
    "class Button;\nclass PopupMenu;\n")
replace_once(EDITOR_NODE_HEADER,
    "EditorTitleBar *title_bar = nullptr;",
    "EditorTitleBar *title_bar = nullptr;\n\tCanvasLayer *mobile_immersive_layer = nullptr;\n\tButton *mobile_immersive_exit_button = nullptr;\n\tbool mobile_immersive_preview = false;\n\tbool mobile_previous_distraction_free = false;\n\tbool mobile_previous_system_immersive = false;\n\tbool mobile_previous_run_bar_visible = true;\n\tint mobile_previous_window_mode = -1;")
replace_once(EDITOR_NODE_HEADER,
    "static Button *get_distraction_free_button() { return singleton->distraction_free; }",
    "static Button *get_distraction_free_button() { return singleton->distraction_free; }\n\tvoid toggle_mobile_immersive_preview();\n\tvoid exit_mobile_immersive_preview();")
replace_once(EDITOR_NODE_HEADER,
    "Button *mobile_immersive_exit_button = nullptr;",
    "Button *mobile_immersive_exit_button = nullptr;\n\tButton *mobile_preview_debug_button = nullptr;\n\tPopupMenu *mobile_preview_debug_menu = nullptr;")
replace_once(EDITOR_NODE_HEADER,
    "void exit_mobile_immersive_preview();",
    "void exit_mobile_immersive_preview();\n\tvoid _mobile_preview_debug_menu_pressed();\n\tvoid _mobile_preview_debug_item_pressed(int p_id);")
replace_once(EDITOR_NODE_SOURCE,
    '#include "scene/main/scene_tree.h"',
    '#include "scene/main/scene_tree.h"\n#include "scene/main/canvas_layer.h"\n#include "scene/gui/button.h"\n#ifdef ANDROID_ENABLED\n#include "platform/android/os_android.h"\n#include "platform/android/java_godot_wrapper.h"\n#endif')
replace_once(EDITOR_NODE_SOURCE,
    '#include "scene/gui/button.h"',
    '#include "scene/gui/button.h"\n#include "scene/gui/popup_menu.h"')
replace_once(EDITOR_NODE_SOURCE,
    "editor_main_screen->set_button_container(main_editor_button_hb);",
    """editor_main_screen->set_button_container(main_editor_button_hb);
#ifdef ANDROID_ENABLED
	Button *mobile_immersive_toolbar_button = memnew(Button);
	mobile_immersive_toolbar_button->set_text(TTR("Inm"));
	mobile_immersive_toolbar_button->set_custom_minimum_size(Size2(48, 44) * EDSCALE);
	mobile_immersive_toolbar_button->set_accessibility_name(TTR("Vista previa inmersiva"));
	mobile_immersive_toolbar_button->set_tooltip_text(TTR("Ampliar el juego en ejecución a pantalla completa."));
	mobile_immersive_toolbar_button->connect(SceneStringName(pressed), callable_mp(this, &EditorNode::toggle_mobile_immersive_preview));
	main_editor_button_hb->add_child(mobile_immersive_toolbar_button);
	mobile_preview_debug_button = memnew(Button);
	mobile_preview_debug_button->set_text(TTR("☀️"));
	mobile_preview_debug_button->set_custom_minimum_size(Size2(48, 44) * EDSCALE);
	mobile_preview_debug_button->set_accessibility_name(TTR("Opciones de depuración de la vista previa"));
	mobile_preview_debug_button->set_tooltip_text(TTR("Colisiones, rutas, navegación, evasión y redibujado 2D."));
	mobile_preview_debug_button->connect(SceneStringName(pressed), callable_mp(this, &EditorNode::_mobile_preview_debug_menu_pressed));
	main_editor_button_hb->add_child(mobile_preview_debug_button);
	mobile_preview_debug_menu = memnew(PopupMenu);
	mobile_preview_debug_menu->add_check_item(TTR("Colisiones 2D/3D, formas y raycasts"), 0);
	mobile_preview_debug_menu->add_check_item(TTR("Rutas Path2D/Path3D"), 1);
	mobile_preview_debug_menu->add_check_item(TTR("Mallas de navegación"), 2);
	mobile_preview_debug_menu->add_check_item(TTR("Áreas y velocidades de evasión"), 3);
	mobile_preview_debug_menu->add_check_item(TTR("Redibujado 2D"), 4);\n\tmobile_preview_debug_menu->add_check_item(TTR("Mostrar FPS"), 5);
	mobile_preview_debug_menu->connect(SceneStringName(id_pressed), callable_mp(this, &EditorNode::_mobile_preview_debug_item_pressed));
	add_child(mobile_preview_debug_menu);
#endif""")

replace_once(EDITOR_NODE_SOURCE,
    "distraction_free->connect(SceneStringName(pressed), callable_mp(this, &EditorNode::_toggle_distraction_free_mode));",
    """distraction_free->connect(SceneStringName(pressed), callable_mp(this, &EditorNode::_toggle_distraction_free_mode));

#ifdef ANDROID_ENABLED
	// A floating return control stays available after the editor title bar is hidden.
	mobile_immersive_layer = memnew(CanvasLayer);
	mobile_immersive_layer->set_layer(128);
	add_child(mobile_immersive_layer);
	mobile_immersive_exit_button = memnew(Button);
	mobile_immersive_exit_button->set_text(TTR("Volver"));
	mobile_immersive_exit_button->set_tooltip_text(TTR("Volver al editor sin detener el juego."));
	mobile_immersive_exit_button->set_accessibility_name(TTR("Salir de vista inmersiva"));
	mobile_immersive_exit_button->set_custom_minimum_size(Size2(72, 48) * EDSCALE);
	mobile_immersive_exit_button->set_anchors_and_offsets_preset(Control::PRESET_TOP_RIGHT);
	mobile_immersive_exit_button->set_offset(SIDE_LEFT, -84 * EDSCALE);
	mobile_immersive_exit_button->set_offset(SIDE_TOP, 8 * EDSCALE);
	mobile_immersive_exit_button->set_offset(SIDE_RIGHT, -8 * EDSCALE);
	mobile_immersive_exit_button->set_offset(SIDE_BOTTOM, 56 * EDSCALE);
	mobile_immersive_exit_button->connect(SceneStringName(pressed), callable_mp(this, &EditorNode::exit_mobile_immersive_preview));
	mobile_immersive_layer->add_child(mobile_immersive_exit_button);
	mobile_immersive_exit_button->hide();
#endif""")
replace_once(EDITOR_NODE_SOURCE,
    "void EditorNode::_toggle_distraction_free_mode() {",
    """void EditorNode::_mobile_preview_debug_menu_pressed() {
#ifdef ANDROID_ENABLED
	if (mobile_preview_debug_menu == nullptr || mobile_preview_debug_button == nullptr) {
		return;
	}
	mobile_preview_debug_menu->set_position(mobile_preview_debug_button->get_screen_position());
	mobile_preview_debug_menu->reset_size();
	mobile_preview_debug_menu->popup();
#endif
}

void EditorNode::_mobile_preview_debug_item_pressed(int p_id) {
#ifdef ANDROID_ENABLED
	if (mobile_preview_debug_menu == nullptr || EditorDebuggerNode::get_singleton() == nullptr) {
		return;
	}
	const int item_index = mobile_preview_debug_menu->get_item_index(p_id);
	if (item_index < 0) {
		return;
	}
	const bool enabled = !mobile_preview_debug_menu->is_item_checked(item_index);
	mobile_preview_debug_menu->set_item_checked(item_index, enabled);
	EditorDebuggerNode *debugger = EditorDebuggerNode::get_singleton();
	switch (p_id) {
		case 0: debugger->set_debug_collisions(enabled); break;
		case 1: debugger->set_debug_paths(enabled); break;
		case 2: debugger->set_debug_navigation(enabled); break;
		case 3: debugger->set_debug_avoidance(enabled); break;
		case 4: debugger->set_debug_canvas_item_redraw(enabled); break;
		case 5: debugger->set_debug_fps(enabled); break;
		default: break;
	}
#endif
}

void EditorNode::toggle_mobile_immersive_preview() {
#ifdef ANDROID_ENABLED
	if (!mobile_immersive_preview && (project_run_bar == nullptr || !project_run_bar->is_playing())) {
		return;
	}
	if (mobile_immersive_preview) {
		exit_mobile_immersive_preview();
		return;
	}
	mobile_immersive_preview = true;
	mobile_previous_window_mode = (int)DisplayServer::get_singleton()->window_get_mode();
	mobile_previous_distraction_free = is_distraction_free_mode_enabled();
	mobile_previous_system_immersive = false;
	if (OS_Android::get_singleton() != nullptr && OS_Android::get_singleton()->get_godot_java() != nullptr) {
		mobile_previous_system_immersive = OS_Android::get_singleton()->get_godot_java()->is_in_immersive_mode();
	}
	set_distraction_free_mode(true);
	mobile_previous_run_bar_visible = project_run_bar != nullptr && project_run_bar->is_visible();
	if (title_bar) {
		title_bar->hide();
	}
	// The black strip above the preview is the editor run bar, not the title
	// bar. Hide it explicitly so fullscreen contains only the running game and
	// the floating Volver control. Restore it when immersive preview exits.
	if (project_run_bar) {
		project_run_bar->hide();
	}
	// Fullscreen makes the editor's game area use the Android display bounds.
	// The game session is not stopped or relaunched by this UI-only transition.
	DisplayServer::get_singleton()->window_set_mode(DisplayServerEnums::WINDOW_MODE_FULLSCREEN);
	if (OS_Android::get_singleton() != nullptr && OS_Android::get_singleton()->get_godot_java() != nullptr) {
		OS_Android::get_singleton()->get_godot_java()->enable_immersive_mode(true);
	}
	EditorDebuggerNode::get_singleton()->set_mobile_immersive_preview(true);
	if (mobile_immersive_exit_button) {
		mobile_immersive_exit_button->show();
	}
#endif
}

void EditorNode::exit_mobile_immersive_preview() {
#ifdef ANDROID_ENABLED
	if (!mobile_immersive_preview) {
		return;
	}
	mobile_immersive_preview = false;
	if (mobile_immersive_exit_button) {
		mobile_immersive_exit_button->hide();
	}
	if (title_bar) {
		title_bar->show();
	}
	if (project_run_bar) {
		project_run_bar->set_visible(mobile_previous_run_bar_visible);
	}
	if (mobile_previous_window_mode >= 0) {
		DisplayServer::get_singleton()->window_set_mode((DisplayServerEnums::WindowMode)mobile_previous_window_mode);
	}
	if (OS_Android::get_singleton() != nullptr && OS_Android::get_singleton()->get_godot_java() != nullptr) {
		OS_Android::get_singleton()->get_godot_java()->enable_immersive_mode(mobile_previous_system_immersive);
	}
	set_distraction_free_mode(mobile_previous_distraction_free);
	mobile_previous_system_immersive = false;
	mobile_previous_window_mode = -1;
#endif
}

void EditorNode::_toggle_distraction_free_mode() {""")
# While immersive preview is active, ask the running game through the existing
# remote-debugger channel to ignore its design aspect ratio, then restore it on exit.
replace_once(EDITOR_NODE_SOURCE,
    "set_distraction_free_mode(mobile_previous_distraction_free);",
    "set_distraction_free_mode(mobile_previous_distraction_free);\n\tEditorDebuggerNode::get_singleton()->set_mobile_immersive_preview(false);")

replace_once(EDITOR_DEBUGGER_HEADER,
    "void set_debug_avoidance(bool p_enabled);",
    "void set_debug_avoidance(bool p_enabled);\n\tvoid set_mobile_immersive_preview(bool p_enabled);")
replace_once(EDITOR_DEBUGGER_SOURCE,
    "void EditorDebuggerNode::set_debug_mute_audio(bool p_mute) {",
    """void EditorDebuggerNode::set_mobile_immersive_preview(bool p_enabled) {
	_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
		dbg->set_mobile_immersive_preview(p_enabled);
	});
}

void EditorDebuggerNode::set_debug_mute_audio(bool p_mute) {""")
replace_once(SCRIPT_DEBUGGER_HEADER,
    "void set_debug_avoidance(bool p_enable);",
    "void set_debug_avoidance(bool p_enable);\n\tvoid set_mobile_immersive_preview(bool p_enable);")
replace_once(SCRIPT_DEBUGGER_SOURCE,
    "void ScriptEditorDebugger::set_debug_mute_audio(bool p_mute) {",
    """void ScriptEditorDebugger::set_mobile_immersive_preview(bool p_enable) {
	Array msg = { p_enable };
	_put_msg("scene:set_mobile_immersive_preview", msg);
}

void ScriptEditorDebugger::set_debug_mute_audio(bool p_mute) {""")
replace_once(SCENE_DEBUGGER_HEADER,
    "static Error _msg_set_debug_canvas_item_redraw(const Array &p_args);",
    "static Error _msg_set_debug_canvas_item_redraw(const Array &p_args);\n\tstatic Error _msg_set_mobile_immersive_preview(const Array &p_args);")
replace_once(SCENE_DEBUGGER_SOURCE,
    '#include "scene/3d/path_3d.h"',
    '#include "scene/3d/path_3d.h"\n#include "scene/main/window.h"')
replace_once(SCENE_DEBUGGER_SOURCE,
    "Error SceneDebugger::_msg_set_debug_collisions(const Array &p_args) {",
    """void SceneDebugger::_create_runtime_debug_overlay() {
\tSceneTree *tree = SceneTree::get_singleton();
\tif (tree == nullptr || tree->get_root() == nullptr) {
\t\treturn;
\t}
\tWindow *root = tree->get_root();
\tif (root->has_node(NodePath("__GodotPreviewDebugOverlay"))) {
\t\treturn;
\t}
\tCanvasLayer *layer = memnew(CanvasLayer);
\tlayer->set_name("__GodotPreviewDebugOverlay");
\tlayer->set_layer(127);
\troot->add_child(layer);
\tButton *button = memnew(Button);
\tbutton->set_name("CollisionButton");
\tbutton->set_text("☀️");
\tbutton->set_tooltip_text("Colisiones, rutas, navegación y evasión de la vista previa");
\tbutton->set_accessibility_name("Opciones de depuración de la vista previa");
\tbutton->set_custom_minimum_size(Size2(60, 44));
\tbutton->set_anchors_and_offsets_preset(Control::PRESET_TOP_RIGHT);
\tbutton->set_offset(SIDE_LEFT, -68);
\tbutton->set_offset(SIDE_TOP, 8);
\tbutton->set_offset(SIDE_RIGHT, -8);
\tbutton->set_offset(SIDE_BOTTOM, 52);
\tlayer->add_child(button);
\tPopupMenu *popup = memnew(PopupMenu);
\tpopup->set_name("CollisionMenu");
\tlayer->add_child(popup);
\tpopup->add_check_item("Colisiones 2D/3D, formas y raycasts", 0);
\tpopup->set_item_tooltip(popup->get_item_index(0), "Incluye rectángulos, círculos, cápsulas, polígonos, cajas 3D, Area2D/Area3D y RayCast2D/3D.");
\tpopup->add_check_item("Rutas Path2D/Path3D", 1);
\tpopup->add_check_item("Mallas de navegación", 2);
\tpopup->add_check_item("Áreas y velocidades de evasión", 3);
\tpopup->add_check_item("Redibujado 2D", 4);
\t\tpopup->add_check_item(\"Mostrar FPS (esquina superior derecha)\", 5);
\tLabel *fps_label = memnew(Label);
\tfps_label->set_name(\"FPSLabel\");
\tfps_label->set_text(\"FPS: --\");
\tfps_label->set_horizontal_alignment(HORIZONTAL_ALIGNMENT_RIGHT);
\tfps_label->set_vertical_alignment(VERTICAL_ALIGNMENT_CENTER);
\tfps_label->set_mouse_filter(Control::MOUSE_FILTER_IGNORE);
\tfps_label->set_anchors_and_offsets_preset(Control::PRESET_TOP_RIGHT);
\tfps_label->set_offset(SIDE_LEFT, -112);
\tfps_label->set_offset(SIDE_TOP, 56);
\tfps_label->set_offset(SIDE_RIGHT, -8);
\tfps_label->set_offset(SIDE_BOTTOM, 82);
\tfps_label->add_theme_color_override(\"font_color\", Color(1, 1, 1, 1));
\tfps_label->add_theme_color_override(\"font_shadow_color\", Color(0, 0, 0, 0.9));
\tfps_label->hide();
\tlayer->add_child(fps_label);
\tTimer *fps_timer = memnew(Timer);
\tfps_timer->set_name(\"FPSTimer\");
\tfps_timer->set_wait_time(0.25);
\tfps_timer->set_one_shot(false);
\tfps_timer->connect("timeout", callable_mp_static(&SceneDebugger::_runtime_fps_timer_timeout));
\tlayer->add_child(fps_timer);
\tbutton->connect("pressed", callable_mp_static(&SceneDebugger::_runtime_debug_button_pressed));
\tpopup->connect("id_pressed", callable_mp_static(&SceneDebugger::_runtime_debug_item_pressed));
}

void SceneDebugger::_runtime_debug_button_pressed() {
\tSceneTree *tree = SceneTree::get_singleton();
\tif (tree == nullptr || tree->get_root() == nullptr) {
\t\treturn;
\t}
\tControl *button = Object::cast_to<Control>(tree->get_root()->get_node_or_null(NodePath("__GodotPreviewDebugOverlay/CollisionButton")));
\tPopupMenu *popup = Object::cast_to<PopupMenu>(tree->get_root()->get_node_or_null(NodePath("__GodotPreviewDebugOverlay/CollisionMenu")));
\tif (button == nullptr || popup == nullptr) {
\t\treturn;
\t}
\tpopup->set_position(button->get_screen_position());
\tpopup->popup();
}

void SceneDebugger::_runtime_fps_timer_timeout() {
\tSceneTree *tree = SceneTree::get_singleton();
\tif (tree == nullptr || tree->get_root() == nullptr) {
\t\treturn;
\t}
\tLabel *fps_label = Object::cast_to<Label>(tree->get_root()->get_node_or_null(NodePath("__GodotPreviewDebugOverlay/FPSLabel")));
\tif (fps_label != nullptr && fps_label->is_visible()) {
\t\tfps_label->set_text(vformat("FPS: %d", Engine::get_singleton()->get_frames_per_second()));
\t}
}

void SceneDebugger::_runtime_debug_item_pressed(int p_id) {
\tSceneTree *tree = SceneTree::get_singleton();
\tif (tree == nullptr || tree->get_root() == nullptr) {
\t\treturn;
\t}
\tPopupMenu *popup = Object::cast_to<PopupMenu>(tree->get_root()->get_node_or_null(NodePath("__GodotPreviewDebugOverlay/CollisionMenu")));
\tif (popup == nullptr) {
\t\treturn;
\t}
\tint index = popup->get_item_index(p_id);
\tif (index < 0) {
\t\treturn;
\t}
\tbool enabled = !popup->is_item_checked(index);
\tpopup->set_item_checked(index, enabled);
\tArray args;
\targs.push_back(enabled);
\tswitch (p_id) {
\t\tcase 0: _msg_set_debug_collisions(args); break;
\t\tcase 1: _msg_set_debug_paths(args); break;
\t\tcase 2: _msg_set_debug_navigation(args); break;
\t\tcase 3: _msg_set_debug_avoidance(args); break;
\t\tcase 4: _msg_set_debug_canvas_item_redraw(args); break;
\t\tcase 5: {
\t\t\tLabel *fps_label = Object::cast_to<Label>(tree->get_root()->get_node_or_null(NodePath("__GodotPreviewDebugOverlay/FPSLabel")));
\t\t\tTimer *fps_timer = Object::cast_to<Timer>(tree->get_root()->get_node_or_null(NodePath("__GodotPreviewDebugOverlay/FPSTimer")));
\t\t\tif (fps_label && fps_timer) {
\t\t\t\tif (enabled) { fps_label->show(); fps_timer->start(); _runtime_fps_timer_timeout(); }
\t\t\t\telse { fps_timer->stop(); fps_label->hide(); }
\t\t\t}
\t\t} break;
\t\tdefault: break;
\t}
}

Error SceneDebugger::_msg_set_debug_collisions(const Array &p_args) {""")
replace_once(SCENE_DEBUGGER_SOURCE,
    "Error SceneDebugger::_msg_set_debug_collisions(const Array &p_args) {",
    """static bool mobile_immersive_preview_active = false;
static Window::ContentScaleAspect mobile_immersive_previous_aspect = Window::CONTENT_SCALE_ASPECT_IGNORE;
static Window::ContentScaleMode mobile_immersive_previous_scale_mode = Window::CONTENT_SCALE_MODE_DISABLED;

Error SceneDebugger::_msg_set_mobile_immersive_preview(const Array &p_args) {
	ERR_FAIL_COND_V(p_args.is_empty(), ERR_INVALID_DATA);
	// This remote-debugger message is received only after the game window exists.
	// Retry overlay creation here as well as at debugger initialization, where the
	// SceneTree root may not yet be ready. This prevents the preview tools vanishing.
	_create_runtime_debug_overlay();
	SceneTree *tree = SceneTree::get_singleton();
	ERR_FAIL_NULL_V(tree, ERR_UNCONFIGURED);
	Window *window = tree->get_root();
	ERR_FAIL_NULL_V(window, ERR_UNCONFIGURED);
	const bool enabled = bool(p_args[0]);
	if (enabled) {
		if (!mobile_immersive_preview_active) {
			mobile_immersive_previous_aspect = window->get_content_scale_aspect();
			mobile_immersive_previous_scale_mode = window->get_content_scale_mode();
			mobile_immersive_preview_active = true;
		}
		// Fill the entire 720x1600 display area instead of preserving a
		// landscape/letterboxed design aspect while immersive preview is active.
		if (window->get_content_scale_mode() == Window::CONTENT_SCALE_MODE_DISABLED) {
			window->set_content_scale_mode(Window::CONTENT_SCALE_MODE_CANVAS_ITEMS);
		}
		window->set_content_scale_aspect(Window::CONTENT_SCALE_ASPECT_IGNORE);
	} else if (mobile_immersive_preview_active) {
		window->set_content_scale_aspect(mobile_immersive_previous_aspect);
		window->set_content_scale_mode(mobile_immersive_previous_scale_mode);
		mobile_immersive_preview_active = false;
	}
	return OK;
}

Error SceneDebugger::_msg_set_debug_collisions(const Array &p_args) {""")
replace_once(SCENE_DEBUGGER_SOURCE,
    'message_handlers["set_debug_canvas_item_redraw"] = _msg_set_debug_canvas_item_redraw;',
    'message_handlers["set_debug_canvas_item_redraw"] = _msg_set_debug_canvas_item_redraw;\n\tmessage_handlers["set_mobile_immersive_preview"] = _msg_set_mobile_immersive_preview;')


# Customizable native Android 3D viewport navigation joysticks. The addon UI
# writes these editor settings; the native controls read them and relayout live.
NATIVE_3D_HEADER = ROOT / "editor/scene/3d/node_3d_editor_plugin.h"
NATIVE_3D_SOURCE = ROOT / "editor/scene/3d/node_3d_editor_plugin.cpp"
EDITOR_SETTINGS_SOURCE = ROOT / "editor/settings/editor_settings.cpp"
for required in (NATIVE_3D_HEADER, NATIVE_3D_SOURCE, EDITOR_SETTINGS_SOURCE):
    if not required.is_file():
        sys.exit(f"Native 3D joystick customization source not found: {required}")

replace_once(EDITOR_SETTINGS_SOURCE,
    '\t_initial_set("editors/3d/navigation/show_viewport_navigation_gizmo", should_show_viewport_navigation_gizmo);',
    '\t_initial_set("editors/3d/navigation/show_viewport_navigation_gizmo", should_show_viewport_navigation_gizmo);\n'
    '\tEDITOR_SETTING(Variant::INT, PROPERTY_HINT_RANGE, "editors/3d/navigation/native_joystick_left_size", 150, "80,240,1")\n'
    '\tEDITOR_SETTING(Variant::INT, PROPERTY_HINT_RANGE, "editors/3d/navigation/native_joystick_right_size", 150, "80,240,1")\n'
    '\tEDITOR_SETTING(Variant::INT, PROPERTY_HINT_RANGE, "editors/3d/navigation/native_joystick_left_inset_x", 0, "0,240,1")\n'
    '\tEDITOR_SETTING(Variant::INT, PROPERTY_HINT_RANGE, "editors/3d/navigation/native_joystick_right_inset_x", 0, "0,240,1")\n'
    '\tEDITOR_SETTING(Variant::INT, PROPERTY_HINT_RANGE, "editors/3d/navigation/native_joystick_left_inset_y", 0, "0,300,1")\n'
    '\tEDITOR_SETTING(Variant::INT, PROPERTY_HINT_RANGE, "editors/3d/navigation/native_joystick_right_inset_y", 0, "0,300,1")')
 
replace_once(NATIVE_3D_HEADER,
    '\tvoid _update_navigation_controls_visibility();',
    '\tvoid _update_navigation_controls_visibility();\n\tvoid _update_native_navigation_control_layout();')
replace_once(NATIVE_3D_SOURCE,
    "void Node3DEditorViewport::_update_navigation_controls_visibility() {",
    """void Node3DEditorViewport::_update_native_navigation_control_layout() {
\tif (position_control == nullptr || look_control == nullptr) {
\t\treturn;
\t}
\tconst int left_size = CLAMP(EDITOR_GET("editors/3d/navigation/native_joystick_left_size").operator int(), 80, 240);
\tconst int right_size = CLAMP(EDITOR_GET("editors/3d/navigation/native_joystick_right_size").operator int(), 80, 240);
\tconst int left_x = CLAMP(EDITOR_GET("editors/3d/navigation/native_joystick_left_inset_x").operator int(), 0, 240);
\tconst int right_x = CLAMP(EDITOR_GET("editors/3d/navigation/native_joystick_right_inset_x").operator int(), 0, 240);
\tconst int left_y = CLAMP(EDITOR_GET("editors/3d/navigation/native_joystick_left_inset_y").operator int(), 0, 300);
\tconst int right_y = CLAMP(EDITOR_GET("editors/3d/navigation/native_joystick_right_inset_y").operator int(), 0, 300);
\tconst real_t scaled_left_size = left_size * EDSCALE;
\tconst real_t scaled_right_size = right_size * EDSCALE;
\tconst real_t scaled_left_x = left_x * EDSCALE;
\tconst real_t scaled_right_x = right_x * EDSCALE;
\tconst real_t scaled_left_y = left_y * EDSCALE;
\tconst real_t scaled_right_y = right_y * EDSCALE;
\tposition_control->set_custom_minimum_size(Size2(left_size, left_size) * EDSCALE);
\tposition_control->set_anchor_and_offset(SIDE_LEFT, ANCHOR_BEGIN, scaled_left_x);
\tposition_control->set_anchor_and_offset(SIDE_TOP, ANCHOR_END, -scaled_left_size - scaled_left_y);
\tposition_control->set_anchor_and_offset(SIDE_RIGHT, ANCHOR_BEGIN, scaled_left_size + scaled_left_x);
\tposition_control->set_anchor_and_offset(SIDE_BOTTOM, ANCHOR_END, -scaled_left_y);
\tlook_control->set_custom_minimum_size(Size2(right_size, right_size) * EDSCALE);
\tlook_control->set_anchor_and_offset(SIDE_LEFT, ANCHOR_END, -scaled_right_size - scaled_right_x);
\tlook_control->set_anchor_and_offset(SIDE_TOP, ANCHOR_END, -scaled_right_size - scaled_right_y);
\tlook_control->set_anchor_and_offset(SIDE_RIGHT, ANCHOR_END, -scaled_right_x);
\tlook_control->set_anchor_and_offset(SIDE_BOTTOM, ANCHOR_END, -scaled_right_y);
}

void Node3DEditorViewport::_update_navigation_controls_visibility() {""")

replace_once(NATIVE_3D_SOURCE,
    '\t\tcase NOTIFICATION_READY: {\n\t\t\tProjectSettings::get_singleton()->connect("settings_changed", callable_mp(this, &Node3DEditorViewport::_project_settings_changed));',
    '\t\tcase NOTIFICATION_READY: {\n\t\t\tProjectSettings::get_singleton()->connect("settings_changed", callable_mp(this, &Node3DEditorViewport::_project_settings_changed));\n'
    '\t\t\t// The terrain add-on writes these values via EditorSettings::set_setting().\n'
    '\t\t\t// Listen to the signal so native joysticks update immediately, not only\n'
    '\t\t\t// after the editor settings dialog sends its deferred notification.\n'
    '\t\t\tEditorSettings::get_singleton()->connect("settings_changed", callable_mp(this, &Node3DEditorViewport::_update_native_navigation_control_layout));')

replace_once(NATIVE_3D_SOURCE,
    '\t\tcase EditorSettings::NOTIFICATION_EDITOR_SETTINGS_CHANGED: {\n\t\t\t_update_view_3d_controller();',
    '\t\tcase EditorSettings::NOTIFICATION_EDITOR_SETTINGS_CHANGED: {\n\t\t\t_update_view_3d_controller();\n\t\t\t_update_native_navigation_control_layout();')
replace_once(NATIVE_3D_SOURCE,
    '\tsurface->add_child(look_control);\n\n\trotation_control = memnew(ViewportRotationControl);',
    '\tsurface->add_child(look_control);\n\t_update_native_navigation_control_layout();\n\n\trotation_control = memnew(ViewportRotationControl);')

print("GitHub import, debug overlays, and Android immersive-preview patches applied successfully.")
