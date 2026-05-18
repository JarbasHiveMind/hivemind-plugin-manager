# Agent Protocol Plugin Guide

An agent protocol plugin bridges HiveMind messages to an AI backend — for example routing
utterances to an OVOS message bus or to a local persona/LLM. HPM provides the abstract base
class; every concrete implementation is a separate package.

---

## Base Class

```python
@dataclass
class AgentProtocol(_SubProtocol):
    """protocol to handle Message objects, the payload of HiveMessage objects"""
    bus: Union[FakeBus, MessageBusClient] = dataclasses.field(default_factory=FakeBus)
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional['HiveMindListenerProtocol'] = None
    callbacks: ClientCallbacks = dataclasses.field(default_factory=ClientCallbacks)
```

Source: `hivemind_plugin_manager/protocols.py:61`

`AgentProtocol` extends `_SubProtocol` (`protocols.py:35`) which provides `.identity`,
`.database`, and `.clients` properties (see [Concepts](../concepts.md#_subprotocol-base)).

---

## Constructor Signature

```python
def __init__(self,
             config: Dict[str, Any] = None,
             bus: Union[FakeBus, MessageBusClient] = None,
             hm_protocol: HiveMindListenerProtocol = None):
```

`AgentProtocolFactory.create` passes these three kwargs — no others.
Source: `hivemind_plugin_manager/__init__.py:47`

| Parameter | Purpose |
|---|---|
| `config` | Plugin-specific configuration dict (e.g. host/port of the message bus) |
| `bus` | Pre-existing bus connection; factory passes `None` and lets the plugin create its own |
| `hm_protocol` | Back-reference to the owning `HiveMindListenerProtocol`; `None` during construction, assigned later |

---

## Minimal Implementation

```python
# my_package/agent.py
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union

from ovos_utils.fakebus import FakeBus
from ovos_bus_client import MessageBusClient
from hivemind_plugin_manager.protocols import AgentProtocol


@dataclass
class EchoAgentProtocol(AgentProtocol):
    """Echoes every utterance back as a spoken response (demo only)."""

    def __post_init__(self):
        # Connect to the bus if not provided
        if not self.bus or isinstance(self.bus, FakeBus):
            host = self.config.get("host", "127.0.0.1")
            port = self.config.get("port", 8181)
            self.bus = MessageBusClient(host=host, port=port)
            self.bus.run_in_thread()

    def handle_utterance(self, utterance: str, lang: str = "en-us",
                         client=None):
        """Called by HiveMindListenerProtocol for each recognised utterance."""
        self.bus.emit(
            Message("speak", {"utterance": f"You said: {utterance}"})
        )
```

The exact methods you override depend on what `HiveMindListenerProtocol` calls on the
agent protocol — refer to `hivemind-core` for the full interface. HPM only defines the
dataclass fields and the `_SubProtocol` property helpers.

---

## Entry-Point Registration

```python
entry_points={
    "hivemind.agent.protocol": [
        "my-echo-agent-plugin = my_package.agent:EchoAgentProtocol"
    ]
}
```

Group name must be exactly `"hivemind.agent.protocol"` —
`HiveMindPluginTypes.AGENT_PROTOCOL`. Source: `hivemind_plugin_manager/__init__.py:13`

---

## Factory Usage

```python
from hivemind_plugin_manager import AgentProtocolFactory

agent = AgentProtocolFactory.create(
    "my-echo-agent-plugin",
    config={"host": "127.0.0.1", "port": 8181},
)
```

`AgentProtocolFactory.create` — `hivemind_plugin_manager/__init__.py:47`

---

## `ClientCallbacks` Integration

`AgentProtocol` inherits a `callbacks: ClientCallbacks` field (`protocols.py:67`).
`ClientCallbacks` holds four callables invoked by `HiveMindListenerProtocol` at connection
lifecycle events:

```python
@dataclass
class ClientCallbacks:
    on_connect:          Callable[['HiveMindClientConnection'], None]
    on_disconnect:       Callable[['HiveMindClientConnection'], None]
    on_invalid_key:      Callable[['HiveMindClientConnection'], None]
    on_invalid_protocol: Callable[['HiveMindClientConnection'], None]
```

Source: `hivemind_plugin_manager/protocols.py:27`

Override in your plugin's `__post_init__` if you need to react to connections:

```python
def __post_init__(self):
    self.callbacks.on_connect = self._on_client_connected

def _on_client_connected(self, client):
    self.bus.emit(Message("hm.client.connected", {"client_id": client.client_id}))
```

---

## Known Implementations

| Package | Entry-point name |
|---|---|
| `ovos-bus-client` (hpm extra) | `hivemind-ovos-agent-plugin` |
| `ovos-persona` (hpm extra) | `hivemind-persona-agent-plugin` |
