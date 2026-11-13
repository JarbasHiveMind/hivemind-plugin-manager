# HiveMind Plugin Manager

> **Full documentation:** [docs/README.md](docs/README.md)
> | [Getting Started](docs/getting-started.md)
> | [Concepts](docs/concepts.md)
> | [API Reference](docs/api-reference.md)
> | [Contributing](docs/contributing.md)

The **HiveMind Plugin Manager (HPM)** discovers, manages, and loads plugins for the HiveMind ecosystem. It defines plugin types for databases, network protocols, agent protocols, binary data handlers, and admission policies. HPM loads these plugins at runtime, so HiveMind agents can swap a backend without changing core code.

## Features

- **Plugin discovery**: find and load plugins of different types, including:
  - **Database plugins**: JSON, SQLite, and Redis.
  - **Agent protocol plugins**: OVOS and Persona, for communication between HiveMind agents.
  - **Network protocol plugins**: WebSockets, for distributed communication.
  - **Binary data handler plugins**: binary data communication, like audio data over HiveMind.

- **Plugin loading**: load a specific plugin by name, type, or from an available entry point.

- **Factories for plugin instantiation**: each plugin type (database, agent protocol, network protocol, binary protocol) has a factory that creates instances from a user configuration.


## Installation

```bash
pip install hivemind-plugin-manager
```

## Usage

The examples below show how to discover and load plugins, and how to create instances with the provided factories.

### Discovering plugins

Use the `find_plugins` function to discover all available plugins for a specific type:

```python
from hivemind_plugin_manager import find_plugins, HiveMindPluginTypes

# Find all database plugins
database_plugins = find_plugins(HiveMindPluginTypes.DATABASE)
print(database_plugins)

# Find all agent protocol plugins
agent_protocol_plugins = find_plugins(HiveMindPluginTypes.AGENT_PROTOCOL)
print(agent_protocol_plugins)
```

### Creating plugin instances

Each plugin type has a factory class that creates plugin instances with the required configuration.

#### Database Plugin Factory

```python
from hivemind_plugin_manager import DatabaseFactory

# Create an instance of a database plugin
db_instance = DatabaseFactory.create("hivemind-redis-db-plugin", password="Password1!", host="192.168.1.11", port=6789)
```

#### Agent Protocol Factory

```python
from hivemind_plugin_manager import AgentProtocolFactory

# Create an agent protocol instance
agent_protocol_instance = AgentProtocolFactory.create("hivemind-ovos-agent-plugin")
```

#### Network Protocol Factory

```python
from hivemind_plugin_manager import NetworkProtocolFactory

# Create a network protocol instance
network_protocol_instance = NetworkProtocolFactory.create("hivemind-websocket-plugin")
```

#### Binary Data Handler Protocol Factory

```python
from hivemind_plugin_manager import BinaryDataHandlerProtocolFactory

# Create a binary data handler protocol instance
binary_data_handler_instance = BinaryDataHandlerProtocolFactory.create("hivemind-audio-binary-protocol-plugin")
```

## Plugin Types

<div align="center">
  <img src="https://github.com/user-attachments/assets/160ebc5c-da61-4175-98dd-ade24bb218e3" alt="HiveMind Plugin Manager" width="800">
</div>

### 1. Database plugins

Supports multiple database systems:

- **JSON database**: stores data in JSON format ([hivemind-json-db-plugin](https://github.com/JarbasHiveMind/hivemind-json-db-plugin)).
- **SQLite database**: stores data locally with SQLite ([hivemind-sqlite-database](https://github.com/JarbasHiveMind/hivemind-sqlite-database)).
- **Redis database**: stores data with Redis, for distributed caching and storage ([hivemind-redis-database](https://github.com/JarbasHiveMind/hivemind-redis-database)).

### 2. Agent protocol plugins

Supports communication protocols for agents:

- **OVOS protocol**: connects to OVOS-based agents ([hivemind-ovos-agent-plugin](https://github.com/JarbasHiveMind/hivemind-ovos-agent-plugin)).
- **Persona protocol**: connects to the Persona framework.

### 3. Network protocol plugins

Supports network communication protocols:

- **WebSocket protocol**: real-time, bidirectional communication over WebSockets ([hivemind-websocket-protocol](https://github.com/JarbasHiveMind/hivemind-websocket-protocol)).

### 4. Binary data handler protocol plugins

Handles binary data, like audio, with a specialized protocol ([hivemind-audio-binary-protocol](https://github.com/JarbasHiveMind/hivemind-audio-binary-protocol)).

## Related projects

- [HiveMind-core](https://github.com/JarbasHiveMind/HiveMind-core): the HiveMind server that consumes these plugins.
- [hivemind-json-db-plugin](https://github.com/JarbasHiveMind/hivemind-json-db-plugin): database plugin for JSON.
- [hivemind-sqlite-database](https://github.com/JarbasHiveMind/hivemind-sqlite-database): database plugin for SQLite.
- [hivemind-redis-database](https://github.com/JarbasHiveMind/hivemind-redis-database): database plugin for Redis.
- [hivemind-ovos-agent-plugin](https://github.com/JarbasHiveMind/hivemind-ovos-agent-plugin): agent protocol plugin for OVOS.
- [hivemind-websocket-protocol](https://github.com/JarbasHiveMind/hivemind-websocket-protocol): network protocol plugin for WebSockets.
- [hivemind-audio-binary-protocol](https://github.com/JarbasHiveMind/hivemind-audio-binary-protocol): binary protocol plugin for audio.

## License

See [LICENSE.md](LICENSE.md).
