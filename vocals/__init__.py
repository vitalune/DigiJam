"""
Vocals module for DigiJam.

Provides voice recording, ElevenLabs Voice Changer integration,
TTS synthesis, lyrics generation, and vocal-instrumental mixing capabilities.
"""

from .vocal_config import (
    VocalConfig,
    RecordingConfig,
    TTSConfig,
    AVAILABLE_VOICES,
    AVAILABLE_VOICES_EXTENDED,
    VOICE_OPTIONS,
    display_voice_options,
    select_voice,
    get_voice_by_index,
)
from .vocal_recorder import VocalRecorder
from .vocal_processor import VocalProcessor
from .vocal_mixer import VocalMixer, SectionMixer
from .tts_processor import (
    TTSProcessor,
    WordTiming,
    CharTiming,
    ForcedAlignmentResult,
)
from .lyrics_generator import LyricsGenerator
from .voice_selector import VoiceSelector
from .high_ai_pipeline import HighAIPipeline, HighAIPipelineConfig
from .medium_ai_pipeline import MediumAIPipeline, MediumAIPipelineConfig

__all__ = [
    # Config
    'VocalConfig',
    'RecordingConfig',
    'TTSConfig',
    'AVAILABLE_VOICES',
    'AVAILABLE_VOICES_EXTENDED',
    'VOICE_OPTIONS',
    'display_voice_options',
    'select_voice',
    'get_voice_by_index',
    # Core processors
    'VocalRecorder',
    'VocalProcessor',
    'VocalMixer',
    'SectionMixer',
    'TTSProcessor',
    # Forced alignment types
    'WordTiming',
    'CharTiming',
    'ForcedAlignmentResult',
    # AI components
    'LyricsGenerator',
    'VoiceSelector',
    # Pipelines
    'HighAIPipeline',
    'HighAIPipelineConfig',
    'MediumAIPipeline',
    'MediumAIPipelineConfig',
]
