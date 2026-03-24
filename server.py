#! /usr/local/bin/python3.9
import nxbt as _nxbt
import flask as _flask
import pygame as _pygame
import gamepad as _gamepad
import threading as _threading
import gamepad_manager as _gamepad_manager
from typing import Optional, Any

_pygame.init()
_nx: _nxbt.Nxbt = _nxbt.Nxbt()
_app: _flask.Flask = _flask.Flask(__name__)

_saved_switches: dict[str, str] = {}
_connected_gamepads: dict[int, dict] = {}
"""
EXAMPLE FOR _connected_gamepads
{
    # Key is same as gamepad's ID
    0: {
        "gamepad": _gamepad.Gamepad(0), # Gamepad Object
        "manager": _gamepad_manager.GamepadManager(_nx, _gamepad.Gamepad(0)), # GamepadManager Object
        "thread": _threading.Thread(target=_gamepad_manager.GamepadManager(_nx, _gamepad.Gamepad(0)).management_loop) # Thread Object
        "name": "Mario (Player 1)" # Custom Name or Gamepad Description
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


@_app.route("/api/connect_controller", methods=["POST"])
def connect_controller() -> _flask.Response:
    ### Get params from request
    data = _flask.request.get_json()

    if not isinstance(data, dict):
        return _flask.Response("Invalid JSON", 400)

    switch_address = data.get("switch_address")
    if _connected_gamepads:
        gamepad_id = min(i for i in range(max(_connected_gamepads) + 2) if i not in _connected_gamepads)
    else:
        gamepad_id = 0
    color = hex_to_rgb(data.get("color", "")) # format is #00ff88, default is pitch black
    custom_name = data.get("name")

    assert isinstance(gamepad_id, int)

    if gamepad_id in _connected_gamepads:
        return _flask.Response("Gamepad already connected", 400)

    ### Set gamepad params
    gamepad: dict[str, Any] = {
        "gamepad": None,
        "manager": None,
        "thread": None,
        "name": None
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
    gamepad["thread"] = _threading.Thread(
        target = gamepad["manager"].management_loop,
        daemon = True
    )

    gamepad["name"] = custom_name or gamepad["gamepad"].get_name()


    ### Start gamepad manager thread
    gamepad["thread"].start()

    
    ### Store gamepad globally
    _connected_gamepads[gamepad_id] = gamepad

    return _flask.jsonify({"status": "connected", "id": gamepad_id})


@_app.route("/api/set_switch_name")
def set_switch_name() -> _flask.Response:
    ### Get params from request
    data = _flask.request.get_json()

    if not isinstance(data, dict):
        return _flask.Response("Invalid JSON", 400)

    switch_address = data.get("switch_address")
    new_name = data.get("name")

    if (
        switch_address is None
        or new_name is None
    ):
        return _flask.Response("Both parametes 'switch_address' and 'name' have to be set!", 400)
    
    ### Rename switch in _saved_switches
    if switch_address in _saved_switches:
        _saved_switches[switch_address] = new_name
    else:
        return _flask.Response(f"Switch {switch_address} was not found, therefore not renamed", 400)

    return _flask.Response("OK", 200)

@_app.route("/api/gamepads/")
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
            name = gp["gamepad"].get_name()
            gamepad["name"] = gp["name"] + f" ({name})" # custom_name (gamepad_name)

        else:
            # Try block ensures that just now disconnected gamepads will be skipped
            try:
                joystick: _pygame.joystick.JoystickType = _pygame.joystick.Joystick(gamepad_id)
                name: str = joystick.get_name()
            except _pygame.error:
                continue

            gamepad["name"] = name
        
        gamepads.append(gamepad)

    return _flask.jsonify(gamepads), 200
