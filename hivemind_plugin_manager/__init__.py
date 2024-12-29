import enum
from typing import Optional, Dict, Any, Union, Type

from ovos_utils.log import LOG

from hivemind_plugin_manager.database import AbstractDB, AbstractRemoteDB
from hivemind_plugin_manager.protocols import AgentProtocol, BinaryDataHandlerProtocol, NetworkProtocol


class HiveMindPluginTypes(str, enum.Enum):
    DATABASE = "hivemind.database"
    NETWORK_PROTOCOL = "hivemind.network.protocol"
    AGENT_PROTOCOL = "hivemind.agent.protocol"
    BINARY_PROTOCOL = "hivemind.binary.protocol"


class DatabaseFactory:
    @classmethod
    def get_class(cls, plugin_name: str) -> Type[AbstractDB]:
        plugins = find_plugins(HiveMindPluginTypes.DATABASE)
        if plugin_name not in plugins:
            raise KeyError(f"'{plugin_name}' not found. Available plugins: {list(plugins.keys())}")
        return plugins[plugin_name]

    @classmethod
    def create(cls, plugin_name: str,
               name: str = "clients",
               subfolder: str = "hivemind-core",
               password: Optional[str] = None,
               host: Optional[str] = None,
               port: Optional[int] = None) -> Union[AbstractRemoteDB, AbstractDB]:
        plugin = cls.get_class(plugin_name)
        if issubclass(plugin, AbstractRemoteDB):
            return plugin(name=name, subfolder=subfolder, password=password, host=host, port=port)
        return plugin(name=name, subfolder=subfolder, password=password)


class AgentProtocolFactory:
    @classmethod
    def get_class(cls, plugin_name: str) -> Type[AgentProtocol]:
        plugins = find_plugins(HiveMindPluginTypes.AGENT_PROTOCOL)
        if plugin_name not in plugins:
            raise KeyError(f"'{plugin_name}' not found. Available plugins: {list(plugins.keys())}")
        return plugins[plugin_name]

    @classmethod
    def create(cls, plugin_name: str,
               config: Optional[Dict[str, Any]] = None,
               bus: Optional[Union['FakeBus', 'MessageBusClient']] = None,
               hm_protocol: Optional['HiveMindListenerProtocol'] = None) -> AgentProtocol:
        config = config or {}
        plugin = cls.get_class(plugin_name)
        return plugin(config=config, bus=bus, hm_protocol=hm_protocol)


class NetworkProtocolFactory:
    @classmethod
    def get_class(cls, plugin_name: str) -> Type[NetworkProtocol]:
        plugins = find_plugins(HiveMindPluginTypes.NETWORK_PROTOCOL)
        if plugin_name not in plugins:
            raise KeyError(f"'{plugin_name}' not found. Available plugins: {list(plugins.keys())}")
        return plugins[plugin_name]

    @classmethod
    def create(cls, plugin_name: str,
               config: Optional[Dict[str, Any]] = None,
               hm_protocol: Optional['HiveMindListenerProtocol'] = None) -> NetworkProtocol:
        config = config or {}
        plugin = cls.get_class(plugin_name)
        return plugin(config=config, hm_protocol=hm_protocol)


class BinaryDataHandlerProtocolFactory:

    @classmethod
    def get_class(cls, plugin_name: str) -> Type[BinaryDataHandlerProtocol]:
        plugins = find_plugins(HiveMindPluginTypes.BINARY_PROTOCOL)
        if plugin_name not in plugins:
            raise KeyError(f"'{plugin_name}' not found. Available plugins: {list(plugins.keys())}")
        return plugins[plugin_name]

    @classmethod
    def create(cls, plugin_name: str,
               config: Optional[Dict[str, Any]] = None,
               hm_protocol: Optional['HiveMindListenerProtocol'] = None,
               agent_protocol: Optional['AgentProtocol'] = None) -> BinaryDataHandlerProtocol:
        config = config or {}
        plugin = cls.get_class(plugin_name)
        return plugin(config=config, hm_protocol=hm_protocol, agent_protocol=agent_protocol)


def _iter_entrypoints(plug_type: Optional[str]):
    """
    Return an iterator containing all entrypoints of the requested type
    @param plug_type: entrypoint name to load
    @return: iterator of all entrypoints
    """
    try:
        from importlib_metadata import entry_points
        for entry_point in entry_points(group=plug_type):
            yield entry_point
    except ImportError:
        import pkg_resources
        for entry_point in pkg_resources.iter_entry_points(plug_type):
            yield entry_point


def find_plugins(plug_type: HiveMindPluginTypes = None) -> dict:
    """
    Finds all plugins matching specific entrypoint type.

    Arguments:
        plug_type (str): plugin entrypoint string to retrieve

    Returns:
        dict mapping plugin names to plugin entrypoints
    """
    entrypoints = {}
    if not plug_type:
        plugs = list(HiveMindPluginTypes)
    elif isinstance(plug_type, str):
        plugs = [plug_type]
    else:
        plugs = plug_type
    for plug in plugs:
        for entry_point in _iter_entrypoints(plug):
            try:
                entrypoints[entry_point.name] = entry_point.load()
                if entry_point.name not in entrypoints:
                    LOG.debug(f"Loaded plugin entry point {entry_point.name}")
            except Exception as e:
                if entry_point not in find_plugins._errored:
                    find_plugins._errored.append(entry_point)
                    # NOTE: this runs in a loop inside skills manager, this would endlessly spam logs
                    LOG.error(f"Failed to load plugin entry point {entry_point}: "
                              f"{e}")
    return entrypoints


find_plugins._errored = []

if __name__ == "__main__":
    print(find_plugins(HiveMindPluginTypes.DATABASE))
    # {'hivemind-json-db-plugin': <class 'json_database.hpm.JsonDB'>,
    # 'hivemind-sqlite-db-plugin': <class 'hivemind_sqlite_database.SQLiteDB'>,
    # 'hivemind-redis-db-plugin': <class 'hivemind_redis_database.RedisDB'>}
    print(find_plugins(HiveMindPluginTypes.NETWORK_PROTOCOL))
    # {'hivemind-websocket-plugin': <class 'hivemind_websocket_protocol.HiveMindWebsocketProtocol'>}
    print(find_plugins(HiveMindPluginTypes.AGENT_PROTOCOL))
    # {'hivemind-ovos-agent-plugin': <class 'ovos_bus_client.hpm.OVOSProtocol'>,
    # 'hivemind-persona-agent-plugin': <class 'ovos_persona.hpm.PersonaProtocol'>}}
    print(find_plugins(HiveMindPluginTypes.BINARY_PROTOCOL))
    # {'hivemind-audio-binary-protocol-plugin': <class 'hivemind_listener.protocol.AudioBinaryProtocol'>}
