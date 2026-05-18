# Network Protocol Plugin Guide

A network protocol plugin is responsible for transporting `HiveMessage` objects between a
HiveMind node and its clients — for example over WebSockets, ZeroMQ, or a serial link.
It is the only plugin type that has an **abstract method** defined directly on the base class.

---

## Base Class

```python
@dataclass
class NetworkProtocol(_SubProtocol):
    """protocol to transport HiveMessage objects around"""
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional['HiveMindListenerProtocol'] = None
    callbacks: ClientCallbacks = dataclasses.field(default_factory=ClientCallbacks)

    @property
    def agent_protocol(self) -> Optional['AgentProtocol']:
        if not self.hm_protocol:
            return None
        return self.hm_protocol.agent_protocol

    @abc.abstractmethod
    def run(self):
        pass
```

Source: `hivemind_plugin_manager/protocols.py:70`

`NetworkProtocol` extends `_SubProtocol`, so `.identity`, `.database`, and `.clients` are
available via `hm_protocol`. It additionally exposes `.agent_protocol` as a shortcut to
`hm_protocol.agent_protocol`.

---

## The `run()` Method

`run()` is the single abstract method. It must block and serve connections. The caller
(typically `hivemind-core`) calls `run()` in a thread or process. When `run()` returns, the
server is considered stopped.

---

## Constructor Signature

`NetworkProtocolFactory.create` passes:

```python
plugin(config=config, hm_protocol=hm_protocol)
```

Source: `hivemind_plugin_manager/__init__.py:69`

| Parameter | Purpose |
|---|---|
| `config` | Dict with transport settings (host, port, SSL, etc.) |
| `hm_protocol` | Back-reference to the owning `HiveMindListenerProtocol` |

---

## Minimal Implementation

```python
# my_package/network.py
import socket
from dataclasses import dataclass
from hivemind_plugin_manager.protocols import NetworkProtocol


@dataclass
class TcpNetworkProtocol(NetworkProtocol):
    """Bare TCP server — for illustration only."""

    def run(self):
        host = self.config.get("host", "0.0.0.0")
        port = self.config.get("port", 5678)
        with socket.socket() as srv:
            srv.bind((host, port))
            srv.listen(5)
            while True:
                conn, addr = srv.accept()
                self._handle(conn, addr)

    def _handle(self, conn, addr):
        # read HiveMessage bytes, route via self.hm_protocol, send response
        pass
```

---

## Entry-Point Registration

```python
entry_points={
    "hivemind.network.protocol": [
        "my-tcp-plugin = my_package.network:TcpNetworkProtocol"
    ]
}
```

Group name must be exactly `"hivemind.network.protocol"` —
`HiveMindPluginTypes.NETWORK_PROTOCOL`. Source: `hivemind_plugin_manager/__init__.py:12`

---

## Factory Usage

```python
from hivemind_plugin_manager import NetworkProtocolFactory

server = NetworkProtocolFactory.create(
    "my-tcp-plugin",
    config={"host": "0.0.0.0", "port": 5678},
)
server.run()   # blocks
```

`NetworkProtocolFactory.create` — `hivemind_plugin_manager/__init__.py:64`

---

## Known Implementations

| Package | Entry-point name |
|---|---|
| `hivemind-websocket-protocol` | `hivemind-websocket-plugin` |
