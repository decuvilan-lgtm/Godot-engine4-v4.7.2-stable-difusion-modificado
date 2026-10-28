"""Small reusable client for AI agents speaking the Godot Live Link protocol.

Runs on the agent side (for example, on a Linux host), not as an Android editor
runtime dependency. It transports operations; it does not decide whether Godot
applied them safely.
"""
from __future__ import annotations

import asyncio
import ipaddress
import re
from urllib.parse import urlsplit
from typing import Any

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

PROJECT_ID_RE = re.compile(r"^[a-fA-F0-9-]{16,64}$")
OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
VALID_OPERATIONS = {"create", "update", "rename", "delete"}


def _is_loopback_ip(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_private_lan_ip(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        return address.version == 4 and address.is_private and not address.is_loopback and not address.is_link_local
    except ValueError:
        return False


class LiveLinkError(RuntimeError):
    """Base exception for connection and protocol failures."""


class LiveLinkAgentClient:
    """Single-operation-at-a-time client requiring a matching target result."""

    def __init__(self, relay_url: str, room: str, token: str, project_id: str,
                 *, timeout: float = 30.0, allow_insecure_lan: bool = False) -> None:
        parsed_url = urlsplit(relay_url)
        secure_remote = parsed_url.scheme == "wss" and bool(parsed_url.hostname)
        loopback_test = (
            parsed_url.scheme == "ws"
            and parsed_url.hostname is not None
            and (
                parsed_url.hostname.lower() == "localhost"
                or _is_loopback_ip(parsed_url.hostname)
            )
        )
        lan_test = (
            allow_insecure_lan
            and parsed_url.scheme == "ws"
            and parsed_url.hostname is not None
            and _is_private_lan_ip(parsed_url.hostname)
        )
        if not (secure_remote or loopback_test or lan_test) or parsed_url.username or parsed_url.password:
            raise ValueError(
                "Use wss:// remotely; ws:// is allowed only for loopback tests or an explicitly enabled private-LAN relay."
            )
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", room):
            raise ValueError("Invalid Live Link room.")
        if not PROJECT_ID_RE.fullmatch(project_id):
            raise ValueError("Invalid project_id.")
        if not token:
            raise ValueError("A relay token is required.")
        if timeout <= 0:
            raise ValueError("timeout must be positive.")
        self.relay_url = relay_url
        self.room = room
        self.token = token
        self.project_id = project_id
        self.timeout = timeout
        self.allow_insecure_lan = allow_insecure_lan
        self._session: ClientSession | None = None
        self._ws: ClientWebSocketResponse | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._ws is not None and not self._ws.closed:
            return
        self._session = ClientSession()
        try:
            self._ws = await self._session.ws_connect(
                self.relay_url, heartbeat=25, autoclose=True, autoping=True
            )
            await self._ws.send_json({
                "type": "join", "room": self.room, "role": "agent", "token": self.token
            })
            message = await asyncio.wait_for(self._ws.receive(), timeout=self.timeout)
            if message.type != WSMsgType.TEXT:
                raise LiveLinkError("Relay closed before confirming the agent joined.")
            reply = message.json()
            if reply.get("type") != "joined" or reply.get("role") != "agent" or reply.get("room") != self.room:
                raise LiveLinkError("Relay rejected the agent join.")
        except Exception:
            await self.close()
            raise

    async def execute(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Send one operation and return only its matching explicit target result.

        The operation must include operation_id, operation, path, and the content/hash
        fields required by the relay. This method enforces the Android policy envelope
        and selected project identity before transmission.
        """
        if not isinstance(operation, dict):
            raise TypeError("operation must be a dict")
        op_id = operation.get("operation_id")
        if not isinstance(op_id, str) or not OPERATION_ID_RE.fullmatch(op_id):
            raise ValueError("operation_id is missing or invalid.")
        if operation.get("project_id") != self.project_id:
            raise ValueError("Operation project_id does not match the selected project.")
        if operation.get("target_platform") != "android_editor" or operation.get("policy_version") != 1:
            raise ValueError("Operation must explicitly target android_editor policy version 1.")
        if operation.get("operation") not in VALID_OPERATIONS:
            raise ValueError("Unsupported operation.")
        if not isinstance(operation.get("path"), str) or not operation["path"]:
            raise ValueError("Operation path is missing.")
        async with self._lock:
            if self._ws is None or self._ws.closed:
                raise LiveLinkError("Agent is not connected.")
            await self._ws.send_json(operation)
            deadline = asyncio.get_running_loop().time() + self.timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"No matching Godot result for operation {op_id!r}.")
                message = await asyncio.wait_for(self._ws.receive(), timeout=remaining)
                if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSE, WSMsgType.ERROR):
                    raise LiveLinkError("Relay connection closed before a result arrived.")
                if message.type != WSMsgType.TEXT:
                    continue
                try:
                    reply = message.json()
                except Exception:
                    continue
                if reply.get("type") != "project_result":
                    continue
                if reply.get("operation_id") != op_id or reply.get("project_id") != self.project_id:
                    continue
                if reply.get("from_role") != "target":
                    continue
                if reply.get("status") not in {"applied", "rejected", "conflict", "failed"}:
                    raise LiveLinkError("Target returned an invalid operation status.")
                return reply

    async def close(self) -> None:
        ws, session = self._ws, self._session
        self._ws = None
        self._session = None
        if ws is not None and not ws.closed:
            await ws.close()
        if session is not None and not session.closed:
            await session.close()

    async def __aenter__(self) -> "LiveLinkAgentClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
