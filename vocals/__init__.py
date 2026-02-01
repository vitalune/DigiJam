"""
Vocals module for DigiJam.

Provides voice recording, ElevenLabs Voice Changer integration,
and vocal-instrumental mixing capabilities.
"""

from .vocal_config import (
    VocalConfig,
    RecordingConfig,
    AVAILABLE_VOICES,
    VOICE_OPTIONS,
    display_voice_options,
    select_voice,
    get_voice_by_index,
)
from .vocal_recorder import VocalRecorder
from .vocal_processor import VocalProcessor
from .vocal_mixer import VocalMixer

__all__ = [
    'VocalConfig',
    'RecordingConfig',
    'AVAILABLE_VOICES',
    'VOICE_OPTIONS',
    'display_voice_options',
    'select_voice',
    'get_voice_by_index',
    'VocalRecorder',
    'VocalProcessor',
    'VocalMixer',
]
