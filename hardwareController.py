"""
hardwareController.py
---------------------
Controls all physical actuators on the Raspberry Pi:
  - DC fan via MOSFET PWM (GPIO 18)
  - WS2812B LED strip (GPIO 12)
  - SSD1306 OLED display (I2C)

Each actuator is encapsulated in its own class.
HardwareController composes all three and exposes a single
applyState(state) method as the public interface.

Note: rpi_ws281x requires sudo to access DMA.
      Run rpiActuators.py with: sudo python3 rpiActuators.py
"""

import logging
from gpiozero import PWMOutputDevice
from rpi_ws281x import PixelStrip, Color
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas

import config

logger = logging.getLogger(__name__)


# ── FAN CONTROLLER ────────────────────────────────────────────────────────────

class FanController:
    """
    Controls a 5V DC fan via an N-channel MOSFET on a hardware PWM GPIO pin.
    Speed is a float in [0.0, 1.0] where 0.0 = off and 1.0 = full speed.
    """

    def __init__(self) -> None:
        self._fan = PWMOutputDevice(config.FAN_GPIO_PIN)
        logger.info(f"FanController initialised on GPIO {config.FAN_GPIO_PIN}.")

    def setSpeed(self, speed: float) -> None:
        """
        Set fan speed.

        Args:
            speed: Float in [0.0, 1.0].
        """
        clampedSpeed = max(0.0, min(1.0, speed))
        self._fan.value = clampedSpeed
        logger.debug(f"Fan speed set to {clampedSpeed:.2f}.")

    def off(self) -> None:
        self._fan.off()

    def cleanup(self) -> None:
        self.off()


# ── LED CONTROLLER ────────────────────────────────────────────────────────────

class LEDController:
    """
    Controls a WS2812B addressable LED strip via rpi_ws281x.
    Fills the entire strip with a solid colour per mental state.
    """

    def __init__(self) -> None:
        self._strip = PixelStrip(
            config.LED_COUNT,
            config.LED_GPIO_PIN,
            config.LED_FREQUENCY,
            config.LED_DMA,
            config.LED_INVERT,
            config.LED_BRIGHTNESS,
        )
        self._strip.begin()
        logger.info(f"LEDController initialised — {config.LED_COUNT} LEDs on GPIO {config.LED_GPIO_PIN}.")

    def setColour(self, red: int, green: int, blue: int) -> None:
        """
        Fill all LEDs with a solid RGB colour.

        Args:
            red, green, blue: Colour channel values in [0, 255].
        """
        colour = Color(red, green, blue)
        for index in range(self._strip.numPixels()):
            self._strip.setPixelColor(index, colour)
        self._strip.show()
        logger.debug(f"LEDs set to RGB ({red}, {green}, {blue}).")

    def off(self) -> None:
        self.setColour(0, 0, 0)

    def cleanup(self) -> None:
        self.off()


# ── OLED CONTROLLER ───────────────────────────────────────────────────────────

class OLEDController:
    """
    Drives an SSD1306 128×64 OLED display over I2C via luma.oled.
    Renders the studio name and the current mental state label.
    """

    def __init__(self) -> None:
        serial      = i2c(port=config.OLED_I2C_PORT, address=config.OLED_I2C_ADDRESS)
        self._oled  = ssd1306(serial)
        logger.info(f"OLEDController initialised at I2C address 0x{config.OLED_I2C_ADDRESS:02X}.")

    def showState(self, state: str) -> None:
        """
        Render the current state on the OLED.

        Args:
            state: Mental state string to display.
        """
        label = config.OLED_LABELS.get(state, state)

        with canvas(self._oled) as draw:
            draw.rectangle(self._oled.bounding_box, outline="white", fill="black")
            draw.text((10, 8),  "Cogniflow",  fill="white")
            draw.line([(10, 28), (118, 28)], fill="white", width=1)
            draw.text((10, 36), label,        fill="white")

        logger.debug(f"OLED updated: '{label}'.")

    def showMessage(self, line1: str, line2: str = "") -> None:
        """Render two arbitrary text lines — useful for boot / shutdown messages."""
        with canvas(self._oled) as draw:
            draw.rectangle(self._oled.bounding_box, outline="white", fill="black")
            draw.text((10, 16), line1, fill="white")
            draw.text((10, 36), line2, fill="white")

    def clear(self) -> None:
        with canvas(self._oled) as draw:
            draw.rectangle(self._oled.bounding_box, fill="black")

    def cleanup(self) -> None:
        self.clear()


# ── HARDWARE CONTROLLER (FACADE) ─────────────────────────────────────────────

class HardwareController:
    """
    Facade that composes FanController, LEDController, and OLEDController.

    External code only interacts with applyState(). Actuator details
    are fully encapsulated — the socket server only needs to call this.
    """

    def __init__(self) -> None:
        self._fan  = FanController()
        self._leds = LEDController()
        self._oled = OLEDController()

        self._applyBootState()
        logger.info("HardwareController ready.")

    def _applyBootState(self) -> None:
        """Set hardware to a safe, visible boot state on startup."""
        self._fan.setSpeed(0.0)
        self._leds.setColour(0, 30, 60)         # Dim blue — "system ready"
        self._oled.showMessage("Cogniflow", "Waiting...")

    def applyState(self, state: str) -> None:
        """
        Apply fan speed, LED colour, and OLED label for the given mental state.

        Args:
            state: One of "FOCUS", "DROWSY", "STRESSED", "RELAXED".
        """
        if state not in config.FAN_SPEED:
            logger.warning(f"Unknown state received: '{state}'. Ignoring.")
            return

        fanSpeed          = config.FAN_SPEED[state]
        red, green, blue  = config.LED_COLOUR[state]

        self._fan.setSpeed(fanSpeed)
        self._leds.setColour(red, green, blue)
        self._oled.showState(state)

        logger.info(f"Hardware applied: state='{state}'  fan={fanSpeed:.2f}  RGB=({red},{green},{blue})")

    def cleanup(self) -> None:
        """Safe shutdown — turn off all actuators."""
        self._fan.cleanup()
        self._leds.cleanup()
        self._oled.cleanup()
        logger.info("HardwareController cleaned up.")