# Database Plugin Guide

Database plugins store and retrieve `Client` records — the credentials/permissions of every
device that connects to a HiveMind node. HPM ships no database implementation itself; it
defines the abstract contract that every implementation must satisfy.

---

## Choose Your Base Class

| Base class | Use when |
|---|---|
| `AbstractDB` | Storage is local (file, SQLite, in-memory) |
| `AbstractRemoteDB` | Storage requires a network connection (Redis, REST API, etc.) |

`AbstractRemoteDB` extends `AbstractDB` with `host` and `port` dataclass fields and
re-declares the same abstract methods so IDEs show the correct signature.

Sources:
- `AbstractDB` — `hivemind_plugin_manager/database.py:158`
- `AbstractRemoteDB` — `hivemind_plugin_manager/database.py:266`

---

## AbstractDB Contract

### Required (abstract) methods

```python
def add_item(self, client: Client) -> bool: ...
def search_by_value(self, key: str,
                    val: Union[str, bool, int, float]) -> List[Client]: ...
def __len__(self) -> int: ...
def __iter__(self) -> Iterable[Client]: ...
```

### Provided (concrete) methods — override only if needed

| Method | Default behaviour | Source |
|---|---|---|
| `delete_item(client)` | Replaces entry with `Client(client_id=..., api_key="revoked")` — **does not remove the row** | `database.py:181` |
| `update_item(client)` | Delegates to `add_item(client)` | `database.py:195` |
| `replace_item(old, new)` | Calls `delete_item(old)` then `add_item(new)` | `database.py:207` |
| `sync()` | No-op; override to reload from disk | `database.py:252` |
| `commit()` | Returns `True`; override to flush writes | `database.py:256` |

### Dataclass fields

```python
@dataclass
class AbstractDB(abc.ABC):
    name: str = "clients"
    subfolder: str = "hivemind-core"
    password: Optional[str] = None
```

`name` and `subfolder` map to XDG data paths in file-backed implementations.

---

## AbstractRemoteDB Contract

Same abstract methods as `AbstractDB`, plus:

```python
@dataclass
class AbstractRemoteDB(AbstractDB):
    host: str = "127.0.0.1"
    port: Optional[int] = None
    name: str = "clients"
    subfolder: str = "hivemind-core"
    password: Optional[str] = None
```

Source: `hivemind_plugin_manager/database.py:267`

`DatabaseFactory.create` detects `issubclass(plugin, AbstractRemoteDB)` and passes `host`
and `port` to the constructor. Source: `hivemind_plugin_manager/__init__.py:33`

---

## Concrete Walkthrough — Local Plugin

```python
# my_package/db.py
from dataclasses import dataclass, field
from typing import List, Iterable, Union
from hivemind_plugin_manager.database import AbstractDB, Client


@dataclass
class JsonFileDB(AbstractDB):
    """Minimal JSON-file-backed database."""
    # AbstractDB already provides: name, subfolder, password
    # Add your own fields here if needed.

    def __post_init__(self):
        import json, os
        from ovos_utils.xdg_utils import xdg_data_home
        self._path = os.path.join(
            xdg_data_home(), self.subfolder, f"{self.name}.json"
        )
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        try:
            with open(self._path) as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            raw = []
        self._data: List[Client] = [Client.deserialize(r) for r in raw]

    # --- required ---

    def add_item(self, client: Client) -> bool:
        for i, c in enumerate(self._data):
            if c.client_id == client.client_id:
                self._data[i] = client
                return self.commit()
        self._data.append(client)
        return self.commit()

    def search_by_value(self, key: str,
                        val: Union[str, bool, int, float]) -> List[Client]:
        return [c for c in self._data if getattr(c, key, None) == val]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterable[Client]:
        return iter(self._data)

    # --- optional overrides ---

    def commit(self) -> bool:
        import json
        with open(self._path, "w") as f:
            json.dump([c.__dict__ for c in self._data], f, indent=2)
        return True

    def sync(self):
        self.__post_init__()
```

---

## Concrete Walkthrough — Remote Plugin

```python
# my_package/remote_db.py
import redis
from dataclasses import dataclass
from typing import List, Iterable, Union
from hivemind_plugin_manager.database import AbstractRemoteDB, Client


@dataclass
class RedisDB(AbstractRemoteDB):
    # AbstractRemoteDB provides: host, port, name, subfolder, password

    def __post_init__(self):
        self._r = redis.Redis(
            host=self.host,
            port=self.port or 6379,
            password=self.password,
            decode_responses=True,
        )

    def add_item(self, client: Client) -> bool:
        self._r.hset(self.name, client.client_id, client.serialize())
        return True

    def search_by_value(self, key: str,
                        val: Union[str, bool, int, float]) -> List[Client]:
        return [c for c in self if getattr(c, key, None) == val]

    def __len__(self) -> int:
        return self._r.hlen(self.name)

    def __iter__(self) -> Iterable[Client]:
        for raw in self._r.hvals(self.name):
            yield Client.deserialize(raw)
```

---

## Entry-Point Registration

```python
# setup.py
entry_points={
    "hivemind.database": [
        "my-json-db-plugin = my_package.db:JsonFileDB",
        "my-redis-db-plugin = my_package.remote_db:RedisDB",
    ]
}
```

The entry-point group must be exactly `"hivemind.database"` — the value of
`HiveMindPluginTypes.DATABASE`. Source: `hivemind_plugin_manager/__init__.py:11`

---

## The `delete_item` Tombstone Pattern

`AbstractDB.delete_item` does **not** remove the row. It replaces the entry with a
tombstone:

```python
client = Client(client_id=client.client_id, api_key="revoked")
return self.update_item(client)
```

Source: `hivemind_plugin_manager/database.py:192`

This prevents `client_id` reuse. If your storage backend requires a true delete (e.g. you
have a unique constraint on `api_key`), override `delete_item` and implement the tombstone
yourself, or skip the tombstone and rely on your own ID-sequencing strategy.

---

## The `Client` Object

See [Concepts — The Client Dataclass](../concepts.md#the-client-dataclass) for the full
field listing. Useful helpers:

- `Client.serialize()` → JSON string — `database.py:71`
- `Client.deserialize(str | dict)` → `Client` — `database.py:81`
- `cast2client(value)` — converts `str`, `dict`, or `list` to `Client` / `List[Client]` — `database.py:15`

---

## Known Implementations

| Package | Entry-point name | Type |
|---|---|---|
| `hivemind-json-db-plugin` | `hivemind-json-db-plugin` | Local (`AbstractDB`) |
| `hivemind-sqlite-db-plugin` | `hivemind-sqlite-db-plugin` | Local (`AbstractDB`) |
| `hivemind-redis-db-plugin` | `hivemind-redis-db-plugin` | Remote (`AbstractRemoteDB`) |
