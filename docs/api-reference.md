# API Reference

All public symbols exported from `hivemind_plugin_manager`.

---

## `hivemind_plugin_manager/__init__.py`

### `HiveMindPluginTypes`

```python
class HiveMindPluginTypes(str, enum.Enum):
    DATABASE         = "hivemind.database"           # line 14
    NETWORK_PROTOCOL = "hivemind.network.protocol"   # line 15
    AGENT_PROTOCOL   = "hivemind.agent.protocol"     # line 16
    BINARY_PROTOCOL  = "hivemind.binary.protocol"    # line 17
    POLICY           = "hivemind.policy"             # line 18
```

Source: `hivemind_plugin_manager/__init__.py:13`

Each value is the setuptools entry-point group string used for plugin discovery.

---

### `find_plugins(plug_type=None) -> dict`

Source: `hivemind_plugin_manager/__init__.py:136`

Discovers all installed plugins matching `plug_type`.

| Argument | Type | Behaviour |
|---|---|---|
| `None` | — | iterates every `HiveMindPluginTypes` group, merges results |
| `HiveMindPluginTypes` member | enum | iterates that one group |
| `str` | raw entry-point group name | iterates that group |

Returns `{plugin_name: class}`.

Entry-point load failures are caught, logged once, and skipped. Already-errored entry
points are stored in `find_plugins._errored` (a module-level list) to suppress repeated
log noise.

---

### `DatabaseFactory`

Source: `hivemind_plugin_manager/__init__.py:21`

#### `DatabaseFactory.get_class(plugin_name: str) -> Type[AbstractDB]`

Returns the class registered under `plugin_name` in `hivemind.database`.
Raises `KeyError` if not found. Source: `__init__.py:23`

#### `DatabaseFactory.create(plugin_name, name="clients", subfolder="hivemind-core", password=None, host=None, port=None) -> Union[AbstractDB, AbstractRemoteDB]`

Instantiates the plugin. If the class is a subclass of `AbstractRemoteDB`, `host` and
`port` are forwarded; otherwise they are dropped. Source: `__init__.py:30`

---

### `AgentProtocolFactory`

Source: `hivemind_plugin_manager/__init__.py:42`

#### `AgentProtocolFactory.get_class(plugin_name: str) -> Type[AgentProtocol]`

Raises `KeyError` if not found. Source: `__init__.py:44`

#### `AgentProtocolFactory.create(plugin_name, config=None, bus=None, hm_protocol=None) -> AgentProtocol`

`config` defaults to `{}` when `None`. Source: `__init__.py:51`

---

### `NetworkProtocolFactory`

Source: `hivemind_plugin_manager/__init__.py:60`

#### `NetworkProtocolFactory.get_class(plugin_name: str) -> Type[NetworkProtocol]`

Raises `KeyError` if not found. Source: `__init__.py:62`

#### `NetworkProtocolFactory.create(plugin_name, config=None, hm_protocol=None) -> NetworkProtocol`

`config` defaults to `{}` when `None`. Source: `__init__.py:69`

---

### `BinaryDataHandlerProtocolFactory`

Source: `hivemind_plugin_manager/__init__.py:77`

#### `BinaryDataHandlerProtocolFactory.get_class(plugin_name: str) -> Type[BinaryDataHandlerProtocol]`

Raises `KeyError` if not found. Source: `__init__.py:80`

#### `BinaryDataHandlerProtocolFactory.create(plugin_name, config=None, hm_protocol=None, agent_protocol=None) -> BinaryDataHandlerProtocol`

`config` defaults to `{}` when `None`. Source: `__init__.py:87`

---

### `PolicyPluginFactory`

Source: `hivemind_plugin_manager/__init__.py:96`

Discovers and instantiates policy plugins registered under `hivemind.policy`.
Consumed by `hivemind-core`'s chain runner when assembling `policy.chain` at startup.

#### `PolicyPluginFactory.get_class(plugin_name: str) -> Type[PolicyPlugin]`

Raises `KeyError` if not found. Source: `__init__.py:103`

#### `PolicyPluginFactory.create(plugin_name, config=None, hm_protocol=None) -> PolicyPlugin`

`config` defaults to `{}` when `None`. Source: `__init__.py:110`

---

## `hivemind_plugin_manager/database.py`

### `Client`

Source: `hivemind_plugin_manager/database.py:35`

```python
@dataclass
class Client:
    client_id: int           # required; must be int
    api_key: str             # required
    name: str = ""
    description: str = ""
    is_admin: bool = False   # must be bool
    last_seen: float = -1
    allowed_types: List[str] = field(default_factory=list)  # whitelist; empty = deny everything
    crypto_key: Optional[str] = None
    password: Optional[str] = None
    can_broadcast: bool = True
    can_escalate: bool = True
    can_propagate: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
```

`__post_init__` (`database.py:56`) enforces int/bool types. `allowed_types` is **not**
pre-populated — an empty list means deny-by-default. No automatic message types are
appended. See [HiveMind-core#85](https://github.com/JarbasHiveMind/HiveMind-core/issues/85).

**Deprecated property shims** — `skill_blacklist` and `intent_blacklist` are read/write
properties (`database.py:86`, `database.py:102`) backed by `Client.metadata`. Setting
them emits `DeprecationWarning`; new code should write to `Client.metadata` directly.
`message_blacklist` is not part of the data model: no property, no metadata
carry-forward. The constructor kwarg is accepted-and-discarded with a
`DeprecationWarning`, and `deserialize` strips the top-level key silently from on-disk
records.

**`metadata`** — free-form per-client dict for plugin-specific context. `deserialize`
migrates legacy top-level blacklist keys into `metadata` automatically (`database.py:153`)
and folds any other unknown top-level keys from older records the same way; an explicit
`metadata` key in the payload wins on collision. A non-dict `metadata` is coerced to
`{}` in `__post_init__` (`database.py:70`).

| Method | Signature | Source |
|---|---|---|
| `serialize()` | `-> str` (JSON) | `database.py:126` |
| `deserialize(data)` | `staticmethod(str \| dict) -> Client` | `database.py:136` |
| `__getitem__(key)` | `-> Any`; raises `KeyError` | `database.py:189` |
| `__setitem__(key, val)` | raises `ValueError` on unknown key | `database.py:206` |
| `__eq__(other)` | compares serialized JSON | `database.py:222` |
| `__repr__()` | returns `serialize()` | `database.py:240` |

---

### `cast2client(ret: ClientTypes) -> Optional[Union[Client, List[Client]]]`

Source: `hivemind_plugin_manager/database.py:16`

Normalises `None`, `Client`, JSON string, dict, or list into `Client` instances. Raises
`TypeError` for unsupported types.

---

### `AbstractDB`

Source: `hivemind_plugin_manager/database.py:300`

```python
@dataclass
class AbstractDB(abc.ABC):
    name: str = "clients"
    subfolder: str = "hivemind-core"
    password: Optional[str] = None

    SCHEMA_VERSION: ClassVar[int] = 2  # bumped 2024-05 for legacy-blacklist purge
```

| Method | Abstract | Signature | Source |
|---|---|---|---|
| `add_item` | yes | `(client: Client) -> bool` | `database.py:312` |
| `search_by_value` | yes | `(key: str, val) -> List[Client]` | `database.py:364` |
| `__len__` | yes | `() -> int` | `database.py:377` |
| `__iter__` | yes | `() -> Iterable[Client]` | `database.py:386` |
| `delete_item` | no | `(client) -> bool` — tombstone pattern | `database.py:323` |
| `update_item` | no | `(client) -> bool` — calls `add_item` | `database.py:337` |
| `replace_item` | no | `(old, new) -> bool` | `database.py:349` |
| `sync` | no | `()` — no-op | `database.py:394` |
| `migrate` | no | `(from_version: int) -> None` — schema migration hook (default no-op); backends override for their persisted on-disk shape | `database.py:405` |
| `commit` | no | `() -> True` | `database.py:420` |

See [Concepts → Database Schema Migration](concepts.md#database-schema-migration)
for the `SCHEMA_VERSION` + `migrate()` contract.

---

### `AbstractRemoteDB`

Source: `hivemind_plugin_manager/database.py:431`

Extends `AbstractDB` with:

```python
host: str = "127.0.0.1"
port: Optional[int] = None
```

Re-declares `add_item`, `search_by_value`, `__len__`, `__iter__` as abstract.

---

## `hivemind_plugin_manager/protocols.py`

### Module-level default callbacks

| Function | Signature | Behaviour | Source |
|---|---|---|---|
| `on_disconnect` | `(client) -> None` | logs debug | `protocols.py:13` |
| `on_connect` | `(client) -> None` | logs debug | `protocols.py:16` |
| `on_invalid_key` | `(client) -> None` | logs debug | `protocols.py:19` |
| `on_invalid_protocol` | `(client) -> None` | logs debug | `protocols.py:22` |

---

### `ClientCallbacks`

Source: `hivemind_plugin_manager/protocols.py:27`

```python
@dataclass
class ClientCallbacks:
    on_connect:          Callable[['HiveMindClientConnection'], None] = on_connect
    on_disconnect:       Callable[['HiveMindClientConnection'], None] = on_disconnect
    on_invalid_key:      Callable[['HiveMindClientConnection'], None] = on_invalid_key
    on_invalid_protocol: Callable[['HiveMindClientConnection'], None] = on_invalid_protocol
```

Defaults to the module-level no-op functions above.

---

### `_SubProtocol`

Source: `hivemind_plugin_manager/protocols.py:35`

Internal base dataclass. All three public protocol classes inherit from it.

Fields: `config: dict`, `hm_protocol: Optional[HiveMindListenerProtocol]`,
`callbacks: ClientCallbacks`.

Properties:

| Property | Returns | Source |
|---|---|---|
| `identity` | `hm_protocol.identity` or fresh `NodeIdentity()` | `protocols.py:41` |
| `database` | `hm_protocol.db` or `None` | `protocols.py:46` |
| `clients` | `hm_protocol.clients` or `{}` | `protocols.py:52` |

---

### `AgentProtocol`

Source: `hivemind_plugin_manager/protocols.py:61`

Fields: inherits `_SubProtocol` fields plus `bus: Union[FakeBus, MessageBusClient]`.

No abstract methods. Subclasses add their own message-handling methods.

---

### `NetworkProtocol`

Source: `hivemind_plugin_manager/protocols.py:70`

Additional property:

| Property | Returns | Source |
|---|---|---|
| `agent_protocol` | `hm_protocol.agent_protocol` or `None` | `protocols.py:77` |

Abstract method: `run(self)` — must block while serving. Source: `protocols.py:82`

---

### `BinaryDataHandlerProtocol`

Source: `hivemind_plugin_manager/protocols.py:88`

Additional field: `agent_protocol: Optional[AgentProtocol]`.

`__post_init__` (`protocols.py:96`) auto-populates `agent_protocol` from `hm_protocol` if
not provided explicitly.

All handler methods are concrete no-ops (log a warning). See
[Binary Protocol Plugin Guide](plugins/binary-protocol.md#handler-methods) for the full
list with signatures.

---

## `hivemind_plugin_manager/tui.py`

CLI entry point registered as `hpm` console script (`setup.py:54`).

| Command | Usage | Source |
|---|---|---|
| `hpm list <type>` | print installed plugins as JSON | `tui.py:84` |
| `hpm set <type> <name>` | write chosen plugin to `server.json` | `tui.py:97` |
| `hpm get <type>` | show currently configured plugin | `tui.py:117` |
| `hpm show-config` | dump full `server.json` | `tui.py:132` |

`<type>` accepts: `network`, `agent`, `binary`, `database`.

Config file: `~/.config/hivemind-core/server.json` (XDG).
`get_server_config()` — `tui.py:54` — creates the file with defaults on first run.
