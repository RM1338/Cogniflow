"""
cogniflowServer.py
------------------
Flask + SocketIO server that reads EEG from muselsl LSL stream,
classifies mental state, and broadcasts live data to the browser dashboard.

Run:
    Terminal 1: muselsl stream --address XX:XX --backend bleak
    Terminal 2: python3 cogniflowServer.py
    Browser:    http://localhost:5000
"""

import sys
import time
import threading
import numpy as np
from scipy.signal import welch
from pylsl import StreamInlet, resolve_byprop
from collections import deque
from flask import Flask, render_template_string, send_from_directory
from flask_socketio import SocketIO
import pygame
import os
import config
from arduinoController import ArduinoController

# ── CONFIG (stabilised for smooth dashboard + LED control) ───────
SAMPLE_RATE      = 256
BUFFER_SECS      = 2          # Welch PSD trailing window (minimized to 2s for fast 4Hz response)
CALIBUFFER_SECS  = 2     # Welch PSD trailing window (minimized to 2s for fast 4Hz response)
CALIBRATION_SECS = 15         # 15s baseline — enough data without over-inflating
HYSTERESIS       = 4          # Epochs to wait before state switch (4 epochs @ 4Hz = 1s lock)
BROADCAST_HZ     = 4          # Front-end updates per second (4Hz = ultra fast UI)
HISTORY_SECS     = 300
EMA_ALPHA        = 0.4        # Exponential moving average (0.4 means 80% change in ~1.5s)

BANDS = {
    "theta": (4.0,  8.0),
    "alpha": (8.0,  13.0),
    "beta":  (13.0, 30.0),
}

THRESHOLDS = {
    "fatigue_min":      config.DROWSY_FATIGUE_INDEX,   # (θ+α)/β above this → DROWSY
    "stress_ratio":     config.STRESSED_BETA_ALPHA,    # β/α above this → STRESSED
    "focus_engagement": config.FOCUS_BETA_ELEVATE,     # β/(θ+α) above this → FOCUS
    "focus_alpha_max":  config.FOCUS_ALPHA_SUPPRESS,   # α below this → confirms FOCUS
}

TRACK_MAP = {
    "FOCUS":    "audios/focus.mp3",
    "DROWSY":   "audios/drowsy.mp3",
    "STRESSED": "audios/stressed.mp3",
    "RELAXED":  "audios/relaxed.mp3",
}

STATE_DESCRIPTIONS = {
    "CALIBRATING": "Building your personal baseline...",
    "FOCUS":       "Alpha suppressed · Beta elevated · Active cognitive processing",
    "DROWSY":      "Theta rising · Beta falling · Fatigue detected",
    "STRESSED":    "Beta dominant · Alpha suppressed · High cognitive load",
    "RELAXED":     "Alpha elevated · Calm resting state",
}

# ── FLASK APP ─────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "cogniflow"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── SHARED STATE ──────────────────────────────────────────────
state = {
    "connected":    False,
    "calibrating":  True,
    "calibSeconds": CALIBRATION_SECS,
    "currentState": "CALIBRATING",
    "description":  STATE_DESCRIPTIONS["CALIBRATING"],
    "theta":        1.0,
    "alpha":        1.0,
    "beta":         1.0,
    "fatigueIndex": 0.0,
    "sessionHistory": [],
    "sessionStats": {"FOCUS": 0, "RELAXED": 0, "DROWSY": 0, "STRESSED": 0},
    "artefactsRejected": 0,
}


# ── SIGNAL PROCESSING (identical to visualiseBands.py) ────────

def bandPower(eeg: np.ndarray, low: float, high: float) -> float:
    nperseg = min(SAMPLE_RATE, eeg.shape[1])
    freqs, psd = welch(eeg, fs=SAMPLE_RATE, nperseg=nperseg)
    mask = np.logical_and(freqs >= low, freqs <= high)
    return float(np.mean(psd[:, mask]))

def allPowers(eeg: np.ndarray) -> dict:
    return {b: bandPower(eeg, *BANDS[b]) for b in BANDS}

def classify(norm: dict) -> str:
    """
    Classify mental state from normalised band powers using NASA standard formulas.

    Order matters:
      1. DROWSY  — Fatigue: (θ+α)/β
      2. FOCUS   — NASA Engagement Index: β / (θ+α)
      3. STRESSED — Stress Ratio: β/α
      4. RELAXED  — default
    """
    t, a, b = norm["theta"], norm["alpha"], norm["beta"]
    
    # Established EEG Indices
    fatigue    = (t + a) / (b + 1e-6)
    stress     = b / (a + 1e-6)
    engagement = b / (t + a + 1e-6)

    # 1. DROWSY (Fatigue > Threshold)
    if fatigue > THRESHOLDS["fatigue_min"]:
        return "DROWSY"

    # 2. FOCUS (NASA Engagement > Threshold + Alpha Suppressed)
    if engagement > THRESHOLDS["focus_engagement"] and a < THRESHOLDS["focus_alpha_max"]:
        return "FOCUS"

    # 3. STRESSED (Stress Ratio > Threshold + Beta elevated)
    if stress > THRESHOLDS["stress_ratio"] and b > 1.2:
        return "STRESSED"

    # 4. RELAXED — default calm resting state
    return "RELAXED"


# ── MUSIC ─────────────────────────────────────────────────────
pygame.mixer.init()
currentTrack = None

def playMusic(stateKey: str) -> None:
    global currentTrack
    track = TRACK_MAP.get(stateKey)
    if track == currentTrack:
        return
    currentTrack = track
    pygame.mixer.music.stop()
    if track and os.path.exists(track):
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.set_volume(0.6)
            pygame.mixer.music.play(loops=-1)
        except Exception as e:
            print(f"  Music error: {e}")


# ── EEG THREAD ────────────────────────────────────────────────

def log(msg: str) -> None:
    """Print with immediate flush so messages appear in terminal."""
    print(msg, flush=True)


def eegThread():
    global state

    log("\n  [ COGNIFLOW ]  EEG thread started.")
    log("  Looking for EEG stream (will retry until found)...\n")

    # ── Retry loop to find the LSL stream ─────────────────────
    inlet = None
    while inlet is None:
        try:
            streams = resolve_byprop("type", "EEG", timeout=5)
            if streams:
                inlet = StreamInlet(streams[0], max_buflen=BUFFER_SECS)
                state["connected"] = True
                log(f"  ✓ Connected to EEG stream: {streams[0].name()}")
                log(f"    Channels: {streams[0].channel_count()}, Rate: {streams[0].nominal_srate()} Hz\n")
            else:
                log("  ✗ No EEG stream found — retrying in 3s... (run: muselsl stream)")
                socketio.emit("eegUpdate", state)
                time.sleep(3)
        except Exception as e:
            log(f"  ✗ Error resolving stream: {e} — retrying in 3s...")
            time.sleep(3)

    # ── Arduino ───────────────────────────────────────────────
    arduino = None
    if config.ARDUINO_ENABLED:
        try:
            arduino = ArduinoController()
            arduino.connect()
            log("  ✓ Arduino connected\n")
        except Exception as e:
            log(f"  ✗ Arduino connection failed: {e} — continuing without it\n")
            arduino = None

    log(f"  Calibrating for {CALIBRATION_SECS}s — sit still, eyes open...\n")

    # ── State (same structure as visualiseBands.py) ───────────
    sampleBuffer  = deque(maxlen=SAMPLE_RATE * BUFFER_SECS)
    calibSamples  = []
    baseline      = None
    calibDone     = False
    calibStart    = time.time()
    hysBuf        = deque(maxlen=HYSTERESIS)
    currentState  = "CALIBRATING"
    historyBuffer = deque(maxlen=HISTORY_SECS * BROADCAST_HZ)
    lastBroadcast = time.time()
    history       = deque(maxlen=60)
    sampleCount   = 0

    # EMA-smoothed band values (initialised after first computation)
    smoothT = None
    smoothA = None
    smoothB = None

    while True:
        try:
            sample, _ = inlet.pull_sample(timeout=0.05)

            if sample is not None:
                sampleCount += 1
                sampleBuffer.append(sample[:4])

                if sampleCount == 1:
                    log(f"  ✓ First EEG sample received! (values: {[round(v,1) for v in sample[:4]]})")
                if sampleCount == SAMPLE_RATE:
                    log(f"  ✓ {SAMPLE_RATE} samples received — stream is healthy")

                # ── Calibration phase ─────────────────────────────
                if not calibDone:
                    calibSamples.append(sample[:4])
                    elapsed   = time.time() - calibStart
                    remaining = max(0, int(CALIBRATION_SECS - elapsed))
                    state["calibSeconds"] = remaining

                    if elapsed >= CALIBRATION_SECS and len(calibSamples) >= SAMPLE_RATE:
                        eegCalib = np.array(calibSamples).T
                        baseline = allPowers(eegCalib)
                        calibDone = True
                        state["calibrating"] = False
                        log(f"  ✓ Calibration complete!")
                        log(f"    Baseline — θ:{baseline['theta']:.4f}  α:{baseline['alpha']:.4f}  β:{baseline['beta']:.4f}")
                        log(f"    Samples collected: {len(calibSamples)}")
                        log(f"    Now classifying live...\n")
                        log(f"  {'STATE':<12} {'θ norm':>8} {'α norm':>8} {'β norm':>8}  FATIGUE")
                        log(f"  {'─'*52}")

            # ── Broadcast at BROADCAST_HZ ─────────────────────
            now = time.time()
            if now - lastBroadcast < 1.0 / BROADCAST_HZ:
                continue

            lastBroadcast = now

            if not calibDone or len(sampleBuffer) < SAMPLE_RATE * BUFFER_SECS:
                socketio.emit("eegUpdate", state)
                continue

            # ── Compute powers ────────────────────────────────
            eeg    = np.array(list(sampleBuffer)).T
            powers = allPowers(eeg)
            eps    = 1e-6

            rawT = powers["theta"] / (baseline["theta"] + eps)
            rawA = powers["alpha"] / (baseline["alpha"] + eps)
            rawB = powers["beta"]  / (baseline["beta"]  + eps)

            # ── EMA smoothing (gradual transitions) ───────────
            a = EMA_ALPHA
            if smoothT is None:
                smoothT, smoothA, smoothB = rawT, rawA, rawB
            else:
                smoothT = a * rawT + (1 - a) * smoothT
                smoothA = a * rawA + (1 - a) * smoothA
                smoothB = a * rawB + (1 - a) * smoothB

            normT, normA, normB = smoothT, smoothA, smoothB
            norm = {"theta": normT, "alpha": normA, "beta": normB}

            fatigue = (normT + normA) / (normB + eps)

            # ── Classify with hysteresis (same as visualiseBands) ─
            rawState = classify(norm)
            hysBuf.append(rawState)

            if len(hysBuf) == HYSTERESIS and len(set(hysBuf)) == 1:
                if currentState != rawState:
                    currentState = rawState
                    if calibDone and arduino:
                        try:
                            arduino.send(currentState)
                        except Exception as e:
                            log(f"  ✗ Arduino send error: {e}")

            history.append(currentState)

            # ── Update shared state ───────────────────────────
            state["theta"]        = round(normT, 3)
            state["alpha"]        = round(normA, 3)
            state["beta"]         = round(normB, 3)
            state["fatigueIndex"] = round(fatigue, 2)
            state["currentState"] = currentState
            state["description"]  = STATE_DESCRIPTIONS[currentState]

            # Session history
            historyBuffer.append(currentState)
            state["sessionHistory"] = list(historyBuffer)[-60:]

            # Session stats
            if currentState in state["sessionStats"]:
                state["sessionStats"][currentState] += 1

            # Music on state change
            if currentState != getattr(eegThread, '_prevState', None):
                playMusic(currentState)
                eegThread._prevState = currentState
                engagement_log = normB / (normT + normA + 1e-6)
                log(f"  {currentState:<12} "
                    f"θ:{normT:>6.2f}×  "
                    f"α:{normA:>6.2f}×  "
                    f"β:{normB:>6.2f}×  "
                    f"fatg:{(normT+normA)/(normB+1e-6):.2f}  "
                    f"engg:{engagement_log:.2f}  "
                    f"str:{normB/(normA+1e-6):.2f}")

            socketio.emit("eegUpdate", state)

        except Exception as e:
            import traceback
            traceback.print_exc()
            log(f"\n  [ EEG THREAD ERROR ] {e}")
            log("  Retrying in 1s...\n")
            time.sleep(1)


# ── ROUTES ────────────────────────────────────────────────────

@app.route("/")
def index():
    with open(os.path.join(os.path.dirname(__file__), "cogniflowDashboard.html")) as f:
        return f.read()

@app.route("/cogniflowGame.js")
def game_script():
    return send_from_directory(os.path.dirname(__file__), "cogniflowGame.js")

@socketio.on("connect")
def onConnect():
    socketio.emit("eegUpdate", state)


# ── MAIN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    thread = threading.Thread(target=eegThread, daemon=True)
    thread.start()

    print("  Dashboard → http://localhost:5000\n")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)