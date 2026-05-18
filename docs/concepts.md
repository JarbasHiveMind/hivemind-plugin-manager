# Concepts

## Plugin Types

HPM defines four plugin types as string-valued enum members.

```python
class HiveMindPluginTypes(str, enum.Enum):
    DATABASE         = "hivemind.database"
    NETWORK_PROTOCOL = "hivemind.network.protocol"
    AGENT_PROTOCOL   = "hivemind.agent.protocol"
    BINARY_PROTOCOL  = "hivemind.binary.protocol"
```

Source: `hivemind_plugin_manager/__init__.py:10`

Each value is the setuptools entry-point group name that plugin packages must use.

---

## Entry Points

Plugins are ordinary Python packages. The only contract with HPM is a single line in the
package's `setup.py` (or `pyproject.toml`):

```ini
# pyproject.toml
[project.entry-points."hivemind.database"]
hivemind-json-db-plugin = "json_database.hpm:JsonDB"
```

or in `setup.py`:

```python
entry_points={
    "hivemind.database": [
        "hivemind-json-db-plugin = json_database.hpm:JsonDB"
    ]
}
```

The left-hand side of the `=` is the **plugin name** — the string callers pass to factories.
The right-hand side is the dotted import path to the class.

HPM itself does not ship any plugin implementation. It only defines the abstractions and
discovers whatever packages are installed in the current Python environment.

---

## Discovery: `find_plugins()`

```python
def find_plugins(plug_type: HiveMindPluginTypes = None) -> dict:
```

Source: `hivemind_plugin_manager/__init__.py:108`

`find_plugins` calls `_iter_entrypoints` (`__init__.py:92`) which tries
`importlib_metadata.entry_points` first and falls back to `pkg_resources` if
`importlib_metadata` is not available.

Return value is `{plugin_name: class}`.

Key behaviours:

- Passing `None` iterates **all four** entry-point groups and merges the results.
- Passing a string (e.g. `"hivemind.database"`) is also accepted.
- If a plugin's `load()` raises, the error is logged once and the entry point is skipped;
  the dict simply will not contain that name. This is the **error-swallowing** behaviour
  described in [Advanced](advanced.md).
- Already-errored entry points are tracked in `find_plugins._errored` to prevent log spam
  on repeated calls.

---

## Factories

Each plugin type has a corresponding factory with two class methods:

| Factory | `get_class(name)` returns | `create(name, ...)` returns |
|---|---|---|
| `DatabaseFactory` | `Type[AbstractDB]` | `AbstractDB` or `AbstractRemoteDB` |
| `AgentProtocolFactory` | `Type[AgentProtocol]` | `AgentProtocol` |
| `NetworkProtocolFactory` | `Type[NetworkProtocol]` | `NetworkProtocol` |
| `BinaryDataHandlerProtocolFactory` | `Type[BinaryDataHandlerProtocol]` | `BinaryDataHandlerProtocol` |

Source: `hivemind_plugin_manager/__init__.py:17–89`

`get_class` raises `KeyError` with a helpful message listing available plugins when the
requested name is not installed. `create` calls `get_class` then instantiates with the
appropriate kwargs.

### DatabaseFactory routing

`DatabaseFactory.create` checks whether the resolved class is a subclass of
`AbstractRemoteDB`. If it is, `host` and `port` are forwarded. If not, they are dropped.
This means callers can always pass all parameters safely.

```python
if issubclass(plugin, AbstractRemoteDB):
    return plugin(name=name, subfolder=subfolder, password=password, host=host, port=port)
return plugin(name=name, subfolder=subfolder, password=password)
```

Source: `hivemind_plugin_manager/__init__.py:33`

---

## Plugin Lifecycle

A plugin class is loaded once when `find_plugins()` is called. Factories instantiate a new
object per `create()` call. There is no HPM-managed teardown; cleanup is the plugin's
responsibility (e.g. close database connections in `__del__` or an explicit `close()` method
if the implementation adds one).

---

## The `Client` Dataclass

`Client` is the core data model — it represents a device or credential authorised to connect
to a HiveMind node.

```python
@dataclass
class Client:
    client_id: int
    api_key: str
    name: str = ""
    description: str = ""
    is_admin: bool = False
    last_seen: float = -1
    intent_blacklist: List[str] = field(default_factory=list)
    skill_blacklist: List[str] = field(default_factory=list)
    message_blacklist: List[str] = field(default_factory=list)
    allowed_types: List[str] = field(default_factory=list)
    crypto_key: Optional[str] = None
    password: Optional[str] = None
    can_broadcast: bool = True
    can_escalate: bool = True
    can_propagate: bool = True
```

Source: `hivemind_plugin_manager/database.py:35`

Notable rules enforced in `__post_init__` (`database.py:52`):

- `client_id` must be `int` — raises `ValueError` otherwise.
- `is_admin` must be `bool` — raises `ValueError` otherwise.
- `allowed_types` is populated with a default set of OVOS message types when empty.
- `"recognizer_loop:utterance"` is always appended to `allowed_types` even if the caller
  provides a custom list.

---

## `_SubProtocol` Base

All three protocol base classes (`AgentProtocol`, `NetworkProtocol`,
`BinaryDataHandlerProtocol`) inherit from `_SubProtocol` (`protocols.py:35`), which
provides three convenience properties:

| Property | Returns when `hm_protocol` is set | Returns when not set |
|---|---|---|
| `identity` | `hm_protocol.identity` (`NodeIdentity`) | fresh `NodeIdentity()` |
| `database` | `hm_protocol.db` | `None` |
| `clients` | `hm_protocol.clients` (dict) | `{}` |

Source: `hivemind_plugin_manager/protocols.py:35`

`hm_protocol` is a forward reference to `HiveMindListenerProtocol` (from `hivemind-core`).
It is `None` during unit tests and during construction when the protocol is passed as a
constructor argument to `HiveMindListenerProtocol` (which assigns `self` back afterward).
