#! /usr/local/bin/python3.9
from typing import Optional
import pygame.joystick
import copy

class Gamepad:
    def __init__(self, controller_id: int, custom_mapping: Optional[dict] = None) -> None:
        """
        Initialize a Gamepad wrapper around a pygame joystick device.

        The gamepad type is automatically detected based on the joystick name.
        Supported types are XBOX, PS4, PS5, and Nintendo Switch Pro Controller.
        If the device cannot be identified and no custom mapping is provided,
        initialization fails with a ValueError.

        Args:
            controller_id (int):
                The pygame joystick index corresponding to the connected device.

            custom_mapping (Optional[dict]):
                A custom input mapping dictionary used when the controller type
                is not recognized.

                The mapping must be a dictionary where each key is a logical
                input name (e.g. "A", "LS X", "UP") and each value is a mapping
                specification dictionary with the following structure:

                    {
                        "<INPUT_NAME>": {
                            "type": "<INPUT_TYPE>",
                            "index": <int>,
                            "function": <callable>  # optional
                        }
                    }

                Mapping fields:

                    - type (str):
                        The pygame input category. Must be one of:
                        "BUTTON", "AXIS", "HAT", or "BALL".

                    - index (int):
                        The index of the input within the selected pygame
                        input category (button index, axis index, etc.).

                    - function (callable, optional):
                        A transformation function applied to the raw input
                        value before it is returned. The function must accept
                        a single argument (the raw input value) and return
                        the transformed value.

                Example:

                    {
                        "A": {"type": "BUTTON", "index": 0},
                        "LS X": {"type": "AXIS", "index": 0},
                        "LT": {
                            "type": "AXIS",
                            "index": 2,
                            "function": lambda x: x / 2 + 0.5
                        },
                        "UP": {
                            "type": "HAT",
                            "index": 0,
                            "function": lambda x: x[1] > 0
                        }
                    }

        Raises:
            ValueError:
                If the controller type is unsupported and no custom mapping
                is provided.
        """
        self._gamepad: pygame.joystick.JoystickType = pygame.joystick.Joystick(controller_id)
        self._id: int = controller_id
        self._ended: bool = False
        self._getter: dict[str, function] = {
            "HAT": self._gamepad.get_hat,
            "AXIS": self._gamepad.get_axis,
            "BALL": self._gamepad.get_ball,
            "BUTTON": self._gamepad.get_button

        }

        for keyword, type in {
            "XBOX ONE": "XBOX ONE",
            "XBOX": "XBOX 360",
            "STADIA": "STADIA",
            "PS4": "PS4",
            "SONY": "PS5",
            "SWITCH PRO": "NSPRO"
        }.items():
            if keyword in self._gamepad.get_name().upper():
                self._type: str = type
                break
        else:
            if custom_mapping is None:
                raise ValueError(f"Unsupported gamepad type: {self._gamepad.get_name()}\nSupported types are: XBOX, PS4, PS5, SWITCH PRO\nYou can also provide a custom mapping dictionary.")
            
            self._type: str = "CUSTOM"
        self._mapping = custom_mapping if self._type == "CUSTOM" else copy.deepcopy(_mappings[self._type])

    def get_name(self) -> str:
        """
        Get the human-readable name of the connected gamepad.

        Returns:
            str:
                The name reported by the underlying pygame joystick device.
        """
        return self._gamepad.get_name()

    def get_power_level(self) -> float:
        """
        Get the current power level of the gamepad as a normalized value.

        The returned value is mapped from pygame's power level strings:

            - 0.0  : empty
            - 0.3  : low
            - 0.6  : medium
            - 1.0  : full
            - 1.1  : wired
            - 0.5  : unknown or unsupported

        Returns:
            float:
                A normalized representation of the gamepad's power level.
        """
        return {
            "empty":   0.0,
            "low":     0.3,
            "medium":  0.6,
            "full":    1.0,
            "wired":   1.1,
        }.get(
            self._gamepad.get_power_level().lower(),
            0.5
        )

    def get_type(self) -> str:
        """
        Get the detected or assigned controller type.

        Returns:
            str:
                The controller type identifier. One of:
                'XBOX', 'PS4', 'PS5', 'NSPRO', or 'CUSTOM'.
        """
        return self._type

    def get_id(self) -> int:
        """
        Get the pygame joystick index associated with this gamepad.

        Returns:
            int:
                The joystick ID used by pygame.
        """
        return self._id

    def get_connected(self) -> bool:
        """
        Check whether the gamepad is still connected and usable.

        This method verifies that the joystick device is still available
        through pygame and that the gamepad has not been explicitly quit.

        Returns:
            bool:
                True if the gamepad is connected and active, False otherwise.
        """
        if self._ended:
            return False
        
        try:
            pygame.joystick.Joystick(self._id)
            return True
        except pygame.error:
            return False

    def quit(self) -> None:
        """
        Release the underlying pygame joystick device and mark the gamepad
        as no longer active.

        After calling this method, the gamepad will be considered disconnected
        and should not be used further.
        """
        self._gamepad.quit()
        self._ended = True

    def get_mapping(self) -> dict:
        """
        Retrieve the active input mapping for the gamepad.

        This method returns the built-in mapping dictionary corresponding
        to the detected controller type, or the custom mapping provided
        during initialization if the type is 'CUSTOM'.

        Returns:
            dict:
                The input mapping dictionary for the gamepad.
        """
        return self._mapping

    def set_mapping(self, custom_mapping: dict) -> None:
        """
        Set a custom input mapping for the gamepad.

        This method allows replacing the current input mapping with a
        user-defined mapping dictionary.
        The type of the gamepad will be set to 'CUSTOM'.
        The mapping dictionary must follow the same structure as described
        in the __init__ method documentation.

custom_mapping
        Args:
            custom_mapping (dict):
                A custom input mapping dictionary structured as described
                in the __init__ method documentation.
        """
        self._type = "CUSTOM"
        self.custom_mapping = custom_mapping

    def get_inputs(self) -> dict[str, float]:
        """
        Read and return the current state of all mapped inputs.

        This method polls the pygame event system, reads the current values
        of all inputs defined in the active mapping (built-in or custom),
        applies any configured transformation functions, and returns the
        results as a dictionary.

        The returned values may be booleans, integers, floats, or tuples,
        depending on the input type and mapping configuration.

        Returns:
            dict[str, float]:
                A dictionary mapping logical input names (e.g. 'A', 'LS X')
                to their current values.
        """
        inputs = {}

        pygame.event.pump()

        for input, mapping in self.get_mapping().items():
            if mapping["type"] not in self._getter:
                continue

            if "function" in mapping:
                inputs[input] = mapping["function"](self._getter[mapping["type"]](mapping["index"]))
            
            else:
                inputs[input] = self._getter[mapping["type"]](mapping["index"])
                
        return inputs


_mappings: dict[str, dict] = {
    "XBOX 360": {
        "A": {"type": "BUTTON", "index": 0},
        "B": {"type": "BUTTON", "index": 1},
        "X": {"type": "BUTTON", "index": 2},
        "Y": {"type": "BUTTON", "index": 3},
        "LB": {"type": "BUTTON", "index": 4},
        "RB": {"type": "BUTTON", "index": 5},
        "BACK": {"type": "BUTTON", "index": 6},
        "START": {"type": "BUTTON", "index": 7},
        "GUIDE": {"type": "BUTTON", "index": 8},
        "LS": {"type": "BUTTON", "index": 9},
        "RS": {"type": "BUTTON", "index": 10},
        "LS X": {"type": "AXIS", "index": 0},
        "LS Y": {"type": "AXIS", "index": 1},
        "LT": {"type": "AXIS", "index": 2, "function": lambda x: x/2 + 0.5},
        "RS X": {"type": "AXIS", "index": 3},
        "RS Y": {"type": "AXIS", "index": 4},
        "RT": {"type": "AXIS", "index": 5, "function": lambda x: x/2 + 0.5},
        "RIGHT": {"type": "HAT", "index": 0, "function": lambda x: x[0] > 0},
        "LEFT": {"type": "HAT", "index": 0, "function": lambda x: x[0] < 0},
        "UP": {"type": "HAT", "index": 0, "function": lambda x: x[1] > 0},
        "DOWN": {"type": "HAT", "index": 0, "function": lambda x: x[1] < 0},
    },

    "XBOX ONE": {
        "A": {"type": "BUTTON", "index": 0},
        "B": {"type": "BUTTON", "index": 1},
        "X": {"type": "BUTTON", "index": 3},
        "Y": {"type": "BUTTON", "index": 4},
        "LB": {"type": "BUTTON", "index": 6},
        "RB": {"type": "BUTTON", "index": 7},
        "BACK": {"type": "BUTTON", "index": 10},
        "START": {"type": "BUTTON", "index": 11},
        "GUIDE": {"type": "BUTTON", "index": 12},
        "LS": {"type": "BUTTON", "index": 13},
        "RS": {"type": "BUTTON", "index": 14},
        "LS X": {"type": "AXIS", "index": 0},
        "LS Y": {"type": "AXIS", "index": 1},
        "LT": {"type": "AXIS", "index": 5, "function": lambda x: x/2 + 0.5},
        "RS X": {"type": "AXIS", "index": 2},
        "RS Y": {"type": "AXIS", "index": 3},
        "RT": {"type": "AXIS", "index": 4, "function": lambda x: x/2 + 0.5},
        "RIGHT": {"type": "HAT", "index": 0, "function": lambda x: x[0] > 0},
        "LEFT": {"type": "HAT", "index": 0, "function": lambda x: x[0] < 0},
        "UP": {"type": "HAT", "index": 0, "function": lambda x: x[1] > 0},
        "DOWN": {"type": "HAT", "index": 0, "function": lambda x: x[1] < 0},
    },

    "PS4": {
        "A": {"type": "BUTTON", "index": 0},
        "B": {"type": "BUTTON", "index": 1},
        "X": {"type": "BUTTON", "index": 2},
        "Y": {"type": "BUTTON", "index": 3},
        "BACK": {"type": "BUTTON", "index": 4},
        "GUIDE": {"type": "BUTTON", "index": 5},
        "START": {"type": "BUTTON", "index": 6},
        "LS": {"type": "BUTTON", "index": 7},
        "RS": {"type": "BUTTON", "index": 8},
        "LB": {"type": "BUTTON", "index": 9},
        "RB": {"type": "BUTTON", "index": 10},
        "UP": {"type": "BUTTON", "index": 11},
        "DOWN": {"type": "BUTTON", "index": 12},
        "LEFT": {"type": "BUTTON", "index": 13},
        "RIGHT": {"type": "BUTTON", "index": 14},
        "EXTRA": {"type": "BUTTON", "index": 15},
        "LS X": {"type": "AXIS", "index": 0},
        "LS Y": {"type": "AXIS", "index": 1},
        "RS X": {"type": "AXIS", "index": 2},
        "RS Y": {"type": "AXIS", "index": 3},
        "LT": {"type": "AXIS", "index": 4},
        "RT": {"type": "AXIS", "index": 5},
    },

    "PS5": {
        "A": {"type": "BUTTON", "index": 0},
        "B": {"type": "BUTTON", "index": 1},
        "X": {"type": "BUTTON", "index": 2},
        "Y": {"type": "BUTTON", "index": 3},
        "LB": {"type": "BUTTON", "index": 4},
        "RB": {"type": "BUTTON", "index": 5},
        "BACK": {"type": "BUTTON", "index": 8},
        "START": {"type": "BUTTON", "index": 9},
        "GUIDE": {"type": "BUTTON", "index": 10},
        "LS": {"type": "BUTTON", "index": 11},
        "RS": {"type": "BUTTON", "index": 12},
        "LS X": {"type": "AXIS", "index": 0},
        "LS Y": {"type": "AXIS", "index": 1},
        "LT": {"type": "AXIS", "index": 2},
        "RS X": {"type": "AXIS", "index": 3},
        "RS Y": {"type": "AXIS", "index": 4},
        "RT": {"type": "AXIS", "index": 5},
        "RIGHT": {"type": "HAT", "index": 0, "function": lambda x: x[0] > 0},
        "LEFT": {"type": "HAT", "index": 0, "function": lambda x: x[0] < 0},
        "UP": {"type": "HAT", "index": 0, "function": lambda x: x[1] > 0},
        "DOWN": {"type": "HAT", "index": 0, "function": lambda x: x[1] < 0},
    },

    "NSPRO": {
        "B": {"type": "BUTTON", "index": 0},
        "A": {"type": "BUTTON", "index": 1},
        "Y": {"type": "BUTTON", "index": 2},
        "X": {"type": "BUTTON", "index": 3},
        "BACK": {"type": "BUTTON", "index": 4},
        "GUIDE": {"type": "BUTTON", "index": 5},
        "START": {"type": "BUTTON", "index": 6},
        "LS": {"type": "BUTTON", "index": 7},
        "RS": {"type": "BUTTON", "index": 8},
        "LB": {"type": "BUTTON", "index": 9},
        "RB": {"type": "BUTTON", "index": 10},
        "UP": {"type": "BUTTON", "index": 11},
        "DOWN": {"type": "BUTTON", "index": 12},
        "LEFT": {"type": "BUTTON", "index": 13},
        "RIGHT": {"type": "BUTTON", "index": 14},
        "EXTRA": {"type": "BUTTON", "index": 15},
        "LS X": {"type": "AXIS", "index": 0},
        "LS Y": {"type": "AXIS", "index": 1},
        "RS X": {"type": "AXIS", "index": 2},
        "RS Y": {"type": "AXIS", "index": 3},
        "LT": {"type": "AXIS", "index": 4},
        "RT": {"type": "AXIS", "index": 5},
    },

    "STADIA": {
        "A": {"type": "BUTTON", "index": 0},
        "B": {"type": "BUTTON", "index": 1},
        "X": {"type": "BUTTON", "index": 2},
        "Y": {"type": "BUTTON", "index": 3},
        "LB": {"type": "BUTTON", "index": 4},
        "RB": {"type": "BUTTON", "index": 5},
        "BACK": {"type": "BUTTON", "index": 6},
        "START": {"type": "BUTTON", "index": 7},
        "GUIDE": {"type": "BUTTON", "index": 8},
        "LS": {"type": "BUTTON", "index": 9},
        "RS": {"type": "BUTTON", "index": 10},
        "EXTRA": {"type": "BUTTON", "index": 12}, # 11 and 12 are EXTRA Buttons, but i just leave 11 unmapped for now.
        "LS X": {"type": "AXIS", "index": 0},
        "LS Y": {"type": "AXIS", "index": 1},
        "LT": {"type": "AXIS", "index": 5, "function": lambda x: x/2 + 0.5},
        "RS X": {"type": "AXIS", "index": 2},
        "RS Y": {"type": "AXIS", "index": 3},
        "RT": {"type": "AXIS", "index": 4, "function": lambda x: x/2 + 0.5},
        "RIGHT": {"type": "HAT", "index": 0, "function": lambda x: x[0] > 0},
        "LEFT": {"type": "HAT", "index": 0, "function": lambda x: x[0] < 0},
        "UP": {"type": "HAT", "index": 0, "function": lambda x: x[1] > 0},
        "DOWN": {"type": "HAT", "index": 0, "function": lambda x: x[1] < 0},
    }
}

if __name__ == "__main__":
    pygame.init()
    gamepad: pygame.joystick.JoystickType = pygame.joystick.Joystick(0)

    num_axes: int = gamepad.get_numaxes()
    num_hats: int = gamepad.get_numhats()
    num_balls: int = gamepad.get_numballs()
    num_buttons: int = gamepad.get_numbuttons()

    print(f"""\
===== Gamepad Diagnosis Tool =====
GAMEPAD INFORMATION (ID: 0):
- Name: {gamepad.get_name()}
- GUID: {gamepad.get_guid()}
- Power Level: {gamepad.get_power_level()}
- Button Count: {num_buttons}
- Axis Count: {num_axes}
- Ball Count: {num_balls}
- Hat Count: {num_hats}""")
    
    input("Press Enter to start input readout")

    clock: pygame.time.Clock = pygame.time.Clock()
    clear_screen = lambda: print()
    prev_output = ""

    try:
        while True:
            clock.tick_busy_loop(20)
            pygame.event.pump() # Essential for running without GUI

            output = (
                "\033[H\033[JAxes: " + " ".join(f"{i}: {gamepad.get_axis(i):.2f}" for i in range(num_axes)) +
                "\nHats: " + ", ".join(f"{i}: {gamepad.get_hat(i)}" for i in range(num_hats)) +
                "\nBalls: " + ", ".join(f"{i}: {tuple(map(lambda x: round(x, 3), gamepad.get_ball(i)))}" for i in range(num_balls)) +
                "\nButtons: " + ", ".join(f"{i}: {gamepad.get_button(i)}" for i in range(num_buttons))
            )

            if output != prev_output:
                prev_output = output
                clear_screen()
                print(output)
    except KeyboardInterrupt:
        print("\nCTRL+C - Exiting Gamepad Diagnosis Tool")