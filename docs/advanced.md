# Advanced Topics

## Internals of `find_plugins`

```python
def find_plugins(plug_type: HiveMindPluginTypes = None) -> dict:
```

Source: `hivemind_plugin_manager/__init__.py:108`

### Entry-point iteration

`_iter_entrypoints(plug_type)` (`__init__.py:92`) tries `importlib_metadata.entry_points`
first. If `importlib_metadata` is not installed it falls back to
`pkg_resources.iter_entry_points`. This keeps HPM compatible with older Python environments
where `importlib.metadata` is absent or incomplete.

### Error swallowing

When an entry point's `.load()` raises any exception:

1. The entry point is appended to `find_plugins._errored` (a module-level list initialised
   to `[]` at `__init__.py:140`).
2. `LOG.error` is called **once** for that entry point.
3. On subsequent calls the entry point is silently skipped (it stays in `_errored`).

This prevents log spam when `find_plugins` is called repeatedly in a tight loop (e.g. from
a skills manager). The trade-off is that a broken plugin is invisible after the first
error. If you are debugging a missing plugin, reset the list:

```python
from hivemind_plugin_manager import find_plugins
find_plugins._errored = []
result = find_plugins()   # errors will surface again
```

### No caching

`find_plugins` does **not** cache results. Every call re-iterates entry points. For
performance-sensitive startup code, call it once and hold the returned dict.

---

## How `DatabaseFactory` Routes Local vs Remote

```python
if issubclass(plugin, AbstractRemoteDB):
    return plugin(name=name, subfolder=subfolder, password=password, host=host, port=port)
return plugin(name=name, subfolder=subfolder, password=password)
```

Source: `hivemind_plugin_manager/__init__.py:33`

The factory uses `issubclass` against `AbstractRemoteDB` at instantiation time. This means:

- Callers can always pass `host` and `port` — they are silently dropped for local plugins.
- A plugin that subclasses `AbstractRemoteDB` but ignores `host`/`port` in its own
  `__init__` is fine; the values are passed as kwargs and Python discards them if the
  signature includes `**kwargs` or if the dataclass field is declared with a default.
- A plugin that subclasses `AbstractDB` directly but needs a host must override
  `__post_init__` and read from `self.config` or environment variables instead.

---

## Identity and `NodeIdentity`

All protocol base classes expose an `.identity` property via `_SubProtocol`:

```python
@property
def identity(self) -> NodeIdentity:
    if not self.hm_protocol:
        return NodeIdentity()
    return self.hm_protocol.identity
```

Source: `hivemind_plugin_manager/protocols.py:41`

`NodeIdentity` comes from `hivemind-bus-client`. It holds the cryptographic identity (key
pair, name, UUID) of the current HiveMind node. A fresh `NodeIdentity()` is returned when
the protocol is not yet attached to a `HiveMindListenerProtocol` — this is the expected
state during unit tests and during early construction.

---

## The `hm_protocol` Circular Reference

When `hivemind-core` constructs a `HiveMindListenerProtocol` it accepts an
`agent_protocol` and a `binary_protocol` as constructor arguments. At that point
`hm_protocol` on both sub-protocols is `None`. After `HiveMindListenerProtocol.__init__`
runs, it assigns `self` back:

```python
# pseudocode from hivemind-core (not in this package)
self.agent_protocol.hm_protocol = self
self.binary_protocol.hm_protocol = self
```

This is why the protocols' `_SubProtocol` property helpers always guard with
`if not self.hm_protocol`. Plugin code that calls `self.database` or `self.clients` during
`__post_init__` will get `None` / `{}` — this is expected. Access them in handler methods
that are called after construction.

The comment in the source is explicit:

```
# usually AgentProtocol is passed as kwarg to hm_protocol
# and only then assigned in hm_protocol.__post_init__
```

Source: `hivemind_plugin_manager/protocols.py:65`

---

## `delete_item` Tombstone and `client_id` Reuse

`AbstractDB.delete_item` replaces a client's `api_key` with `"revoked"` rather than
removing the row:

```python
client = Client(client_id=client.client_id, api_key="revoked")
return self.update_item(client)
```

Source: `hivemind_plugin_manager/database.py:192`

The comment in the source explains the intent:

```
# leave the deleted entry in db, do not allow reuse of client_id !
```

When writing a database plugin you must honour this: your `add_item` must handle an
upsert (update-on-same-`client_id`) rather than always inserting. The test suite
verifies this behaviour at `tests/test_database.py:185`.

---

## Version Compatibility

HPM declares no version constraints on its plugin implementations. The entry-point contract
is purely structural: a class that subclasses the right abstract base and implements the
required methods is a valid plugin. HPM does not check class hierarchies at discovery
time — it only calls `entry_point.load()`. Type-safety is the plugin author's
responsibility.

The `_iter_entrypoints` fallback (`__init__.py:92`) ensures compatibility across Python
3.8+ environments where `importlib.metadata` behaviour differs.

---

## `allowed_types` Default Set

When a `Client` is created with an empty `allowed_types`, `__post_init__` populates it with:

```python
["recognizer_loop:utterance",
 "recognizer_loop:record_begin",
 "recognizer_loop:record_end",
 "recognizer_loop:audio_output_start",
 "recognizer_loop:audio_output_end",
 "recognizer_loop:b64_transcribe",
 "speak:b64_audio",
 "ovos.common_play.SEI.get.response"]
```

Source: `hivemind_plugin_manager/database.py:60`

Additionally, `"recognizer_loop:utterance"` is always appended even when the caller
provides a custom list (`database.py:68`). This ensures satellite devices can always send
utterances regardless of how `allowed_types` was configured.
