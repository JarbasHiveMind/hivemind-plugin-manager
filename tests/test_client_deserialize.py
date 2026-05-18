import json
import unittest

from hivemind_plugin_manager.database import Client


class TestClientDeserialize(unittest.TestCase):
    def _base(self, **overrides):
        data = {"client_id": 1, "name": "alice", "api_key": "k"}
        data.update(overrides)
        return data

    def test_plain_record_has_empty_metadata(self):
        c = Client.deserialize(self._base())
        self.assertEqual(c.metadata, {})

    def test_json_string_input(self):
        c = Client.deserialize(json.dumps(self._base()))
        self.assertEqual(c.name, "alice")
        self.assertEqual(c.metadata, {})

    def test_explicit_metadata_preserved(self):
        c = Client.deserialize(self._base(metadata={"region": "eu"}))
        self.assertEqual(c.metadata, {"region": "eu"})

    def test_legacy_unknown_fields_swept_into_metadata(self):
        c = Client.deserialize(self._base(weird=42, extra="x"))
        self.assertEqual(c.metadata, {"weird": 42, "extra": "x"})

    def test_explicit_metadata_wins_over_legacy_collision(self):
        c = Client.deserialize(
            self._base(weird=42, metadata={"weird": "explicit"})
        )
        self.assertEqual(c.metadata, {"weird": "explicit"})

    def test_legacy_and_explicit_metadata_merge_without_collision(self):
        c = Client.deserialize(
            self._base(weird=42, metadata={"other": 1})
        )
        self.assertEqual(c.metadata, {"weird": 42, "other": 1})

    def test_none_metadata_coerced_to_empty(self):
        c = Client.deserialize(self._base(metadata=None))
        self.assertEqual(c.metadata, {})

    def test_non_dict_metadata_raises(self):
        with self.assertRaises(TypeError):
            Client.deserialize(self._base(metadata="nope"))

    def test_deserialize_does_not_mutate_input(self):
        payload = self._base(weird=42, metadata={"a": 1})
        snapshot = json.loads(json.dumps(payload))
        Client.deserialize(payload)
        self.assertEqual(payload, snapshot)

    def test_post_init_resets_non_dict_metadata(self):
        c = Client(client_id=1, name="alice", api_key="k", metadata="bad")
        self.assertEqual(c.metadata, {})

    def test_roundtrip_serialize_deserialize(self):
        original = Client(
            client_id=7,
            name="bob",
            api_key="kk",
            metadata={"tier": "gold", "tags": ["a", "b"]},
        )
        restored = Client.deserialize(original.serialize())
        self.assertEqual(restored, original)
        self.assertEqual(restored.metadata, {"tier": "gold", "tags": ["a", "b"]})


if __name__ == "__main__":
    unittest.main()
