# Live Link client for external AI agents

The reusable Python client is `relay/agent_client.py`. It is an **agent-side**
library: it can run on a Linux host or in an external service and does not add a
Python runtime dependency to the Android editor.

## Connection

Install the relay requirements in the agent environment and configure these
values outside source control:

- `LIVE_LINK_RELAY_URL`: the deployed `wss://...` WebSocket endpoint. The client rejects plain `ws://` for remote hosts; unencrypted WebSockets are allowed only for loopback integration tests.
- `LIVE_LINK_ROOM`: the same room configured in the Godot add-on.
- `LIVE_LINK_TOKEN`: the relay shared token.
- `LIVE_LINK_PROJECT_ID`: the project ID displayed by the selected Godot project.

Never commit the relay token or put it in a public issue, screenshot, or prompt.
The project ID selects a project but is not a secret or an authorization token.
Because the current relay uses a shared room token, use a private room and trusted
clients only; per-project credentials and stronger room authorization remain future
hardening work.

## Sin depender de una API ni de un relay de terceros

Live Link puede usarse sin API de IA, sin API de GitHub y sin alojar el relay en un proveedor externo:

1. Conecta el teléfono Android y el equipo que ejecuta el agente a la misma red Wi-Fi/LAN.
2. En el equipo de confianza, inicia el relay incluido en este repositorio: `python -m pip install -r relay/requirements.txt`, define `LIVE_LINK_TOKEN` y ejecuta `python relay/server.py`.
3. Averigua la IP privada del equipo en esa red y configura en el complemento Godot `ws://IP_PRIVADA:8765/ws`; usa el mismo token y la misma sala.
4. En el agente, usa la misma URL, sala, token e ID de proyecto. Para el cliente Python, activa explícitamente `allow_insecure_lan=True` solo en esta red privada.

Ejemplo de cliente LAN:

```python
async with LiveLinkAgentClient(
    "ws://192.168.1.20:8765/ws",
    room,
    token,
    project_id,
    allow_insecure_lan=True,
) as client:
    result = await client.execute(operation)
```

Sustituye la IP de ejemplo por la IP real del equipo que aloja el relay. Permite el puerto TCP 8765 en el cortafuegos solo para la red local. El relay escucha en todas las interfaces por defecto: no lo expongas a Internet ni uses esta modalidad en Wi-Fi público; el tráfico WS de LAN no está cifrado. Usa WSS para conexiones remotas o redes no confiables.

Este modo no depende de un servicio externo ni de una API, pero sí requiere que el equipo que ejecuta el relay esté encendido y accesible en la misma red. Para conectar desde fuera de la LAN sin un relay de terceros, haría falta configurar un relay propio con WSS o una VPN/red privada; no existe una conexión remota directa universal si ambos dispositivos están detrás de NAT/firewalls.

## Example

```python
import asyncio
import base64
import hashlib
import os
import uuid

from relay.agent_client import LiveLinkAgentClient

async def main():
    raw = b"[gd_scene format=3]\n\n[node name=\"Root\" type=\"Node2D\"]\n"
    operation = {
        "type": "project_operation",
        "target_platform": "android_editor",
        "policy_version": 1,
        "project_id": os.environ["LIVE_LINK_PROJECT_ID"],
        "operation_id": str(uuid.uuid4()),
        "operation": "create",
        "path": "Scenes/live_link_probe.tscn",
        "content_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "base_sha256": "",
    }
    async with LiveLinkAgentClient(
        os.environ["LIVE_LINK_RELAY_URL"],
        os.environ["LIVE_LINK_ROOM"],
        os.environ["LIVE_LINK_TOKEN"],
        os.environ["LIVE_LINK_PROJECT_ID"],
    ) as client:
        result = await client.execute(operation)
        print("Godot result:", result["status"], result.get("message", ""))

asyncio.run(main())
```

This example creates a small scene file and is intended only for a deliberately
selected test project. Do not run it against a project you care about without
reviewing the operation first.

## Result semantics

- `execute()` checks the Android policy envelope and exact selected project ID
  before sending.
- It waits for a `project_result` matching both the operation ID and project ID.
- `applied` is the target editor's explicit response; `rejected`, `conflict`
  and `failed` are not success.
- A timeout or disconnect raises an exception. It does **not** mean the operation
  failed or succeeded; inspect Godot and reconcile the project before retrying.
- The client serializes operations per connection to keep response correlation simple.

The relay is a transport, not a security sandbox. The Android add-on must continue
to validate paths, project identity, hashes, backups and each operation before
changing project files. CI parser/tests do not prove the editor is connected to a
real phone; Android end-to-end testing is still required.
