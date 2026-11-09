## Godot Shared Project Sync

This add-on is included with the modified Godot Android editor source repository. Use the modified Android Project Manager's **Shared Sync** button to install both this add-on and the matching AI Bridge add-on into the selected project. If installing manually, copy the `addons/godot_project_sync` folder and the `addons/godot_ai_bridge` folder from this repository into the project, then enable both plugins under Project > Project Settings > Plugins.

Pair the Android editor using a one-time code created for `android_editor`. Pair the Godot Web editor using a separate code for `web_editor`. Both must use the same Command Center workspace and select the same shared project.

The add-on provides manual Analyze and Synchronize actions, revision-aware SHA-256 comparisons, conflict blocking, local rescue copies before remote overwrites/deletions, and incremental file transfers through the Render relay. Analyze displays the exact file operations; Synchronize is enabled only for the same reviewed plan and blocks if the remote revision or operation set changes. It never writes Neon credentials into the project. The editor credential is held only in memory.

See the integration repository's shared-project-sync add-on README for the synchronization contract and safety limits.
