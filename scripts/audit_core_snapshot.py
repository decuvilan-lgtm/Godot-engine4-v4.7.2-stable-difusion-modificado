#!/usr/bin/env python3
"""Compare the saved custom Godot core snapshot against the pinned upstream tree."""
from __future__ import annotations
import argparse
import hashlib
import os
import tarfile
from pathlib import Path, PurePosixPath

SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".h", ".hh", ".hpp", ".gd", ".py", ".cfg", ".json", ".md", ".txt", ".xml", ".tres", ".tscn", ".svg", ".gdshader", ".sh", ".yml", ".yaml", ".toml", ".scons", ".rst"}
EXCLUDED_PARTS = {".git", ".scons_cache", "__pycache__", "bin", "build", "dist", ".godot"}

def is_source_file(relative: str) -> bool:
    path = PurePosixPath(relative)
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return False
    return path.suffix.lower() in SOURCE_EXTENSIONS or path.name == "SConstruct"

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    if not args.archive.is_file() or not (upstream / "SConstruct").is_file():
        raise SystemExit("archive or pinned upstream checkout is missing")
    upstream_commit = __import__("subprocess").check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    modified: list[tuple[str, str, str]] = []
    custom_only: list[str] = []
    missing: list[str] = []
    identical = 0
    with tarfile.open(args.archive, "r:gz") as archive:
        members = archive.getmembers()
        roots = [member.name for member in members if member.isfile() and PurePosixPath(member.name).name == "SConstruct"]
        if not roots:
            raise SystemExit("could not locate SConstruct in the saved source archive")
        root_member = min(roots, key=lambda value: len(PurePosixPath(value).parts))
        prefix = root_member[:-len("SConstruct")]
        snapshot_files: dict[str, tarfile.TarInfo] = {}
        for member in members:
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            relative = member.name[len(prefix):]
            if relative and is_source_file(relative):
                snapshot_files[relative] = member
        for relative, member in sorted(snapshot_files.items()):
            upstream_file = upstream / relative
            stream = archive.extractfile(member)
            if stream is None:
                continue
            snapshot_digest = digest(stream.read())
            if not upstream_file.is_file():
                custom_only.append(relative)
                continue
            upstream_digest = digest(upstream_file.read_bytes())
            if snapshot_digest == upstream_digest:
                identical += 1
            else:
                modified.append((relative, snapshot_digest, upstream_digest))
    for current_dir, directory_names, file_names in os.walk(upstream):
        directory_names[:] = [name for name in directory_names if name not in EXCLUDED_PARTS]
        for file_name in file_names:
            upstream_file = Path(current_dir) / file_name
            relative = upstream_file.relative_to(upstream).as_posix()
            if is_source_file(relative) and relative not in snapshot_files:
                missing.append(relative)
    root_display = prefix if prefix else "."
    lines = [
        "# Existing Godot core snapshot audit",
        "",
        f"- Archive: `{args.archive.name}`",
        f"- Pinned upstream commit: `{upstream_commit}`",
        f"- Source root inside archive: `{root_display}`",
        f"- Snapshot source files compared: **{len(snapshot_files)}**",
        f"- Identical to upstream: **{identical}**",
        f"- Modified source files: **{len(modified)}**",
        f"- Custom-only source files: **{len(custom_only)}**",
        f"- Upstream source files missing from snapshot: **{len(missing)}**",
        "",
        "## Modified source files (snapshot SHA-256 vs upstream SHA-256)",
        "",
    ]
    if modified:
        lines.extend(f"- `{relative}` — `{snapshot_sha[:12]}` vs `{upstream_sha[:12]}`" for relative, snapshot_sha, upstream_sha in modified[:250])
        if len(modified) > 250:
            lines.append(f"- … and {len(modified) - 250} additional modified source files")
    else:
        lines.append("- None")
    lines.extend(["", "## Custom-only source files", ""])
    lines.extend(f"- `{relative}`" for relative in custom_only[:250])
    if len(custom_only) > 250:
        lines.append(f"- … and {len(custom_only) - 250} additional custom-only files")
    if not custom_only:
        lines.append("- None")
    lines.extend(["", "## Upstream source files missing from snapshot", ""])
    lines.extend(f"- `{relative}`" for relative in missing[:250])
    if len(missing) > 250:
        lines.append(f"- … and {len(missing) - 250} additional missing files")
    if not missing:
        lines.append("- None")
    lines.extend(["", "## Important interpretation", "", "This report compares source-like files only; generated binaries and build caches are excluded. A matching file hash proves that file is identical to the pinned upstream checkout. Differences must be reviewed and mapped to tracked patchers before claiming parity."])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output.read_text(encoding="utf-8"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())