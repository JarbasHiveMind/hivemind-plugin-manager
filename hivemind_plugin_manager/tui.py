import json
import os.path
from typing import List

import click
from hivemind_plugin_manager import find_plugins, HiveMindPluginTypes
from json_database import JsonStorageXDG
from ovos_utils.xdg_utils import xdg_config_home, xdg_data_home

_DEFAULT = {
    "agent_protocol": {"module": "hivemind-ovos-agent-plugin",
                       "hivemind-ovos-agent-plugin": {
                           "host": "127.0.0.1",
                           "port": 8181
                       }},
    "binary_protocol": {"module": None},
    "network_protocol": {"module": "hivemind-websocket-plugin",
                         "hivemind-websocket-plugin": {
                             "host": "0.0.0.0",
                             "port": 5678,
                             "ssl": False,
                             "cert_dir": f"{xdg_data_home()}/hivemind",
                             "cert_name": "hivemind"
                         }},
    "database": {"module": "hivemind-json-db-plugin",
                 "hivemind-json-db-plugin": {
                     "name": "clients",
                     "subfolder": "hivemind-core"
                 }}
}

mapping = {
    HiveMindPluginTypes.BINARY_PROTOCOL: "binary_protocol",
    HiveMindPluginTypes.AGENT_PROTOCOL: "agent_protocol",
    HiveMindPluginTypes.NETWORK_PROTOCOL: "network_protocol",
    HiveMindPluginTypes.DATABASE: "database"
}


def cast_to_enum(plugin_type: str) -> HiveMindPluginTypes:
    if plugin_type == "network":
        plugin_type = HiveMindPluginTypes.NETWORK_PROTOCOL
    elif plugin_type == "agent":
        plugin_type = HiveMindPluginTypes.AGENT_PROTOCOL
    elif plugin_type == "binary":
        plugin_type = HiveMindPluginTypes.BINARY_PROTOCOL
    elif plugin_type == "database":
        plugin_type = HiveMindPluginTypes.DATABASE
    else:
        raise ValueError("invalid plugin type")
    return plugin_type


def get_server_config() -> JsonStorageXDG:
    """from ~/.config/hivemind-core/server.json """
    db = JsonStorageXDG("server",
                        xdg_folder=xdg_config_home(),
                        subfolder="hivemind-core")
    # create file if it doesnt exist
    if not os.path.isfile(db.path):
        db.merge(_DEFAULT)
        db.store()
    # ensure no missing top level values
    for k in [_ for _ in _DEFAULT if _ not in db]:
        db[k] = _DEFAULT[k]
    return db


# Initialize the configuration
config = get_server_config()


def list_plugins(plugin_type: str) -> List[str]:
    """Find all plugins of the specified type."""
    return list(find_plugins(HiveMindPluginTypes(plugin_type)))


@click.group()
def cli():
    """A TUI for managing HiveMind configuration."""
    pass


@cli.command("list")
@click.argument("plugin_type", type=click.Choice(["network", "agent", "binary", "database"]))
def list_plugins_command(plugin_type):
    """List available plugins of the given type. Valid: "network", "agent", "binary", "database" """
    if plugin_type not in ["network", "agent", "binary", "database"]:
        click.echo(f"Invalid plugin type: {plugin_type}", err=True)
        return
    plugin_type = cast_to_enum(plugin_type)
    plugins = list_plugins(plugin_type)
    click.echo(json.dumps(plugins, indent=2))


@cli.command("set")
@click.argument("plugin_type", type=click.Choice(["network", "agent", "binary", "database"]))
@click.argument("plugin_name")
def set_plugin(plugin_type, plugin_name):
    """Set the plugin for a specific type. Valid: "network", "agent", "binary", "database" """
    if plugin_type not in ["network", "agent", "binary", "database"]:
        click.echo(f"Invalid plugin type: {plugin_type}", err=True)
        return

    plugin_type = cast_to_enum(plugin_type)

    available_plugins = list_plugins(plugin_type)
    if plugin_name not in available_plugins:
        click.echo(f"Plugin '{plugin_name}' not available for '{plugin_type}'.", err=True)
        return

    config[mapping[plugin_type]]["module"] = plugin_name
    config.store()
    click.echo(f"Set {plugin_type} to {plugin_name}.")


@cli.command("get")
@click.argument("plugin_type", type=click.Choice(["network", "agent", "binary", "database"]))
def get_plugin(plugin_type):
    """Get the current plugin for a specific type. Valid: "network", "agent", "binary", "database" """
    if plugin_type not in ["network", "agent", "binary", "database"]:
        click.echo(f"Invalid plugin type: {plugin_type}", err=True)
        return
    plugin_type = cast_to_enum(plugin_type)
    key = mapping[plugin_type]
    if key in config and "module" in config[key]:
        click.echo(config[plugin_type]["module"])
    else:
        click.echo(f"No plugin set for {plugin_type}.")


@cli.command("show-config")
def show_config():
    """Show the full configuration."""
    click.echo(json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    cli()
