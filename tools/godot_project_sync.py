#!/usr/bin/env python3
"""Pull immutable, verified snapshots from the shared Godot project relay.

This client deliberately never overwrites an existing project and has no push,
shell, process-launch, or arbitrary filesystem API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_RELAY = "https://godot-web-ia-relay.onrender.com"
MAX_FILES = 10_000
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_NAMES = {
    ".env", ".env.local", ".env.production", "id_rsa", "id_ed25519",
}
FORBIDDEN_SUFFIXES = (
    ".pem", ".key", ".p8", ".asc", ".gpg", ".p12", ".pfx",
    ".keystore", ".jks", ".mobileprovision",
)


class SyncError(RuntimeError):
    pass


def validate_relative_path(raw: str) -> PurePosixPath:
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 1024:
        raise SyncError("El servidor devolvió una ruta vacía o demasiado larga.")
    if raw.startswith("/") or "\\" in raw or "\x00" in raw or ":" in raw:
        raise SyncError(f"Ruta remota no permitida: {raw!r}")
    path = PurePosixPath(raw)
    parts = raw.split("/")
    if path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise SyncError(f"Ruta remota no segura: {raw!r}")
    lowered = [part.lower() for part in parts]
    if any(part in {".git", ".godot"} for part in lowered):
        raise SyncError(f"El manifiesto incluye una carpeta excluida: {raw!r}")
    name = lowered[-1]
    if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES):
        raise SyncError(f"El manifiesto incluye un archivo sensible: {raw!r}")
    if name.endswith(".env") or name.startswith(".env."):
        raise SyncError(f"El manifiesto incluye un archivo de entorno: {raw!r}")
    return path


def validate_manifest(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("project"), dict):
        raise SyncError("Formato de manifiesto inválido.")
    project = payload["project"]
    if not isinstance(project.get("id"), str) or not isinstance(project.get("slug"), str):
        raise SyncError("El manifiesto no identifica el proyecto.")
    revision = payload.get("head_revision")
    files = payload.get("files")
    if not isinstance(revision, int) or revision < 0 or not isinstance(files, list):
        raise SyncError("El manifiesto no contiene una revisión o lista de archivos válida.")
    if len(files) > MAX_FILES:
        raise SyncError(f"El proyecto supera el límite de {MAX_FILES} archivos.")
    seen: set[str] = set()
    total = 0
    normalized: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict):
            raise SyncError("Entrada de archivo inválida en el manifiesto.")
        rel = validate_relative_path(item.get("path"))
        path_text = rel.as_posix()
        if path_text in seen:
            raise SyncError(f"Ruta duplicada en el manifiesto: {path_text}")
        seen.add(path_text)
        digest = item.get("sha256")
        size = item.get("byte_size")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise SyncError(f"Hash SHA-256 inválido para {path_text}.")
        if not isinstance(size, int) or size < 0 or size > MAX_FILE_BYTES:
            raise SyncError(f"Tamaño inválido para {path_text}.")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise SyncError("El proyecto supera el límite de descarga de 512 MiB.")
        normalized.append({**item, "path": path_text, "sha256": digest, "byte_size": size})
    # Reject file/directory collisions such as "a" and "a/b".
    for name in seen:
        parts = name.split("/")
        for index in range(1, len(parts)):
            if "/".join(parts[:index]) in seen:
                raise SyncError(f"Colisión entre archivo y carpeta en {name!r}.")
    return project, normalized


class RelayClient:
    def __init__(self, base_url: str, token: str, timeout: float = 45.0):
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise SyncError("La URL del relay debe ser HTTPS y no puede incluir credenciales.")
        if parsed.query or parsed.fragment:
            raise SyncError("La URL base del relay no puede incluir query ni fragmento.")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(self, path: str, *, query: dict[str, str] | None = None) -> tuple[bytes, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/json, application/octet-stream",
                "User-Agent": "godot-linux-headless-project-sync/0.1",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read(MAX_TOTAL_BYTES + 1)
                if len(data) > MAX_TOTAL_BYTES:
                    raise SyncError("La respuesta del relay excede el límite permitido.")
                return data, response.headers
        except urllib.error.HTTPError as exc:
            # Do not print request headers or the bearer credential.
            detail = exc.read(2048).decode("utf-8", "replace")
            raise SyncError(f"Relay respondió HTTP {exc.code}: {detail}") from None
        except urllib.error.URLError as exc:
            raise SyncError(f"No se pudo conectar con el relay: {exc.reason}") from None

    def list_projects(self) -> list[dict[str, Any]]:
        data, _ = self.request("/v1/command-center/projects")
        try:
            payload = json.loads(data)
            projects = payload["projects"]
        except (ValueError, KeyError, TypeError):
            raise SyncError("Respuesta inválida al listar proyectos.") from None
        if not isinstance(projects, list):
            raise SyncError("La lista de proyectos del relay es inválida.")
        return projects

    def get_manifest(self, project_id: str) -> dict[str, Any]:
        data, _ = self.request(
            f"/v1/command-center/projects/{urllib.parse.quote(project_id, safe='')}/manifest"
        )
        try:
            return json.loads(data)
        except ValueError:
            raise SyncError("El relay devolvió un manifiesto JSON inválido.") from None

    def download_file(self, project_id: str, path: str, expected_size: int,
                      expected_sha256: str) -> bytes:
        data, headers = self.request(
            f"/v1/command-center/projects/{urllib.parse.quote(project_id, safe='')}/files/content",
            query={"path": path},
        )
        actual = hashlib.sha256(data).hexdigest()
        header_hash = headers.get("X-File-SHA256", "")
        if len(data) != expected_size:
            raise SyncError(f"Tamaño incorrecto al descargar {path!r}.")
        if actual != expected_sha256 or (header_hash and header_hash != expected_sha256):
            raise SyncError(f"SHA-256 incorrecto al descargar {path!r}.")
        return data


def pull_snapshot(client: RelayClient, project_id: str, destination: Path) -> Path:
    manifest = client.get_manifest(project_id)
    project, files = validate_manifest(manifest)
    if project["id"] != project_id:
        raise SyncError("El ID del proyecto no coincide con el solicitado.")
    destination = destination.expanduser()
    parent = destination.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / destination.name
    if os.path.lexists(destination):
        raise SyncError(
            f"El destino ya existe y no se sobrescribirá: {destination}. "
            "Elegí una carpeta nueva para este snapshot."
        )
    staging = Path(tempfile.mkdtemp(prefix=".godot-sync-staging-", dir=parent))
    try:
        for item in files:
            relative = validate_relative_path(item["path"])
            target = staging.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            data = client.download_file(
                project_id, item["path"], item["byte_size"], item["sha256"]
            )
            # Exclusive creation prevents accidental replacement inside staging.
            with target.open("xb") as handle:
                handle.write(data)
        # The staging directory is a sibling, so the final rename stays on one filesystem.
        if os.path.lexists(destination):
            raise SyncError(f"El destino apareció durante la descarga: {destination}")
        os.rename(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(
        f"Snapshot recibido: {project.get('display_name', project['slug'])} "
        f"(revisión {manifest['head_revision']}) — {len(files)} archivos — {destination}"
    )
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sincronización de entrada: descarga snapshots verificados de Godot Web."
    )
    parser.add_argument(
        "--relay", default=os.environ.get("GODOT_RELAY_URL", DEFAULT_RELAY),
        help="URL HTTPS del relay (o GODOT_RELAY_URL).",
    )
    parser.add_argument(
        "--token", default=os.environ.get("GODOT_AGENT_TOKEN"),
        help="Bearer temporal agent_controller (o GODOT_AGENT_TOKEN).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Lista los proyectos compartidos del workspace.")
    pull = sub.add_parser("sync", aliases=["pull"], help="Descarga un snapshot nuevo sin sobrescribir proyectos.")
    pull.add_argument("project_id", help="UUID del proyecto compartido.")
    pull.add_argument("--dest", required=True, type=Path, help="Carpeta nueva donde crear el snapshot.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.token:
        print("Falta GODOT_AGENT_TOKEN (credencial temporal emparejada como agent_controller).", file=sys.stderr)
        return 2
    try:
        client = RelayClient(args.relay, args.token)
        if args.command == "list":
            projects = client.list_projects()
            if not projects:
                print("No hay proyectos compartidos en este workspace.")
            for item in projects:
                print(
                    f"{item.get('id')}  {item.get('slug')}  "
                    f"{item.get('display_name')}  rev={item.get('head_revision')}"
                )
            return 0
        if args.command in {"sync", "pull"}:
            pull_snapshot(client, args.project_id, args.dest)
            return 0
    except (SyncError, OSError) as exc:
        print(f"Error de sincronización: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
