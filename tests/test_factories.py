import unittest
from unittest.mock import patch

from hivemind_plugin_manager import (
    AgentProtocolFactory,
    BinaryDataHandlerProtocolFactory,
    DatabaseFactory,
    HiveMindPluginTypes,
    NetworkProtocolFactory,
    find_plugins,
)
from hivemind_plugin_manager.database import AbstractDB, AbstractRemoteDB, Client


class _FakeLocalDB(AbstractDB):
    def add_item(self, client): return True
    def search_by_value(self, key, val): return []
    def __len__(self): return 0
    def __iter__(self): return iter([])


class _FakeRemoteDB(AbstractRemoteDB):
    def add_item(self, client): return True
    def search_by_value(self, key, val): return []
    def __len__(self): return 0
    def __iter__(self): return iter([])


class _FakeAgentProtocol:
    def __init__(self, config=None, bus=None, hm_protocol=None):
        self.config = config
        self.bus = bus
        self.hm_protocol = hm_protocol


class _FakeNetworkProtocol:
    def __init__(self, config=None, hm_protocol=None):
        self.config = config
        self.hm_protocol = hm_protocol


class _FakeBinaryProtocol:
    def __init__(self, config=None, hm_protocol=None, agent_protocol=None):
        self.config = config
        self.hm_protocol = hm_protocol
        self.agent_protocol = agent_protocol


class TestHiveMindPluginTypes(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(HiveMindPluginTypes.DATABASE.value, "hivemind.database")
        self.assertEqual(HiveMindPluginTypes.AGENT_PROTOCOL.value, "hivemind.agent.protocol")
        self.assertEqual(HiveMindPluginTypes.NETWORK_PROTOCOL.value, "hivemind.network.protocol")
        self.assertEqual(HiveMindPluginTypes.BINARY_PROTOCOL.value, "hivemind.binary.protocol")


class TestDatabaseFactory(unittest.TestCase):
    @patch("hivemind_plugin_manager.find_plugins")
    def test_get_class_returns_registered(self, mock_find):
        mock_find.return_value = {"local": _FakeLocalDB}
        self.assertIs(DatabaseFactory.get_class("local"), _FakeLocalDB)

    @patch("hivemind_plugin_manager.find_plugins")
    def test_get_class_raises_on_missing(self, mock_find):
        mock_find.return_value = {}
        with self.assertRaises(KeyError):
            DatabaseFactory.get_class("missing")

    @patch("hivemind_plugin_manager.find_plugins")
    def test_create_local_db(self, mock_find):
        mock_find.return_value = {"local": _FakeLocalDB}
        db = DatabaseFactory.create("local", name="db", subfolder="sf")
        self.assertIsInstance(db, _FakeLocalDB)
        self.assertEqual(db.name, "db")
        self.assertEqual(db.subfolder, "sf")

    @patch("hivemind_plugin_manager.find_plugins")
    def test_create_remote_db_passes_host_port(self, mock_find):
        mock_find.return_value = {"remote": _FakeRemoteDB}
        db = DatabaseFactory.create("remote", host="1.2.3.4", port=9999)
        self.assertIsInstance(db, _FakeRemoteDB)
        self.assertEqual(db.host, "1.2.3.4")
        self.assertEqual(db.port, 9999)


class TestAgentProtocolFactory(unittest.TestCase):
    @patch("hivemind_plugin_manager.find_plugins")
    def test_get_class(self, mock_find):
        mock_find.return_value = {"agent": _FakeAgentProtocol}
        self.assertIs(AgentProtocolFactory.get_class("agent"), _FakeAgentProtocol)

    @patch("hivemind_plugin_manager.find_plugins")
    def test_get_class_missing(self, mock_find):
        mock_find.return_value = {}
        with self.assertRaises(KeyError):
            AgentProtocolFactory.get_class("agent")

    @patch("hivemind_plugin_manager.find_plugins")
    def test_create_defaults_empty_config(self, mock_find):
        mock_find.return_value = {"agent": _FakeAgentProtocol}
        inst = AgentProtocolFactory.create("agent")
        self.assertEqual(inst.config, {})


class TestNetworkProtocolFactory(unittest.TestCase):
    @patch("hivemind_plugin_manager.find_plugins")
    def test_get_class(self, mock_find):
        mock_find.return_value = {"net": _FakeNetworkProtocol}
        self.assertIs(NetworkProtocolFactory.get_class("net"), _FakeNetworkProtocol)

    @patch("hivemind_plugin_manager.find_plugins")
    def test_get_class_missing(self, mock_find):
        mock_find.return_value = {}
        with self.assertRaises(KeyError):
            NetworkProtocolFactory.get_class("net")

    @patch("hivemind_plugin_manager.find_plugins")
    def test_create_with_config(self, mock_find):
        mock_find.return_value = {"net": _FakeNetworkProtocol}
        inst = NetworkProtocolFactory.create("net", config={"a": 1})
        self.assertEqual(inst.config, {"a": 1})


class TestBinaryDataHandlerProtocolFactory(unittest.TestCase):
    @patch("hivemind_plugin_manager.find_plugins")
    def test_get_class(self, mock_find):
        mock_find.return_value = {"bin": _FakeBinaryProtocol}
        self.assertIs(
            BinaryDataHandlerProtocolFactory.get_class("bin"), _FakeBinaryProtocol
        )

    @patch("hivemind_plugin_manager.find_plugins")
    def test_get_class_missing(self, mock_find):
        mock_find.return_value = {}
        with self.assertRaises(KeyError):
            BinaryDataHandlerProtocolFactory.get_class("bin")

    @patch("hivemind_plugin_manager.find_plugins")
    def test_create_defaults_empty_config(self, mock_find):
        mock_find.return_value = {"bin": _FakeBinaryProtocol}
        inst = BinaryDataHandlerProtocolFactory.create("bin")
        self.assertEqual(inst.config, {})


class TestFindPlugins(unittest.TestCase):
    @patch("hivemind_plugin_manager.entry_points")
    def test_find_plugins_specific_type(self, mock_iter):
        class _EP:
            name = "fake"
            def load(self):
                return _FakeLocalDB
        mock_iter.return_value = iter([_EP()])
        result = find_plugins(HiveMindPluginTypes.DATABASE)
        self.assertIn("fake", result)
        self.assertIs(result["fake"], _FakeLocalDB)

    @patch("hivemind_plugin_manager.entry_points")
    def test_find_plugins_string_type(self, mock_iter):
        mock_iter.return_value = iter([])
        result = find_plugins("hivemind.database")
        self.assertEqual(result, {})

    @patch("hivemind_plugin_manager.entry_points")
    def test_find_plugins_no_type_iterates_all(self, mock_iter):
        mock_iter.return_value = iter([])
        result = find_plugins()
        self.assertEqual(result, {})
        # called once per HiveMindPluginTypes member
        self.assertEqual(mock_iter.call_count, len(HiveMindPluginTypes))

    @patch("hivemind_plugin_manager.entry_points")
    def test_find_plugins_swallows_load_errors(self, mock_iter):
        find_plugins._errored = []  # reset

        class _BadEP:
            name = "bad"
            def load(self):
                raise RuntimeError("boom")
        mock_iter.return_value = iter([_BadEP()])
        result = find_plugins(HiveMindPluginTypes.DATABASE)
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
