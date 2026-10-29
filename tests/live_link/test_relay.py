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
        relay.PENDING.clear()
        relay.SEEN_OPERATIONS.clear()
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
        relay.PENDING.clear()
        relay.SEEN_OPERATIONS.clear()

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

    async def test_routes_valid_remote_input_to_target(self):
        target = await self.join("target", room="valid_input_room")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
        controller = await self.join("controller", room="valid_input_room")
        self.assertEqual((await controller.receive_json(timeout=2))["type"], "joined")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")
        await controller.send_json({
            "type": "remote_input",
            "event": {"kind": "mouse_button", "x": 0.5, "y": 0.25, "button_index": 1, "pressed": True}
        })
        received = await target.receive_json(timeout=2)
        self.assertEqual(received["type"], "remote_input")
        self.assertEqual(received["from_role"], "controller")
        self.assertEqual(received["event"]["x"], 0.5)
        with self.assertRaises(asyncio.TimeoutError):
            await controller.receive(timeout=0.15)
        await controller.close()
        await target.close()

    async def test_routes_keyboard_input_without_pointer_coordinates(self):
        target = await self.join("target", room="keyboard_room")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
        controller = await self.join("controller", room="keyboard_room")
        self.assertEqual((await controller.receive_json(timeout=2))["type"], "joined")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")
        key_event = {
            "kind": "key", "keycode": 65, "physical_keycode": 65,
            "unicode": 97, "pressed": True, "echo": False,
            "shift": False, "ctrl": True, "alt": False, "meta": False
        }
        await controller.send_json({"type": "remote_input", "event": key_event})
        received = await target.receive_json(timeout=2)
        self.assertEqual(received["type"], "remote_input")
        self.assertEqual(received["from_role"], "controller")
        self.assertEqual(received["event"], key_event)
        await controller.close()
        await target.close()

    async def test_rooms_are_isolated(self):
        target_a = await self.join("target", room="isolated_a")
        self.assertEqual((await target_a.receive_json(timeout=2))["type"], "joined")
        controller_b = await self.join("controller", room="isolated_b")
        self.assertEqual((await controller_b.receive_json(timeout=2))["type"], "joined")
        await target_a.send_json({
            "type": "screen_frame", "width": 320, "height": 240, "data": "aGVsbG8="
        })
        with self.assertRaises(asyncio.TimeoutError):
            await controller_b.receive(timeout=0.2)
        await controller_b.close()
        await target_a.close()

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

    async def test_controller_cannot_publish_screen_frames(self):
        target = await self.join("target", room="direction_room")
        await target.receive_json(timeout=2)
        controller = await self.join("controller", room="direction_room")
        await controller.receive_json(timeout=2)
        await target.receive_json(timeout=2)  # peer_joined
        await controller.send_json({
            "type": "screen_frame", "width": 320, "height": 240, "data": "aGVsbG8="
        })
        with self.assertRaises(asyncio.TimeoutError):
            await target.receive(timeout=0.2)
        await controller.close()
        await target.close()

    async def test_target_cannot_publish_remote_input(self):
        target = await self.join("target", room="direction_input_room")
        await target.receive_json(timeout=2)
        controller = await self.join("controller", room="direction_input_room")
        await controller.receive_json(timeout=2)
        await target.receive_json(timeout=2)  # peer_joined
        await target.send_json({
            "type": "remote_input",
            "event": {"kind": "key", "keycode": 65, "pressed": True}
        })
        with self.assertRaises(asyncio.TimeoutError):
            await controller.receive(timeout=0.2)
        await controller.close()
        await target.close()


    def test_project_operation_validation_rejects_unsafe_paths(self):
        base = {
            "type": "project_operation",
            "target_platform": "android_editor",
            "policy_version": 1,
            "project_id": "4827",
            "operation_id": "op-1",
            "operation": "create",
            "path": "Scenes/room.tscn",
            "content_base64": "YQ==",
            "sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
            "base_sha256": ""
        }
        self.assertTrue(relay.valid_project_operation(base))
        self.assertFalse(relay.valid_project_operation(dict(base, target_platform="desktop_editor")))
        self.assertFalse(relay.valid_project_operation({k: v for k, v in base.items() if k != "target_platform"}))
        self.assertFalse(relay.valid_project_operation(dict(base, policy_version=2)))
        for path in ("../project.godot", "/tmp/escape", "C:/outside", "Scenes\\\\escape.gd", ".git/config", ".godot/imported/x"):
            candidate = dict(base, path=path)
            self.assertFalse(relay.valid_project_operation(candidate), path)
        self.assertFalse(relay.valid_project_operation(dict(base, project_id="bad")))
        self.assertFalse(relay.valid_project_operation(dict(base, sha256="not-a-hash")))
        self.assertFalse(relay.valid_project_operation(dict(base, content_base64="x" * (relay.MAX_PROJECT_CONTENT * 2))))

    async def test_agent_project_operation_reaches_only_target_and_result_returns(self):
        target = await self.join("target", room="project_ops_room")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
        agent = await self.join("agent", room="project_ops_room")
        self.assertEqual((await agent.receive_json(timeout=2))["type"], "joined")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")
        operation = {
            "type": "project_operation",
            "target_platform": "android_editor",
            "policy_version": 1,
            "project_id": "12345678-1234-1234-1234-123456789abc",
            "operation_id": "op-2",
            "operation": "create",
            "path": "Scenes/room.tscn",
            "content_base64": "YQ==",
            "sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
            "base_sha256": ""
        }
        await agent.send_json(operation)
        received = await target.receive_json(timeout=2)
        self.assertEqual(received["type"], "project_operation")
        self.assertEqual(received["from_role"], "agent")
        self.assertEqual(received["operation_id"], "op-2")
        with self.assertRaises(asyncio.TimeoutError):
            await agent.receive(timeout=0.15)
        result = {
            "type": "project_result",
            "project_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "operation_id": "op-2",
            "status": "applied",
            "message": "must not be accepted for another project"
        }
        await target.send_json(result)
        with self.assertRaises(asyncio.TimeoutError):
            await agent.receive(timeout=0.15)
        result["project_id"] = operation["project_id"]
        result["message"] = "validated by test receiver"
        await target.send_json(result)
        received_result = await agent.receive_json(timeout=2)
        self.assertEqual(received_result["type"], "project_result")
        self.assertEqual(received_result["status"], "applied")
        self.assertEqual(received_result["from_role"], "target")
        # A result is one-shot: replaying it after completion must not reach the agent.
        await target.send_json(result)
        with self.assertRaises(asyncio.TimeoutError):
            await agent.receive(timeout=0.15)
        # Replaying the completed operation ID must not reach the target either.
        await asyncio.sleep(1.05)  # Let the per-message rate limit stop masking the replay guard.
        await agent.send_json(operation)
        with self.assertRaises(asyncio.TimeoutError):
            await target.receive(timeout=0.2)
        await agent.close()
        await target.close()

    async def test_agent_cannot_publish_project_result_and_target_cannot_issue_operations(self):
        target = await self.join("target", room="project_direction_room")
        await target.receive_json(timeout=2)
        agent = await self.join("agent", room="project_direction_room")
        await agent.receive_json(timeout=2)
        await target.receive_json(timeout=2)
        await target.send_json({
            "type": "project_operation",
            "project_id": "12345678-1234-1234-1234-123456789abc",
            "operation_id": "bad-op", "operation": "delete", "path": "Scenes/room.tscn"
        })
        await agent.send_json({
            "type": "project_result",
            "project_id": "12345678-1234-1234-1234-123456789abc",
            "operation_id": "bad-op", "status": "applied"
        })
        with self.assertRaises(asyncio.TimeoutError):
            await target.receive(timeout=0.15)
        with self.assertRaises(asyncio.TimeoutError):
            await agent.receive(timeout=0.15)
        await agent.close()
        await target.close()


    async def test_rejects_result_after_pending_operation_ttl(self):
        target = await self.join("target", room="expired_result_room")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
        agent = await self.join("agent", room="expired_result_room")
        self.assertEqual((await agent.receive_json(timeout=2))["type"], "joined")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")

        operation = {
            "type": "project_operation",
            "target_platform": "android_editor",
            "policy_version": 1,
            "project_id": "12345678-1234-1234-1234-123456789abc",
            "operation_id": "expired-op-1",
            "operation": "create",
            "path": "Scenes/expired.txt",
            "content_base64": "YQ==",
            "sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
            "base_sha256": "",
        }
        await agent.send_json(operation)
        forwarded = await target.receive_json(timeout=2)
        self.assertEqual(forwarded["operation_id"], "expired-op-1")

        old_ttl = relay.PENDING_TTL_SECONDS
        try:
            relay.PENDING_TTL_SECONDS = 0.01
            await asyncio.sleep(0.03)
            await target.send_json({
                "type": "project_result",
                "project_id": operation["project_id"],
                "operation_id": operation["operation_id"],
                "status": "applied",
                "message": "late result must be discarded",
            })
            with self.assertRaises(asyncio.TimeoutError):
                await agent.receive(timeout=0.2)
            self.assertNotIn("expired-op-1", relay.PENDING.get("expired_result_room", {}))
        finally:
            relay.PENDING_TTL_SECONDS = old_ttl
            await agent.close()
            await target.close()


if __name__ == "__main__":
    unittest.main()
