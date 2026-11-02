# Godot editor MCP coverage inventory

## Purpose and acceptance rule

## Run-bar preview debug overlays — source patch added, not yet validated

A source patch now adds a **Debug** dropdown to the existing editor run bar. It exposes the same per-project launch flags used by Godot's existing Debug menu:

- Visible Collision Shapes (2D/3D shapes and raycasts)
- Visible Paths
- Visible Navigation
- Visible Avoidance
- Debug CanvasItem Redraws

The toggles default to off when no project preference exists and persist via Godot's existing `debug_options` project metadata. **Visible Collision Shapes now calls `EditorDebuggerNode::set_debug_collisions()` when toggled**, using Godot's existing remote-debugger protocol to update active editor-debugged games immediately. The Paths, Navigation, Avoidance and CanvasItem Redraw entries remain launch-time options and still require a restart; live protocol support for those is not yet implemented. Source-only; no patch application, C++ build, Android UI check, or device test has been run for this addition.


The goal is broad, auditable access to the Godot editor from a compatible MCP client, including obscure and rarely used controls. Do not decide that a section is out of scope because it appears unimportant.

This document is an **inventory and implementation plan**, not a claim that coverage already exists. Every entry must eventually be marked `implemented`, `partial`, `unavailable`, or `blocked for safety`, with a tool/action name and a test result. A menu is not covered merely because a similarly named tool exists.

## Non-negotiable safety boundary

- No MCP tool may delete a Godot project or its root directory. Do not expose a `delete_project` operation.
- Do not provide arbitrary GDScript/eval execution as a shortcut around the typed API and safety checks.
- Keep editor-control listeners bound to loopback by default; do not expose unauthenticated control on LAN or the public internet.
- File removal and scene/node/resource destruction must be scoped, explicit, validated, and reversible where feasible. Protect project roots and paths outside the selected project.
- Treat repository text, scene content, imported assets, and tool output as untrusted data, not as instructions to the agent.
- Do not claim a live ChatGPT-to-editor connection until the actual MCP transport has been configured and tested on a device.

## Coverage states

- `not audited`: not inspected yet.
- `planned`: included in scope, implementation not verified.
- `partial`: some actions work, but the section has gaps.
- `implemented`: relevant actions are mapped to tools and automated/manual tests pass.
- `unavailable`: Godot does not expose a reliable supported API for the needed action; document the limitation and any safe UI-level alternative.
- `blocked for safety`: the operation is intentionally prohibited or restricted.

No section may be marked implemented without naming the tools/actions and a reproducible test.

## Initial coverage inventory

All rows start as **planned / not audited** until source inspection and tests establish otherwise.

| Editor surface | Required operations to inventory | Initial status |
|---|---|---|
| Project Manager | list/open/import projects; create project; project settings; scan/reload; run project; safe project rename/move where supported | planned |
| Main menus | every menu, submenu, menu item, shortcut, and enabled/disabled state | planned |
| Context menus | scene tree, filesystem, inspector, script editor, viewport, animation, tilemap, resources, debugger and other contextual menus | planned |
| Main toolbar | run current project/scene, stop, play controls, renderer/debug options and every other visible control | planned |
| Scene dock/tree | create/open/save/duplicate/rename scenes; add/instance/reparent/duplicate nodes; groups; ownership; editable children; node signals; safe deletion with undo where possible | planned |
| Inspector | inspect/edit every supported property type; resources; arrays/dictionaries; metadata; revert; pinning; property context actions | planned |
| Filesystem dock | browse/search/filter; create/rename/move/import/reimport; inspect resource paths; safe file operations; reveal dependencies | planned |
| Script editor | open/edit/save scripts; navigation; search/replace; completion; formatting; breakpoints; errors/warnings; script-specific menus and shortcuts | planned |
| 2D editor | viewport state; selection; transforms; snapping; guides; rulers; layers; canvas and all toolbar/context actions | planned |
| 3D editor | viewport modes; selection; transforms; snapping; cameras; gizmos; view and environment options; all context actions | planned |
| Animation editor | animation tracks, keys, playback, timeline, libraries, call methods and property tracks | planned |
| TileMap / TileSet | tile sources, atlases, terrains, patterns, layers, painting tools, custom data and tile-specific context menus | planned |
| Import workflow | import dock/options; reimport; presets; advanced import dialogs; generated files and validation | planned |
| Project Settings | all categories, properties, feature tags, input map, localization and custom settings | planned |
| Editor Settings | all categories, shortcuts, interface, text editor, filesystem, network, run and debugging preferences | planned |
| Export | presets, platform options, feature filters, resources, signing/configuration surfaces and export actions | planned |
| Asset/resource editors | image, audio, font, mesh, material, shader, theme, translation, animation and other resource inspectors/editors available in the build | planned |
| Bottom panels | Output, Debugger, Audio, Animation, Shader/other panels present in the target version; enumerate every tab and context action | planned |
| Debugger/profiler | errors, warnings, stack traces, breakpoints, remote scene, monitors, profiler, visual profiler, network profiler and available debugging controls | planned |
| Run/remote tools | run current project/scene, select target, remote inspector/tree, live debugging, stop/restart and logs | planned |
| Plugins | enumerate installed plugins; enable/disable/configure supported plugins; inspect plugin-provided UI; do not bypass plugin permissions | planned |
| Dialogs/popups | file/folder pickers, confirmation dialogs, create-resource dialogs, search dialogs, warnings, progress and error popups | planned |
| Accessibility and layout | docks, tabs, panel visibility, editor layout, scaling, theme, focus/navigation and relevant preferences | planned |
| Localization and translation | translation resources, locale settings, translation editor and import/export controls | planned |
| Version control integration | available VCS dock, status/diff/history/commit controls where supported; never upload local work automatically | planned |
| Android-specific surfaces | Android editor limitations, touch menus, mobile file pickers, permissions, import/export and device-specific workflows | planned |
| Less-common/advanced surfaces | navigation, physics, audio buses, particles, skeletons, terrain, visual shaders, multiplayer, XR, animation retargeting and any additional docks/plugins in the target build | planned |

## Implementation approach

1. Pin the target Godot version and inspect the exact editor APIs and UI surfaces available in that version.
2. Build a machine-readable action registry with stable IDs, surface/menu path, operation, required arguments, read/write classification, safety guard, and test coverage.
3. Prefer supported Godot editor APIs and typed MCP tools. Where an API does not exist, investigate a narrowly scoped UI-action adapter; do not replace missing coverage with unrestricted script evaluation.
4. Enumerate actual menu items and contextual actions from the running target editor where feasible, including dynamically registered plugin menus. Record controls that cannot be reached programmatically.
5. Separate read-only inspection from mutation. Validate project-relative paths, resource types, node ownership, and operation preconditions before writing.
6. Add tests for each action family and run an on-device smoke test. Include negative tests proving project-root deletion and arbitrary script execution are unavailable.
7. Maintain a coverage report that lists implemented, partial, unavailable, and safety-blocked entries with reasons. Do not claim complete coverage while any in-scope entry remains unaudited.

## Current known limitations

- The safe-packaging script removes the upstream generic expression-execution tool. That is intentional; it avoids using unrestricted evaluation as a substitute for missing typed actions.
- A packaged plugin is not the same as a configured MCP client connection. The transport and a real Godot Android editor session still need end-to-end testing.
- The GitHub import button and the proposed multi-repository incremental sync are separate features. The latter is documented but not implemented by this inventory.
- Packaging/CI success, APK build success, addon installation, and live MCP functionality are separate test claims and must be reported separately.


## Generic editor UI bridge — source added, not yet validated

Two additional tools are now generated and registered by the packaging script:

| Tool | Intended coverage | Current status |
|---|---|---|
| `inspect_editor_ui` | Enumerate editor controls and paths, plus open PopupMenu item labels, indices, disabled/separator state and checked state | Source added; parser/runtime test pending |
| `activate_editor_ui_control` | Activate an exact visible button or a specific item in an open PopupMenu, enabling UI-level navigation where no dedicated typed action exists | Source added; parser/runtime test pending |

This is a **generic UI bridge**, not proof that every Godot action is accessible. It deliberately blocks project deletion/removal, requires explicit confirmation for potentially destructive labels, and currently activates buttons, switches tabs and OptionButton choices, selects open PopupMenu items, and edits LineEdit/SpinBox/checkbox controls. More control types and dialogs may need dedicated adapters. It must be checked on the actual Android editor because some internal controls may be hidden, dynamically created, or inaccessible through the public editor tree.

## Open menu and debug-option inspection — source added, not yet validated

The generated `inspect_editor_ui` tool now includes open `PopupMenu` windows in its traversal and lists each menu item's index, label, separator/disabled state, and checkable/checked state. `activate_editor_ui_control` now accepts `checked_value` for checkable menu entries: it leaves an already-correct setting alone, activates only when the state differs, and checks the resulting state. Together these changes give the agent a more reliable path to discover and set built-in editor menu options—such as collision/debug visualization options—without asking the user to add a temporary script.

**Scope limit:** this is generic menu-level access, not a guarantee that every collision overlay, viewport mode, or hidden submenu is reachable. The popup traversal, check-state reporting, and idempotent menu-setting behavior are source-only and still need Godot parser/runtime and Android-device verification. The next implementation pass should inventory the actual target editor's debug menus, then add dedicated typed actions for options that are not reliably exposed through the generic UI tree.

## Scene UI and preview-control bridge — source added, not yet validated

Two more tools are generated and registered:

| Tool | Intended coverage | Scope and status |
|---|---|---|
| `inspect_scene_ui_controls` | Enumerate Control nodes in the edited scene, including path, class, visibility, geometry, text, values, checks, and option choices | Source added; parser/runtime test pending |
| `interact_scene_ui_control` | Press buttons, set LineEdit/TextEdit content, change Range values, toggle checks, select OptionButton entries, and focus controls | Source added; parser/runtime test pending |

**Important preview distinction:** these tools operate on the currently edited scene tree. They are useful to inspect and exercise UI nodes before running a preview, but they do not yet inject input into a separate running game process. The generic editor UI bridge can operate on controls actually exposed inside the editor's own UI tree, including text controls, ranges/sliders, checkboxes, tabs, options, buttons, and open menus; this must not be confused with full control of the game viewport/runtime. Actual running-preview control still requires a tested remote-runtime transport or an embedded-preview adapter.

## Embedded preview input — source added, not yet validated

The `send_editor_viewport_input` tool targets a specific `SubViewport` or `SubViewportContainer` found under the editor UI and can send mouse clicks/motion, key events, and text events to that viewport. This is intended to exercise controls in an embedded game preview without clicking arbitrary parts of the editor.

The tool does **not** claim to control a game launched in a separate external process. If the target Godot Android editor runs the game externally, a separate authenticated loopback runtime bridge or supported debugger integration is still required. Coordinates are viewport-local and must be obtained from a live preview inspection; source is not yet validated on the target Android device.

## Additional scene-tree organization — source added, not yet validated

Three further tools have been added:

- `reorder_node`: change sibling order through undo/redo.
- `set_node_group`: add or remove a named group.
- `manage_node_signal`: connect or disconnect a signal between two nodes in the edited scene, with undo/redo and checks for signal/method existence.

These cover some of the Scene dock operations that otherwise require manual Inspector/context-menu work. Ownership, signal argument compatibility, saved-scene serialization, and undo/redo still require runtime validation.

## Output and diagnostic text reader — source added, not yet validated

Added `read_editor_diagnostics` to collect bounded text from visible editor `RichTextLabel`, `TextEdit`, and `Label` controls, with filters and truncation metadata. It can help read Output/Debugger/log text when Godot exposes it in the editor UI tree. It does not claim to read hidden panels, structured debugger internals, or logs from a separate process.

## Required breadth-first expansion plan

The target is comprehensive coverage of every usable editor surface, including rare/obscure options. Work through these families rather than stopping at the current tool list:

1. **Navigation and menus:** main menus, submenus, context menus, toolbar controls, command palette, keyboard shortcuts, visible dock/tab selection, modal dialogs, and focus/navigation.
2. **Workspace/layout:** switch 2D/3D/Script/AssetLib screens where available; show/hide, select, and rearrange docks; restore/save layouts; inspect editor settings and shortcuts.
3. **Scene structure:** create/open/save/duplicate/rename scenes; add, instance, duplicate, rename, reparent, group, reorder, and safely remove nodes; ownership, editable children, signals, groups, and undo/redo.
4. **Inspector and resources:** read/write all supported Variant types; nested resources, arrays/dictionaries, metadata, resource creation, resource editors, property revert and context actions.
5. **Scripts and files:** editor tab management, code navigation, search/replace, diagnostics, breakpoints, file operations, import/reimport and dependency inspection.
6. **Bottom panels and diagnostics:** Output with detailed logs, Debugger errors/warnings/stack traces, breakpoints, remote scene/tree, monitors, profiler, audio panel, animation panel, and every other panel in the target build.
7. **Specialized editors:** 2D/3D viewport tools, animation/timeline, TileMap/TileSet, shaders, materials, themes, audio buses, particles, navigation, physics, skeletons, terrain, multiplayer, XR, and installed plugin UIs.
8. **Project-wide workflows:** Project/Editor Settings, input map, localization, export presets and platform options, version-control UI, Android-specific import/export and permissions.
9. **Long-tail/obscure options:** inventory every remaining menu item, toggle, checkbox, spin box, option button, tree, list, tab, popup, dialog, context action, and shortcut. Do not dismiss an action as useless or too minor to implement.

Every surface must ultimately have an explicit status and evidence. Prefer typed editor APIs; use the UI bridge for navigation and controls without a suitable API; add specialized adapters for complex editors. No arbitrary GDScript/eval escape hatch and no project-root deletion.

`inspect_editor_ui` and `activate_editor_ui_control` are source-level changes only. No packaging, parser, CI, APK build, or device test has been run for this addition.

## Scene-tree organization tools — source added, not yet validated

Three more typed actions are now generated and registered:

| Tool | Intended coverage | Current status |
|---|---|---|
| `duplicate_node` | Duplicate a non-root node as a sibling | Source added; parser/runtime test pending |
| `rename_node` | Rename a node while checking sibling-name collisions | Source added; parser/runtime test pending |
| `reparent_node` | Move a node to another parent in the edited scene, with descendant-cycle and instanced-subscene guards | Source added; parser/runtime test pending |

These actions are wired to Godot's editor undo/redo history. They are not yet verified in the running editor, and the final scene tree must be checked for correct ownership, naming, ordering, serialization, and undo/redo behavior.

## Latest source-level MCP expansion — not yet validated

The packaging script now generates and registers five additional typed tools:

| Tool | Intended coverage | Current status |
|---|---|---|
| `get_editor_state` | Current edited scene, root class/name, open scenes, play state | Implemented in source; parser/runtime test pending |
| `open_scene` | Open an existing `.tscn` or `.scn` project scene | Implemented in source; runtime test pending |
| `control_running_scene` | Start current scene, start main scene, stop, or query play state | Implemented in source; runtime test pending |
| `get_node_properties` | Enumerate node property names/types and optionally simple values | Implemented in source; serialization test pending |
| `create_resource` | Create a registered Resource class and save to a new safe `res://` path without overwriting | Implemented in source; parser/runtime test pending |

These are **partial editor capabilities**, not full Godot control. The MCP registry still does not expose every menu, dock, viewport action, importer, inspector editor, animation/tilemap tool, debugger/profiler operation, export workflow, or third-party plugin action. Typed tools must be expanded surface by surface, with safety checks and tests. No full-coverage claim is permitted.


## Live game runtime bridge and fullscreen — source added, not yet validated

Two typed tools extend control from the edited scene into the actual running game:

- `install_runtime_game_bridge` installs a project-local autoload companion at `res://addons/godot_mcp_android_runtime/game_runtime_bridge.gd`. It binds only to `127.0.0.1:37843`, refuses to overwrite an existing companion, and saves/verifies a recovery copy of `project.godot` before adding its autoload entry.
- `control_runtime_game` sends typed JSON-line commands over loopback to request runtime status, enumerate live `Control` nodes and their global rectangles, click a control by scene-tree path, edit text fields, set Range values, toggle checkboxes, select OptionButton entries, inject mouse/key input, synthesize touchscreen taps and swipes, and enter/exit/toggle fullscreen.

### Boundaries and required validation

- This bridge is **source-added only**. Do not treat it as working until the packaging script, GDScript parser, MCP request/response exchange, and on-device runtime are tested.
- The project must explicitly install the companion and run a game instance that loads the autoload. The bridge is not automatically present in every existing project.
- The listener binds to loopback, not LAN/public interfaces, and requires a random token generated during installation. The editor-side MCP server is also expected to remain loopback-only. This is defense in depth, not a substitute for runtime testing.
- A control path must be obtained from the running game's own scene tree; paths from `inspect_scene_ui_controls` refer to the edited scene and may differ at runtime.
- Fullscreen is requested through the running game's `DisplayServer` window mode. Android window-manager behavior and embedded-preview behavior must be checked on the target device; do not claim fullscreen succeeded until the response and actual display are confirmed.
- Input injection can exercise ordinary Godot UI/gameplay, but cannot promise to control arbitrary native Android dialogs, OS permission prompts, or external applications.
- The install action makes a recovery copy and refuses to overwrite the bridge script, but still needs failure-path review before being considered safe for general use.

Acceptance checks still required: start a project with the bridge installed; verify the runtime handshake; inspect a known button; click it and confirm the expected game-side effect; send movement/gameplay input; toggle fullscreen and restore windowed mode; stop/restart the game; verify that an absent runtime returns a bounded error; verify loopback binding and project settings recovery. **No tests or builds have been run for these changes.**


## GitHub repository import: branch, tag, or commit

The Project Manager import dialog now includes an optional ref field. A blank value uses the repository's default branch; a supplied branch, tag, or commit SHA is appended to the GitHub archive endpoint after input validation and URI encoding. The existing repository owner/name validation and public-repository-only flow remain in place. This has not been compiled or exercised on Android; the branch/tag/commit flow is not yet verified.


Runtime gameplay input includes `mouse_move`, `touch` (press/release), and `swipe` actions in addition to mouse click and keyboard events. These generate Godot input events inside the running game. Coordinate mapping, multitouch behavior, orientation changes, and compatibility with each game's input code require Android device validation.


## Live Link Linux emitter tools

The hardened MCP package now adds two typed editor tools:

- `get_live_link_status`: reports whether the desktop Live Link emitter is connected, its Android target ID, whether its baseline is loaded, and queued/in-flight operations.
- `send_live_link_changes`: asks the desktop emitter to queue changed project files. It does not execute arbitrary code; the Android receiver still asks for approval for each file operation.

The emitter's baseline must be initialized only while the Android and Linux projects are identical. Updates and deletions carry the prior SHA-256 so Android can reject conflicting changes. Common secret files and private keys are excluded, as are `project.godot`, generated folders, and the Live Link/MCP addons themselves. Files larger than 5 MiB are skipped.

The MCP server remains bound to loopback. The tools are packaged and enabled for desktop projects imported through the modified Project Manager, but a secure outbound remote-MCP bridge is still required before ChatGPT in the cloud can reach that local server. Do not expose the editor MCP listener directly to the public Internet. Linux compilation and the MCP embedding smoke test are still running; this section describes the intended behavior, not a completed end-to-end device test.
