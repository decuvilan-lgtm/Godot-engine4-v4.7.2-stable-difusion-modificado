#!/usr/bin/env python3
"""Enable safe additive GitHub ZIP import in the native Project Manager.

The import is deliberately non-destructive: only absent files are created.
Existing files and directories are never overwritten. If a write fails, newly
created files are removed before returning.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "godot-source"
HEADER = ROOT / "editor/project_manager/project_manager.h"
SOURCE = ROOT / "editor/project_manager/project_manager.cpp"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, got {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if not HEADER.is_file() or not SOURCE.is_file():
        raise SystemExit("Expected Godot source under godot-source/.")

    header = HEADER.read_text(encoding="utf-8")
    if "github_sync_apply_button" in header:
        print("Native additive GitHub import already patched.")
        return

    replace_once(HEADER, "\tButton *github_review_button = nullptr;\n",
        "\tButton *github_review_button = nullptr;\n"
        "\tButton *github_sync_apply_button = nullptr;\n"
        "\tbool github_archive_download_pending = false;\n"
        "\tvoid _apply_github_import();\n"
        "\tvoid _apply_github_archive(const PackedByteArray &p_archive);\n")
    replace_once(SOURCE, '#include "core/io/json.h"\n',
        '#include "core/io/json.h"\n#include "core/io/zip_reader.h"\n')

    old_button = ('\t\tButton *disabled_sync = memnew(Button);\n'
        '\t\tdisabled_sync->set_text(TTR("Sync (not available yet)"));\n'
        '\t\tdisabled_sync->set_disabled(true);\n'
        '\t\tlayout->add_child(disabled_sync);')
    new_button = ('\t\tgithub_sync_apply_button = memnew(Button);\n'
        '\t\tgithub_sync_apply_button->set_text(TTR("Importar archivos faltantes"));\n'
        '\t\tgithub_sync_apply_button->set_tooltip_text(TTR("Importa archivos del repositorio revisado sin sobrescribir archivos locales."));\n'
        '\t\tgithub_sync_apply_button->set_custom_minimum_size(Size2(0, 48) * EDSCALE);\n'
        '\t\tgithub_sync_apply_button->set_disabled(true);\n'
        '\t\tgithub_sync_apply_button->connect(SceneStringName(pressed), callable_mp(this, &ProjectManager::_apply_github_import));\n'
        '\t\tlayout->add_child(github_sync_apply_button);')
    replace_once(SOURCE, old_button, new_button)

    callback_anchor = ('\tif (!github_analysis_output) {\n\t\treturn;\n\t}\n'
        '\tif (p_result != HTTPRequest::RESULT_SUCCESS')
    callback_new = ('\tif (!github_analysis_output) {\n\t\treturn;\n\t}\n'
        '\tif (github_archive_download_pending) {\n'
        '\t\tgithub_archive_download_pending = false;\n'
        '\t\tif (p_result != HTTPRequest::RESULT_SUCCESS || p_code < 200 || p_code >= 300 || p_body.is_empty()) {\n'
        '\t\t\tgithub_analysis_output->append_text(vformat(TTR("\\\\nGitHub archive download failed (HTTP %d, result %d). No files changed."), p_code, p_result));\n'
        '\t\t\treturn;\n\t\t}\n'
        '\t\t_apply_github_archive(p_body);\n\t\treturn;\n\t}\n'
        '\tif (p_result != HTTPRequest::RESULT_SUCCESS')
    replace_once(SOURCE, callback_anchor, callback_new)

    methods = r'''
void ProjectManager::_apply_github_import() {
	if (!github_review_valid || github_analysis_fingerprint.is_empty() || github_review_repo.is_empty() || github_review_ref.is_empty()) {
		github_analysis_output->append_text(TTR("\nAnalyze and review the repository before importing."));
		return;
	}
	Vector<ProjectList::Item> selected = project_list->get_selected_projects();
	if (selected.size() != 1 || selected[0].path != github_local_project_path) {
		github_review_valid = false;
		github_sync_apply_button->set_disabled(true);
		github_analysis_output->append_text(TTR("\nImport cancelled: selected project changed."));
		return;
	}
	PackedStringArray parts = github_review_repo.split("/", false);
	if (parts.size() != 2) {
		return;
	}
	String url = "https://api.github.com/repos/" + parts[0].uri_encode() + "/" + parts[1].uri_encode() +
			"/zipball/" + github_analysis_commit_sha.uri_encode();
	PackedStringArray headers;
	headers.push_back("Accept: application/vnd.github+json");
	github_archive_download_pending = true;
	github_sync_apply_button->set_disabled(true);
	github_analysis_output->append_text(TTR("\nDownloading reviewed GitHub snapshot..."));
	Error err = github_analysis_request->request(url, headers, HTTPClient::METHOD_GET);
	if (err != OK) {
		github_archive_download_pending = false;
		github_analysis_output->append_text(vformat(TTR("\nCould not start archive download (error %d)."), err));
	}
}

void ProjectManager::_apply_github_archive(const PackedByteArray &p_archive) {
	String temp_zip = OS::get_singleton()->get_cache_path().path_join("godot_github_import.zip");
	Ref<FileAccess> zip_file = FileAccess::open(temp_zip, FileAccess::WRITE);
	if (zip_file.is_null()) {
		github_analysis_output->append_text(TTR("\nCannot create temporary archive; project unchanged."));
		return;
	}
	zip_file->store_buffer(p_archive);
	zip_file.unref();
	Ref<ZIPReader> reader;
	reader.instantiate();
	if (reader->open(temp_zip) != OK) {
		DirAccess::remove_absolute(temp_zip);
		github_analysis_output->append_text(TTR("\nDownloaded archive is invalid; project unchanged."));
		return;
	}
	PackedStringArray entries = reader->get_files();
	String root_prefix;
	for (const String &entry : entries) {
		PackedStringArray segments = entry.split("/", false);
		if (segments.size() >= 2 && segments[0].length() > 20) {
			root_prefix = segments[0] + "/";
			break;
		}
	}
	if (root_prefix.is_empty()) {
		reader->close();
		DirAccess::remove_absolute(temp_zip);
		github_analysis_output->append_text(TTR("\nArchive structure is unexpected; project unchanged."));
		return;
	}
	PackedStringArray created;
	int added = 0;
	int preserved = 0;
	bool failed = false;
	for (const String &entry : entries) {
		if (!entry.begins_with(root_prefix) || entry.ends_with("/")) {
			continue;
		}
		String relative = entry.trim_prefix(root_prefix).replace("\\", "/");
		if (relative.is_empty() || relative.begins_with("/") || relative.contains(":") ||
				relative == ".." || relative.begins_with("../") || relative.contains("/../") ||
				relative == ".git" || relative.begins_with(".git/") ||
				relative == ".godot" || relative.begins_with(".godot/") ||
				relative == ".github" || relative.begins_with(".github/")) {
			continue;
		}
		String target = github_local_project_path.path_join(relative);
		if (FileAccess::file_exists(target) || DirAccess::dir_exists_absolute(target)) {
			preserved++;
			continue;
		}
		if (DirAccess::make_dir_recursive_absolute(target.get_base_dir()) != OK) {
			failed = true;
			break;
		}
		PackedByteArray bytes = reader->read_file(entry);
		Ref<FileAccess> output = FileAccess::open(target, FileAccess::WRITE);
		if (output.is_null()) {
			failed = true;
			break;
		}
		output->store_buffer(bytes);
		output.unref();
		Ref<FileAccess> verify = FileAccess::open(target, FileAccess::READ);
		if (verify.is_null() || verify->get_length() != bytes.size()) {
			verify.unref();
			DirAccess::remove_absolute(target);
			failed = true;
			break;
		}
		verify.unref();
		created.push_back(target);
		added++;
	}
	reader->close();
	DirAccess::remove_absolute(temp_zip);
	if (failed) {
		for (const String &path : created) {
			DirAccess::remove_absolute(path);
		}
		github_analysis_output->append_text(vformat(TTR("\nImport rolled back after a write failure. Removed %d new files; pre-existing files were untouched."), created.size()));
		return;
	}
	github_analysis_output->append_text(vformat(TTR("\nImport complete: %d new files; %d pre-existing files preserved. Existing files were never overwritten."), added, preserved));
	github_review_valid = false;
	github_analysis_fingerprint = "";
	if (github_sync_apply_button) {
		github_sync_apply_button->set_disabled(true);
	}
}

'''
    replace_once(SOURCE, "void ProjectManager::_run_project() {\n", methods + "void ProjectManager::_run_project() {\n")

    # Only enable import after the explicit review pass has revalidated the fingerprint.
    old_review = ('\t\tif (current_fingerprint == github_review_expected_fingerprint) {\n'
        '\t\t\tgithub_review_valid = true;\n')
    new_review = ('\t\tif (current_fingerprint == github_review_expected_fingerprint) {\n'
        '\t\t\tgithub_review_valid = true;\n'
        '\t\t\tif (github_sync_apply_button) { github_sync_apply_button->set_disabled(false); }\n')
    replace_once(SOURCE, old_review, new_review)
    replace_once(SOURCE, "\\t\\tgithub_review_valid = true;\\n", "\\t\\tgithub_review_valid = true;\\n\\t\\tif (github_sync_apply_button) { github_sync_apply_button->set_disabled(false); }\\n")
    print("Enabled native additive GitHub ZIP import after pinned commit review; existing files are preserved and newly created files are rolled back on write failure.")


if __name__ == "__main__":
    main()
