#! /usr/local/bin/python3.9
from gamepad import Gamepad
from typing import Text, Optional
from pygame.time import Clock
import nxbt, time, threading

class GamepadManager:
    def __init__(
            self, nx: nxbt.Nxbt,
            gamepad: Gamepad,
            color: tuple[int, int, int]=(60, 60, 60),
            reconnect_address: Optional[str] = None
    ) -> None:
        self.nx = nx
        self._gamepad = gamepad
        self.color = color
        self.reconnect_address = reconnect_address
        self.player_number: int = -1
        self.manager_thread: Optional[threading.Thread] = None
        self.stop_manager_event: Optional[threading.Event] = None
    
    def connect(self) -> int:
        self.player_number = self.nx.create_controller(
            nxbt.PRO_CONTROLLER,
            colour_body=self.color,
            reconnect_address=self.reconnect_address
        )
        return self.player_number

    def change_gamepad(self, new_gamepad: Gamepad) -> None:
        self._gamepad = new_gamepad
        
    def get_connected(self) -> bool:
        if (
                self.player_number == -1 or
                not self._gamepad.get_connected() or
                self.player_number not in self.nx.state
        ):
            return False

        return self.nx.state[self.player_number]["state"] in ("connected", "reconnecting")

    def send_switch_inputs(self) -> None:
        packet = self.nx.create_input_packet()

        inputs = self._gamepad.get_inputs()

        for button, mapping in _conversion_table.items():
            packet[mapping] = inputs.get(button, 0) >= 0.5

        packet["L_STICK"]["PRESSED"] = inputs["LS"] >= 0.5
        packet["L_STICK"]["X_VALUE"] = int(inputs["LS X"] * 100)
        packet["L_STICK"]["Y_VALUE"] = int(inputs["LS Y"] * -100)

        packet["R_STICK"]["PRESSED"] = inputs["RS"] >= 0.5
        packet["R_STICK"]["X_VALUE"] = int(inputs["RS X"] * 100)
        packet["R_STICK"]["Y_VALUE"] = int(inputs["RS Y"] * -100)

        self.nx.set_controller_input(self.player_number, packet)

    def disconnect(self) -> None:
        if self.player_number > -1:
            try:
                self.nx.remove_controller(self.player_number)
            except:
                return

    def start_manager(self, transmitting_rate_hz: int=120) -> None:
        self.stop_manager_event = threading.Event()
        self.manager_thread = threading.Thread(
            target=self.management_loop,
            args=(transmitting_rate_hz, self.stop_manager_event)
        )
        self.manager_thread.start()

        return self.manager_thread

    def stop_manager(self) -> None:
        if self.manager_thread:
            self.stop_manager_event.set()
            self.manager_thread.join()
            self.stop_manager_event = None
            self.manager_thread = None
    
    def management_loop(self, transmitting_rate_hz: int, stop_event: threading.Event) -> None:
        try:
            clock: Clock = Clock()

            if not self._gamepad.get_connected():
                raise RuntimeError("Gamepad is not connected.")

            if self.player_number == -1:
                self.connect()

            self.nx.wait_for_connection(self.player_number)
            
            while self.get_connected() and not stop_event.is_set():
                clock.tick_busy_loop(transmitting_rate_hz)
                self.send_switch_inputs()
            
            self.disconnect()
        except KeyboardInterrupt:
            self.disconnect()
            

_conversion_table: dict[str, Text] = {
        "A": nxbt.Buttons.B,
        "B": nxbt.Buttons.A,
        "X": nxbt.Buttons.Y,
        "Y": nxbt.Buttons.X,
        "LB": nxbt.Buttons.L,
        "RB": nxbt.Buttons.R,
        "BACK": nxbt.Buttons.MINUS,
        "START": nxbt.Buttons.PLUS,
        "GUIDE": nxbt.Buttons.HOME,
        "LT": nxbt.Buttons.ZL,
        "RT": nxbt.Buttons.ZR,
        "UP": nxbt.Buttons.DPAD_UP,
        "DOWN": nxbt.Buttons.DPAD_DOWN,
        "LEFT": nxbt.Buttons.DPAD_LEFT,
        "RIGHT": nxbt.Buttons.DPAD_RIGHT,
        "EXTRA": nxbt.Buttons.CAPTURE
    }