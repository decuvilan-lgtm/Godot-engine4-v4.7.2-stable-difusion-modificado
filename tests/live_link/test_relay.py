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
import account_api as account_api_module
import command_center_api as command_center_api_module


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
        relay.install_account_routes(test_app)
        command_center_api_module.install_command_center_routes(test_app)
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

    async def test_account_api_fails_closed_without_neon(self):
        response = await self.client.post("/v1/devices/enroll", json={
            "ticket": "x" * 32, "device_label": "test", "platform": "android"
        })
        self.assertEqual(response.status, 503)
        response = await self.client.get("/v1/account/devices")
        self.assertEqual(response.status, 401)

    async def test_pairing_completion_fails_closed_without_neon(self):
        response = await self.client.post("/v1/devices/pair/complete", json={
            "pair_code": "x" * 24, "device_label": "Linux editor"
        })
        self.assertEqual(response.status, 503)

    async def test_pair_code_creation_requires_authenticated_device(self):
        response = await self.client.post("/v1/devices/pair", json={"device_label": "Linux editor"})
        self.assertEqual(response.status, 401)

    def test_device_secret_hashing_is_one_way_and_stable(self):
        first = account_api_module.digest_secret("device-secret-example")
        self.assertEqual(first, account_api_module.digest_secret("device-secret-example"))
        self.assertNotEqual(first, account_api_module.digest_secret("another-secret"))
        self.assertNotEqual(first.decode("latin1"), "device-secret-example")
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

    def test_mobile_capture_validation_is_bounded(self):
        import base64
        valid = {
            "type": "mobile_capture", "project_id": "4827",
            "capture_id": "capture-1", "width": 720, "height": 1280,
            "data": base64.b64encode(b"\xff\xd8\xff\xd9").decode("ascii"),
        }
        self.assertTrue(relay.valid_mobile_capture(valid))
        self.assertFalse(relay.valid_mobile_capture(dict(valid, project_id="bad")))
        self.assertFalse(relay.valid_mobile_capture(dict(valid, width=721)))
        self.assertFalse(relay.valid_mobile_capture(dict(valid, data="bm90LWEtanBlZw==")))
        self.assertFalse(relay.valid_mobile_capture(dict(valid, data="!" * 100)))

    async def test_mobile_capture_routes_only_to_agent(self):
        target = await self.join("target", room="mobile_capture_room")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
        agent = await self.join("agent", room="mobile_capture_room")
        self.assertEqual((await agent.receive_json(timeout=2))["type"], "joined")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")
        controller = await self.join("controller", room="mobile_capture_room")
        self.assertEqual((await controller.receive_json(timeout=2))["type"], "joined")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")
        self.assertEqual((await agent.receive_json(timeout=2))["type"], "peer_joined")
        import base64
        capture = {
            "type": "mobile_capture", "project_id": "4827",
            "capture_id": "capture-route-1", "width": 320, "height": 240,
            "data": base64.b64encode(b"\xff\xd8\xff\xd9").decode("ascii"),
        }
        await target.send_json(capture)
        received = await agent.receive_json(timeout=2)
        self.assertEqual(received["type"], "mobile_capture")
        self.assertEqual(received["from_role"], "target")
        self.assertEqual(received["project_id"], "4827")
        with self.assertRaises(asyncio.TimeoutError):
            await controller.receive(timeout=0.2)
        await controller.close()
        await agent.close()
        await target.close()

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
        for invalid_id in ("123", "12345", "12a4", "1234-5678", "12345678-1234-1234-1234-123456789abc"):
            self.assertFalse(relay.valid_project_operation(dict(base, project_id=invalid_id)), invalid_id)
        for valid_id in ("0000", "4827", "9999"):
            self.assertTrue(relay.valid_project_operation(dict(base, project_id=valid_id)), valid_id)
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
            "project_id": "4827",
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
            "project_id": "4827",
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


    def test_scene_operation_validation_is_bounded_and_allowlisted(self):
        base = {
            "type": "scene_operation", "protocol_version": 1, "approval": "required",
            "project_id": "0427", "operation_id": "scene-1",
            "scene_path": "res://main.tscn", "expected_scene_revision": 0,
            "target_node_path": "",
            "operation": "create_node",
            "arguments": {"parent_path": "", "name": "WallNorth", "class": "CSGBox3D"},
        }
        self.assertTrue(relay.valid_scene_operation(base))
        self.assertFalse(relay.valid_scene_operation(dict(base, project_id="bad")))
        self.assertFalse(relay.valid_scene_operation(dict(base, scene_path="res://../outside.tscn")))
        self.assertFalse(relay.valid_scene_operation(dict(base, expected_scene_revision=True)))
        self.assertFalse(relay.valid_scene_operation(dict(base, operation="execute_script")))
        self.assertFalse(relay.valid_scene_operation(dict(base, approval="automatic")))
        self.assertFalse(relay.valid_scene_operation(dict(base, arguments={"parent_path": "", "name": "../escape", "class": "CSGBox3D"})))
        transform = dict(base, operation="set_transform", target_node_path="WallNorth", arguments={"position": [0, 1, -4]})
        self.assertTrue(relay.valid_scene_operation(transform))
        self.assertFalse(relay.valid_scene_operation(dict(transform, arguments={"position": [float("inf"), 0, 0]})))

    async def test_agent_scene_operation_routes_to_target_and_ack_returns_once(self):
        target = await self.join("target", room="scene_ops_room")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
        agent = await self.join("agent", room="scene_ops_room")
        self.assertEqual((await agent.receive_json(timeout=2))["type"], "joined")
        self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")
        operation = {
            "type": "scene_operation", "protocol_version": 1, "approval": "required",
            "project_id": "0427", "operation_id": "scene-op-1",
            "scene_path": "res://main.tscn", "expected_scene_revision": 0,
            "target_node_path": "",
            "operation": "create_node",
            "arguments": {"parent_path": "", "name": "Floor", "class": "CSGBox3D"},
        }
        await agent.send_json(operation)
        received = await target.receive_json(timeout=2)
        self.assertEqual(received["type"], "scene_operation")
        self.assertEqual(received["from_role"], "agent")
        self.assertEqual(received["operation_id"], "scene-op-1")
        result = {
            "type": "scene_operation_result", "project_id": "0427",
            "operation_id": "scene-op-1", "status": "applied",
            "scene_revision": 1, "message": "applied in editor memory",
        }
        await target.send_json(result)
        forwarded = await agent.receive_json(timeout=2)
        self.assertEqual(forwarded["type"], "scene_operation_result")
        self.assertEqual(forwarded["status"], "applied")
        await target.send_json(result)
        with self.assertRaises(asyncio.TimeoutError):
            await agent.receive(timeout=0.15)
        await agent.close()
        await target.close()


    async def test_android_scene_state_is_forwarded_to_agent(self):
        target = await self.join("target", room="scene_state_room")
        await target.receive_json(timeout=2)
        agent = await self.join("agent", room="scene_state_room")
        await agent.receive_json(timeout=2)
        await target.receive_json(timeout=2)
        await target.send_json({"type":"scene_state", "project_id":"0427", "scene_path":"res://house.tscn", "scene_revision":3})
        state = await agent.receive_json(timeout=2)
        self.assertEqual(state["type"], "scene_state")
        self.assertEqual(state["scene_path"], "res://house.tscn")
        self.assertEqual(state["scene_revision"], 3)
        await agent.close()
        await target.close()


if __name__ == "__main__":
    unittest.main()


class CommandCenterApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_database_url = os.environ.pop("DATABASE_URL", None)
        self.old_cc_database_url = os.environ.pop("COMMAND_CENTER_DATABASE_URL", None)
        self.old_admin_token = os.environ.pop("COMMAND_CENTER_ADMIN_TOKEN", None)
        app = web.Application()
        command_center_api_module.install_command_center_routes(app)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        for key, value in (
            ("DATABASE_URL", self.old_database_url),
            ("COMMAND_CENTER_DATABASE_URL", self.old_cc_database_url),
            ("COMMAND_CENTER_ADMIN_TOKEN", self.old_admin_token),
        ):
            if value is not None:
                os.environ[key] = value

    async def test_pairing_code_creation_requires_admin_secret(self):
        response = await self.client.post(
            "/v1/command-center/pairing-codes",
            json={"device_kind": "android_editor"},
        )
        self.assertEqual(response.status, 401)

    async def test_pairing_fails_closed_without_database(self):
        response = await self.client.post(
            "/v1/command-center/pair",
            json={
                "pairing_code": "p" * 32,
                "label": "Android editor",
                "installation_id": "installation-123456",
            },
        )
        self.assertEqual(response.status, 503)

    async def test_command_submission_requires_agent_device(self):
        response = await self.client.post(
            "/v1/command-center/commands",
            json={"target": "android_editor", "action": "ping", "args": {}},
        )
        self.assertEqual(response.status, 401)

    async def test_command_poll_requires_editor_device(self):
        response = await self.client.get("/v1/command-center/commands/next")
        self.assertEqual(response.status, 401)

    async def test_command_center_secrets_are_hashed(self):
        first = command_center_api_module.digest_secret("sample-device-credential")
        self.assertEqual(first, command_center_api_module.digest_secret("sample-device-credential"))
        self.assertNotEqual(first, command_center_api_module.digest_secret("different-credential"))
        self.assertNotEqual(first, "sample-device-credential")

    def test_command_policy_is_read_only_allowlist(self):
        self.assertIn("project.get_state", command_center_api_module.ALLOWED_ACTIONS)
        self.assertIn("script.read", command_center_api_module.ALLOWED_ACTIONS)
        self.assertNotIn("script.write", command_center_api_module.ALLOWED_ACTIONS)
        self.assertNotIn("shell.execute", command_center_api_module.ALLOWED_ACTIONS)

    def test_json_payload_size_is_bounded(self):
        self.assertLessEqual(command_center_api_module._json_size({"ok": True}), 64)
        self.assertGreater(command_center_api_module._json_size({"data": "x" * (300 * 1024)}),
                           command_center_api_module.MAX_ARGS_BYTES)
