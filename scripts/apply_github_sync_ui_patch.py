#!/usr/bin/env python3
"""Add a compact GitHub analysis entry to the existing Project Manager sidebar.

This patch deliberately adds read-only repository analysis first. It does not
pretend to sync files; Sync remains disabled until the transactional native
writer is implemented and validated.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "godot-source"
HEADER = ROOT / "editor/project_manager/project_manager.h"
SOURCE = ROOT / "editor/project_manager/project_manager.cpp"


def once(path: Path, old: str, new: str) -> None:
    data = path.read_text(encoding="utf-8")
    n = data.count(old)
    if n != 1:
        raise SystemExit(f"{path}: expected one anchor, found {n}: {old[:90]!r}")
    path.write_text(data.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if not HEADER.is_file() or not SOURCE.is_file():
        raise SystemExit("Expected official Godot 4.7.2 source in godot-source/.")

    once(HEADER, "class VBoxContainer;\n", "class VBoxContainer;\nclass HTTPRequest;\n")
    once(HEADER, "\tButton *run_btn = nullptr;\n", "\tButton *run_btn = nullptr;\n\tButton *github_sync_btn = nullptr;\n")
    once(HEADER, "\tvoid _run_project();\n", "\tvoid _run_project();\n\tvoid _open_github_analysis();\n\tvoid _run_github_analysis();\n\tvoid _github_analysis_request_completed(int p_result, int p_code, const PackedStringArray &p_headers, const PackedByteArray &p_body);\n")
    once(HEADER, "\tProjectDialog *project_dialog = nullptr;\n", "\tProjectDialog *project_dialog = nullptr;\n\tString github_local_project_path;\n\tPanelContainer *github_analysis_panel = nullptr;\n\tLineEdit *github_repo_input = nullptr;\n\tLineEdit *github_ref_input = nullptr;\n\tRichTextLabel *github_analysis_output = nullptr;\n\tHTTPRequest *github_analysis_request = nullptr;\n\tButton *github_analyze_button = nullptr;\n")

    once(SOURCE, '#include "scene/gui/flow_container.h"\n', '#include "scene/gui/flow_container.h"\n#include "core/crypto/hashing_context.h"\n#include "core/io/dir_access.h"\n#include "core/io/file_access.h"\n#include "core/io/json.h"\n#include "scene/main/http_request.h"\n#include <functional>\n')
    once(SOURCE, '\t\t\tsidebar_buttons_containter->add_child(run_btn);\n', '\t\t\t\tsidebar_buttons_containter->add_child(run_btn);\n\n\t\t\t\tgithub_sync_btn = memnew(Button);\n\t\t\t\tgithub_sync_btn->set_text(TTRC("GitHub Sync"));\n\t\t\t\tgithub_sync_btn->set_tooltip_text(TTRC("Analyze a public GitHub repository before syncing."));\n\t\t\t\tgithub_sync_btn->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_open_github_analysis));\n\t\t\t\tgithub_sync_btn->set_h_size_flags(Control::SIZE_EXPAND_FILL);\n\t\t\t\tsidebar_buttons_containter->add_child(github_sync_btn);\n')
    once(SOURCE, 'void ProjectManager::_run_project() {\n', '''void ProjectManager::_open_github_analysis() {
	if (!github_analysis_panel) {
		github_analysis_panel = memnew(PanelContainer);
		github_analysis_panel->set_h_size_flags(Control::SIZE_EXPAND_FILL);
		github_analysis_panel->set_custom_minimum_size(Size2(0, 240) * EDSCALE);
		VBoxContainer *layout = memnew(VBoxContainer);
		github_analysis_panel->add_child(layout);
		HBoxContainer *title_row = memnew(HBoxContainer);
		layout->add_child(title_row);
		Label *title = memnew(Label);
		title->set_text(TTR("GitHub Sync — Analyze"));
		title->set_h_size_flags(Control::SIZE_EXPAND_FILL);
		title_row->add_child(title);
		Button *close_button = memnew(Button);
		close_button->set_text(TTR("Close"));
		close_button->connect(SceneStringName(pressed), callable_mp(github_analysis_panel, &Control::hide));
		title_row->add_child(close_button);

		Label *repo_label = memnew(Label);
		repo_label->set_text(TTR("Public repository (owner/name)"));
		layout->add_child(repo_label);
		github_repo_input = memnew(LineEdit);
		github_repo_input->set_placeholder(TTR("owner/repository"));
		github_repo_input->set_clear_button_enabled(true);
		layout->add_child(github_repo_input);
		Label *ref_label = memnew(Label);
		ref_label->set_text(TTR("Branch or tag"));
		layout->add_child(ref_label);
		github_ref_input = memnew(LineEdit);
		github_ref_input->set_text("HEAD");
		github_ref_input->set_clear_button_enabled(true);
		layout->add_child(github_ref_input);
		github_analyze_button = memnew(Button);
		github_analyze_button->set_text(TTR("Analyze repository"));
		github_analyze_button->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_run_github_analysis));
		layout->add_child(github_analyze_button);
		github_analysis_output = memnew(RichTextLabel);
		github_analysis_output->set_fit_content(true);
		github_analysis_output->set_selection_enabled(true);
		github_analysis_output->set_v_size_flags(Control::SIZE_EXPAND_FILL);
		github_analysis_output->set_custom_minimum_size(Size2(0, 120) * EDSCALE);
		layout->add_child(github_analysis_output);
		github_analysis_request = memnew(HTTPRequest);
		github_analysis_request->set_timeout(30.0);
		github_analysis_request->connect("request_completed", callable_mp(this, &ProjectManager::_github_analysis_request_completed));
		add_child(github_analysis_request);
		Button *disabled_sync = memnew(Button);
		disabled_sync->set_text(TTR("Sync (not available yet)"));
		disabled_sync->set_disabled(true);
		layout->add_child(disabled_sync);
		local_projects_vb->add_child(github_analysis_panel);
		local_projects_vb->move_child(github_analysis_panel, 1);
		github_analysis_panel->hide();
	}
	if (github_analysis_panel->is_visible()) {
		github_analysis_panel->hide();
		return;
	}
	github_analysis_output->clear();
	github_analysis_output->append_text(TTR("Read-only analysis. No local project files will be changed. Enter owner/name and a branch or tag, then analyze."));
	github_analysis_panel->show();
}

void ProjectManager::_run_github_analysis() {
	if (!github_analysis_panel || !github_analysis_panel->is_visible()) {
		return;
	}
	String repo = github_repo_input->get_text().strip_edges();
	String ref = github_ref_input->get_text().strip_edges();
	PackedStringArray parts = repo.split("/", false);
	if (parts.size() != 2 || parts[0].is_empty() || parts[1].is_empty() ||
			repo.contains("..") || repo.contains(" ") || repo.contains("?") || repo.contains("#") ||
			ref.is_empty() || ref.contains(" ") || ref.contains("?") || ref.contains("#")) {
		github_analysis_output->clear();
		github_analysis_output->append_text(TTR("Enter a valid public repository as owner/name and a branch or tag without spaces."));
		return;
	}
	Vector<ProjectList::Item> selected_projects = project_list->get_selected_projects();
	if (selected_projects.size() != 1) {
		github_analysis_output->clear();
		github_analysis_output->append_text(TTR("Select exactly one local Godot project in the list, then analyze again."));
		return;
	}
	github_local_project_path = selected_projects[0].path;
	if (!FileAccess::file_exists(github_local_project_path.path_join("project.godot"))) {
		github_analysis_output->clear();
		github_analysis_output->append_text(TTR("The selected folder is not a readable Godot project (project.godot was not found)."));
		return;
	}
	if (github_analysis_request->get_http_client_status() != HTTPClient::STATUS_DISCONNECTED) {
		github_analysis_output->append_text(TTR("\\nA request is already in progress."));
		return;
	}
	String url = "https://api.github.com/repos/" + parts[0].uri_encode() + "/" + parts[1].uri_encode() +
			"/git/trees/" + ref.uri_encode() + "?recursive=1";
	github_analysis_output->clear();
	github_analysis_output->append_text(TTR("Contacting GitHub…\\n"));
	github_analyze_button->set_disabled(true);
	PackedStringArray headers;
	headers.push_back("Accept: application/vnd.github+json");
	Error err = github_analysis_request->request(url, headers, HTTPClient::METHOD_GET);
	if (err != OK) {
		github_analyze_button->set_disabled(false);
		github_analysis_output->append_text(vformat(TTR("Could not start request (error %d)."), err));
	}
}

void ProjectManager::_github_analysis_request_completed(int p_result, int p_code, const PackedStringArray &p_headers, const PackedByteArray &p_body) {
	if (github_analyze_button) {
		github_analyze_button->set_disabled(false);
	}
	if (!github_analysis_output) {
		return;
	}
	if (p_result != HTTPRequest::RESULT_SUCCESS || p_code < 200 || p_code >= 300) {
		github_analysis_output->append_text(vformat(TTR("\\nGitHub request failed (HTTP %d, result %d). Check the repository, branch, connection, or API rate limit."), p_code, p_result));
		return;
	}
	Ref<JSON> json;
	json.instantiate();
	Error parse_error = json->parse(p_body.get_string_from_utf8());
	if (parse_error != OK || json->get_data().get_type() != Variant::DICTIONARY) {
		github_analysis_output->append_text(TTR("\\nGitHub returned an unreadable response."));
		return;
	}
	Dictionary root = json->get_data();
	Array tree = root.get("tree", Array());
	if (!root.has("tree")) {
		github_analysis_output->append_text(TTR("\\nGitHub response has no tree. Choose a valid branch or tag."));
		return;
	}
	if (root.get("truncated", false)) {
		github_analysis_output->append_text(TTR("\\nGitHub truncated this tree response. Refusing to produce an incomplete comparison."));
		return;
	}
	HashMap<String, String> remote_files;
	for (int i = 0; i < tree.size(); i++) {
		Dictionary entry = tree[i];
		if (String(entry.get("type", "")) != "blob") {
			continue;
		}
		String path = entry.get("path", "");
		String sha = entry.get("sha", "");
		if (path.is_empty() || sha.length() != 40 || path.begins_with("/") || path.contains("\\\\") ||
				path == ".." || path.begins_with("../") || path.contains("/../") || path.ends_with("/..")) {
			github_analysis_output->append_text(TTR("\\nRepository tree contains an invalid path or blob ID; comparison stopped."));
			return;
		}
		if (path == ".git" || path.begins_with(".git/") || path == ".godot" || path.begins_with(".godot/") ||
				path == ".github" || path.begins_with(".github/") || path == "github_sync_manifest.json") {
			continue;
		}
		remote_files.insert(path, sha.to_lower());
	}
	HashMap<String, String> local_files;
	int local_scan_errors = 0;
	std::function<void(const String &, const String &)> scan_directory;
	scan_directory = [&](const String &p_absolute, const String &p_relative) {
		Ref<DirAccess> parent = DirAccess::open(p_absolute);
		if (parent.is_null()) {
			local_scan_errors++;
			return;
		}
		PackedStringArray dirs = DirAccess::get_directories_at(p_absolute);
		for (const String &dir : dirs) {
			if (dir == "." || dir == ".." || dir == ".git" || dir == ".godot" || dir == ".github" || parent->is_link(dir)) {
				continue;
			}
			String relative = p_relative.is_empty() ? dir : p_relative.path_join(dir);
			scan_directory(p_absolute.path_join(dir), relative);
		}
		PackedStringArray files = DirAccess::get_files_at(p_absolute);
		for (const String &file : files) {
			if (file == "github_sync_manifest.json" || parent->is_link(file)) {
				continue;
			}
			String relative = p_relative.is_empty() ? file : p_relative.path_join(file);
			String absolute = p_absolute.path_join(file);
			Error open_error = OK;
			Ref<FileAccess> local_file = FileAccess::open(absolute, FileAccess::READ, &open_error);
			if (local_file.is_null()) {
				local_scan_errors++;
				continue;
			}
			uint64_t expected_size = local_file->get_length();
			PackedByteArray bytes = local_file->get_buffer(expected_size);
			if (bytes.size() != (int64_t)expected_size) {
				local_scan_errors++;
				continue;
			}
			String header = "blob " + itos(bytes.size()) + String::chr(0);
			PackedByteArray blob_data = header.to_utf8_buffer();
			blob_data.append_array(bytes);
			Ref<HashingContext> hasher;
			hasher.instantiate();
			if (hasher->start(HashingContext::HASH_SHA1) != OK || hasher->update(blob_data) != OK) {
				local_scan_errors++;
				continue;
			}
			PackedByteArray digest = hasher->finish();
			local_files.insert(relative.replace("\\\\", "/"), String::hex_encode_buffer(digest.ptr(), digest.size()));
		}
	};
	scan_directory(github_local_project_path, "");
	if (local_scan_errors > 0) {
		github_analysis_output->append_text(vformat(TTR("\\nLocal scan incomplete: %d file/directory read failures. No comparison was produced."), local_scan_errors));
		return;
	}
	int adds = 0;
	int updates = 0;
	int unchanged = 0;
	int local_only = 0;
	for (const KeyValue<String, String> &remote : remote_files) {
		if (!local_files.has(remote.key)) {
			adds++;
		} else if (local_files[remote.key] == remote.value) {
			unchanged++;
		} else {
			updates++;
		}
	}
	for (const KeyValue<String, String> &local : local_files) {
		if (!remote_files.has(local.key)) {
			local_only++;
		}
	}
	github_analysis_output->append_text(vformat(TTR("Local project: %s\\n"), github_local_project_path));
	github_analysis_output->append_text(vformat(TTR("Pinned tree entries: %d\\n"), tree.size()));
	github_analysis_output->append_text(vformat(TTR("ADD: %d | UPDATE: %d | UNCHANGED: %d | LOCAL-ONLY (preserved): %d\\n"),
			adds, updates, unchanged, local_only));
	int shown = 0;
	for (const KeyValue<String, String> &remote : remote_files) {
		String action = !local_files.has(remote.key) ? "ADD" :
				(local_files[remote.key] == remote.value ? "OK" : "UPDATE");
		if (shown < 150 && action != "OK") {
			github_analysis_output->append_text(vformat("%s  %s\\n", action, remote.key));
			shown++;
		}
	}
	if (adds + updates > shown) {
		github_analysis_output->append_text(vformat(TTR("Showing %d of %d add/update paths.\\n"), shown, adds + updates));
	}
	github_analysis_output->append_text(TTR("\\nComparison is read-only. Local-only files are preserved; no remote-deletion inference or file writes occur."));

}

void ProjectManager::_run_project() {
''')
    # Verify required integration points before accepting the patch.
    h = HEADER.read_text(encoding="utf-8")
    c = SOURCE.read_text(encoding="utf-8")
    for token in ("github_sync_btn", "_github_analysis_request_completed", "GitHub Sync", "Local project:", "HashingContext::HASH_SHA1"):
        if token not in h + c:
            raise SystemExit(f"Patch verification failed: {token}")
    print("Added sidebar GitHub comparison against exactly one selected local project; writes and deletes remain disabled.")


if __name__ == "__main__":
    main()
