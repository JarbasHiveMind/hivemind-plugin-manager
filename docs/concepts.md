# Concepts

## Plugin Types

HPM defines five plugin types as string-valued enum members.

```python
class HiveMindPluginTypes(str, enum.Enum):
    DATABASE         = "hivemind.database"
    NETWORK_PROTOCOL = "hivemind.network.protocol"
    AGENT_PROTOCOL   = "hivemind.agent.protocol"
    BINARY_PROTOCOL  = "hivemind.binary.protocol"
    POLICY           = "hivemind.policy"
```

Source: `hivemind_plugin_manager/__init__.py:13`

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

- Passing `None` iterates **all five** entry-point groups (database, agent protocol, network protocol, binary protocol, policy) and merges the results.
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
| `PolicyPluginFactory` | `Type[PolicyPlugin]` | `PolicyPlugin` |

Source: `hivemind_plugin_manager/__init__.py:21–115`

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
    allowed_types: List[str] = field(default_factory=list)  # admission whitelist; empty = deny everything
    crypto_key: Optional[str] = None
    password: Optional[str] = None
    can_broadcast: bool = True
    can_escalate: bool = True
    can_propagate: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
```

Source: `hivemind_plugin_manager/database.py:35`

Notable rules enforced in `__post_init__` (`database.py:56`):

- `client_id` must be `int` — raises `ValueError` otherwise.
- `is_admin` must be `bool` — raises `ValueError` otherwise.
- `allowed_types` is **not** pre-populated. An empty list means the client cannot inject
  any message type (deny-by-default). The consumer that enforces this (typically
  `hivemind-core`) decides how operators grant access — HPM only owns the data shape.
  See [HiveMind-core#85](https://github.com/JarbasHiveMind/HiveMind-core/issues/85)
  for the admission-chain design that consumes this field.

`skill_blacklist` and `intent_blacklist` are **deprecated property shims** (`database.py:86`,
`database.py:102`) that read and write `Client.metadata["skill_blacklist"]` /
`Client.metadata["intent_blacklist"]` transparently. Setting them emits
`DeprecationWarning`. `message_blacklist` was removed from the data model — it was
introduced 2024-12-20 (commit `94a2141`) alongside legitimate ACL work but contradicted
the deny-by-default whitelist model and never functioned as a real gate. No property,
no carry-forward into `metadata`.

**Legacy constructor kwargs** (`skill_blacklist`, `intent_blacklist`) are accepted via a
wrapped `__init__` (`database.py:249`) and auto-migrated into `metadata` with a
`DeprecationWarning`. `message_blacklist` is also accepted at the kwarg surface (so
already-shipped backends — notably the pre-release SQLite plugin's `_row_to_client` —
don't crash on partial HPM upgrades) but the value is **discarded** with a
`DeprecationWarning`. Net effect: callers can keep passing the kwarg during the
upgrade window, but the data is dropped.

### `metadata` — plugin-specific extension point

`metadata` is a free-form dict that plugins can use to attach arbitrary per-client
context (routing hints, auth metadata, feature flags, telemetry tags, etc.) without
adding new top-level fields to the core dataclass.

`Client.deserialize` (`database.py:135`) is forward-compatible with older records in two
ways:

- **Legacy blacklist fields** (`skill_blacklist`, `intent_blacklist`) found as top-level
  JSON keys are silently migrated into `metadata` with a `DeprecationWarning`, so
  existing on-disk JSON databases keep loading without manual migration. Source:
  `database.py:153`. **`message_blacklist`** top-level keys are dropped silently — the
  field is gone for good and the data is not carried forward.
- **Any other unknown top-level key** is folded into `metadata` so plugin-added fields
  do not break deserialization. Explicit `metadata` dict entries win on collision.

A non-dict `metadata` value in `__post_init__` is coerced to `{}` (`database.py:70`),
signalling an upstream serializer bug via a missing-key outcome rather than a crash.

---

## Database Schema Migration

`AbstractDB` declares a `SCHEMA_VERSION: ClassVar[int]` constant (currently
`2`) and a non-abstract `migrate(self, from_version: int)` hook
(`database.py:368`). The default implementation is a no-op; backends opt in
by overriding it.

**Contract for backend authors:**

1. Persist the current schema version somewhere backend-native — `PRAGMA
   user_version` for SQLite, a sentinel key (`hivemind:schema_version`) for
   Redis, a top-level `__schema_version__` field for JSON files, etc.
2. At backend init (typically `__post_init__`), read the persisted version;
   if it is lower than `AbstractDB.SCHEMA_VERSION`, call
   `self.migrate(from_version=stored)` and then write the new version.
3. `migrate()` MUST be **idempotent and crash-safe**. A partial migration
   interrupted by a crash must produce the same final state when re-run.

**Migration matrix:**

| from → to | What the backend must do |
|---|---|
| `1 → 2` | Move legacy top-level OVOS blacklist fields (`skill_blacklist`, `intent_blacklist`) into each `Client.metadata` dict (`setdefault` — never clobber an explicit metadata value), then drop the legacy storage. **`message_blacklist`** is dropped without carry-forward (the field was removed from the data model entirely; backends MAY still persist it in `metadata` if they like, but it is no longer a load-bearing key). |

The legacy field names map 1:1 to keys under `metadata` — this is what the
`Client.skill_blacklist` etc. property shims read from
(`database.py:87`–`140`).

### Partial-upgrade safety

HPM, the backends, and `hivemind-core` can be merged and released independently.
Every combination is supported during the upgrade window:

- **New HPM + old backends.** The wrapped `__init__` accepts every legacy kwarg
  (`skill_blacklist`, `intent_blacklist`, `message_blacklist`) so pre-release
  backends that pass those positionally don't crash. `skill_blacklist` and
  `intent_blacklist` migrate into `metadata` with a `DeprecationWarning`;
  `message_blacklist` is discarded with a `DeprecationWarning` (no
  carry-forward). `Client.deserialize` strips the same three keys from on-disk
  records the same way.
- **Old HPM + new backends.** Each backend gates its `migrate()` call on
  `getattr(AbstractDB, "SCHEMA_VERSION", 1)`, so if the constant is missing
  the backend treats the on-disk shape as already-at-target and skips
  migration. On-disk rows continue to carry the legacy keys; reads still
  succeed because the backend's `_row_to_client` path doesn't depend on the
  new contract.
- **Mixed backend versions.** Each backend tracks its own schema version
  natively (SQLite `PRAGMA user_version`, Redis sentinel key, JsonDB sibling
  file). Migrating one backend has no effect on the others.

The cost of this safety is that a `message_blacklist` value passed via the
constructor kwarg silently disappears, with only a `DeprecationWarning` to
flag it. Callers should stop passing the kwarg; it is no longer load-bearing.

---

Existing third-party backends that don't override `migrate()` continue to
work — they just won't clean up legacy on-disk shape. The
`@property` shims on `Client` ensure read-path code keeps functioning
regardless of whether migration has run.

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
