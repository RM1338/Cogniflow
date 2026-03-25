"""
bandClassifier.py
-----------------
Handles all EEG signal processing and mental state classification.

Responsibilities:
  - Extract per-band power from raw EEG epochs using Welch PSD
  - Build a personal baseline during the calibration phase
  - Classify mental state using relative band power ratios
  - Apply hysteresis to prevent rapid state flickering
  - Reject artefact-contaminated epochs before classification
"""

import time
import logging
import numpy as np
from scipy.signal import welch
from collections import deque
from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels

import config

logger = logging.getLogger(__name__)


# ── TYPE ALIASES ──────────────────────────────────────────────────────────────

BandPowers  = dict[str, float]   # {"theta": 0.002, "alpha": 0.004, ...}
MentalState = str                # "FOCUS" | "DROWSY" | "STRESSED" | "RELAXED"


# ── EEG BOARD ─────────────────────────────────────────────────────────────────

class EEGBoard:
    """
    Wraps BrainFlow board lifecycle — prepare, stream, read, stop.
    Keeps the rest of the codebase free of BrainFlow-specific calls.
    """

    def __init__(self) -> None:
        BoardShim.disable_board_logger()
        params       = BrainFlowInputParams()
        self._board  = BoardShim(config.MUSE_BOARD_ID, params)
        self._channels = BoardShim.get_eeg_channels(config.MUSE_BOARD_ID)
        self._is_prepared = False

    def start(self) -> None:
        self._board.prepare_session()
        self._is_prepared = True
        self._board.start_stream()
        logger.info("EEG stream started.")

    def stop(self) -> None:
        if self._is_prepared:
            try:
                self._board.stop_stream()
            except Exception as e:
                logger.debug(f"Error stopping stream: {e}")
            self._board.release_session()
            self._is_prepared = False
            logger.info("EEG stream stopped.")

    def readEpoch(self) -> np.ndarray | None:
        """
        Returns an (n_channels × EPOCH_SAMPLES) array of the most recent epoch,
        or None if the buffer does not yet contain enough samples.
        """
        data = self._board.get_current_board_data(config.EPOCH_SAMPLES)
        eeg  = data[self._channels, :]

        if eeg.shape[1] < config.EPOCH_SAMPLES:
            return None

        return eeg


# ── BAND POWER ────────────────────────────────────────────────────────────────

def computeBandPower(eeg: np.ndarray, band: str) -> float:
    """
    Estimate average power in a frequency band across all EEG channels
    using Welch's power spectral density method.

    Args:
        eeg:  (n_channels × n_samples) array of raw EEG data.
        band: Key from config.BANDS — "delta", "theta", "alpha", or "beta".

    Returns:
        Mean PSD value across channels within the specified frequency band.
    """
    low, high = config.BANDS[band]

    freqs, psd = welch(eeg, fs=config.SAMPLE_RATE, nperseg=config.SAMPLE_RATE)

    bandMask = np.logical_and(freqs >= low, freqs <= high)
    return float(np.mean(psd[:, bandMask]))


def computeAllBandPowers(eeg: np.ndarray) -> BandPowers:
    """
    Compute power for all four bands in one call.

    Returns:
        Dict mapping band name to mean PSD value.
    """
    return {band: computeBandPower(eeg, band) for band in config.BANDS}


# ── ARTEFACT REJECTION ────────────────────────────────────────────────────────

def isCleanEpoch(eeg: np.ndarray) -> bool:
    """
    Reject epochs contaminated by muscle noise or movement artefacts.
    A high per-channel variance indicates a noisy epoch that should be skipped.

    Args:
        eeg: (n_channels × n_samples) raw EEG array.

    Returns:
        True if the epoch is clean enough to classify.
    """
    maxVariance = float(np.max(np.var(eeg, axis=1)))

    if maxVariance > config.ARTIFACT_VARIANCE_MAX:
        logger.debug(f"Artefact rejected — variance: {maxVariance:.2f} µV²")
        return False

    return True


# ── BASELINE CALIBRATION ──────────────────────────────────────────────────────

def collectBaseline(board: EEGBoard) -> BandPowers:
    """
    Collect resting-state EEG for CALIBRATION_DURATION seconds to establish
    a personal band power baseline. All classification thresholds are applied
    as multipliers against this baseline — never as absolute values.

    Args:
        board: Active EEGBoard instance already streaming.

    Returns:
        BandPowers dict representing the subject's resting-state reference.
    """
    logger.info(f"Calibrating for {config.CALIBRATION_DURATION}s — sit still, eyes open.")
    print(f"\n  [ CALIBRATING ]  Sit still, eyes open, breathe normally.")
    print(f"  This takes {config.CALIBRATION_DURATION} seconds...\n")

    time.sleep(config.CALIBRATION_DURATION)

    # Collect the full calibration window in one read
    eeg = board.readEpoch()

    # If buffer is shorter than expected, take whatever we have
    if eeg is None:
        logger.warning("Calibration buffer short — using available data.")
        data = board._board.get_board_data()
        eeg  = data[board._channels, :]

    baseline = computeAllBandPowers(eeg)

    logger.info(f"Baseline — θ:{baseline['theta']:.4f}  α:{baseline['alpha']:.4f}  β:{baseline['beta']:.4f}")
    print(f"  [ BASELINE SET ]  θ={baseline['theta']:.4f}  α={baseline['alpha']:.4f}  β={baseline['beta']:.4f}\n")

    return baseline


# ── STATE CLASSIFIER ──────────────────────────────────────────────────────────

class StateClassifier:
    """
    Classifies mental state from band powers relative to a personal baseline.

    Uses two composite indices:
      - Fatigue index  = (θ + α) / β  — rises with drowsiness
      - Stress index   = β / α         — rises with stress / cognitive overload

    Hysteresis buffer prevents rapid state flickering by requiring
    HYSTERESIS_EPOCHS consecutive matching classifications before firing.
    """

    def __init__(self, baseline: BandPowers) -> None:
        self._baseline = baseline
        self._buffer: deque[MentalState] = deque(maxlen=config.HYSTERESIS_EPOCHS)

    def _normalisedRatios(self, powers: BandPowers) -> tuple[float, float, float]:
        """
        Normalise theta, alpha, beta against personal baseline.

        Returns:
            (normTheta, normAlpha, normBeta) — dimensionless ratios.
        """
        epsilon = 1e-6   # Prevent division by zero

        normTheta = powers["theta"] / (self._baseline["theta"] + epsilon)
        normAlpha = powers["alpha"] / (self._baseline["alpha"] + epsilon)
        normBeta  = powers["beta"]  / (self._baseline["beta"]  + epsilon)

        return normTheta, normAlpha, normBeta

    def _rawClassify(self, powers: BandPowers) -> MentalState:
        """
        Apply threshold logic to band power ratios.
        Returns one of: "DROWSY", "STRESSED", "FOCUS", "RELAXED".
        """
        t, a, b = self._normalisedRatios(powers)

        fatigueIndex = (t + a) / (b + 1e-6)
        stressIndex  = b / (a + 1e-6)

        if fatigueIndex > config.DROWSY_FATIGUE_INDEX:
            return "DROWSY"

        if stressIndex > config.STRESSED_BETA_ALPHA:
            return "STRESSED"

        if a < config.FOCUS_ALPHA_SUPPRESS and b > config.FOCUS_BETA_ELEVATE:
            return "FOCUS"

        return "RELAXED"

    def classify(self, powers: BandPowers) -> MentalState | None:
        """
        Classify with hysteresis. Returns a confirmed state only after
        HYSTERESIS_EPOCHS consecutive matching epochs — returns None otherwise.

        Args:
            powers: Current epoch band powers.

        Returns:
            Confirmed MentalState string, or None if not yet confirmed.
        """
        rawState = self._rawClassify(powers)
        self._buffer.append(rawState)

        bufferFull     = len(self._buffer) == config.HYSTERESIS_EPOCHS
        allAgree       = len(set(self._buffer)) == 1

        if bufferFull and allAgree:
            return rawState

        return None