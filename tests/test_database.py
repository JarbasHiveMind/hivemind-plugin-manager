import json
import unittest
from typing import List, Union, Iterable

from hivemind_plugin_manager.database import (
    AbstractDB,
    AbstractRemoteDB,
    Client,
    cast2client,
)


class _InMemoryDB(AbstractDB):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items: List[Client] = []

    def add_item(self, client: Client) -> bool:
        for i, c in enumerate(self._items):
            if c.client_id == client.client_id:
                self._items[i] = client
                return True
        self._items.append(client)
        return True

    def search_by_value(self, key: str, val) -> List[Client]:
        return [c for c in self._items if getattr(c, key, None) == val]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterable[Client]:
        return iter(self._items)


class _InMemoryRemoteDB(AbstractRemoteDB):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items: List[Client] = []

    def add_item(self, client: Client) -> bool:
        self._items.append(client)
        return True

    def search_by_value(self, key: str, val) -> List[Client]:
        return [c for c in self._items if getattr(c, key, None) == val]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterable[Client]:
        return iter(self._items)


class TestClient(unittest.TestCase):
    def _make(self, **overrides) -> Client:
        defaults = dict(client_id=1, api_key="k", name="alice")
        defaults.update(overrides)
        return Client(**defaults)

    def test_defaults_populate_allowed_types(self):
        c = self._make()
        self.assertIn("recognizer_loop:utterance", c.allowed_types)
        self.assertGreater(len(c.allowed_types), 1)

    def test_allowed_types_always_contains_utterance(self):
        c = self._make(allowed_types=["custom:event"])
        self.assertIn("recognizer_loop:utterance", c.allowed_types)
        self.assertIn("custom:event", c.allowed_types)

    def test_post_init_rejects_non_int_client_id(self):
        with self.assertRaises(ValueError):
            Client(client_id="1", api_key="k")

    def test_post_init_rejects_non_bool_is_admin(self):
        with self.assertRaises(ValueError):
            Client(client_id=1, api_key="k", is_admin="yes")

    def test_serialize_returns_json_string(self):
        c = self._make()
        data = json.loads(c.serialize())
        self.assertEqual(data["client_id"], 1)
        self.assertEqual(data["api_key"], "k")
        self.assertEqual(data["name"], "alice")

    def test_deserialize_from_dict(self):
        c = Client.deserialize({"client_id": 2, "api_key": "z", "name": "bob"})
        self.assertEqual(c.client_id, 2)
        self.assertEqual(c.name, "bob")

    def test_deserialize_from_json_string(self):
        payload = json.dumps({"client_id": 3, "api_key": "y", "name": "eve"})
        c = Client.deserialize(payload)
        self.assertEqual(c.client_id, 3)

    def test_getitem_returns_attribute(self):
        c = self._make()
        self.assertEqual(c["name"], "alice")

    def test_getitem_raises_on_unknown(self):
        c = self._make()
        with self.assertRaises(KeyError):
            _ = c["does_not_exist"]

    def test_setitem_updates_attribute(self):
        c = self._make()
        c["name"] = "renamed"
        self.assertEqual(c.name, "renamed")

    def test_setitem_raises_on_unknown(self):
        c = self._make()
        with self.assertRaises(ValueError):
            c["does_not_exist"] = 1

    def test_equality_same_data(self):
        a = self._make()
        b = self._make()
        self.assertEqual(a, b)

    def test_equality_against_dict(self):
        a = self._make()
        self.assertEqual(a, json.loads(a.serialize()))

    def test_equality_against_json_string(self):
        a = self._make()
        self.assertEqual(a, a.serialize())

    def test_inequality_against_unrelated_type(self):
        a = self._make()
        self.assertNotEqual(a, 42)

    def test_repr_is_serialized(self):
        c = self._make()
        self.assertEqual(repr(c), c.serialize())


class TestCast2Client(unittest.TestCase):
    def test_none_passthrough(self):
        self.assertIsNone(cast2client(None))

    def test_client_passthrough(self):
        c = Client(client_id=1, api_key="k")
        self.assertIs(cast2client(c), c)

    def test_from_dict(self):
        c = cast2client({"client_id": 1, "api_key": "k"})
        self.assertIsInstance(c, Client)

    def test_from_json_string(self):
        c = cast2client(json.dumps({"client_id": 1, "api_key": "k"}))
        self.assertIsInstance(c, Client)

    def test_from_list(self):
        result = cast2client(
            [
                {"client_id": 1, "api_key": "k"},
                Client(client_id=2, api_key="k2"),
            ]
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(all(isinstance(c, Client) for c in result))

    def test_unsupported_type_raises(self):
        with self.assertRaises(TypeError):
            cast2client(42)


class TestAbstractDB(unittest.TestCase):
    def test_add_and_iter(self):
        db = _InMemoryDB()
        db.add_item(Client(client_id=1, api_key="k", name="a"))
        db.add_item(Client(client_id=2, api_key="k2", name="b"))
        self.assertEqual(len(db), 2)
        names = sorted(c.name for c in db)
        self.assertEqual(names, ["a", "b"])

    def test_search_by_value(self):
        db = _InMemoryDB()
        db.add_item(Client(client_id=1, api_key="k", name="match"))
        db.add_item(Client(client_id=2, api_key="k2", name="other"))
        found = db.search_by_value("name", "match")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].client_id, 1)

    def test_delete_replaces_with_revoked(self):
        db = _InMemoryDB()
        db.add_item(Client(client_id=1, api_key="real", name="a"))
        db.delete_item(Client(client_id=1, api_key="real"))
        self.assertEqual(len(db), 1)
        revoked = list(db)[0]
        self.assertEqual(revoked.api_key, "revoked")

    def test_update_item_delegates_to_add(self):
        db = _InMemoryDB()
        c = Client(client_id=1, api_key="k", name="a")
        db.add_item(c)
        c2 = Client(client_id=1, api_key="k", name="renamed")
        db.update_item(c2)
        self.assertEqual(list(db)[0].name, "renamed")

    def test_replace_item(self):
        db = _InMemoryDB()
        old = Client(client_id=1, api_key="old")
        new = Client(client_id=2, api_key="new")
        db.add_item(old)
        db.replace_item(old, new)
        ids = sorted(c.client_id for c in db)
        # delete leaves revoked entry, plus new
        self.assertIn(2, ids)

    def test_commit_default_returns_true(self):
        db = _InMemoryDB()
        self.assertTrue(db.commit())

    def test_sync_default_noop(self):
        db = _InMemoryDB()
        self.assertIsNone(db.sync())

    def test_default_fields(self):
        db = _InMemoryDB()
        self.assertEqual(db.name, "clients")
        self.assertEqual(db.subfolder, "hivemind-core")
        self.assertIsNone(db.password)


class TestAbstractRemoteDB(unittest.TestCase):
    def test_default_host_port(self):
        db = _InMemoryRemoteDB()
        self.assertEqual(db.host, "127.0.0.1")
        self.assertIsNone(db.port)

    def test_custom_host_port(self):
        db = _InMemoryRemoteDB(host="10.0.0.1", port=6379)
        self.assertEqual(db.host, "10.0.0.1")
        self.assertEqual(db.port, 6379)

    def test_add_and_search(self):
        db = _InMemoryRemoteDB()
        db.add_item(Client(client_id=1, api_key="k", name="x"))
        self.assertEqual(len(db), 1)
        self.assertEqual(db.search_by_value("name", "x")[0].client_id, 1)


if __name__ == "__main__":
    unittest.main()
