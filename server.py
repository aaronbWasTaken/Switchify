#! /usr/local/bin/python3.9

import nxbt as _nxbt
import json as _json
import flask as _flask
import pygame as _pygame
import gamepad as _gamepad
import gamepad_manager as _gamepad_manager
from io import BytesIO
from typing import Optional, Any
from flask_cors import CORS as _CORS
from os import remove as remove_file

CONFIG_FILE = "config.json"

_pygame.init()
_nx: _nxbt.Nxbt = _nxbt.Nxbt()
_app: _flask.Flask = _flask.Flask(__name__)
_CORS(_app)

_saved_switches: dict[str, str] = {}
"""
EXAMPLE FOR _saved_switches
    {
        # Key is the bluetooth hardware id of the Nintendo Switch
        # Value is the Switch's alias 
        "12:34:56:78:9A:BC": "aaronbWasTaken's Nintendo Switch 2",
        "FE:DC:BA:98:76:54": "My Nintendo Switch Lite"
    }
"""
_saved_gamepads: dict[str, dict] = {}
"""
EXAMPLE FOR _saved_gamepads
    {
        # Key is same as gamepad's UUID
        "0123456789abcdef1011121314151617": {
            "name": "Blue XBOX One Controller", # Name in the web interface
            "color": (30, 40, 170), # RGB values of the gamepad in the web interface and on the switch
            "last_gamepad_id": None, # Never was connected so it's None
            "switch_mac_addess": "12:34:56:78:9A:BC"
        }
    }
"""
_gamepad_managers: dict[str, _gamepad_manager.GamepadManager] = {}
"""
EXAMPLE FOR _gamepad_managers
    {
        # Key is same as gamepad's UUID
        "050082795e040000200b000023050000": _gamepad_manager.GamepadManager(_nx, _gamepad.Gamepad(0))
    }
"""


### DEPENDENCY FUNCTIONS ###

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    ### THIS IS THE MOST JAVASCRIPT WAY OF DOING IT I ASSUME, THIS AINT GIVING A SHIT WHAT STRING YOU FEED IT XD
    hex_color = "".join(digit for digit in hex_color.upper() if digit in "0123456789ABCDEF")[:6].ljust(6, "0")
    return (
        int(hex_color[:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16)
    )

def rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#" + "".join(hex(channel)[2:].zfill(2) for channel in (r, g, b))

def fix_saved_gamepads() -> None:
    joystick_uuids: tuple[str] = tuple(
        _pygame.joystick.Joystick(i).get_guid()
        for i in range(_pygame.joystick.get_count())
    )

    for gamepad_uuid in _saved_gamepads:
        if gamepad_uuid in joystick_uuids:
            _saved_gamepads[gamepad_uuid]["last_gamepad_id"] = joystick_uuids.index(gamepad_uuid)
        

### GAMEPAD ENDPOINTS ###

@_app.route("/api/gamepads/<string:gamepad_uuid>")
def get_gamepad_by_uuid(gamepad_uuid: str) -> _flask.Response:
    _pygame.event.pump() # Ensures that all JOYSTICKADDED events are getting processed
    fix_saved_gamepads()

    if gamepad_uuid in _saved_gamepads:
        gamepad: dict[str, Any] = _saved_gamepads[gamepad_uuid]
        return _flask.jsonify({
            "uuid": gamepad_uuid,
            "name": gamepad["name"],
            "last_gamepad_id": gamepad["last_gamepad_id"],
            "connected": gamepad_uuid in _gamepad_managers,
            "switch_mac_address": gamepad["switch_mac_address"],
            "color": None if gamepad["color"] is None else rgb_to_hex(*gamepad["color"]),
            "available": (
                gamepad_uuid not in _gamepad_managers and
                gamepad["last_gamepad_id"] is not None and
                gamepad["last_gamepad_id"] < _pygame.joystick.get_count() and
                _pygame.joystick.Joystick(gamepad["last_gamepad_id"]).get_guid() == gamepad_uuid
            )
        })
    
    for i in range(_pygame.joystick.get_count()):
        joystick: _pygame.joystick.JoystickType = _pygame.joystick.Joystick(i)

        if joystick.get_guid() == gamepad_uuid:
            return _flask.jsonify({
                "color": None,
                "available": True,
                "connected": False,
                "last_gamepad_id": i,
                "uuid": gamepad_uuid,
                "switch_mac_address": None,
                "name": joystick.get_name()
            })
    
    return _flask.Response(f"No gamepad with UUID of '{gamepad_uuid}' found.", 404)

@_app.route("/api/gamepads")
def get_gamepads() -> _flask.Response:
    _pygame.event.pump() # Ensures that all JOYSTICKADDED events are getting processed
    fix_saved_gamepads()

    gamepads: list[dict[str, dict]] = []
    uuids: set[str] = set()

    for gamepad_uuid, gamepad in _saved_gamepads.items():
        my_gamepad: dict[str, Any] = {k: v for k, v in gamepad.items()}
        my_gamepad["uuid"] = gamepad_uuid
        my_gamepad["connected"] = gamepad_uuid in _gamepad_managers
        my_gamepad["available"] = (
            gamepad_uuid not in _gamepad_managers and
            gamepad["last_gamepad_id"] is not None and
            gamepad["last_gamepad_id"] < _pygame.joystick.get_count() and
            _pygame.joystick.Joystick(gamepad["last_gamepad_id"]).get_guid() == gamepad_uuid
        )
        if gamepad["color"] is not None:
            my_gamepad["color"] = rgb_to_hex(*gamepad["color"])
        else:
            my_gamepad["color"] = None

        gamepads.append(my_gamepad)
        uuids.add(gamepad_uuid)

    for i in range(_pygame.joystick.get_count()):
        joystick: _pygame.joystick.JoystickType = _pygame.joystick.Joystick(i)

        if joystick.get_guid() in uuids:
            continue

        gamepads.append({
            "color": None,
            "available": True,
            "connected": False,
            "last_gamepad_id": i,
            "switch_mac_address": None,
            "uuid": joystick.get_guid(),
            "name": joystick.get_name()
        })

    return _flask.jsonify(gamepads)

@_app.route("/api/gamepads/<string:gamepad_uuid>/connect")
def connect_gamepad(gamepad_uuid: str) -> _flask.Response:
    ### Major error handling
    if gamepad_uuid not in _saved_gamepads:
        return _flask.Response(f"No gamepad with UUID of '{gamepad_uuid}' found.", 404)
    
    if len(_nx.get_available_adapters()) <= len(_gamepad_managers):
        return _flask.Response("Not enough Bluteooth adapters.", 500)

    gamepad: dict[str, Any] = _saved_gamepads[gamepad_uuid]

    if (
        gamepad["last_gamepad_id"] is None or
        gamepad["last_gamepad_id"] >= _pygame.joystick.get_count() or
        _pygame.joystick.Joystick(gamepad["last_gamepad_id"]).get_guid() != gamepad_uuid
    ):
        return _flask.Response(f"Gamepad with UUID of {gamepad_uuid} is not available to connect." +
        "It may not be connected at all or already be connected to a switch.", 400)

    try:
        manager: _gamepad_manager.GamepadManager = _gamepad_manager.GamepadManager(
            _nx, 
            gamepad_uuid, 
            gamepad["color"],
            gamepad["switch_mac_address"],
            45 # Disconnect Timeout
        )
    except RuntimeError:
        return _flask.Response(f"No gamepad with UUID of '{gamepad_uuid}' found.", 404)
    

    ### Starting manager
    manager.start_manager()

    ### Store connection details
    _gamepad_managers[gamepad_uuid] = manager

    return get_gamepad_by_uuid(gamepad_uuid)

@_app.route("/api/gamepads/<string:gamepad_uuid>/disconnect")
def disconnect_gamepad(gamepad_uuid: str) -> _flask.Response:
    if gamepad_uuid in _gamepad_managers:
        _gamepad_managers[gamepad_uuid].stop_manager()
        del _gamepad_managers[gamepad_uuid]
        
        return get_gamepad_by_uuid(gamepad_uuid)
    
    return _flask.Response(f"No gamepad with UUID of '{gamepad_uuid}' found.", 404)

@_app.route("/api/gamepads/<string:gamepad_uuid>/set_config", methods=["POST"])
def set_gamepad_config(gamepad_uuid: str) -> _flask.Response:
    ### Get params from request
    data = _flask.request.get_json()

    if not isinstance(data, dict):
        return _flask.Response("Invalid JSON", 400)
    
    if not all((
        isinstance(data.get("name"), (str, type(None))),
        isinstance(data.get("color"), (str, type(None))),
        isinstance(data.get("switch_mac_address"), (str, type(None)))
    )):
        return _flask.Response("Parameters 'name', 'color' and 'switch_mac_address' must be null or of type string.", 400)
    
    if "color" in data and data["color"] is not None:
        data["color"] = hex_to_rgb(data["color"])

    ### Change gamepad config
    if gamepad_uuid in _saved_gamepads:
        if "name" in data:
            _saved_gamepads[gamepad_uuid]["name"] = data["name"]
        
        if "color" in data:
            _saved_gamepads[gamepad_uuid]["color"] = data["color"]
        
        if "switch_mac_address" in data:
            _saved_gamepads[gamepad_uuid]["switch_mac_address"] = data["switch_mac_address"]

        return get_gamepad_by_uuid(gamepad_uuid)
    
    ### Create gamepad config
    _pygame.event.pump()
    for gamepad_id in range(_pygame.joystick.get_count()):
        joystick: _pygame.joystick.JoystickType = _pygame.joystick.Joystick(gamepad_id)

        if joystick.get_guid() != gamepad_uuid:
            continue

        _saved_gamepads[gamepad_uuid] = {
            "color": data["color"],
            "last_gamepad_id": gamepad_id,
            "switch_mac_address": data["switch_mac_address"],
            "name": data["name"] if "name" in data else joystick.get_name()
        }

        return get_gamepad_by_uuid(gamepad_uuid)
    
    return _flask.Response(f"No gamepad with UUID of '{gamepad_uuid}' found.", 404)

@_app.route("/api/gamepads", methods=["DELETE"])
def delete_gamepad_configs() -> _flask.Response:
    _saved_gamepads = {}

    return _flask.Response("No Content", 204)

@_app.route("/api/gamepads/<string:gamepad_uuid>", methods=["DELETE"])
def delete_gamepad_config(gamepad_uuid: str) -> _flask.Response:
    if gamepad_uuid in _saved_gamepads:
        del _saved_gamepads[gamepad_uuid]

        return _flask.Response("No Content", 204)
    
    return _flask.Response(f"No gamepad with UUID of '{gamepad_uuid}' found.", 404)

@_app.route("/api/gamepads/<string:gamepad_uuid>/get_timeout")
def get_gamepad_timeout(gamepad_uuid: str) -> _flask.Response:
    if gamepad_uuid in _gamepad_managers:
        return _flask.jsonify(_gamepad_managers[gamepad_uuid].get_connection_timeout())
    
    return _flask.Response(f"No gamepad with UUID of '{gamepad_uuid}' found.", 404)


### SWITCH ENDPOINTS ###

@_app.route("/api/switches")
def get_switches() -> _flask.Response:
    switches: list[dict[str, str]] = [{
        "address": address,
        "name": _saved_switches.get(address)
    } for address in _nx.get_switch_addresses()]

    for address, name in _saved_switches.items():
        switch: dict[str, str] = {"address": address}

        if name or name != address:
            switch["name"] = name

    switches.append({
        "name": "Pair new Switch",
        "address": None
    })
    
    return _flask.jsonify(switches)


@_app.route("/api/switches/<string:switch_address>", methods=["POST"])
def set_switch_name(switch_address: str) -> _flask.Response:
    ### Get params from request
    data = _flask.request.get_json()

    if not isinstance(data, dict):
        return _flask.Response("Invalid JSON", 400)

    new_name = data.get("name")

    if new_name is None:
        return _flask.Response("Parametes 'name' has to be set!", 400)
    
    ### Rename switch in _saved_switches
    _saved_switches[switch_address] = new_name

    return _flask.Response("OK", 200)

@_app.route("/api/switches", methods=["DELETE"])
def delete_switches() -> _flask.Response:
    _saved_switches = {}

    return _flask.Response("No Content", 204)

@_app.route("/api/switches/<string:switch_address>", methods=["DELETE"])
def delete_switch(switch_address: str) -> _flask.Response:
    if switch_address in _saved_switches:
        del _saved_switches[switch_address]

        return _flask.Response("No Content", 204)
    
    return _flask.Response(f"No device with address '{switch_address}' found!", 404)


### CONFIG ENDPOINTS ###

@_app.route("/config")
def get_config() -> _flask.Response:
    return _flask.send_file(
        BytesIO(_json.dumps({
            "switches": _saved_switches,
            "gamepads": _saved_gamepads
        }, indent=4).encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name="Switchify Config.json"
    )

@_app.route("/config", methods=["POST"])
def post_config() -> _flask.Response:
    global _saved_switches, _saved_gamepads
    config = _json.loads(_flask.request.data.decode("utf-8"))

    _saved_switches.update(config["switches"])
    _saved_gamepads.update(config["gamepads"])

    return _flask.Response("OK", 200)

@_app.route("/config", methods=["PUT"])
def put_config() -> _flask.Response:
    global _saved_switches, _saved_gamepads
    config = _json.loads(_flask.request.data.decode("utf-8"))

    _saved_switches = config["switches"]
    _saved_gamepads = config["gamepads"]

    return _flask.Response("OK", 200)

@_app.route("/config", methods=["DELETE"])
def delete_config() -> _flask.Response:
    global _saved_switches, _saved_gamepads
    _saved_switches = {}
    _saved_gamepads = {}

    return _flask.Response("No Content", 204)


### SERVER CONTROL ###

@_app.route("/shutdown", methods=["GET"])
def shutdown() -> _flask.Response:
    # Disconnect all gamepads
    # Clone UUIDs first, then iterate over them
    for gamepad_uuid in tuple(_gamepad_managers):
        disconnect_gamepad(gamepad_uuid)
    
    # Save config to file
    create_config_file()
    
    # Safely shutdown Flask server by sending SIGINT to itself
    # Basically simulates pressing Ctrl+C in the terminal as recommended from Flask itself

    # Me: Hey Copilot, should i move the imports to the top of the file?
    # Copilot: Nah, this is the only place where we need these and they are only needed when shutting down the server, so it makes more sense to keep them here in my opinion.
    # Me: Thank you, Copilot!
    from signal import SIGINT
    from os import kill, getpid
    kill(getpid(), SIGINT)

    return _flask.Response("Shutting down server...", 200)


@_app.route("/create_config_file")
def create_config_file() -> _flask.Response:
    with open(CONFIG_FILE, "w") as config_file:
        _json.dump({
            "switches": _saved_switches,
            "gamepads": _saved_gamepads
        }, config_file, indent=4)

    return _flask.Response("Created", 201)

@_app.route("/delete_config_file", methods=["DELETE", "GET"])
def delete_config_file() -> _flask.Response:
    try:
        remove_file(CONFIG_FILE)
    except FileNotFoundError:
        pass

    return _flask.Response("OK", 200)


@_app.route("/")
def index() -> _flask.Response:
    return _flask.render_template("client.html")

if __name__ == "__main__":
    # Load config from file
    try:
        with open("config.json", "r") as config_file:
            config: dict = _json.load(config_file)
            _saved_switches = config.get("switches", {})
            _saved_gamepads = config.get("gamepads", {})
    except FileNotFoundError:
        pass

    _app.run("127.0.0.1", 8080)