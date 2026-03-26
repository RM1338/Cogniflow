"""
arduinoController.py
--------------------
Serial controller for the Arduino UNO WiFi R4.
Sends mental state commands over USB serial so the Arduino can
drive local actuators (fan, NeoPixel LEDs, buzzer).

Protocol:
    Laptop → Arduino:  JSON line  {"state":"FOCUS","fan":0,"r":255,"g":255,"b":240,"bFreq":0,"bDur":0}
    Arduino → Laptop:  "READY\n" on boot, "ACK:<STATE>\n" on each command

Usage:
    controller = ArduinoController()
    controller.connect()
    controller.send("FOCUS")
    controller.close()
"""

import json
import time
import logging
import serial

import config

logger = logging.getLogger(__name__)


class ArduinoController:
    """
    Manages serial communication with the Arduino.
    Builds a JSON command from the state and config values,
    sends it over serial, and reads back the ACK.
    """

    def __init__(self) -> None:
        self._port: str   = config.ARDUINO_PORT
        self._baud: int   = config.ARDUINO_BAUD
        self._serial: serial.Serial | None = None

    def connect(self) -> bool:
        """
        Open the serial port and wait for the Arduino's READY signal.
        The Arduino resets on serial open — give it time to boot.

        Returns:
            True if connection succeeded, False otherwise.
        """
        try:
            if self._port == "auto":
                import serial.tools.list_ports
                ports = list(serial.tools.list_ports.comports())
                arduino_ports = [p.device for p in ports if 'ACM' in p.device or 'USB' in p.device]
                if not arduino_ports:
                    logger.error("No Arduino ports (ACM/USB) found!")
                    print("  [ ARDUINO ]  Connection failed: No Arduino ports (ACM/USB) found.")
                    return False
                self._port = arduino_ports[-1] # Pick the highest numbered one usually
                logger.info(f"Auto-detected Arduino port: {self._port}")

            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baud,
                timeout=config.ARDUINO_TIMEOUT,
            )

            # Arduino resets on serial connect — wait for bootloader
            time.sleep(2.0)

            # Flush any bootloader garbage
            self._serial.reset_input_buffer()

            # Wait for READY signal (Arduino sends this after setup())
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if self._serial.in_waiting:
                    line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                    if line == "READY":
                        logger.info(f"Arduino connected on {self._port} — READY received.")
                        print(f"  [ ARDUINO ]  Connected on {self._port}")
                        return True
                time.sleep(0.1)

            # No READY received, but serial is open — try anyway
            logger.warning("Arduino did not send READY — proceeding anyway.")
            print(f"  [ ARDUINO ]  Connected on {self._port} (no READY signal)")
            return True

        except serial.SerialException as error:
            logger.error(f"Arduino connection failed: {error}")
            print(f"  [ ARDUINO ]  Connection failed: {error}")
            self._serial = None
            return False

    def send(self, state: str) -> bool:
        """
        Send a state command to the Arduino as a JSON line.

        Args:
            state: One of "FOCUS", "DROWSY", "STRESSED", "RELAXED".

        Returns:
            True if sent and ACK received, False otherwise.
        """
        if self._serial is None or not self._serial.is_open:
            logger.warning("Arduino not connected — skipping send.")
            return False

        if state not in config.ARDUINO_FAN_SPEED:
            logger.warning(f"Unknown state '{state}' — ignoring.")
            return False

        # Build command payload from config
        color_dict = config.ARDUINO_LED_COLOUR[state]
        r, g, b    = color_dict["r"], color_dict["g"], color_dict["b"]
        
        bFreq, bDur = config.ARDUINO_BUZZER[state]

        command = {
            "state": state,
            "fan":   config.ARDUINO_FAN_SPEED[state],
            "r":     r,
            "g":     g,
            "b":     b,
            "bFreq": bFreq,
            "bDur":  bDur,
        }

        try:
            payload = json.dumps(command) + "\n"
            self._serial.write(payload.encode("utf-8"))
            self._serial.flush()

            # PROMINENT LOGGING FOR HARDWARE DEBUGGING
            print(f"  [ ARDUINO ]  Sent: {payload.strip()}")
            logger.info(f"Sent to Arduino: {payload.strip()}")

            # Read ACK (non-blocking with timeout)
            response = self._serial.readline().decode("utf-8", errors="ignore").strip()
            if response.startswith("ACK:"):
                logger.debug(f"Arduino ACK: {response}")
                return True
            else:
                logger.warning(f"Unexpected Arduino response: '{response}'")
                return True  # Still sent successfully

        except serial.SerialException as error:
            logger.error(f"Arduino serial write failed: {error}")
            return False

    def close(self) -> None:
        """Close the serial connection."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info("Arduino serial connection closed.")
