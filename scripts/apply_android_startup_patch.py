#!/usr/bin/env python3
"""Patch the Android editor's native splash and in-engine startup overlay."""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "godot-source"
LAYOUT = ROOT / "platform/android/java/editor/src/main/res/layout/godot_editor_layout.xml"
THEMES = ROOT / "platform/android/java/editor/src/main/res/values/themes.xml"

def replace_once(path: Path, old: str, new: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"Missing Android editor resource: {path}")
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path.relative_to(ROOT)}: expected one anchor, found {count}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")

if not LAYOUT.is_file() or not THEMES.is_file():
    sys.exit("Android editor resource tree missing; check out Godot 4.7.2 source first.")

replace_once(THEMES,
"""	<style name="GodotEditorSplashScreenTheme" parent="Theme.SplashScreen.IconBackground">
		<!-- Set the theme of the Activity that directly follows your splash
		screen. This is required. -->
		<item name="postSplashScreenTheme">@style/GodotEditorTheme</item>
	</style>""",
"""	<style name="GodotEditorSplashScreenTheme" parent="Theme.SplashScreen.IconBackground">
		<!-- Keep the native splash and the editor's own loading overlay visually consistent. -->
		<item name="windowSplashScreenBackground">#10141C</item>
		<item name="windowSplashScreenAnimatedIcon">@mipmap/themed_icon</item>
		<item name="windowSplashScreenIconBackgroundColor">#263244</item>
		<item name="postSplashScreenTheme">@style/GodotEditorTheme</item>
	</style>""")

replace_once(LAYOUT,
"""	<ProgressBar
		style="@android:style/Widget.Holo.ProgressBar.Large"
		android:id="@+id/editor_loading_indicator"
		android:layout_width="80dp"
		android:layout_height="80dp"
		android:indeterminate="true"
		app:layout_constraintEnd_toEndOf="parent"
		app:layout_constraintStart_toStartOf="parent"
		app:layout_constraintTop_toTopOf="parent"
		app:layout_constraintBottom_toBottomOf="parent"
		app:layout_constraintVertical_bias="0.80"/>""",
"""	<!-- Covers the native engine startup until onGodotMainLoopStarted hides this view. -->
	<FrameLayout
		android:id="@+id/editor_loading_indicator"
		android:layout_width="match_parent"
		android:layout_height="match_parent"
		android:background="#10141C"
		android:clickable="true"
		android:focusable="true"
		app:layout_constraintTop_toTopOf="parent"
		app:layout_constraintBottom_toBottomOf="parent"
		app:layout_constraintStart_toStartOf="parent"
		app:layout_constraintEnd_toEndOf="parent">

		<LinearLayout
			android:layout_width="wrap_content"
			android:layout_height="wrap_content"
			android:layout_gravity="center"
			android:orientation="vertical"
			android:gravity="center"
			android:padding="28dp"
			android:background="#1A2230">

			<ImageView
				android:layout_width="88dp"
				android:layout_height="88dp"
				android:src="@mipmap/themed_icon"
				android:contentDescription="Godot Android Editor"/>

			<TextView
				android:layout_width="wrap_content"
				android:layout_height="wrap_content"
				android:layout_marginTop="18dp"
				android:text="Godot Android Editor"
				android:textColor="#FFFFFF"
				android:textSize="20sp"
				android:textStyle="bold"
				android:gravity="center"/>

			<TextView
				android:layout_width="wrap_content"
				android:layout_height="wrap_content"
				android:layout_marginTop="8dp"
				android:text="Preparing your workspace…"
				android:textColor="#C7D0DE"
				android:textSize="14sp"
				android:gravity="center"/>

			<ProgressBar
				style="@android:style/Widget.Material.ProgressBar"
				android:layout_width="48dp"
				android:layout_height="48dp"
				android:layout_marginTop="22dp"
				android:indeterminate="true"/>
		</LinearLayout>
	</FrameLayout>""")

print("PASS: native Android splash has an explicit icon/background.")
print("PASS: startup overlay covers the editor until the Godot main loop starts.")
print("Note: Android resource/Gradle and device runtime checks are still required.")
