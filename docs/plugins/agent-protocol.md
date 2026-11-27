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

## Mandatory Abstract Method

Every agent protocol must implement `natural_language_query`:

```python
@abc.abstractmethod
def natural_language_query(self, utterance: str,
                           lang: str) -> Iterator[Optional[str]]:
    ...
```

Source: `hivemind_plugin_manager/protocols.py`

This is the seam that hivemind-core's **QUERY** and **CASCADE** message handlers consume.
It must be a generator that:

1. Yields zero or more `str` answer chunks — each chunk is the text of one spoken response.
2. Yields a final `None` sentinel to signal end-of-query.

Yielding `None` immediately (no chunks) means the agent has no answer; the node then
escalates the query upstream instead of stalling.

This streaming contract lets a satellite start speaking the first sentence while the
rest is still being generated. An LLM/persona agent yields sentences as the model produces
them; an OVOS agent yields each `speak` as it lands on the bus and `None` when the
utterance is fully handled.

## Minimal Implementation

```python
# my_package/agent.py
from dataclasses import dataclass
from typing import Dict, Any, Iterator, Optional

from hivemind_plugin_manager.protocols import AgentProtocol


@dataclass
class EchoAgentProtocol(AgentProtocol):
    """Echoes every utterance back (demo only)."""

    def natural_language_query(self, utterance: str,
                               lang: str) -> Iterator[Optional[str]]:
        # Yield the answer text, then None to signal completion.
        yield f"You said: {utterance}"
        yield None
```

For a real agent that connects to a message bus:

```python
@dataclass
class OVOSBridgeProtocol(AgentProtocol):
    def __post_init__(self):
        from ovos_bus_client import MessageBusClient
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port", 8181)
        self.bus = MessageBusClient(host=host, port=port)
        self.bus.run_in_thread()

    def natural_language_query(self, utterance: str,
                               lang: str) -> Iterator[Optional[str]]:
        import threading

        from ovos_bus_client.message import Message
        responses = []
        done = threading.Event()

        def on_speak(msg):
            responses.append(msg.data.get("utterance", ""))

        def on_complete(msg):
            done.set()

        self.bus.on("speak", on_speak)
        self.bus.on("mycroft.skill.handler.complete", on_complete)
        self.bus.emit(Message("recognizer_loop:utterance",
                               {"utterances": [utterance], "lang": lang}))
        done.wait(timeout=10)
        self.bus.remove("speak", on_speak)
        self.bus.remove("mycroft.skill.handler.complete", on_complete)
        for chunk in responses:
            yield chunk
        yield None
```

The exact additional methods available on `HiveMindListenerProtocol` are documented in
hivemind-core. HPM only defines the dataclass fields, `_SubProtocol` property helpers,
and the `natural_language_query` contract.

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
