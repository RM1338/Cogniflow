"""
socketClient.py
---------------
UDP socket client that sends single-word state commands from the
laptop to the Raspberry Pi actuator server.

UDP is used over TCP because:
  - We don't need guaranteed delivery — a missed packet just means
    the actuator holds its previous state for one cycle (fine)
  - No connection management overhead
  - Lower latency on a local network

Usage:
    client = StateSocketClient()
    client.send("DROWSY")
    client.close()
"""

import socket
import logging

import config

logger = logging.getLogger(__name__)


class StateSocketClient:
    """
    Sends mental state strings to the RPi actuator server over UDP.
    Each call to send() opens and closes a socket to keep it stateless
    and avoid stale connection issues across long sessions.
    """

    def __init__(self) -> None:
        self._address = (config.RPI_IP, config.RPI_PORT)
        logger.info(f"StateSocketClient configured for {self._address}.")

    def send(self, state: str) -> None:
        """
        Transmit a state string to the RPi.

        Args:
            state: Mental state string — "FOCUS", "DROWSY", "STRESSED", "RELAXED".
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                payload = state.encode("utf-8")
                sock.sendto(payload, self._address)
                logger.debug(f"Sent state '{state}' to {self._address}.")

        except OSError as error:
            logger.error(f"Socket send failed: {error}")
            logger.error(f"Verify RPi is reachable at {config.RPI_IP}:{config.RPI_PORT}.")