"""
visualiseBands.py — Demo Version
Requires: muselsl stream running in Terminal 1
Run:      python3 visualiseBands.py
"""

import time
import numpy as np
from scipy.signal import welch
from pylsl import StreamInlet, resolve_byprop
from collections import deque
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── CONFIG ────────────────────────────────────────────────────
SAMPLE_RATE      = 256
BUFFER_SECS      = 2
CALIBRATION_SECS = 10        # Short for demo — increase to 30 for real use
HYSTERESIS       = 2

BANDS = {
    "theta": (4.0,  8.0),
    "alpha": (8.0,  13.0),
    "beta":  (13.0, 30.0),
}

THRESHOLDS = {
    "drowsy_fatigue":  2.2,
    "stressed_stress": 1.6,
    "focus_alpha_max": 0.8,
    "focus_beta_min":  1.1,
}

STATE_COLOURS = {
    "CALIBRATING": "#555577",
    "FOCUS":       "#2ecc71",
    "DROWSY":      "#f39c12",
    "STRESSED":    "#e74c3c",
    "RELAXED":     "#3498db",
}

STATE_DESCRIPTIONS = {
    "CALIBRATING": "Building your personal baseline...",
    "FOCUS":       "Alpha suppressed · Beta elevated · Active cognitive processing",
    "DROWSY":      "Theta rising · Beta falling · Fatigue detected",
    "STRESSED":    "Beta dominant · Alpha suppressed · High cognitive load",
    "RELAXED":     "Alpha elevated · Calm resting state",
}


# ── SIGNAL ────────────────────────────────────────────────────

def bandPower(eeg: np.ndarray, low: float, high: float) -> float:
    nperseg = min(SAMPLE_RATE, eeg.shape[1])
    freqs, psd = welch(eeg, fs=SAMPLE_RATE, nperseg=nperseg)
    mask = np.logical_and(freqs >= low, freqs <= high)
    return float(np.mean(psd[:, mask]))

def allPowers(eeg: np.ndarray) -> dict:
    return {b: bandPower(eeg, *BANDS[b]) for b in BANDS}

def classify(norm: dict) -> str:
    t, a, b = norm["theta"], norm["alpha"], norm["beta"]
    fatigue = (t + a) / (b + 1e-6)
    stress  = b / (a + 1e-6)

    if fatigue > THRESHOLDS["drowsy_fatigue"]:
        return "DROWSY"
    if stress > THRESHOLDS["stressed_stress"]:
        return "STRESSED"
    if a < THRESHOLDS["focus_alpha_max"] and b > THRESHOLDS["focus_beta_min"]:
        return "FOCUS"
    return "RELAXED"


# ── MAIN ──────────────────────────────────────────────────────

def main() -> None:
    print("\n  [ Cogniflow ]  Connecting to EEG stream...\n")

    streams = resolve_byprop("type", "EEG", timeout=10)
    if not streams:
        print("  ERROR: No EEG stream. Run muselsl stream first.")
        return

    inlet = StreamInlet(streams[0])
    print(f"  Connected: {streams[0].name()}\n")
    print(f"  Calibrating for {CALIBRATION_SECS}s — sit still, eyes open...\n")

    # ── State ─────────────────────────────────────────────────
    sampleBuffer = deque(maxlen=SAMPLE_RATE * BUFFER_SECS)
    calibSamples = []
    baseline     = None
    calibDone    = False
    calibStart   = time.time()
    hysBuf       = deque(maxlen=HYSTERESIS)
    currentState = "CALIBRATING"
    history      = deque(maxlen=60)   # last 60 state readings for timeline

    # ── Figure layout ─────────────────────────────────────────
    plt.ion()
    fig = plt.figure(figsize=(11, 7), facecolor="#0d0d1a")
    fig.canvas.manager.set_window_title("Cogniflow — Live EEG Classifier")

    gs = gridspec.GridSpec(3, 3, figure=fig,
                           hspace=0.55, wspace=0.35,
                           left=0.08, right=0.96,
                           top=0.92, bottom=0.08)

    axBars    = fig.add_subplot(gs[0:2, 0:2])   # Band power bars
    axGauge   = fig.add_subplot(gs[0:2, 2])     # Fatigue gauge
    axState   = fig.add_subplot(gs[2, :])       # State label

    # ── Bar chart ─────────────────────────────────────────────
    bandLabels = ["Theta  θ\n(4–8 Hz)", "Alpha  α\n(8–13 Hz)", "Beta  β\n(13–30 Hz)"]
    barColours = ["#9b59b6", "#3498db", "#e74c3c"]
    barVals    = [1.0, 1.0, 1.0]

    bars = axBars.bar(bandLabels, barVals, color=barColours,
                      width=0.5, edgecolor="#333355", linewidth=1.5)

    axBars.set_facecolor("#0d1117")
    axBars.set_ylim(0, 2.5)
    axBars.set_ylabel("Normalised Power\n(1.0 = your baseline)",
                      color="#8888aa", fontsize=9)
    axBars.set_title("Live Band Powers", color="white", fontsize=11, pad=8)
    axBars.tick_params(colors="white", labelsize=9)
    axBars.axhline(y=1.0, color="#4444aa", linestyle="--",
                   linewidth=1.2, label="Your baseline")
    axBars.legend(facecolor="#0d1117", labelcolor="#8888aa", fontsize=8)
    for spine in axBars.spines.values():
        spine.set_edgecolor("#222244")

    # Value labels on bars
    barTexts = [
        axBars.text(i, 1.05, "1.00×", ha="center", va="bottom",
                    color="white", fontsize=10, fontweight="bold")
        for i in range(3)
    ]

    # ── Fatigue index gauge ────────────────────────────────────
    axGauge.set_facecolor("#0d1117")
    axGauge.set_title("Fatigue Index\n(θ+α)/β", color="white", fontsize=9, pad=6)
    axGauge.set_xlim(0, 1)
    axGauge.set_ylim(0, 4)
    axGauge.axis("off")

    gaugeBar  = axGauge.barh(2, 0.5, height=0.6,
                              color="#3498db", align="center")[0]
    gaugeText = axGauge.text(0.5, 0.5, "–",
                              ha="center", va="center",
                              color="white", fontsize=18, fontweight="bold",
                              transform=axGauge.transAxes)
    axGauge.text(0.5, 0.12, "threshold: 2.2",
                 ha="center", color="#555577", fontsize=8,
                 transform=axGauge.transAxes)

    # ── State panel ───────────────────────────────────────────
    axState.set_facecolor("#0d1117")
    axState.axis("off")

    stateLabel = axState.text(
        0.5, 0.65, "⏳  CALIBRATING",
        ha="center", va="center",
        fontsize=28, fontweight="bold", color="#555577",
        transform=axState.transAxes
    )
    stateDesc = axState.text(
        0.5, 0.2,
        f"Sit still, eyes open — {CALIBRATION_SECS}s remaining",
        ha="center", va="center",
        fontsize=10, color="#445566",
        transform=axState.transAxes
    )

    fig.suptitle("Cogniflow  ·  Cognitive Load Adaptive Environment",
                 color="#6688aa", fontsize=11, y=0.97)

    # ── Loop ──────────────────────────────────────────────────
    lastDraw = time.time()

    while plt.fignum_exists(fig.number):
        sample, _ = inlet.pull_sample(timeout=0.05)

        if sample is not None:
            sampleBuffer.append(sample[:4])

            if not calibDone:
                calibSamples.append(sample[:4])
                elapsed   = time.time() - calibStart
                remaining = max(0, CALIBRATION_SECS - int(elapsed))
                stateDesc.set_text(
                    f"Sit still, eyes open — {remaining}s remaining"
                )

                if elapsed >= CALIBRATION_SECS and len(calibSamples) >= SAMPLE_RATE:
                    eegCalib = np.array(calibSamples).T
                    baseline = allPowers(eegCalib)
                    calibDone = True
                    print(f"  Baseline — θ:{baseline['theta']:.1f}  "
                          f"α:{baseline['alpha']:.1f}  β:{baseline['beta']:.1f}\n")
                    print(f"  {'STATE':<12} {'θ norm':>8} {'α norm':>8} {'β norm':>8}  FATIGUE")
                    print(f"  {'─'*52}")

        # Redraw at ~10fps
        if time.time() - lastDraw < 0.1:
            plt.pause(0.01)
            continue

        lastDraw = time.time()

        if not calibDone or len(sampleBuffer) < SAMPLE_RATE * BUFFER_SECS:
            plt.pause(0.01)
            continue

        # ── Compute powers ────────────────────────────────────
        eeg    = np.array(list(sampleBuffer)).T
        powers = allPowers(eeg)
        eps    = 1e-6

        normT = powers["theta"] / (baseline["theta"] + eps)
        normA = powers["alpha"] / (baseline["alpha"] + eps)
        normB = powers["beta"]  / (baseline["beta"]  + eps)
        norm  = {"theta": normT, "alpha": normA, "beta": normB}

        fatigue = (normT + normA) / (normB + eps)

        # ── Classify with hysteresis ──────────────────────────
        rawState = classify(norm)
        hysBuf.append(rawState)

        if len(hysBuf) == HYSTERESIS and len(set(hysBuf)) == 1:
            currentState = rawState

        history.append(currentState)

        # ── Update bars ───────────────────────────────────────
        normVals = [normT, normA, normB]
        for bar, val in zip(bars, normVals):
            bar.set_height(val)

        for txt, val, i in zip(barTexts, normVals, range(3)):
            txt.set_position((i, val + 0.04))
            txt.set_text(f"{val:.2f}×")

        axBars.set_ylim(0, max(2.5, max(normVals) * 1.15))

        # Colour bars relative to baseline
        colours = ["#9b59b6", "#3498db", "#e74c3c"]
        for bar, base_colour, val in zip(bars, colours, normVals):
            if val > 1.5:
                bar.set_color("#ff4444" if base_colour == "#e74c3c" else "#ffaa00")
            elif val < 0.6:
                bar.set_color("#224422" if base_colour == "#2ecc71" else "#222244")
            else:
                bar.set_color(base_colour)

        # ── Update fatigue gauge ──────────────────────────────
        gaugeVal = min(fatigue / 4.0, 1.0)
        gaugeBar.set_width(gaugeVal)
        gaugeColour = ("#2ecc71" if fatigue < 1.5
                       else "#f39c12" if fatigue < 2.2
                       else "#e74c3c")
        gaugeBar.set_color(gaugeColour)
        gaugeText.set_text(f"{fatigue:.2f}")
        gaugeText.set_color(gaugeColour)

        # ── Update state label ────────────────────────────────
        colour = STATE_COLOURS[currentState]
        icons  = {
            "FOCUS":    "🟢  FOCUS",
            "DROWSY":   "🟡  DROWSY",
            "STRESSED": "🔴  STRESSED",
            "RELAXED":  "🔵  RELAXED",
        }
        stateLabel.set_text(icons.get(currentState, currentState))
        stateLabel.set_color(colour)
        stateDesc.set_text(STATE_DESCRIPTIONS[currentState])
        stateDesc.set_color(colour)

        # Terminal log
        print(f"  {currentState:<12} "
              f"θ:{normT:>6.2f}×  "
              f"α:{normA:>6.2f}×  "
              f"β:{normB:>6.2f}×  "
              f"fatigue:{fatigue:.2f}")

        plt.pause(0.01)

    print("\n  [ STOPPED ]\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  [ STOPPED ]\n")
    finally:
        plt.close("all")