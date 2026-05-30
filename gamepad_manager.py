#! /usr/local/bin/python3.9
from gamepad import Gamepad
from typing import Text, Optional
import nxbt, threading, time, pygame
pygame.init()

class GamepadManager:
    def __init__(
            self, nx: nxbt.Nxbt,
            gamepad_uuid: str,
            color: tuple[int, int, int]=(60, 60, 60),
            reconnect_address: Optional[str] = None,
            connection_timeout: int = 60
    ) -> None:
        self.nx: nxbt.Nxbt = nx
        self.color: tuple[int, int, int] = color
        self.reconnect_address: Optional[str] = reconnect_address
        self.connection_timeout: int = connection_timeout
        self.player_number: int = -1
        self.disconnected_start: int = 0
        self.manager_thread: Optional[threading.Thread] = None
        self.stop_manager_event: Optional[threading.Event] = None
        self.change_gamepad(gamepad_uuid)
    
    def connect(self) -> int:
        self.player_number = self.nx.create_controller(
            nxbt.PRO_CONTROLLER,
            colour_body=self.color,
            reconnect_address=self.reconnect_address
        )
        return self.player_number
    
    def get_gamepad(self) -> Gamepad:
        return self._gamepad
    
    def get_connection_timeout(self) -> dict[str, int]:
        return {
            "status": int(time.time()) - self.disconnected_start,
            "limit": self.connection_timeout
        }

    def change_gamepad(self, gamepad_uuid: str) -> None:
        pygame.event.pump()
        for i in range(pygame.joystick.get_count()):
            if pygame.joystick.Joystick(i).get_guid() == gamepad_uuid:
                self._gamepad: Gamepad = Gamepad(i)
                return
        
        raise RuntimeError(f"No gamepad with UUID of '{gamepad_uuid}' found.")
        
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

        if self._gamepad.get_connected():
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

    def start_manager(self) -> threading.Thread :
        if self.stop_manager_event is None:
            self.stop_manager_event = threading.Event()
            self.manager_thread = threading.Thread(
                target=self.management_loop,
                args=(self.stop_manager_event, self.connection_timeout)
            )
            self.manager_thread.start()

            return self.manager_thread

        raise RuntimeError("A management thread is already running.")
        

    def stop_manager(self) -> None:
        if self.manager_thread:
            self.stop_manager_event.set()
            self.manager_thread.join()
            self.stop_manager_event = None
            self.manager_thread = None
    
    def management_loop(self, stop_event: threading.Event, connection_timeout: int) -> None:
        try:
            if not self._gamepad.get_connected():
                raise RuntimeError("Gamepad is not connected.")
            
            gamepad_uuid: str = self._gamepad.get_uuid()

            if self.player_number == -1:
                self.connect()

            # Replaces self.nx.wait_for_connection(self.player_number)
            while not(
                stop_event.is_set() or
                self.nx.state[self.player_number]["state"] == "connected"
            ):
                if self.nx.state[self.player_number]["state"] == "crashed":
                    raise OSError(
                        "The watched controller has crashe with error",
                        self.nx.state[self.player_number]["errors"]
                    )
                
                time.sleep(0.2)

            while (
                not stop_event.is_set() and 
                (
                    self._gamepad.get_connected() or
                    int(time.time()) - self.disconnected_start < connection_timeout
                )
            ):
                self.send_switch_inputs()
                if self._gamepad.get_connected():
                    self.disconnected_start = int(time.time())
                else:
                    time.sleep(1)
                    try:
                        self.change_gamepad(gamepad_uuid)
                    except RuntimeError:
                        continue

        except KeyboardInterrupt:
            pass
        finally:
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