#! /usr/local/bin/python3.9
from gamepad import Gamepad
from typing import Text, Optional
import nxbt

class GamepadManager:
    def __init__(
            self, nx: nxbt.Nxbt,
            gamepad: Gamepad,
            color: tuple[int, int, int]=(60, 60, 60),
            reconnect_address: Optional[str] = None
    ) -> None:
        self.nx = nx
        self.gamepad = gamepad
        self.color = color
        self.reconnect_address = reconnect_address
        self.player_number: int = -1
    
    def connect(self) -> int:
        self.player_number = self.nx.create_controller(
            nxbt.PRO_CONTROLLER,
            colour_body=self.color,
            reconnect_address=self.reconnect_address
        )
        return self.player_number
        
    def get_connected(self) -> bool:
        if self.player_number == -1 or self.player_number not in self.nx.state:
            return False

        return self.nx.state[self.player_number]["state"] == "connected"

    def send_switch_inputs(self) -> None:
        packet = self.nx.create_input_packet()

        inputs = self.gamepad.get_inputs()

        for button, mapping in conversion_table.items():
            packet[mapping] = inputs.get(button, 0) >= 0.5

        packet["L_STICK"]["PRESSED"] = inputs["LS"] >= 0.5
        packet["L_STICK"]["X_VALUE"] = int(inputs["LS X"] * 100)
        packet["L_STICK"]["Y_VALUE"] = int(inputs["LS Y"] * -100)

        packet["R_STICK"]["PRESSED"] = inputs["RS"] >= 0.5
        packet["R_STICK"]["X_VALUE"] = int(inputs["RS X"] * 100)
        packet["R_STICK"]["Y_VALUE"] = int(inputs["RS Y"] * -100)

        self.nx.set_controller_input(self.player_number, packet)

    def disconnect(self) -> None:
        self.nx.remove_controller(self.player_number)
        self.player_number = -1
    
    def quit(self) -> None:
        self.gamepad.quit()
        self.disconnect()
    
    def management_loop(self) -> None:
        try:
            if not self.gamepad.get_connected():
                raise RuntimeError("Gamepad is not connected.")

            if self.player_number == -1:
                self.connect()
            
            if self.get_connected() is False:
                self.nx.wait_for_connection(self.player_number)
            
            while self.gamepad.get_connected():
                self.send_switch_inputs()
            
            self.quit()
        except KeyboardInterrupt:
            self.quit()
            

conversion_table: dict[str, Text] = {
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