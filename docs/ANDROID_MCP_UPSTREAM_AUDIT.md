# Android MCP upstream capability audit

Date: 2026-10-22

Reviewed upstream revision pinned in CI: `5df91076250ece38ab182b2ca8b8a4a5d9a2d938`.

## Scope

This is a source-level initial audit of the public upstream addon `GeorgeMee/godot-mcp-android`, which the current packaging workflow checks out from its `main` branch. It is not a device test and does not imply a live MCP client is connected.

## Upstream tool surface observed

The upstream README lists these tools:

- `ping`
- `get_project_info`
- `get_scene_tree`
- `add_node`
- `set_node_property`
- `save_scene`
- `list_files`
- `read_file`
- `write_file`
- `scan_filesystem`
- `get_resource_uid`
- `validate_resource`
- `get_editor_log`

The upstream source also contains scene removal functionality and a generic expression-evaluation tool. The hardened packaging process removes the generic expression-evaluation tool and its registry entries before packaging. Scene/node removal must still be reviewed for path/ownership validation and undo behavior.

## Gap assessment against the full editor goal

The listed tools are a useful initial bridge, but they do not establish full editor coverage. At minimum, the following families need explicit source inspection and tool-level tests:

1. Project Manager actions and safe project lifecycle operations.
2. Main menus, submenus, context menus, shortcuts, toolbar actions and dynamic plugin menus.
3. Scene lifecycle and complete scene-tree operations: open/close/reload, node duplication/reparenting, groups, ownership, signals, instancing and undo/redo.
4. Inspector property types and resource editing, including arrays, dictionaries, nested resources and custom inspectors.
5. Filesystem operations, imports/reimports, dependencies, safe rename/move and conflict-aware file handling.
6. Script editor operations, diagnostics, navigation, breakpoints, search and replace.
7. 2D and 3D viewport controls, selection, transforms, snapping, gizmos and contextual tools.
8. Animation, TileMap/TileSet, visual shaders, particles, navigation, physics, audio and other specialized editors.
9. Project Settings, Editor Settings, input map, localization, autoloads and export presets.
10. Bottom panels, debugger, profiler, remote inspector, output logs, play/stop and runtime testing.
11. Plugin management and controls added by third-party plugins.
12. Dialogs, popups, file pickers, confirmation flows and Android-specific UI limitations.

This list is not exhaustive; the full inventory in `MCP_EDITOR_COVERAGE.md` is the scope of record.

## Concrete safety gaps found during source inspection

- `write_file` and `edit_file` still perform direct filesystem writes rather than routing file contents through Godot's undo manager. However, the current `package_safe_mcp_android.py` patch injects a project-local `.godot_mcp_backups` recovery copy before overwriting an existing file and verifies the copy before writing. This is source-level protection only: runtime failure handling, backup retention/cleanup, and restoration still require Android validation.
- The upstream `set_node_property` and `remove_node` implementations originally lacked property-existence validation and editor undo/redo integration. The packaging script now patches both: it checks that the property exists, records property changes through the editor undo manager, and removes nodes reversibly without calling `queue_free()`. These changes are source-patched but still require a successful package build and runtime undo/redo test in Godot Android.
- The common project-path helper rejects normalized paths that escape with `..`, but path validation still deserves tests for empty/directory paths, unusual separators, and platform-specific edge cases.
- The HTTP server has wildcard CORS in upstream source; the packaging script removes that header. Both transport implementations also read host settings, so the package must continue to force loopback after settings are applied.
- The registry contains more tools than the README's short public list: it also registers `get_node_property`, `remove_node`, `edit_file`, and `grep`. Audit the actual registry, not only the README.

These are source-review findings, not proof that a particular exploit has been reproduced. Until each mutation has safe behavior and tests, the addon should not be described as fully safe for autonomous editing.

## Security and packaging checks

The packaging job should continue to assert all of the following:

- No generic `execute_script` tool is registered or packaged.
- No `delete_project` tool exists.
- HTTP and WebSocket listeners bind to `127.0.0.1`, regardless of project settings.
- The HTTP server does not advertise wildcard CORS.
- The resulting ZIP contains a valid addon root and `plugin.cfg`.
- Every destructive operation is inspected individually; absence of a project-delete tool alone does not prove that file or scene operations are safe.

## Validation matrix

| Check | Automated coverage | What it proves | What it does not prove |
|---|---|---|---|
| Python syntax | `py_compile` in Actions | Packaging and import-patch scripts parse | Patch anchors match the upstream tree |
| Pinned upstream source | Actions checkout by immutable SHA | The same upstream source is used on each run | The upstream revision is bug-free |
| Patch anchors | Packaging script requires each source snippet exactly once | Unexpected upstream drift fails loudly | GDScript compiles in Godot |
| Archive integrity | Actions opens ZIP and checks required plugin files | A non-empty addon archive was produced | Plugin can be enabled on Android |
| Safety assertions | Actions inspects registry and packaged scripts | Generic evaluator and project-delete tool are absent; loopback/CORS and undo patches are present | Other editor features are fully safe |
| Editor runtime | Not yet automated | Must load addon and exercise tool calls in target Godot build | Requires Godot runtime/device |
| Undo/redo | Not yet automated | Must mutate and restore a test node/property in the actual editor | Static string checks alone are insufficient |
| MCP end-to-end | Not yet automated | Must connect a real MCP client, list tools, call read-only and mutation tools, and verify errors | Packaging alone does not prove connectivity |
| Android install | Not yet automated | Must install/enable on the user's target phone | CI Linux cannot reproduce device installer constraints |

## Next engineering steps

1. Keep the reviewed upstream revision pinned; update the SHA only after reviewing the new diff.
2. Run the packaging workflow and inspect its actual logs/artifact.
3. Audit every registered tool and its input validation.
4. Add typed tool families in small tested groups, prioritizing read-only inspection first.
5. Finish safe file-write recovery and review all remaining mutations.
6. Add a menu/action inventory and report unsupported or dynamically registered controls rather than silently omitting them.
7. Test in the actual Godot Android editor and then test a real MCP client connection.


## Current build checkpoint — ARM32 + ARM64

- The Android editor workflow was changed to follow Godot's documented multi-architecture sequence: build `arm32` first, then `arm64` with `generate_android_binaries=yes` on the final build.
- Full Android build run [39813174735](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39813174735) is currently compiling both ABIs. It is not yet an APK success claim.
- MCP addon validation run [39813174855](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39813174855) passed, including the upstream patch anchors, packaging checks, and headless addon load.
- After the APK job completes, inspect the actual archive for both `lib/armeabi-v7a/libgodot_android.so` and `lib/arm64-v8a/libgodot_android.so`, verify the package metadata/signature, and only then publish the dual-ABI artifact as the current test candidate. Physical-device installation remains a separate test.

## Next MCP hardening task

The pinned upstream `write_file` and `edit_file` tools still overwrite project files directly. Before expanding mutation coverage, add collision-safe recovery copies for existing files, reject directory targets and empty/invalid paths, and test both successful writes and failure paths. Keep recovery data outside the project tree and never upload it. This work remains unimplemented until code and automated tests land.


## Updated dual-ABI build result — 2026-10-22

The previously pending full Android build has now completed successfully: [run 39813174735](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39813174735).

- The downloadable artifact `godot-4.7.2-android-editor-arm32-arm64` (ID `12444807436`) contains the full APK and badging metadata.
- APK SHA-256: `8ab4089907fc6aaed3eb62e6794bf4287e3cc3f4ce9f50389db3fd4f8573b06f`; artifact ZIP SHA-256: `09a298d4a86582ba4fee733ee2a3785ee5f944cfbf0ea55e3bdeec8b383a2e51`.
- Verified ABI metadata and native-library entries include both `armeabi-v7a` and `arm64-v8a`; ZIP integrity, APK v2 signature verification, and ZIP alignment passed.
- Package ID: `org.godotengine.editor.v4.debug.prilcustom`.
- The APK contains the MCP addon files and ZIP bundle, and CI checks enforce loopback listeners, no wildcard CORS, and no generic expression-execution or project-deletion tool registration.
- These results establish a source-built, signed dual-ABI artifact—not successful installation or live MCP operation on a physical Android device. File write/edit recovery and runtime undo/redo remain open hardening tasks.


## Source changes after the initial audit — 2026-10-22, validation pending

The packaging script now creates and registers five more typed tools: `get_editor_state`, `open_scene`, `control_running_scene`, `get_node_properties`, and `create_resource`. They are designed to add editor-state inspection, scene opening/playback control, property reflection, and non-overwriting resource creation. The validation workflow now asserts that their scripts are present in the packaged ZIP and that each is registered.

These changes have **not been tested by running the packaging workflow or the Godot headless parser**. The tools must not be counted as runtime-verified until those checks pass. Even if they pass, the MCP still exposes only a small subset of Godot's editor surfaces; the full coverage inventory remains the source of truth.


## Expanded registered tool inventory — source state only

After packaging, the intended registry contains 22 typed tools (this count is source-derived, not runtime-confirmed):

- Connection/project: `ping`, `get_project_info`, `get_editor_state`
- Scene/node: `get_scene_tree`, `add_node`, `set_node_property`, `get_node_property`, `get_node_properties`, `remove_node`, `save_scene`, `open_scene`, `control_running_scene`
- Resources/diagnostics: `get_resource_uid`, `validate_resource`, `create_resource`, `get_editor_log`
- Filesystem: `list_files`, `read_file`, `write_file`, `edit_file`, `grep`, `scan_filesystem`

The upstream `execute_script` expression tool is intentionally removed. The registered tools cover useful slices of project inspection, file editing, scene/node editing, resource creation and scene playback, but do not expose every Godot Editor API or every visual editor operation. All newly generated tools remain pending parser, package and live MCP round-trip validation.
