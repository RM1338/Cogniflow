"""
musicPlayer.py
--------------
State-driven adaptive music playback using pygame.

Each mental state maps to a specific audio track defined in config.TRACK_MAP.
Tracks loop indefinitely until the state changes. Silence is handled gracefully
(RELAXED → no music, do not interrupt a good state).

Usage:
    player = MusicPlayer()
    player.playForState("DROWSY")   # switches track immediately
    player.stop()
"""

import logging
import pygame

import config

logger = logging.getLogger(__name__)


class MusicPlayer:
    """
    Wraps pygame.mixer for state-driven music playback.
    Initialises the mixer once and reuses it across state transitions.
    """

    def __init__(self) -> None:
        pygame.mixer.init()
        self._currentState: str | None = None
        logger.info("MusicPlayer initialised.")

    def playForState(self, state: str) -> None:
        """
        Switch to the track mapped to the given mental state.
        Does nothing if the state hasn't changed since last call.

        Args:
            state: One of "FOCUS", "DROWSY", "STRESSED", "RELAXED".
        """
        if state == self._currentState:
            return

        self._currentState = state
        trackPath = config.TRACK_MAP.get(state)

        pygame.mixer.music.stop()

        if trackPath is None:
            logger.info(f"Music: silence for state '{state}'.")
            return

        try:
            pygame.mixer.music.load(trackPath)
            pygame.mixer.music.set_volume(config.MUSIC_VOLUME)
            pygame.mixer.music.play(loops=-1)   # -1 = loop indefinitely
            logger.info(f"Music: playing '{trackPath}' for state '{state}'.")

        except pygame.error as error:
            logger.error(f"Music load failed for '{trackPath}': {error}")
            logger.error("Ensure the MP3 file exists in the same directory as laptopBrain.py.")

    def stop(self) -> None:
        """Stop playback and reset state tracking."""
        pygame.mixer.music.stop()
        self._currentState = None
        logger.info("MusicPlayer stopped.")