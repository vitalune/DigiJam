"""
DigiJam Audio Engine Module

Provides audio processing capabilities for rendering gesture-detected
music sessions to WAV files.
"""

from .loader import AudioEvent, load_drums_session, load_guitar_session, load_piano_session
from .quantizer import build_grid, snap_to_grid, get_grid_for_event
from .pitch import find_closest_sample, pitch_shift
from .mixer import AudioMixer

__all__ = [
    'AudioEvent',
    'load_drums_session',
    'load_guitar_session',
    'load_piano_session',
    'build_grid',
    'snap_to_grid',
    'get_grid_for_event',
    'find_closest_sample',
    'pitch_shift',
    'AudioMixer',
]
