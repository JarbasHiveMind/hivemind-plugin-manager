# Getting Started

## What Is HiveMind Plugin Manager?

HiveMind Plugin Manager (HPM) is the extension layer that lets the HiveMind ecosystem swap its
storage backend, agent integration, network transport, and binary data handling without changing
core code. Every implementation — whether a JSON file database, a WebSocket server, or an audio
handler — is a separate installable Python package that registers itself under a standardised
setuptools entry-point group. HPM discovers those entry points at runtime and exposes factory
classes so callers never need to hard-code import paths.

There are exactly four plugin types:

| Type | Entry-point group | What it does |
|---|---|---|
| `DATABASE` | `hivemind.database` | Stores and retrieves `Client` credentials |
| `AGENT_PROTOCOL` | `hivemind.agent.protocol` | Bridges HiveMind messages to an AI backend |
| `NETWORK_PROTOCOL` | `hivemind.network.protocol` | Transports `HiveMessage` objects over a wire |
| `BINARY_PROTOCOL` | `hivemind.binary.protocol` | Handles raw binary payloads (audio, images, files) |

Source: `hivemind_plugin_manager/__init__.py:10`

---

## Install

```bash
pip install hivemind-plugin-manager
```

Runtime dependencies pulled in automatically: `json_database`, `ovos-bus-client`, `ovos-utils`,
and `hivemind-bus-client` (via protocols).

---

## Verify Installation

```python
from hivemind_plugin_manager import find_plugins, HiveMindPluginTypes

# Returns a dict of {plugin_name: class} for every installed DB plugin
print(find_plugins(HiveMindPluginTypes.DATABASE))
```

If you have `hivemind-json-db-plugin` installed you will see something like:

```
{'hivemind-json-db-plugin': <class 'json_database.hpm.JsonDB'>}
```

---

## Hello-World Plugin (Database)

The fastest way to understand HPM is to write a trivial database plugin and register it.

### 1. Implement the abstract class

```python
# my_hpm_plugin/db.py
from typing import List, Iterable, Union
from hivemind_plugin_manager.database import AbstractDB, Client


class InMemoryDB(AbstractDB):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._store: List[Client] = []

    def add_item(self, client: Client) -> bool:
        for i, c in enumerate(self._store):
            if c.client_id == client.client_id:
                self._store[i] = client
                return True
        self._store.append(client)
        return True

    def search_by_value(self, key: str,
                        val: Union[str, bool, int, float]) -> List[Client]:
        return [c for c in self._store if getattr(c, key, None) == val]

    def __len__(self) -> int:
        return len(self._store)

    def __iter__(self) -> Iterable[Client]:
        return iter(self._store)
```

### 2. Register the entry point

In `setup.py` (or `pyproject.toml`):

```python
# setup.py
setup(
    name="my-hpm-plugin",
    ...
    entry_points={
        "hivemind.database": [
            "my-inmemory-db-plugin = my_hpm_plugin.db:InMemoryDB"
        ]
    }
)
```

### 3. Install and verify

```bash
pip install -e .
python -c "from hivemind_plugin_manager import find_plugins, HiveMindPluginTypes; print(find_plugins(HiveMindPluginTypes.DATABASE))"
# {'my-inmemory-db-plugin': <class 'my_hpm_plugin.db.InMemoryDB'>}
```

### 4. Instantiate via factory

```python
from hivemind_plugin_manager import DatabaseFactory

db = DatabaseFactory.create("my-inmemory-db-plugin", name="clients", subfolder="hivemind-core")
```

`DatabaseFactory.create` — `hivemind_plugin_manager/__init__.py:26`

---

## CLI Tool: `hpm`

After installation a `hpm` command is available (entry point registered in `setup.py:54`):

```bash
hpm list database          # list installed database plugins
hpm get database           # show currently configured database plugin
hpm set database hivemind-json-db-plugin   # activate a plugin
hpm show-config            # dump full server.json
```

Config is stored in `~/.config/hivemind-core/server.json` (XDG).
See `hivemind_plugin_manager/tui.py` for full CLI implementation.
