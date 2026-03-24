"""
laptopBrain.py
--------------
Main entry point for the laptop side of Cogniflow.

Pipeline:
  1. Start Muse EEG stream via BrainFlow
  2. Collect 60s personal baseline
  3. Loop every 0.2s:
       a. Read latest EEG epoch
       b. Reject artefact-contaminated epochs
       c. Compute band powers
       d. Classify mental state (with hysteresis)
       e. On confirmed state change:
            - Send state to RPi via UDP (fan / LED / OLED)
            - Switch music track (pygame)

Run:
    muselsl stream          # Terminal 1 — must be running first
    python3 laptopBrain.py  # Terminal 2
"""

import time
import logging

import config
from bandClassifier import EEGBoard, collectBaseline, computeAllBandPowers, isCleanEpoch, StateClassifier
from musicPlayer import MusicPlayer
from socketClient import StateSocketClient

# ── LOGGING SETUP ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── DISPLAY HELPERS ───────────────────────────────────────────────────────────

STATE_ICONS: dict[str, str] = {
    "FOCUS":    "🟢",
    "DROWSY":   "🟡",
    "STRESSED": "🔴",
    "RELAXED":  "🔵",
}

def printStateChange(state: str, powers: dict[str, float]) -> None:
    """Print a formatted line whenever the confirmed state changes."""
    icon = STATE_ICONS.get(state, "⚪")
    print(
        f"  {icon}  STATE → {state:<10s}  |  "
        f"θ: {powers['theta']:.4f}   "
        f"α: {powers['alpha']:.4f}   "
        f"β: {powers['beta']:.4f}"
    )


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n  ╔══════════════════════════════════╗")
    print("  ║         NEUROENV  v1.0           ║")
    print("  ║  Cognitive Load Adaptive Env     ║")
    print("  ╚══════════════════════════════════╝\n")

    board      = EEGBoard()
    music      = MusicPlayer()
    client     = StateSocketClient()
    prevState: str | None = None

    try:
        board.start()

        # ── Phase 1: Calibration ──────────────────────────────────────────────
        baseline   = collectBaseline(board)
        classifier = StateClassifier(baseline)

        print("  [ RUNNING ]  Monitoring cognitive state...\n")

        # ── Phase 2: Classification Loop ──────────────────────────────────────
        while True:
            time.sleep(config.SHIFT_SAMPLES / config.SAMPLE_RATE)

            eeg = board.readEpoch()
            if eeg is None:
                continue

            # Skip noisy epochs — muscle movement, jaw clench, etc.
            if not isCleanEpoch(eeg):
                continue

            powers = computeAllBandPowers(eeg)
            state  = classifier.classify(powers)

            # classifier returns None until hysteresis buffer confirms the state
            if state is None:
                continue

            # Only act on a genuine state transition
            if state == prevState:
                continue

            prevState = state
            printStateChange(state, powers)

            client.send(state)          # → RPi: fan, LED strip, OLED
            music.playForState(state)   # → Laptop speaker: adaptive music

    except KeyboardInterrupt:
        print("\n  [ STOPPED ]  KeyboardInterrupt received.")

    finally:
        music.stop()
        board.stop()
        print("  [ SHUTDOWN ]  Clean exit.\n")


if __name__ == "__main__":
    main()