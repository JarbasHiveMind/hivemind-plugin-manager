"""E2E: manager-resolved plugins interoperating inside a hivescope hive.

``hivemind_plugin_manager`` is the plugin seam of the HiveMind stack: every
factory here is what ``hivemind-core`` calls at boot to assemble a hub from
entry points. These tests prove that seam end to end with **real published
plugins** (no stand-ins registered by this repo):

* every plugin family (database / network / agent / binary / policy) resolves
  through its factory from the ``hivemind.*`` entry-point groups, and the
  resolved classes honour the ABC contracts defined in this package;
* a hivescope ``MasterNode`` whose client database is a **factory-loaded**
  ``hivemind-json-db-plugin`` (via ``DatabaseFactory``) admits a satellite:
  the full handshake + crypto + whitelist-ACL admission path runs against
  rows persisted by the real plugin;
* a **factory-loaded** policy plugin (``hivemind-message-type-acl-policy``)
  reviews live topology traffic and produces the expected allow/deny
  verdicts using this package's ``Verdict`` primitives.

The provider packages are pulled in by the ``[e2e]`` extra; hivescope drives
the topology fully in-process.
"""
import inspect
from typing import List, Optional

import pytest
from ovos_bus_client.message import Message

from hivemind_plugin_manager import (
    AgentProtocol,
    AgentProtocolFactory,
    BinaryDataHandlerProtocol,
    BinaryDataHandlerProtocolFactory,
    DatabaseFactory,
    HiveMindPluginTypes,
    NetworkProtocol,
    NetworkProtocolFactory,
    PolicyPlugin,
    PolicyPluginFactory,
    Verdict,
    find_plugins,
)
from hivemind_plugin_manager.database import AbstractDB

from hivemind_bus_client.message import HiveMessage, HiveMessageType
from hivescope.assertions import assert_bus_message_routed, assert_handshake_complete
from hivescope.topology import TopologyBuilder


# Canonical published plugin per family — installed via the [e2e] extra.
CANONICAL_PLUGINS = {
    HiveMindPluginTypes.DATABASE: "hivemind-json-db-plugin",
    HiveMindPluginTypes.NETWORK_PROTOCOL: "hivemind-websocket-plugin",
    HiveMindPluginTypes.AGENT_PROTOCOL: "hivemind-ovos-agent-plugin",
    HiveMindPluginTypes.BINARY_PROTOCOL: "hivemind-audio-binary-protocol-plugin",
    HiveMindPluginTypes.POLICY: "hivemind-message-type-acl-policy",
}

FACTORY_AND_ABC = {
    HiveMindPluginTypes.DATABASE: (DatabaseFactory, AbstractDB),
    HiveMindPluginTypes.NETWORK_PROTOCOL: (NetworkProtocolFactory, NetworkProtocol),
    HiveMindPluginTypes.AGENT_PROTOCOL: (AgentProtocolFactory, AgentProtocol),
    HiveMindPluginTypes.BINARY_PROTOCOL: (BinaryDataHandlerProtocolFactory,
                                          BinaryDataHandlerProtocol),
    HiveMindPluginTypes.POLICY: (PolicyPluginFactory, PolicyPlugin),
}


class PluginBackedClientDatabase:
    """The ``ClientDatabase`` surface hivemind-core exposes to the listener
    protocol, backed by a **factory-resolved** database plugin.

    Mirrors ``hivemind_core.database.ClientDatabase`` but is constructed
    through ``DatabaseFactory`` directly, so the object under test is this
    package's resolution path, and adds the ``can_*`` flag kwargs hivescope's
    ``register_satellite`` passes through.
    """

    def __init__(self, plugin_name: str, **db_kwargs):
        self.db: AbstractDB = DatabaseFactory.create(plugin_name, **db_kwargs)

    # --- write API (hivescope register_satellite calls this) ---

    def add_client(self,
                   name: str,
                   key: str = "",
                   admin: bool = False,
                   allowed_types: Optional[List[str]] = None,
                   crypto_key: Optional[str] = None,
                   password: Optional[str] = None,
                   can_escalate: bool = True,
                   can_propagate: bool = True,
                   can_broadcast: bool = True,
                   intent_blacklist: Optional[List[str]] = None,
                   skill_blacklist: Optional[List[str]] = None,
                   message_blacklist: Optional[List[str]] = None) -> bool:
        from hivemind_plugin_manager.database import Client
        if crypto_key is not None:
            crypto_key = crypto_key[:16]
        metadata = {}
        if skill_blacklist:
            metadata["skill_blacklist"] = list(skill_blacklist)
        if intent_blacklist:
            metadata["intent_blacklist"] = list(intent_blacklist)
        client = Client(
            api_key=key,
            name=name,
            client_id=len(self.db) + 1,
            is_admin=admin,
            allowed_types=allowed_types or [],
            crypto_key=crypto_key,
            password=password,
            can_escalate=can_escalate,
            can_propagate=can_propagate,
            can_broadcast=can_broadcast,
            metadata=metadata,
        )
        ok = self.db.add_item(client)
        # persist — the real consumer (hivemind-core CLI) uses the
        # ClientDatabase as a context manager and commits on __exit__
        self.db.commit()
        return ok

    def update_item(self, client) -> bool:
        return self.db.update_item(client)

    # --- read API (admission hot path) ---

    def get_client_by_api_key(self, api_key: str):
        found = self.db.search_by_value("api_key", api_key)
        return found[0] if found else None

    def get_client_by_id(self, client_id: int):
        return self.db.get_client_by_id(client_id)

    def total_clients(self) -> int:
        return len(self.db)

    def sync(self):
        self.db.sync()

    def __iter__(self):
        yield from self.db

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        self.db.commit()


@pytest.fixture
def isolated_xdg(tmp_path, monkeypatch):
    """Point XDG dirs at a tmp dir so the json db plugin writes there."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path


# ---------------------------------------------------------------------------
# 1. every plugin family resolves through the manager
# ---------------------------------------------------------------------------

class TestFactoryResolution:

    @pytest.mark.parametrize("family", list(CANONICAL_PLUGINS))
    def test_family_resolves_and_honours_contract(self, family):
        plugin_name = CANONICAL_PLUGINS[family]
        factory, abc_cls = FACTORY_AND_ABC[family]

        plugins = find_plugins(family)
        assert plugin_name in plugins, (
            f"{plugin_name} not registered under {family.value}; "
            f"found: {list(plugins)}"
        )

        clazz = factory.get_class(plugin_name)
        assert inspect.isclass(clazz)
        assert issubclass(clazz, abc_cls), (
            f"{clazz.__name__} does not implement {abc_cls.__name__}"
        )

    def test_unknown_plugin_raises_keyerror(self):
        with pytest.raises(KeyError):
            DatabaseFactory.get_class("no-such-plugin")


# ---------------------------------------------------------------------------
# 2. a MasterNode built on a factory-loaded database admits a satellite
# ---------------------------------------------------------------------------

class TestFactoryLoadedTopology:

    def test_satellite_admitted_against_factory_loaded_db(self, isolated_xdg):
        db = PluginBackedClientDatabase("hivemind-json-db-plugin",
                                        name="clients",
                                        subfolder="hivemind-e2e")

        b = TopologyBuilder()
        m = b.add_master("M0", db=db)
        s = b.add_satellite("S0", upstream=m,
                            allowed_types=["test.ping"])
        try:
            b.start_all()

            # handshake + crypto completed against rows served by the plugin
            assert_handshake_complete(m, s)
            assert len(m.connected_peers()) == 1

            # the registration row was persisted by the REAL plugin
            row = db.get_client_by_api_key(s.identity.access_key)
            assert row is not None
            assert row.allowed_types == ["test.ping"]
            json_files = list((isolated_xdg / "data").rglob("clients.json"))
            assert json_files, "json db plugin did not persist to disk"

            # whitelist-ACL admission passes for the allowed type
            s.send(HiveMessage(HiveMessageType.BUS,
                               payload=Message("test.ping", {"n": 1})))
            assert_bus_message_routed(m, count=1)
        finally:
            b.stop_all()

    def test_disallowed_type_not_routed(self, isolated_xdg):
        db = PluginBackedClientDatabase("hivemind-json-db-plugin",
                                        name="clients",
                                        subfolder="hivemind-e2e")

        b = TopologyBuilder()
        m = b.add_master("M0", db=db)
        s = b.add_satellite("S0", upstream=m,
                            allowed_types=["test.ping"])
        try:
            b.start_all()
            assert_handshake_complete(m, s)

            s.send(HiveMessage(HiveMessageType.BUS,
                               payload=Message("admin.command", {})))
            # deny-by-default: the type is outside the whitelist row the
            # factory-loaded db serves, so nothing reaches the agent bus
            m.agent_protocol.assert_injected("admin.command", count=0)
        finally:
            b.stop_all()


# ---------------------------------------------------------------------------
# 3. a factory-loaded policy plugin reviews live topology traffic
# ---------------------------------------------------------------------------

class TestFactoryLoadedPolicy:

    def test_policy_verdicts_on_live_connection(self, isolated_xdg):
        db = PluginBackedClientDatabase("hivemind-json-db-plugin",
                                        name="clients",
                                        subfolder="hivemind-e2e")

        b = TopologyBuilder()
        m = b.add_master("M0", db=db)
        s = b.add_satellite("S0", upstream=m,
                            allowed_types=["test.ping"])
        try:
            b.start_all()
            assert_handshake_complete(m, s)

            policy = PolicyPluginFactory.create(
                "hivemind-message-type-acl-policy",
                hm_protocol=m.hm_protocol,
            )
            assert isinstance(policy, PolicyPlugin)

            connection = m.hm_protocol.clients[s.peer]

            allowed = policy.review(Message("test.ping", {}), connection)
            assert isinstance(allowed, Verdict)
            assert not allowed.denied

            denied = policy.review(Message("admin.command", {}), connection)
            assert denied.denied
        finally:
            b.stop_all()
