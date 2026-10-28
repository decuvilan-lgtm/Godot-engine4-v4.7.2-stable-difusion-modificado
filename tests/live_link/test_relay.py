"""Integration tests for the Live Link relay protocol.

Run from the repository root with:
    python -m pip install -r relay/requirements.txt
    python -m unittest discover -s tests/live_link -v
"""
import asyncio
import importlib.util
import os
import pathlib
import unittest

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ["LIVE_LINK_TOKEN"] = "test-token-live-link"
spec = importlib.util.spec_from_file_location("live_link_relay", ROOT / "relay" / "server.py")
relay = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(relay)


class LiveLinkRelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        relay.ROOMS.clear()
        relay.ROLES.clear()
        relay.LAST.clear()
        test_app = web.Application(client_max_size=relay.MAX_MESSAGE)
        test_app.router.add_get("/health", relay.health)
        test_app.router.add_get("/ws", relay.websocket)
        self.client = TestClient(TestServer(test_app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        relay.ROOMS.clear()
        relay.ROLES.clear()
        relay.LAST.clear()

    async def join(self, role, token="test-token-live-link", room="test_room"):
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({"type": "join", "room": room, "role": role, "token": token})
        return ws

    async def test_health_endpoint(self):
        response = await self.client.get("/health")
        self.assertEqual(response.status, 200)
        body = await response.json()
        self.assertEqual(body["status"], "ok")

    async def test_rejects_wrong_token(self):
        ws = await self.join("target", token="wrong-token")
        message = await ws.receive(timeout=2)
        self.assertEqual(message.type, WSMsgType.CLOSE)
        await ws.close()

    async def test_rejects_duplicate_role_in_same_room(self):
        target = await self.join("target")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
        duplicate = await self.join("target")
        message = await duplicate.receive(timeout=2)
        self.assertEqual(message.type, WSMsgType.CLOSE)
        await target.close()
        await duplicate.close()

    async def test_routes_screen_only_to_controller(self):
        target = await self.join("target", room="route_room")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
        controller = await self.join("controller", room="route_room")
        self.assertEqual((await controller.receive_json(timeout=2))["type"], "joined")
        # Consume peer notification sent to the first participant.
        self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")
        await target.send_json({
            "type": "screen_frame", "width": 320, "height": 240, "data": "aGVsbG8="
        })
        received = await controller.receive_json(timeout=2)
        self.assertEqual(received["type"], "screen_frame")
        self.assertEqual(received["from_role"], "target")
        # The target must not receive its own frame.
        with self.assertRaises(asyncio.TimeoutError):
            await target.receive(timeout=0.15)
        await controller.close()
        await target.close()

    async def test_rejects_out_of_range_remote_input(self):
        target = await self.join("target", room="input_room")
        await target.receive_json(timeout=2)
        controller = await self.join("controller", room="input_room")
        await controller.receive_json(timeout=2)
        await target.receive_json(timeout=2)  # peer_joined
        await controller.send_json({
            "type": "remote_input",
            "event": {"kind": "mouse_button", "x": 1.5, "y": 0.5}
        })
        with self.assertRaises(asyncio.TimeoutError):
            await target.receive(timeout=0.15)
        await controller.close()
        await target.close()


if __name__ == "__main__":
    unittest.main()
