import abc
import dataclasses
from dataclasses import dataclass
from typing import Dict, Any, Union, Optional

from ovos_bus_client import MessageBusClient
from ovos_utils.fakebus import FakeBus
from ovos_utils.log import LOG

from hivemind_bus_client.identity import NodeIdentity
from hivemind_core.database import ClientDatabase
from hivemind_core.protocol import HiveMindClientConnection


@dataclass
class _SubProtocol:
    """base class all protocols derive from"""
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional['HiveMindListenerProtocol'] = None

    @property
    def identity(self) -> NodeIdentity:
        return self.hm_protocol.identity

    @property
    def database(self) -> ClientDatabase:
        return self.hm_protocol.db

    @property
    def clients(self) -> Dict[str, HiveMindClientConnection]:
        return self.hm_protocol.clients


@dataclass
class AgentProtocol(_SubProtocol):
    """protocol to handle Message objects, the payload of HiveMessage objects"""
    bus: Union[FakeBus, MessageBusClient] = dataclasses.field(default_factory=FakeBus)
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional['HiveMindListenerProtocol'] = None


@dataclass
class NetworkProtocol(_SubProtocol):
    """protocol to transport HiveMessage objects around"""
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional['HiveMindListenerProtocol'] = None

    @abc.abstractmethod
    def run(self):
        pass


@dataclass
class BinaryDataHandlerProtocol(_SubProtocol):
    """protocol to handle Binary data HiveMessage objects"""
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    hm_protocol: Optional['HiveMindListenerProtocol'] = None
    agent_protocol: Optional[AgentProtocol] = None

    def handle_microphone_input(self, bin_data: bytes,
                                sample_rate: int,
                                sample_width: int,
                                client: HiveMindClientConnection):
        LOG.warning(f"Ignoring received binary audio input: {len(bin_data)} bytes at sample_rate: {sample_rate}")

    def handle_stt_transcribe_request(self, bin_data: bytes,
                                      sample_rate: int,
                                      sample_width: int,
                                      lang: str,
                                      client: HiveMindClientConnection):
        LOG.warning(f"Ignoring received binary STT input: {len(bin_data)} bytes")

    def handle_stt_handle_request(self, bin_data: bytes,
                                  sample_rate: int,
                                  sample_width: int,
                                  lang: str,
                                  client: HiveMindClientConnection):
        LOG.warning(f"Ignoring received binary STT input: {len(bin_data)} bytes")

    def handle_numpy_image(self, bin_data: bytes,
                           camera_id: str,
                           client: HiveMindClientConnection):
        LOG.warning(f"Ignoring received binary image: {len(bin_data)} bytes")

    def handle_receive_tts(self, bin_data: bytes,
                           utterance: str,
                           lang: str,
                           file_name: str,
                           client: HiveMindClientConnection):
        LOG.warning(f"Ignoring received binary TTS audio: {utterance} with {len(bin_data)} bytes")

    def handle_receive_file(self, bin_data: bytes,
                            file_name: str,
                            client: HiveMindClientConnection):
        LOG.warning(f"Ignoring received binary file: {file_name} with {len(bin_data)} bytes")
