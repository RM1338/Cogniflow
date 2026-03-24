"""
testHardware.py
---------------
Runs each RPi actuator in sequence to verify wiring before the full system.
Run this on the Raspberry Pi BEFORE rpiActuators.py.

Sequence:
  1. Fan: 3 seconds at 70% speed, then off
  2. LEDs: cycle through all 4 state colours, 2 seconds each
  3. OLED: display each state label, 2 seconds each

Run with sudo:
    sudo python3 testHardware.py
"""

import time
import logging
from gpiozero import PWMOutputDevice
from rpi_ws281x import PixelStrip, Color
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

# ── CONFIG (inline — no import needed for standalone test) ────────────────────

FAN_PIN        = 18
LED_PIN        = 12
LED_COUNT      = 30
OLED_PORT      = 1
OLED_ADDRESS   = 0x3C

STATES = ["FOCUS", "DROWSY", "STRESSED", "RELAXED"]

LED_COLOURS = {
    "FOCUS":    (255, 255, 240),
    "DROWSY":   (180, 210, 255),
    "STRESSED": (255, 180,  80),
    "RELAXED":  (255, 200, 120),
}


# ── TESTS ─────────────────────────────────────────────────────────────────────

def testFan() -> None:
    print("\n  [ FAN TEST ]  Spinning at 70% for 3 seconds...")
    fan = PWMOutputDevice(FAN_PIN)
    fan.value = 0.7
    time.sleep(3)
    fan.off()
    print("  [ FAN TEST ]  Done. Fan should have spun then stopped.")


def testLEDs() -> None:
    print("\n  [ LED TEST ]  Cycling through state colours...")
    strip = PixelStrip(LED_COUNT, LED_PIN, 800000, 10, False, 255)
    strip.begin()

    for state in STATES:
        r, g, b = LED_COLOURS[state]
        colour  = Color(r, g, b)
        print(f"    → {state}  RGB({r}, {g}, {b})")

        for index in range(strip.numPixels()):
            strip.setPixelColor(index, colour)
        strip.show()
        time.sleep(2)

    # Turn off
    for index in range(strip.numPixels()):
        strip.setPixelColor(index, Color(0, 0, 0))
    strip.show()
    print("  [ LED TEST ]  Done. LEDs should have cycled through 4 colours.")


def testOLED() -> None:
    print("\n  [ OLED TEST ]  Displaying each state label...")
    serial = i2c(port=OLED_PORT, address=OLED_ADDRESS)
    oled   = ssd1306(serial)

    for state in STATES:
        print(f"    → {state}")
        with canvas(oled) as draw:
            draw.rectangle(oled.bounding_box, outline="white", fill="black")
            draw.text((10, 8),  "Cogniflow", fill="white")
            draw.line([(10, 28), (118, 28)], fill="white", width=1)
            draw.text((10, 36), state,       fill="white")
        time.sleep(2)

    with canvas(oled) as draw:
        draw.rectangle(oled.bounding_box, outline="white", fill="black")
        draw.text((10, 20), "All tests", fill="white")
        draw.text((10, 36), "passed!",   fill="white")

    print("  [ OLED TEST ]  Done.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n╔══════════════════════════════════╗")
    print("  ║     Cogniflow — Hardware Test    ║")
    print("  ╚══════════════════════════════════╝")

    testFan()
    testLEDs()
    testOLED()

    print("\n  [ COMPLETE ]  All hardware tests passed. Ready for rpiActuators.py\n")


if __name__ == "__main__":
    main()