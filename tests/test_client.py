"""Unit tests for the Client dataclass."""

import json
import unittest

from hivemind_plugin_manager.database import Client


class TestClientPipelineBlacklist(unittest.TestCase):
    def test_default_is_empty_list(self):
        c = Client(client_id=1, api_key="k")
        self.assertEqual(c.pipeline_blacklist, [])

    def test_value_is_preserved(self):
        c = Client(
            client_id=1,
            api_key="k",
            pipeline_blacklist=["ovos-fallback-pipeline-plugin-low"],
        )
        self.assertEqual(
            c.pipeline_blacklist, ["ovos-fallback-pipeline-plugin-low"]
        )

    def test_serialize_includes_pipeline_blacklist(self):
        c = Client(client_id=1, api_key="k", pipeline_blacklist=["a", "b"])
        data = json.loads(c.serialize())
        self.assertEqual(data["pipeline_blacklist"], ["a", "b"])

    def test_serialize_default_is_empty_list(self):
        c = Client(client_id=1, api_key="k")
        data = json.loads(c.serialize())
        self.assertIn("pipeline_blacklist", data)
        self.assertEqual(data["pipeline_blacklist"], [])

    def test_deserialize_roundtrip(self):
        original = Client(client_id=1, api_key="k", pipeline_blacklist=["x"])
        restored = Client.deserialize(original.serialize())
        self.assertEqual(restored.pipeline_blacklist, ["x"])
        self.assertEqual(restored, original)

    def test_deserialize_legacy_without_field_defaults_to_empty(self):
        """Old serialized payloads predating pipeline_blacklist must still load."""
        legacy_payload = json.dumps(
            {
                "client_id": 1,
                "api_key": "k",
                "name": "n",
                "intent_blacklist": [],
                "skill_blacklist": [],
                "message_blacklist": [],
                "allowed_types": ["recognizer_loop:utterance"],
            }
        )
        c = Client.deserialize(legacy_payload)
        self.assertEqual(c.pipeline_blacklist, [])

    def test_getitem_setitem_access(self):
        """Dict-style access works for the new field (used by some plugins)."""
        c = Client(client_id=1, api_key="k")
        self.assertEqual(c["pipeline_blacklist"], [])
        c["pipeline_blacklist"] = ["y"]
        self.assertEqual(c.pipeline_blacklist, ["y"])


if __name__ == "__main__":
    unittest.main()
