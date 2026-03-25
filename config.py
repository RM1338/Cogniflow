"""
config.py
---------
Single source of truth for all Cogniflow configuration.
Edit this file only — nothing else should contain magic numbers.
"""


# ── EEG HARDWARE ──────────────────────────────────────────────────────────────

MUSE_BOARD_ID: int = 38          # BrainFlow board ID for Muse 2
SAMPLE_RATE:   int = 256         # Hz — Muse native sample rate
EPOCH_SAMPLES: int = 256         # 1 second of data per classification window
SHIFT_SAMPLES: int = 51          # ~0.2s shift → 5 Hz update rate


# ── EEG FREQUENCY BANDS (Hz) ──────────────────────────────────────────────────

BAND_DELTA: tuple[float, float] = (1.0,  4.0)
BAND_THETA: tuple[float, float] = (4.0,  8.0)
BAND_ALPHA: tuple[float, float] = (8.0,  13.0)
BAND_BETA:  tuple[float, float] = (13.0, 30.0)

BANDS: dict[str, tuple[float, float]] = {
    "delta": BAND_DELTA,
    "theta": BAND_THETA,
    "alpha": BAND_ALPHA,
    "beta":  BAND_BETA,
}


# ── CLASSIFICATION THRESHOLDS ─────────────────────────────────────────────────
# All values are RELATIVE multipliers against personal baseline.
# Never use absolute µV thresholds — every brain is different.

DROWSY_FATIGUE_INDEX:   float = 2.5   # (θ+α)/β above this → DROWSY
STRESSED_BETA_ALPHA:    float = 1.8   # β/α above this → STRESSED
FOCUS_ALPHA_SUPPRESS:   float = 0.7   # α below baseline × this → possible FOCUS
FOCUS_BETA_ELEVATE:     float = 1.2   # Hysteresis for LED state changes
# Require N consecutive epochs of the same state before changing the light.
# At 4Hz broadcast, 8 epochs = 2.0 seconds of sustained state.
HYSTERESIS_EPOCHS:      int   = 8     # 2.0 seconds at 4Hz broadcast before state change
ARTIFACT_VARIANCE_MAX:  float = 100.0 # µV² — discard epoch above this (muscle noise)
CALIBRATION_DURATION:   int   = 60    # Seconds of baseline collection on startup


# ── NETWORK ───────────────────────────────────────────────────────────────────

RPI_IP: str = "192.168.1.x"
RPI_PORT: int = 5005
BUFFER_SIZE: int = 64


# ── MUSIC TRACKS ──────────────────────────────────────────────────────────────
# Place MP3 files in the same directory as laptopBrain.py

MUSIC_VOLUME: float = 0.6   # 0.0 – 1.0

TRACK_MAP: dict[str, str | None] = {
    "FOCUS":    "focusLofi.mp3",       # Dark Sci-Fi / 40Hz
    "DROWSY":   "drowsyUpbeat.mp3",    # Upbeat Lofi Hip Hop
    "STRESSED": "stressedCalm.mp3",    # Heavy Rain
    "RELAXED":  "relaxedGentle.mp3",   # Gentle Piano
}


# ── ACTUATOR: FAN (RPi GPIO) ──────────────────────────────────────────────────

FAN_GPIO_PIN: int = 18   # Must be a hardware PWM pin on RPi

FAN_SPEED: dict[str, float] = {
    "FOCUS":    0.0,    # Off — no distraction during peak focus
    "DROWSY":   0.78,   # Strong airflow — cold air elevates cortical arousal
    "STRESSED": 0.31,   # Gentle breeze — calming without stimulating
    "RELAXED":  0.0,    # Off — sustain the good state
}


# ── ACTUATOR: LED STRIP (RPi GPIO) ────────────────────────────────────────────
# Therapeutic phototherapy colours:
# STRESSED → Warm amber (2700K) : reduces cortical activation, soothing
# DROWSY   → Cool blue-white (6500K) : suppresses melatonin, elevates alertness
# FOCUS    → Soft purple/lavender : calming yet focused, nootropic association
# RELAXED  → Gentle warm white (3000K) : sustain calm without stimulating

LED_GPIO_PIN:  int = 12    # GPIO 12 or 18 required for rpi_ws281x
LED_COUNT:     int = 30
LED_FREQUENCY: int = 800000
LED_DMA:       int = 10
LED_INVERT:    bool = False
LED_BRIGHTNESS:int = 255
# LED colors for the Raspberry Pi NeoPixel strip
# Format: (R, G, B) — 0 to 255.
# These have been updated to a therapeutic phototherapy palette.
LED_COLOUR: dict[str, tuple[int, int, int]] = {
    "CALIBRATING": (10,  10,  10),   # Dim white
    "FOCUS":       (80,   0, 120),   # Deep Purple (low arousal, steady focus)
    "DROWSY":      (255, 180,   0),  # Bright Yellow (alertness, activates visual cortex)
    "STRESSED":    (0,  120, 120),   # Cool Teal (parasympathetic response, lowers heart rate)
    "RELAXED":     (200, 80,   0),   # Warm Amber 2700K (simulates sunset, sustains alpha)
}


# ── ACTUATOR: OLED DISPLAY (RPi I2C) ─────────────────────────────────────────

OLED_I2C_PORT:    int = 1
OLED_I2C_ADDRESS: int = 0x3C

OLED_LABELS: dict[str, str] = {
    "FOCUS":    "FOCUS",
    "DROWSY":   "DROWSY",
    "STRESSED": "STRESSED",
    "RELAXED":  "RELAXED",
}


# ── ACTUATOR: ARDUINO (USB Serial) ───────────────────────────────────────────
# Arduino UNO WiFi R4 connected via USB to the laptop.
# Controls local actuators: fan (PWM), NeoPixel LEDs, buzzer.

ARDUINO_ENABLED:  bool = True
ARDUINO_PORT:     str  = "auto"            # Auto-detected; change if needed
ARDUINO_BAUD:     int  = 115200
ARDUINO_TIMEOUT:  float = 2.0              # Seconds — serial read timeout

# Fan PWM values (0–255, mapped to analogWrite on Arduino pin 9)
ARDUINO_FAN_SPEED: dict[str, int] = {
    "FOCUS":    0,       # Off — no distraction
    "DROWSY":   255,     # Full blast airflow
    "STRESSED": 130,     # Low fan
    "RELAXED":  0,       # Off — sustain the good state
}

# NeoPixel LED colours — therapeutic phototherapy palette
# Must match the LED_COLOUR dictionary above logically, but formatted for the Arduino JSON
ARDUINO_LED_COLOUR: dict[str, dict[str, int]] = {
    "CALIBRATING": {"r": 10,  "g": 10,  "b": 10},
    "FOCUS":       {"r": 80,  "g": 0,   "b": 120},
    "DROWSY":      {"r": 255, "g": 180, "b": 0},
    "STRESSED":    {"r": 0,   "g": 120, "b": 120},
    "RELAXED":     {"r": 200, "g": 80,  "b": 0},
}

# Buzzer alert on state transition (frequency Hz, duration ms, 0 = silent)
ARDUINO_BUZZER: dict[str, tuple[int, int]] = {
    "FOCUS":    (0,    0),       # Silent
    "DROWSY":   (1000, 200),     # Short alert beep
    "STRESSED": (800,  300),     # Slightly longer warning
    "RELAXED":  (0,    0),       # Silent
}

# Arduino pin assignments (must match the sketch)
ARDUINO_PIN_FAN:    int = 9
ARDUINO_PIN_LED:    int = 6
ARDUINO_PIN_BUZZER: int = 3
ARDUINO_LED_COUNT:  int = 30