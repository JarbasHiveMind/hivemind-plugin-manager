import unittest
from unittest.mock import MagicMock

from hivemind_plugin_manager.protocols import (
    AgentProtocol,
    BinaryDataHandlerProtocol,
    ClientCallbacks,
    NetworkProtocol,
    on_connect,
    on_disconnect,
    on_invalid_key,
    on_invalid_protocol,
)


class TestModuleLevelCallbacks(unittest.TestCase):
    def test_callbacks_are_callable_and_return_none(self):
        # Each just logs and returns None; calling with a sentinel must not raise.
        sentinel = object()
        self.assertIsNone(on_connect(sentinel))
        self.assertIsNone(on_disconnect(sentinel))
        self.assertIsNone(on_invalid_key(sentinel))
        self.assertIsNone(on_invalid_protocol(sentinel))


class TestClientCallbacks(unittest.TestCase):
    def test_defaults_bound_to_module_functions(self):
        cb = ClientCallbacks()
        self.assertIs(cb.on_connect, on_connect)
        self.assertIs(cb.on_disconnect, on_disconnect)
        self.assertIs(cb.on_invalid_key, on_invalid_key)
        self.assertIs(cb.on_invalid_protocol, on_invalid_protocol)

    def test_custom_callbacks_assigned(self):
        f = lambda c: None  # noqa: E731
        cb = ClientCallbacks(on_connect=f)
        self.assertIs(cb.on_connect, f)


class TestAgentProtocol(unittest.TestCase):
    def test_defaults(self):
        p = AgentProtocol()
        self.assertEqual(p.config, {})
        self.assertIsNone(p.hm_protocol)
        self.assertIsInstance(p.callbacks, ClientCallbacks)

    def test_identity_returns_new_when_no_hm_protocol(self):
        p = AgentProtocol()
        # NodeIdentity instantiable; just ensure property doesn't blow up
        self.assertIsNotNone(p.identity)

    def test_identity_delegates_to_hm_protocol(self):
        sentinel = object()
        hm = MagicMock(identity=sentinel)
        p = AgentProtocol(hm_protocol=hm)
        self.assertIs(p.identity, sentinel)

    def test_database_none_when_no_hm_protocol(self):
        self.assertIsNone(AgentProtocol().database)

    def test_database_delegates_to_hm_protocol(self):
        sentinel = object()
        hm = MagicMock(db=sentinel)
        self.assertIs(AgentProtocol(hm_protocol=hm).database, sentinel)

    def test_clients_empty_when_no_hm_protocol(self):
        self.assertEqual(AgentProtocol().clients, {})

    def test_clients_delegates_to_hm_protocol(self):
        hm = MagicMock(clients={"a": 1})
        self.assertEqual(AgentProtocol(hm_protocol=hm).clients, {"a": 1})


class TestNetworkProtocol(unittest.TestCase):
    def test_agent_protocol_none_when_no_hm_protocol(self):
        # NetworkProtocol is abstract; use a concrete subclass.
        class _N(NetworkProtocol):
            def run(self): pass
        self.assertIsNone(_N().agent_protocol)

    def test_agent_protocol_delegates(self):
        class _N(NetworkProtocol):
            def run(self): pass
        sentinel = object()
        hm = MagicMock(agent_protocol=sentinel)
        self.assertIs(_N(hm_protocol=hm).agent_protocol, sentinel)


class TestBinaryDataHandlerProtocol(unittest.TestCase):
    def test_defaults(self):
        p = BinaryDataHandlerProtocol()
        self.assertEqual(p.config, {})
        self.assertIsNone(p.agent_protocol)

    def test_post_init_inherits_agent_protocol_from_hm(self):
        agent = object()
        hm = MagicMock(agent_protocol=agent)
        p = BinaryDataHandlerProtocol(hm_protocol=hm)
        self.assertIs(p.agent_protocol, agent)

    def test_post_init_does_not_overwrite_explicit_agent(self):
        explicit = object()
        other = object()
        hm = MagicMock(agent_protocol=other)
        p = BinaryDataHandlerProtocol(hm_protocol=hm, agent_protocol=explicit)
        self.assertIs(p.agent_protocol, explicit)

    def test_default_handlers_are_noops(self):
        p = BinaryDataHandlerProtocol()
        client = object()
        # Each handler just logs; calling must not raise.
        p.handle_microphone_input(b"x", 16000, 2, client)
        p.handle_stt_transcribe_request(b"x", 16000, 2, "en", client)
        p.handle_stt_handle_request(b"x", 16000, 2, "en", client)
        p.handle_numpy_image(b"x", "cam0", client)
        p.handle_receive_tts(b"x", "hi", "en", "out.wav", client)
        p.handle_receive_file(b"x", "out.bin", client)


if __name__ == "__main__":
    unittest.main()
