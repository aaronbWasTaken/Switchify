#! /usr/local/bin/python3.9
import nxbt as _nxbt
import flask as _flask
import pygame as _pygame
import gamepad as _gamepad
import threading as _threading
import gamepad_manager as _gamepad_manager
from typing import Optional, Any
from flask_cors import CORS as _CORS

_pygame.init()
_nx: _nxbt.Nxbt = _nxbt.Nxbt()
_app: _flask.Flask = _flask.Flask(__name__)
_CORS(_app)

_switches: dict[str, str] = {}
_connected_gamepads: dict[int, dict] = {}
"""
EXAMPLE FOR _connected_gamepads
{
    # Key is same as gamepad's ID
    0: {
        "gamepad": _gamepad.Gamepad(0), # Gamepad Object
        "manager": _gamepad_manager.GamepadManager(_nx, _gamepad.Gamepad(0)), # GamepadManager Object
    }
}
"""

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    ### THIS IS THE MOST JAVASCRIPT WAY OF DOING IT I ASSUME, THIS AINT GIVING A SHIT WHAT STRING YOU FEED IT XD
    hex_color = "".join(digit for digit in hex_color.upper() if digit in "0123456789ABCDEF")[:6].ljust(6, "0")
    return (
        int(hex_color[:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16)
    )


@_app.route("/api/gamepads/connect", methods=["POST"])
def connect_gamepad() -> _flask.Response:
    if len(_nx.get_available_adapters()) <= len(_connected_gamepads):
        response: _flask.Response = _flask.jsonify({"error": "Not enough Bluteooth adapters"})
        response.status_code = 500

        return response

    ### Get params from request
    data = _flask.request.get_json()

    if not isinstance(data, dict):
        return _flask.Response("Invalid JSON", 400)

    switch_address = data.get("switch_address")
    gamepad_id = data.get("gamepad_id", (
        min(i for i in range(max(_connected_gamepads) + 2) if i not in _connected_gamepads)
            if _connected_gamepads else
        0
    ))
    color = hex_to_rgb(data.get("color", "")) # format is #00ff88, default is pitch black

    assert isinstance(gamepad_id, int)

    if gamepad_id in _connected_gamepads:
        return _flask.Response("Gamepad already connected", 400)

    ### Set gamepad params
    gamepad: dict[str, Any] = {
        "gamepad": None,
        "manager": None
    }

    try:
        gamepad["gamepad"] = _gamepad.Gamepad(gamepad_id)

    except _pygame.error:
        # Invalid joystick id (because there's no joystick)
        return _flask.Response("Joystick ID is invalid. Check if the joystick is connected.", 500)
    
    gamepad["manager"] = _gamepad_manager.GamepadManager( 
        nx = _nx,
        gamepad = gamepad["gamepad"],
        color = color,
        reconnect_address = switch_address
    )

    ### Start gamepad manager thread
    gamepad["manager"].start_manager()
    
    ### Store gamepad globally
    _connected_gamepads[gamepad_id] = gamepad

    return _flask.jsonify({"id": gamepad_id, "connected": True})

@_app.route("/api/gamepads/<int:gamepad_id>/disconnect")
def disconnect_gamepad(gamepad_id: int) -> _flask.Response:
    gamepad = _connected_gamepads.get(gamepad_id)

    if gamepad is not None:
        manager = gamepad.get("manager")
        if isinstance(manager, _gamepad_manager.GamepadManager):
            manager.stop_manager()

            # Delete controller entry
            del _connected_gamepads[gamepad_id]
        
    return _flask.jsonify({"id": gamepad_id, "connected": False})

@_app.route("/api/switches/<string:switch_address>/set_name", methods=["POST"])
def set_switch_name(switch_address: str) -> _flask.Response:
    ### Get params from request
    data = _flask.request.get_json()

    if not isinstance(data, dict):
        return _flask.Response("Invalid JSON", 400)

    new_name = data.get("name")

    if (
        switch_address is None
        or new_name is None
    ):
        return _flask.Response("Both parametes 'switch_address' and 'name' have to be set!", 400)
    
    ### Rename switch in _switches
    _switches[switch_address] = new_name

    return _flask.Response("OK", 200)

@_app.route("/api/gamepads")
def get_gamepads() -> tuple[_flask.Response, int]:
    _pygame.event.pump() # Ensures that all JOYSTICKADDED events are getting processed

    gamepads: list[dict[str, Any]] = []

    for gamepad_id in range(_pygame.joystick.get_count()):
        gamepad: dict[str, Any] = {
            "id": gamepad_id,
            "name": None,
            "connected": False
        }

        if gamepad_id in _connected_gamepads:
            gamepad["connected"] = True
            gp = _connected_gamepads[gamepad_id]
            gamepad["name"] = gp["gamepad"].get_name()

        else:
            try:
                joystick: _pygame.joystick.JoystickType = _pygame.joystick.Joystick(gamepad_id)
                gamepad["name"] = joystick.get_name()

            except _pygame.error: # Joystick ID not found
                continue
        
        gamepads.append(gamepad)

    return _flask.jsonify(gamepads), 200

@_app.route("/api/switches")
def get_switches() -> tuple[_flask.Response, int]:
    switches: list[dict[str, str]] = [{
        "address": address,
        "name": _switches.get(address)
    } for address in _nx.get_switch_addresses()]

    for address, name in _switches.items():
        switch: dict[str, str] = {"address": address}

        if name or name != address:
            switch["name"] = name

    switches.append({
        "name": "Pair new Switch",
        "address": None
    })
    
    return _flask.jsonify(switches), 200


if __name__ == "__main__":
    _app.run(
        "127.0.0.1",
        8080
    )
