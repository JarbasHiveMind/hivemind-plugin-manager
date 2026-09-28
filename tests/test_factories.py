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


class TestPluginIdIsRecorded(unittest.TestCase):
    """The entry-point name a plugin was loaded under reaches the instance.

    hivemind-core stamps the agent plugin's id into the Layer-1 ``destination``
    of an injected message, so the label a human reads names the agent that
    answered. Before this, the name was known only inside ``create`` and thrown
    away.
    """

    @patch("hivemind_plugin_manager.entry_points")
    def test_the_agent_factory_records_the_entry_point_name(self, mock_iter):
        class _EP:
            name = "hivemind-ovos-agent-plugin"
            def load(self):
                return _FakeAgentProtocol
        mock_iter.return_value = iter([_EP()])
        agent = AgentProtocolFactory.create("hivemind-ovos-agent-plugin")
        self.assertEqual(agent.plugin_id, "hivemind-ovos-agent-plugin")

    @patch("hivemind_plugin_manager.entry_points")
    def test_a_plugin_with_its_own_init_is_not_broken_by_the_label(self,
                                                                   mock_iter):
        # _FakeAgentProtocol defines __init__(config, bus, hm_protocol) and
        # accepts no plugin_id keyword. The label is set on the instance AFTER
        # construction for exactly this reason: passing it as a keyword would
        # raise TypeError on every third-party plugin shaped like this one.
        class _EP:
            name = "strict-init-plugin"
            def load(self):
                return _FakeAgentProtocol
        mock_iter.return_value = iter([_EP()])
        agent = AgentProtocolFactory.create("strict-init-plugin")
        self.assertEqual(agent.plugin_id, "strict-init-plugin")
        self.assertIsNone(agent.bus)

    @patch("hivemind_plugin_manager.entry_points")
    def test_the_network_factory_records_it_too(self, mock_iter):
        class _EP:
            name = "hivemind-websocket-protocol"
            def load(self):
                return _FakeNetworkProtocol
        mock_iter.return_value = iter([_EP()])
        net = NetworkProtocolFactory.create("hivemind-websocket-protocol")
        self.assertEqual(net.plugin_id, "hivemind-websocket-protocol")

    def test_a_plugin_built_directly_has_an_empty_id(self):
        # The default is the empty string, NOT a class name: a caller that
        # needs a label must handle the empty case rather than read a second
        # spelling of the same thing.
        from hivemind_plugin_manager.protocols import _SubProtocol
        self.assertEqual(_SubProtocol().plugin_id, "")

    @patch("hivemind_plugin_manager.entry_points")
    def test_a_slotted_plugin_does_not_raise(self, mock_iter):
        class _Slotted:
            __slots__ = ("config", "bus", "hm_protocol")
            def __init__(self, config=None, bus=None, hm_protocol=None):
                self.config, self.bus = config, bus
                self.hm_protocol = hm_protocol

        class _EP:
            name = "slotted"
            def load(self):
                return _Slotted
        mock_iter.return_value = iter([_EP()])
        agent = AgentProtocolFactory.create("slotted")  # must not raise
        self.assertFalse(hasattr(agent, "plugin_id"))


class TestPluginIdIsKeywordOnly(unittest.TestCase):
    """A positional call must bind exactly as it did before this field existed.

    Found by reviewer-b on JarbasHiveMind/hivemind-plugin-manager#65. A subclass
    that re-declares an inherited field keeps that field's inherited position, so
    a plain ``plugin_id`` on ``_SubProtocol`` lands in the MIDDLE of the subclass
    order: config, hm_protocol, callbacks, plugin_id, bus. A caller passing four
    positional arguments then hands its bus to ``plugin_id``, ``bus`` is built
    from the default factory, and the agent listens on a bus nobody else holds.
    No exception is raised; the agent simply never answers.
    """

    def test_a_four_positional_call_still_binds_the_bus(self):
        import dataclasses

        from hivemind_plugin_manager.protocols import AgentProtocol

        class _Agent(AgentProtocol):
            def natural_language_query(self, utterance, lang):
                yield None

        marker = object()
        from hivemind_plugin_manager.protocols import ClientCallbacks
        agent = _Agent({}, None, ClientCallbacks(), marker)
        self.assertIs(agent.bus, marker,
                      "the fourth positional argument must still be bus")
        self.assertEqual(agent.plugin_id, "")
        self.assertTrue(
            dataclasses.fields(AgentProtocol)[3].kw_only
            or [f.name for f in dataclasses.fields(AgentProtocol)
                if not f.kw_only][3] == "bus")

    def test_the_positional_order_excludes_plugin_id(self):
        import dataclasses

        from hivemind_plugin_manager.protocols import (
            AgentProtocol, BinaryDataHandlerProtocol)

        for cls, expected_last in ((AgentProtocol, "bus"),
                                   (BinaryDataHandlerProtocol,
                                    "agent_protocol")):
            positional = [f.name for f in dataclasses.fields(cls)
                          if not f.kw_only]
            self.assertNotIn("plugin_id", positional)
            self.assertEqual(positional[-1], expected_last)


class TestEveryFactoryRecordsTheName(unittest.TestCase):
    """All FOUR factories, not the two that had cells.

    reviewer-b measured the gap: with the label removed from the binary and
    policy call sites only, the suite stayed green, so half the change could
    revert unnoticed.
    """

    @patch("hivemind_plugin_manager.entry_points")
    def test_the_binary_factory_records_it(self, mock_iter):
        class _FakeBinary:
            def __init__(self, config=None, hm_protocol=None,
                         agent_protocol=None):
                self.config = config
                self.hm_protocol = hm_protocol
                self.agent_protocol = agent_protocol

        class _EP:
            name = "hivemind-audio-binary-protocol"
            def load(self):
                return _FakeBinary
        mock_iter.return_value = iter([_EP()])
        handler = BinaryDataHandlerProtocolFactory.create(
            "hivemind-audio-binary-protocol")
        self.assertEqual(handler.plugin_id, "hivemind-audio-binary-protocol")

    @patch("hivemind_plugin_manager.entry_points")
    def test_the_policy_factory_records_it(self, mock_iter):
        from hivemind_plugin_manager import PolicyPluginFactory

        class _FakePolicy:
            def __init__(self, config=None, hm_protocol=None):
                self.config = config
                self.hm_protocol = hm_protocol

        class _EP:
            name = "hivemind-ovos-agent-policy"
            def load(self):
                return _FakePolicy
        mock_iter.return_value = iter([_EP()])
        policy = PolicyPluginFactory.create("hivemind-ovos-agent-policy")
        self.assertEqual(policy.plugin_id, "hivemind-ovos-agent-policy")


if __name__ == "__main__":
    unittest.main()
