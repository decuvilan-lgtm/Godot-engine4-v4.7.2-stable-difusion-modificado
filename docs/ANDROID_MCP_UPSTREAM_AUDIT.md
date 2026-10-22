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

- `write_file` and `edit_file` can overwrite an existing project file directly. They currently do not create a recovery copy or route the operation through Godot's undo manager.
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

## Next engineering steps

1. Keep the reviewed upstream revision pinned; update the SHA only after reviewing the new diff.
2. Run the packaging workflow and inspect its actual logs/artifact.
3. Audit every registered tool and its input validation.
4. Add typed tool families in small tested groups, prioritizing read-only inspection first.
5. Finish safe file-write recovery and review all remaining mutations.
6. Add a menu/action inventory and report unsupported or dynamically registered controls rather than silently omitting them.
7. Test in the actual Godot Android editor and then test a real MCP client connection.
