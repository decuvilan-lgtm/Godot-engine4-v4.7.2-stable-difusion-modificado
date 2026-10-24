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
\tgithub_import_dialog->popup_centered(Size2i(520 * EDSCALE, 0));
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
	github_results_dialog->popup_centered(Size2i(560 * EDSCALE, 0));
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


# Add built-in run/debug visibility toggles to the editor's run bar. These write
# the same per-project metadata consumed by EditorRun when launching the preview.
RUN_BAR_HEADER = ROOT / "editor/run/editor_run_bar.h"
RUN_BAR_SOURCE = ROOT / "editor/run/editor_run_bar.cpp"
if not RUN_BAR_HEADER.is_file() or not RUN_BAR_SOURCE.is_file():
    sys.exit("Godot run-bar source not found; cannot add preview debug controls.")

replace_once(RUN_BAR_SOURCE,
    '#include "scene/gui/panel_container.h"\n#include "scene/main/scene_tree.h"',
    '#include "scene/gui/panel_container.h"\n#include "scene/gui/popup_menu.h"\n#include "scene/main/scene_tree.h"')
replace_once(RUN_BAR_HEADER,
    "MenuButton *write_movie_button = nullptr;",
    "MenuButton *write_movie_button = nullptr;\n\tMenuButton *preview_debug_button = nullptr;")
replace_once(RUN_BAR_HEADER,
    "\tvoid _movie_maker_item_pressed(int p_id);",
    """\tenum PreviewDebugMenuItem {
\t\tPREVIEW_DEBUG_COLLISIONS = 0,
\t\tPREVIEW_DEBUG_PATHS,
\t\tPREVIEW_DEBUG_NAVIGATION,
\t\tPREVIEW_DEBUG_AVOIDANCE,
\t\tPREVIEW_DEBUG_CANVAS_REDRAW,
\t};

\tvoid _preview_debug_item_pressed(int p_id);
\tvoid _movie_maker_item_pressed(int p_id);""")
replace_once(RUN_BAR_SOURCE,
    "void EditorRunBar::_movie_maker_item_pressed(int p_id) {",
    """void EditorRunBar::_preview_debug_item_pressed(int p_id) {
\tif (preview_debug_button == nullptr) {
\t\treturn;
\t}

\tPopupMenu *popup = preview_debug_button->get_popup();
\tint item_index = popup->get_item_index(p_id);
\tif (item_index < 0) {
\t\treturn;
\t}

\tbool enabled = !popup->is_item_checked(item_index);
\tpopup->set_item_checked(item_index, enabled);

\tconst char *metadata_key = nullptr;
\tswitch (p_id) {
\t\tcase PREVIEW_DEBUG_COLLISIONS:
\t\t\tmetadata_key = "run_debug_collisions";
\t\t\tbreak;
\t\tcase PREVIEW_DEBUG_PATHS:
\t\t\tmetadata_key = "run_debug_paths";
\t\t\tbreak;
\t\tcase PREVIEW_DEBUG_NAVIGATION:
\t\t\tmetadata_key = "run_debug_navigation";
\t\t\tbreak;
\t\tcase PREVIEW_DEBUG_AVOIDANCE:
\t\t\tmetadata_key = "run_debug_avoidance";
\t\t\tbreak;
\t\tcase PREVIEW_DEBUG_CANVAS_REDRAW:
\t\t\tmetadata_key = "run_debug_canvas_redraw";
\t\t\tbreak;
\t\tdefault:
\t\t\treturn;
\t}

\tEditorSettings::get_singleton()->set_project_metadata("debug_options", metadata_key, enabled);

\t// Collision overlays support live updates through Godot's remote debugger protocol.
\t// Apply immediately to every active editor-debugged game, without restarting it.
\tif (p_id == PREVIEW_DEBUG_COLLISIONS) {
\t\tEditorDebuggerNode::get_singleton()->set_debug_collisions(enabled);
\t}
}

void EditorRunBar::_movie_maker_item_pressed(int p_id) {""")
replace_once(RUN_BAR_SOURCE,
    "\tplay_button = memnew(Button);",
    """\t// Quick access to Godot's built-in runtime debug overlays. All options
\t// default to off unless the project already has an explicit preference.
\tpreview_debug_button = memnew(MenuButton);
\tmain_hbox->add_child(preview_debug_button);
\tpreview_debug_button->set_theme_type_variation("RunBarButton");
\tpreview_debug_button->set_text(TTR("Debug"));
\tpreview_debug_button->set_tooltip_text(TTR("Show built-in debug overlays in the running game preview."));
\tPopupMenu *preview_debug_popup = preview_debug_button->get_popup();
\tpreview_debug_popup->add_check_item(TTRC("Visible Collision Shapes"), PREVIEW_DEBUG_COLLISIONS);
\tpreview_debug_popup->set_item_tooltip(preview_debug_popup->get_item_index(PREVIEW_DEBUG_COLLISIONS), TTRC("Show 2D/3D collision shapes and raycast nodes in the running game."));
\tpreview_debug_popup->add_check_item(TTRC("Visible Paths"), PREVIEW_DEBUG_PATHS);
\tpreview_debug_popup->set_item_tooltip(preview_debug_popup->get_item_index(PREVIEW_DEBUG_PATHS), TTRC("Show curves used by path nodes."));
\tpreview_debug_popup->add_check_item(TTRC("Visible Navigation"), PREVIEW_DEBUG_NAVIGATION);
\tpreview_debug_popup->set_item_tooltip(preview_debug_popup->get_item_index(PREVIEW_DEBUG_NAVIGATION), TTRC("Show navigation meshes and polygons."));
\tpreview_debug_popup->add_check_item(TTRC("Visible Avoidance"), PREVIEW_DEBUG_AVOIDANCE);
\tpreview_debug_popup->set_item_tooltip(preview_debug_popup->get_item_index(PREVIEW_DEBUG_AVOIDANCE), TTRC("Show avoidance shapes, radiuses, and velocities."));
\tpreview_debug_popup->add_separator();
\tpreview_debug_popup->add_check_item(TTRC("Debug CanvasItem Redraws"), PREVIEW_DEBUG_CANVAS_REDRAW);
\tpreview_debug_popup->set_item_tooltip(preview_debug_popup->get_item_index(PREVIEW_DEBUG_CANVAS_REDRAW), TTRC("Flash 2D items when they request redraws."));
\tconst String debug_keys[] = {"run_debug_collisions", "run_debug_paths", "run_debug_navigation", "run_debug_avoidance", "run_debug_canvas_redraw"};
\tfor (int i = 0; i < 5; i++) {
\t\tpreview_debug_popup->set_item_checked(preview_debug_popup->get_item_index(i), EditorSettings::get_singleton()->get_project_metadata("debug_options", debug_keys[i], false));
\t}
\tpreview_debug_popup->connect(SceneStringName(id_pressed), callable_mp(this, &EditorRunBar::_preview_debug_item_pressed));

\tplay_button = memnew(Button);""")


# Extend the existing remote-debugger channel so navigation and avoidance overlays
# can be switched in a running editor-debugged game. Path curves remain launch-time
# only: SceneTree documents its path hint as not intended for runtime changes.
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
    "void set_debug_collisions(bool p_enabled);",
    "void set_debug_collisions(bool p_enabled);\n\tvoid set_debug_navigation(bool p_enabled);\n\tvoid set_debug_avoidance(bool p_enabled);")
replace_once(EDITOR_DEBUGGER_SOURCE,
    "void EditorDebuggerNode::set_debug_collisions(bool p_enabled) {",
    """void EditorDebuggerNode::set_debug_navigation(bool p_enabled) {
\t_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
\t\tdbg->set_debug_navigation(p_enabled);
\t});
}

void EditorDebuggerNode::set_debug_avoidance(bool p_enabled) {
\t_for_all(tabs, [&](ScriptEditorDebugger *dbg) {
\t\tdbg->set_debug_avoidance(p_enabled);
\t});
}

void EditorDebuggerNode::set_debug_collisions(bool p_enabled) {""")

replace_once(SCRIPT_DEBUGGER_HEADER,
    "void set_debug_collisions(bool p_enable);",
    "void set_debug_collisions(bool p_enable);\n\tvoid set_debug_navigation(bool p_enable);\n\tvoid set_debug_avoidance(bool p_enable);")
replace_once(SCRIPT_DEBUGGER_SOURCE,
    "void ScriptEditorDebugger::set_debug_collisions(bool p_enable) {",
    """void ScriptEditorDebugger::set_debug_navigation(bool p_enable) {
\tArray msg = { p_enable };
\t_put_msg("scene:set_debug_navigation", msg);
}

void ScriptEditorDebugger::set_debug_avoidance(bool p_enable) {
\tArray msg = { p_enable };
\t_put_msg("scene:set_debug_avoidance", msg);
}

void ScriptEditorDebugger::set_debug_collisions(bool p_enable) {""")

replace_once(SCENE_DEBUGGER_HEADER,
    "static Error _msg_debug_mute_audio(const Array &p_args);",
    "static Error _msg_debug_mute_audio(const Array &p_args);\n\tstatic Error _msg_set_debug_navigation(const Array &p_args);\n\tstatic Error _msg_set_debug_avoidance(const Array &p_args);")
replace_once(SCENE_DEBUGGER_SOURCE,
    '#include "servers/rendering/rendering_server.h"',
    '#include "servers/rendering/rendering_server.h"\n#include "servers/navigation_2d/navigation_server_2d.h"\n#include "servers/navigation_3d/navigation_server_3d.h"')
replace_once(SCENE_DEBUGGER_SOURCE,
    "Error SceneDebugger::_msg_debug_mute_audio(const Array &p_args) {",
    """Error SceneDebugger::_msg_set_debug_navigation(const Array &p_args) {
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

Error SceneDebugger::_msg_debug_mute_audio(const Array &p_args) {""")
replace_once(SCENE_DEBUGGER_SOURCE,
    'message_handlers["debug_mute_audio"] = _msg_debug_mute_audio;',
    'message_handlers["debug_mute_audio"] = _msg_debug_mute_audio;\n\tmessage_handlers["set_debug_navigation"] = _msg_set_debug_navigation;\n\tmessage_handlers["set_debug_avoidance"] = _msg_set_debug_avoidance;')

print("GitHub import and Android Gallery protection patches applied successfully.")
