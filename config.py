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
FOCUS_BETA_ELEVATE:     float = 1.2   # β above baseline × this → confirms FOCUS
RELAXED_ALPHA_ELEVATE:  float = 1.3   # α above baseline × this → RELAXED

HYSTERESIS_EPOCHS:      int   = 3     # Consecutive matching epochs before state fires
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
    "FOCUS":    "focusLofi.mp3",
    "DROWSY":   "drowsyUpbeat.mp3",
    "STRESSED": "stressedCalm.mp3",
    "RELAXED":  None,               # Silence — do not interrupt a good state
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
# Colours are (R, G, B). Values approximate phototherapy colour temperatures.
# DROWSY  → 8000K blue-white  : suppresses melatonin, elevates alertness
# STRESSED → 2700K warm amber : reduces cortical activation, calming
# FOCUS   → 6500K cool white  : neutral, alert, non-intrusive
# RELAXED → 3000K soft white  : sustain without changing

LED_GPIO_PIN:  int = 12    # GPIO 12 or 18 required for rpi_ws281x
LED_COUNT:     int = 30
LED_FREQUENCY: int = 800000
LED_DMA:       int = 10
LED_INVERT:    bool = False
LED_BRIGHTNESS:int = 255

LED_COLOUR: dict[str, tuple[int, int, int]] = {
    "FOCUS":    (255, 255, 240),   # 6500K — cool white
    "DROWSY":   (180, 210, 255),   # 8000K — blue-white
    "STRESSED": (255, 180,  80),   # 2700K — warm amber
    "RELAXED":  (255, 200, 120),   # 3000K — soft warm white
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