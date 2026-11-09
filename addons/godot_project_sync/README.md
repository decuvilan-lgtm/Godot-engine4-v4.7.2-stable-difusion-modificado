## Godot Shared Project Sync

This add-on is included with the modified Godot Android editor source repository. Copy the `addons/godot_project_sync` folder into the root of a Godot project, open it in the modified Android editor, then enable **Godot Shared Project Sync** under Project > Project Settings > Plugins.

Pair the Android editor using a one-time code created for `android_editor`. Pair the Godot Web editor using a separate code for `web_editor`. Both must use the same Command Center workspace and select the same shared project.

The add-on provides manual Analyze and Synchronize actions, revision-aware SHA-256 comparisons, conflict blocking, local rescue copies before remote overwrites/deletions, and incremental file transfers through the Render relay. It never writes Neon credentials into the project. The editor credential is held only in memory.

See the integration repository's shared-project-sync add-on README for the synchronization contract and safety limits.
