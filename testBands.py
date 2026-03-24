import time
import numpy as np
from scipy.signal import welch
from pylsl import StreamInlet, resolve_byprop

SAMPLE_RATE = 256
BUFFER_SECS = 3
BANDS = {
    "theta": (4.0,  8.0),
    "alpha": (8.0,  13.0),
    "beta":  (13.0, 30.0),
}

def computePower(eeg: np.ndarray, low: float, high: float) -> float:
    freqs, psd = welch(eeg, fs=SAMPLE_RATE, nperseg=SAMPLE_RATE)
    mask = np.logical_and(freqs >= low, freqs <= high)
    return float(np.mean(psd[:, mask]))

def main() -> None:
    print("\n  [ BAND TEST ]  Looking for EEG stream from muselsl...\n")

    streams = resolve_byprop("type", "EEG", timeout=10)

    if not streams:
        print("  ERROR: No EEG stream found.")
        print("  Make sure muselsl stream is running in another terminal.")
        return

    inlet = StreamInlet(streams[0])
    print(f"  Found: {streams[0].name()}  |  Channels: {streams[0].channel_count()}\n")
    print("  Buffering 3 seconds...\n")
    print(f"  {'θ (theta)':>16}   {'α (alpha)':>16}   {'β (beta)':>16}\n")

    buffer = []

    while True:
        sample, _ = inlet.pull_sample(timeout=1.0)

        if sample:
            buffer.append(sample[:4])

        if len(buffer) < SAMPLE_RATE * BUFFER_SECS:
            continue

        if len(buffer) > SAMPLE_RATE * BUFFER_SECS:
            buffer = buffer[-(SAMPLE_RATE * BUFFER_SECS):]

        eeg   = np.array(buffer).T
        theta = computePower(eeg, *BANDS["theta"])
        alpha = computePower(eeg, *BANDS["alpha"])
        beta  = computePower(eeg, *BANDS["beta"])

        print(f"  θ: {theta:>14.5f}   α: {alpha:>14.5f}   β: {beta:>14.5f}")
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  [ STOPPED ]\n")