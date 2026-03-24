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

import time
import threading
import numpy as np
from scipy.signal import welch
from pylsl import StreamInlet, resolve_byprop
from collections import deque
from flask import Flask, render_template_string
from flask_socketio import SocketIO
import pygame
import os

# ── CONFIG ────────────────────────────────────────────────────
SAMPLE_RATE      = 256
BUFFER_SECS      = 2
CALIBRATION_SECS = 30
HYSTERESIS       = 3
BROADCAST_HZ     = 5       # Updates per second to browser
HISTORY_SECS     = 300     # 5 minute session history

BANDS = {
    "theta": (4.0,  8.0),
    "alpha": (8.0,  13.0),
    "beta":  (13.0, 30.0),
}

THRESHOLDS = {
    "drowsy":  2.2,
    "stressed": 1.6,
    "focusAlphaMax": 0.8,
    "focusBetaMin":  1.1,
}

TRACK_MAP = {
    "FOCUS":    "focusLofi.mp3",
    "DROWSY":   "drowsyUpbeat.mp3",
    "STRESSED": "stressedCalm.mp3",
    "RELAXED":  None,
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


# ── SIGNAL PROCESSING ─────────────────────────────────────────

def bandPower(eeg: np.ndarray, low: float, high: float) -> float:
    nperseg = min(SAMPLE_RATE, eeg.shape[1])
    freqs, psd = welch(eeg, fs=SAMPLE_RATE, nperseg=nperseg)
    mask = np.logical_and(freqs >= low, freqs <= high)
    return float(np.mean(psd[:, mask]))

def classify(normT: float, normA: float, normB: float) -> str:
    fatigue = (normT + normA) / (normB + 1e-6)
    stress  = normB / (normA + 1e-6)
    if fatigue > THRESHOLDS["drowsy"]:
        return "DROWSY"
    if stress > THRESHOLDS["stressed"]:
        return "STRESSED"
    if normA < THRESHOLDS["focusAlphaMax"] and normB > THRESHOLDS["focusBetaMin"]:
        return "FOCUS"
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

def eegThread():
    global state

    print("\n  [ COGNIFLOW ]  Looking for EEG stream...\n")
    streams = resolve_byprop("type", "EEG", timeout=15)

    if not streams:
        print("  ERROR: No EEG stream found. Start muselsl first.")
        return

    inlet = StreamInlet(streams[0])
    state["connected"] = True
    print(f"  Connected: {streams[0].name()}\n")
    print(f"  Calibrating for {CALIBRATION_SECS}s...\n")

    sampleBuffer  = deque(maxlen=SAMPLE_RATE * BUFFER_SECS)
    calibSamples  = []
    baseline      = None
    calibDone     = False
    calibStart    = time.time()
    hysBuf        = deque(maxlen=HYSTERESIS)
    prevState     = None
    historyBuffer = deque(maxlen=HISTORY_SECS * BROADCAST_HZ)
    lastBroadcast = time.time()

    while True:
        sample, _ = inlet.pull_sample(timeout=0.05)

        if sample is not None:
            sampleBuffer.append(sample[:4])

            # ── Calibration phase ──────────────────────────
            if not calibDone:
                calibSamples.append(sample[:4])
                elapsed   = time.time() - calibStart
                remaining = max(0, int(CALIBRATION_SECS - elapsed))
                state["calibSeconds"] = remaining

                if elapsed >= CALIBRATION_SECS and len(calibSamples) >= SAMPLE_RATE:
                    eegCalib = np.array(calibSamples).T
                    baseline = {
                        "theta": bandPower(eegCalib, *BANDS["theta"]),
                        "alpha": bandPower(eegCalib, *BANDS["alpha"]),
                        "beta":  bandPower(eegCalib, *BANDS["beta"]),
                    }
                    calibDone          = True
                    state["calibrating"] = False
                    print(f"  Baseline — θ:{baseline['theta']:.1f}  α:{baseline['alpha']:.1f}  β:{baseline['beta']:.1f}\n")

        # ── Broadcast at BROADCAST_HZ ──────────────────────
        if time.time() - lastBroadcast < 1.0 / BROADCAST_HZ:
            continue

        lastBroadcast = time.time()

        if not calibDone or len(sampleBuffer) < SAMPLE_RATE * BUFFER_SECS:
            socketio.emit("eegUpdate", state)
            continue

        # ── Compute powers ────────────────────────────────
        eeg = np.array(list(sampleBuffer)).T

        # Artefact rejection
        if np.max(np.var(eeg, axis=1)) > 50000:
            state["artefactsRejected"] += 1
            socketio.emit("eegUpdate", state)
            continue

        eps    = 1e-6
        powers = {b: bandPower(eeg, *BANDS[b]) for b in BANDS}
        normT  = powers["theta"] / (baseline["theta"] + eps)
        normA  = powers["alpha"] / (baseline["alpha"] + eps)
        normB  = powers["beta"]  / (baseline["beta"]  + eps)
        fatigue = (normT + normA) / (normB + eps)

        # ── Classify with hysteresis ──────────────────────
        rawState = classify(normT, normA, normB)
        hysBuf.append(rawState)

        if len(hysBuf) == HYSTERESIS and len(set(hysBuf)) == 1:
            currentState = rawState
        else:
            currentState = prevState or "RELAXED"

        # ── Update shared state ───────────────────────────
        state["theta"]        = round(normT, 3)
        state["alpha"]        = round(normA, 3)
        state["beta"]         = round(normB, 3)
        state["fatigueIndex"] = round(fatigue, 2)
        state["currentState"] = currentState
        state["description"]  = STATE_DESCRIPTIONS[currentState]

        # Session history — one entry per broadcast
        historyBuffer.append(currentState)
        state["sessionHistory"] = list(historyBuffer)[-60:]   # last 60 points

        # Session stats
        if currentState in state["sessionStats"]:
            state["sessionStats"][currentState] += 1

        # Music
        if currentState != prevState:
            playMusic(currentState)
            prevState = currentState
            print(f"  {currentState:<10}  θ:{normT:.2f}×  α:{normA:.2f}×  β:{normB:.2f}×  fatigue:{fatigue:.2f}")

        socketio.emit("eegUpdate", state)


# ── ROUTES ────────────────────────────────────────────────────

@app.route("/")
def index():
    with open(os.path.join(os.path.dirname(__file__), "cogniflowDashboard.html")) as f:
        return f.read()


@socketio.on("connect")
def onConnect():
    socketio.emit("eegUpdate", state)


# ── MAIN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    thread = threading.Thread(target=eegThread, daemon=True)
    thread.start()

    print("  Dashboard → http://localhost:5000\n")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)