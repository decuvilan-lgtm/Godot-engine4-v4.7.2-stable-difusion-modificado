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
