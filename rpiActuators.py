"""
rpiActuators.py
---------------
Main entry point for the Raspberry Pi side of Cogniflow.

Listens for UDP state commands from the laptop (laptopBrain.py)
and applies the corresponding physical environment changes via
HardwareController.

Run with sudo (required by rpi_ws281x for DMA access):
    sudo python3 rpiActuators.py
"""

import socket
import logging

import config
from hardwareController import HardwareController

# ── LOGGING SETUP ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── SOCKET SERVER ─────────────────────────────────────────────────────────────

class StateSocketServer:
    """
    Blocking UDP server that receives mental state strings from the laptop
    and delegates hardware actuation to HardwareController.
    """

    def __init__(self, hardware: HardwareController) -> None:
        self._hardware = hardware
        self._socket   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(("0.0.0.0", config.RPI_PORT))
        logger.info(f"StateSocketServer bound to port {config.RPI_PORT}.")

    def listen(self) -> None:
        """
        Block and process incoming state commands indefinitely.
        Exits cleanly on KeyboardInterrupt.
        """
        print(f"\n  [ RPi READY ]  Listening on port {config.RPI_PORT}...\n")

        while True:
            rawData, senderAddress = self._socket.recvfrom(config.BUFFER_SIZE)
            state = rawData.decode("utf-8").strip()

            logger.info(f"Received '{state}' from {senderAddress[0]}.")
            print(f"  ← {state:<10s}  from {senderAddress[0]}")

            self._hardware.applyState(state)

    def close(self) -> None:
        self._socket.close()
        logger.info("Socket closed.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n╔══════════════════════════════════╗")
    print("  ║      Cogniflow  —  RPi Node      ║")
    print("  ║   Fan  ·  LEDs  ·  OLED  ·  I2C  ║")
    print("  ╚══════════════════════════════════╝\n")

    hardware = HardwareController()
    server   = StateSocketServer(hardware)

    try:
        server.listen()

    except KeyboardInterrupt:
        print("\n  [ STOPPED ]  KeyboardInterrupt received.")

    finally:
        server.close()
        hardware.cleanup()
        print("  [ SHUTDOWN ]  Clean exit.\n")


if __name__ == "__main__":
    main()