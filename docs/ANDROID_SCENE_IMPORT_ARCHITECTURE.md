# Import Godot projects without flattening scenes

## User-facing requirement

When importing a Godot project or its files from GitHub, do not flatten the project's scene hierarchy into the currently open/main scene. Having all source files visible in the FileSystem panel is expected; the problem is attaching every imported node, scene instance, and child to one active scene.

Godot's FileSystem panel and the scene tabs are different concepts:
- The FileSystem panel lists project files and folders.
- Each existing `.tscn` scene should remain a separate scene file and open as its own scene tab when the user chooses it.
- The top scene-tab bar's **+** creates a new scene; it should not be used to create duplicate tabs or duplicate scene contents unnecessarily.

## Import behavior

1. **Import a full Godot project/repository:** copy the project tree while preserving directory structure and all existing `.tscn`, `.scn`, scripts, resources, assets, and references. Do not flatten all discovered scenes into the currently active scene.
2. **Keep runtime behavior through scene instancing:** a scene can be instanced once into the main scene, and its descendants inside that scene remain part of that instantiated scene hierarchy and can affect the main scene at runtime. Do not separately instantiate every child scene/node into the main scene just to make those descendants work. This is the intended clean organization: one instance of a parent scene can contain its own child nodes/scene instances, scripts, signals, and behavior.
3. **Keep editable structure separated:** child nodes and nested scene structure should remain organized inside their own scene file. Users can inspect or edit them by opening that scene from the scene-tab bar. The main scene tree should show the parent scene instance rather than a flattened copy of all descendants, while runtime behavior remains intact.
4. **Import a single scene file:** copy the scene and its dependencies/resources to the project, preserving relative paths. Open that scene as its own tab only if the user explicitly chooses “Open after import”; otherwise leave the current scene unchanged.
5. **Import a folder or multiple files:** preserve folder layout and references. Never automatically add every imported node to the current scene. If the input is a reusable node/scene asset rather than a project, provide explicit actions: “Copy files”, “Open scene”, or “Instantiate in current scene”.
6. **Existing scenes:** detect valid scene files and retain each as an independent scene resource. Do not rewrite a scene's root, children, owners, connections, scripts, or external-resource references merely to make it visible in the editor.
7. **Scene tabs:** opening an existing scene uses Godot's native scene-opening mechanism, which should create/select a tab for that scene. Do not emulate this by creating a new empty scene and copying all nodes into it.
8. **Safe duplicate handling:** if the target path already exists, compare hashes and offer a clear replace/skip/rename choice; do not silently merge all nodes into the active scene.
9. **Dependencies:** preserve relative paths and import metadata where appropriate. Let Godot's resource importer reimport supported assets. Detect missing external resources and report them instead of silently flattening or dropping references.

## Post-import resource error report (required behavior)

After the import has finished and Godot has completed loading the imported project, show one consolidated popup if any files or resources failed to load. The popup should say that some files/resources could not be loaded and list each affected path, with a concise error/reason when available. It should not make the user guess which asset failed.

- Do not interrupt a large import with one dialog per failure. Collect diagnostics throughout import and project loading, then present the summary once the editor is ready.
- Include actionable details where available: project-relative path, failure stage (copy/import/resource-load), and Godot's error message. Allow the user to copy the report and open the affected file's folder when possible.
- If everything loads successfully, do not show an error popup.
- A missing or unreadable resource must not be silently replaced, omitted, or fabricated. Preserve the source files where possible and report the failure accurately.
- Keep import-fatal problems separate from post-load warnings: unsafe paths or a failed transaction may require stopping/rolling back; ordinary resource-load failures should be summarized after loading when it is safe to continue.
- Deduplicate repeated messages for the same resource while retaining distinct causes when they materially differ. Cap popup content for very large failure sets and provide a complete copyable report.
- The report must identify the exact affected files/resources and must not label a valid standalone scene as an error merely because no scene references it.
## Isolated scenes and import safety (required)

A scene that is not reachable from the main scene is not, by itself, an import error. It may be intentionally standalone, unfinished, experimental, or intended for later manual use. A large import must not pause for human decisions just because a valid scene is not referenced by another scene.

- Import and preserve every valid project file, including standalone `.tscn`/`.scn` files, in its original relative folder path.
- Make standalone scenes discoverable in the editor's scene/file navigation so the user can open them later. Opening a scene as a tab is an explicit navigation action; do not auto-open every scene or add every scene to the active node tree.
- Do not delete, quarantine, hide, or omit a scene merely because it has no incoming instance reference from the main scene or any other scene.
- Do not invent node instances, parent-child links, scripts, resource references, or scene connections to make an isolated scene appear connected.
- Do not block or prompt during bulk import solely because a scene is isolated. Continue the import and, if useful, include isolation as non-blocking informational metadata in a report.
- Reserve blocking errors for actual failures that prevent safe import (for example, corrupt/unreadable files or an unsafe path), not for valid content that is currently unused.
- Preserve the distinction between “file exists in the project”, “resource depends on another resource”, and “scene is instantiated in the runtime tree”. These are different states and must never be inferred from one another.
## Runtime semantics and the distinction that matters

The requirement is **not** “keep every imported scene disconnected from the main scene.” The requirement is to preserve the original scene composition. If the original main scene has one instance of a parent scene, that parent scene and all its descendants continue to participate in the main scene at runtime. The children do not need to be instantiated a second time individually in the main scene. Their node hierarchy remains inside the parent scene and can be inspected by opening the corresponding scene tab.

For example, if `Main.tscn` contains one instance of `Player.tscn`, and `Player.tscn` contains `Sprite2D`, `CollisionShape2D`, and child nodes with scripts, the main tree should show the `Player` instance as a single organized branch. The descendants remain part of that instance at runtime. The editor should not copy Sprite2D, CollisionShape2D, and all other descendants as duplicate top-level nodes in Main. To edit those children, open `Player.tscn` from the scene tabs.

Do not invent parent-child links that were absent from the imported project's original scenes. Preserve the source project's intended composition and external-resource references exactly.

## GitHub Analyze/Sync interaction

The Analyze/Sync workflow should treat scene files as ordinary tracked project files. Synchronization must preserve their paths and content. A remote change to `Scenes/Level01.tscn` updates that file at its path; it does not inject the level's nodes into whichever scene happens to be open. A tracked scene deleted from the remote is removed locally according to the authoritative sync policy.

## Mobile UI

On the 1600x720 landscape display and narrow/portrait layouts:
- Use compact actions for “Import project”, “Copy files”, “Open scene”, and “Instantiate in current scene” when applicable.
- Keep progress and errors visible without blocking the editor UI thread.
- Avoid dialogs that exceed the viewport or are hidden by the on-screen keyboard.

## Acceptance tests

- Import a project containing at least three `.tscn` files and confirm the scene files remain separate.
- Confirm the current scene node tree is unchanged after importing a whole project, except for parent scene instances already present in the original main scene.
- Open two existing scenes and confirm Godot opens/selects separate scene tabs, not duplicated nodes in one scene.
- Import a single scene and confirm external resources/scripts remain connected.
- Confirm explicit “Instantiate in current scene” is the only mode that adds a new scene instance to the current scene; its descendants remain inside that instance's own hierarchy and are not flattened or duplicated.
- Test overwrite/skip/rename for existing files.
- Run tests on Android ARM32 and ARM64; validate the actual Android editor on the target device. Do not use Linux editor builds or desktop screenshots as release gates.

## Status

This file records the required behavior and acceptance criteria. It does not claim the import UI or scene-opening implementation is already complete. Implementation must use Godot 4.7.2's native resource/scene APIs and must be verified in the Android build.


## Nested scene dependency graph (required technical behavior)

A scene dependency is not limited to scenes instantiated directly by the project main scene. Scene instancing is transitive and may occur at any depth. For example:

```text
Main.tscn
└── Level.tscn
    └── Enemy.tscn
        └── Weapon.tscn
```

Here, `Enemy.tscn` is not directly instanced by `Main.tscn`, but it is still part of the runtime scene graph through `Level.tscn`; likewise, `Weapon.tscn` is reachable through the enemy. The importer, dependency resolver, report, and any “copy scene with dependencies” operation must traverse this transitive graph rather than inspecting only the root scene's immediate children.

### Required rules

- Treat each scene file as an independent resource and each instance relationship as an edge in a dependency graph. Preserve the source paths and all original `ExtResource` references; do not flatten, clone, or rewrite nested scenes just to make their nodes visible in the root scene tree.
- Traverse transitive dependencies recursively, including scenes nested inside scenes, scripts, textures, fonts, audio, materials, shaders, and other external resources. Use Godot's native resource dependency APIs where possible rather than trying to parse every resource format manually.
- Track visited resource paths to avoid infinite recursion and duplicate work. Detect and report missing dependencies and cyclic dependency chains; do not silently drop a resource or loop forever. Cycles that Godot itself supports must be preserved rather than “fixed” by rewriting files.
- Preserve inherited scenes and editable-instance overrides. Do not replace an inherited scene with a flattened copy, erase instance overrides, or modify node ownership, signal connections, groups, scripts, unique-name references, or resource UIDs unnecessarily.
- Distinguish the **resource dependency graph** (which files refer to which other files) from the **runtime node tree** (which instances exist during execution). A resource may be present in the project without being instantiated at runtime; importing it must not automatically add it to the active scene.
- A scene instance nested several levels deep remains part of the runtime hierarchy when its ancestors are instantiated. It should not be added a second time to the main scene. To edit it, open the corresponding original scene resource in its own editor tab.
- “Instantiate in current scene” adds exactly one instance of the selected scene at the chosen insertion point. It does not recursively instantiate every descendant scene as separate siblings.
- When copying one scene with dependencies, calculate the transitive dependency closure and preserve relative paths. If a dependency is already present at the same target path, compare content and handle conflicts explicitly; do not overwrite unrelated resources silently.
- When syncing from GitHub, update or delete scene/resource files at their original paths. A change in a deeply nested scene must never be translated into node insertions in the currently open scene. Remote deletion of a tracked dependency must be reported with its dependents so the user can understand which scenes may become invalid before the authoritative sync is applied.
- Validation must include a chain of at least four scenes across multiple nesting levels, a scene inherited from another scene, shared resources referenced by multiple scenes, missing dependency reporting, and confirmation that importing leaves the active scene tree unchanged.

### Additional acceptance test

Create a fixture where `Main.tscn` instances `Level.tscn`, `Level.tscn` instances `Enemy.tscn`, and `Enemy.tscn` instances `Weapon.tscn`. Import the project and verify all four files and their resources remain separate, the nested instances are reachable at runtime through their ancestors, and the main scene contains no duplicate sibling copies of `Enemy` or `Weapon`. Open `Enemy.tscn` and `Weapon.tscn` individually and confirm they open as their own scene tabs without modifying `Main.tscn`.
