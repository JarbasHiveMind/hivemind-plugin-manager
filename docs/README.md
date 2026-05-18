# HiveMind Plugin Manager — Documentation

HiveMind Plugin Manager (HPM) is the extension point system for the HiveMind ecosystem.
It defines four plugin types (database, agent protocol, network protocol, binary protocol),
discovers implementations registered via setuptools entry points, and provides factory classes
for instantiation.

---

## Who Should Read What

| You want to... | Start here |
|---|---|
| Install HPM and understand what it does | [Getting Started](getting-started.md) |
| Learn the concepts (plugin types, factories, lifecycle) | [Concepts](concepts.md) |
| Write a database plugin | [Database Plugin Guide](plugins/database.md) |
| Write an agent protocol plugin | [Agent Protocol Plugin Guide](plugins/agent-protocol.md) |
| Write a network protocol plugin | [Network Protocol Plugin Guide](plugins/network-protocol.md) |
| Write a binary data handler plugin | [Binary Protocol Plugin Guide](plugins/binary-protocol.md) |
| Look up every public class and function | [API Reference](api-reference.md) |
| Understand internals, error handling, identity, factory routing | [Advanced](advanced.md) |
| Contribute to this package | [Contributing](contributing.md) |

---

## Key Classes at a Glance

| Class | Plugin type | Source |
|---|---|---|
| `HiveMindPluginTypes` | enum of entry-point group names | `hivemind_plugin_manager/__init__.py:10` |
| `DatabaseFactory` | creates `AbstractDB` / `AbstractRemoteDB` instances | `hivemind_plugin_manager/__init__.py:17` |
| `AgentProtocolFactory` | creates `AgentProtocol` instances | `hivemind_plugin_manager/__init__.py:38` |
| `NetworkProtocolFactory` | creates `NetworkProtocol` instances | `hivemind_plugin_manager/__init__.py:56` |
| `BinaryDataHandlerProtocolFactory` | creates `BinaryDataHandlerProtocol` instances | `hivemind_plugin_manager/__init__.py:73` |
| `find_plugins()` | discovers all installed plugins for a type | `hivemind_plugin_manager/__init__.py:108` |
| `Client` | dataclass representing a connected device/credential | `hivemind_plugin_manager/database.py:35` |
| `AbstractDB` | base class for local database plugins | `hivemind_plugin_manager/database.py:158` |
| `AbstractRemoteDB` | base class for remote database plugins | `hivemind_plugin_manager/database.py:266` |
| `AgentProtocol` | base class for agent protocol plugins | `hivemind_plugin_manager/protocols.py:61` |
| `NetworkProtocol` | base class for network protocol plugins | `hivemind_plugin_manager/protocols.py:70` |
| `BinaryDataHandlerProtocol` | base class for binary protocol plugins | `hivemind_plugin_manager/protocols.py:88` |
| `ClientCallbacks` | dataclass of lifecycle hooks | `hivemind_plugin_manager/protocols.py:27` |
