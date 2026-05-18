# Binary Protocol Plugin Guide

A binary data handler protocol plugin processes raw binary `HiveMessage` payloads — audio
streams, STT requests, camera images, TTS audio, and arbitrary file transfers.

The base class provides **no-op implementations** of every handler so that a subclass only
needs to override the handlers it actually cares about.

---

## Base Class

```python
@dataclass
class BinaryDataHandlerProtocol(_SubProtocol):
    """protocol to handle Binary data HiveMessage objects"""
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional['HiveMindListenerProtocol'] = None
    agent_protocol: Optional['AgentProtocol'] = None
    callbacks: ClientCallbacks = dataclasses.field(default_factory=ClientCallbacks)
```

Source: `hivemind_plugin_manager/protocols.py:88`

---

## `__post_init__` Behaviour

```python
def __post_init__(self):
    if not self.agent_protocol and self.hm_protocol:
        self.agent_protocol = self.hm_protocol.agent_protocol
```

Source: `hivemind_plugin_manager/protocols.py:96`

If `agent_protocol` is not provided explicitly but `hm_protocol` is available, the binary
protocol inherits the agent protocol from it. An explicit `agent_protocol` kwarg always
wins.

---

## Constructor Signature

`BinaryDataHandlerProtocolFactory.create` passes:

```python
plugin(config=config, hm_protocol=hm_protocol, agent_protocol=agent_protocol)
```

Source: `hivemind_plugin_manager/__init__.py:88`

---

## Handler Methods

All handlers have no-op defaults that emit a `LOG.warning`. Override the ones you need.

### `handle_microphone_input`

```python
def handle_microphone_input(self, bin_data: bytes,
                            sample_rate: int,
                            sample_width: int,
                            client: 'HiveMindClientConnection'):
```

Source: `hivemind_plugin_manager/protocols.py:101`

Raw microphone audio from a satellite device. Typical action: forward to an STT engine.

### `handle_stt_transcribe_request`

```python
def handle_stt_transcribe_request(self, bin_data: bytes,
                                  sample_rate: int,
                                  sample_width: int,
                                  lang: str,
                                  client: 'HiveMindClientConnection'):
```

Source: `hivemind_plugin_manager/protocols.py:107`

Client requests transcription of audio and wants the text back.

### `handle_stt_handle_request`

```python
def handle_stt_handle_request(self, bin_data: bytes,
                              sample_rate: int,
                              sample_width: int,
                              lang: str,
                              client: 'HiveMindClientConnection'):
```

Source: `hivemind_plugin_manager/protocols.py:114`

Client requests transcription **and** intent handling of audio.

### `handle_numpy_image`

```python
def handle_numpy_image(self, bin_data: bytes,
                       camera_id: str,
                       client: 'HiveMindClientConnection'):
```

Source: `hivemind_plugin_manager/protocols.py:121`

Raw image bytes from a camera peripheral.

### `handle_receive_tts`

```python
def handle_receive_tts(self, bin_data: bytes,
                       utterance: str,
                       lang: str,
                       file_name: str,
                       client: 'HiveMindClientConnection'):
```

Source: `hivemind_plugin_manager/protocols.py:127`

TTS audio synthesised by the node, delivered to the plugin for forwarding or playback.

### `handle_receive_file`

```python
def handle_receive_file(self, bin_data: bytes,
                        file_name: str,
                        client: 'HiveMindClientConnection'):
```

Source: `hivemind_plugin_manager/protocols.py:133`

Arbitrary file received from a client.

---

## Minimal Implementation

```python
# my_package/binary.py
import io
import wave
from dataclasses import dataclass
from hivemind_plugin_manager.protocols import BinaryDataHandlerProtocol


@dataclass
class WavFileBinaryProtocol(BinaryDataHandlerProtocol):
    """Saves every microphone input chunk to a .wav file."""

    def handle_microphone_input(self, bin_data, sample_rate, sample_width, client):
        path = f"/tmp/hm_audio_{client.client_id}.wav"
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(bin_data)
```

---

## Entry-Point Registration

```python
entry_points={
    "hivemind.binary.protocol": [
        "my-wav-binary-plugin = my_package.binary:WavFileBinaryProtocol"
    ]
}
```

Group name must be exactly `"hivemind.binary.protocol"` —
`HiveMindPluginTypes.BINARY_PROTOCOL`. Source: `hivemind_plugin_manager/__init__.py:14`

---

## Factory Usage

```python
from hivemind_plugin_manager import BinaryDataHandlerProtocolFactory

handler = BinaryDataHandlerProtocolFactory.create(
    "my-wav-binary-plugin",
    config={},
    agent_protocol=my_agent,
)
```

`BinaryDataHandlerProtocolFactory.create` — `hivemind_plugin_manager/__init__.py:83`

---

## Known Implementations

| Package | Entry-point name |
|---|---|
| `hivemind-listener` | `hivemind-audio-binary-protocol-plugin` |
