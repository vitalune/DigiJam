"""
ElevenLabs Text-to-Speech API integration.

Synthesizes speech from text using ElevenLabs TTS API for high AI support mode.
Includes Forced Alignment for precise word/character timing.
"""

import os
import wave
from io import BytesIO
from pathlib import Path
from typing import Optional, Union, Tuple, List
from dataclasses import dataclass

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from .vocal_config import TTSConfig, AVAILABLE_VOICES_EXTENDED


@dataclass
class WordTiming:
    """Timing information for a single word."""
    text: str
    start: float  # seconds
    end: float    # seconds
    loss: float   # confidence score (lower is better)


@dataclass
class CharTiming:
    """Timing information for a single character."""
    text: str
    start: float  # seconds
    end: float    # seconds


@dataclass
class ForcedAlignmentResult:
    """Result from forced alignment API."""
    words: List[WordTiming]
    characters: List[CharTiming]
    loss: float  # overall confidence


# Load environment variables
load_dotenv()


def _get_sample_rate_from_format(output_format: str) -> int:
    """Extract sample rate from ElevenLabs output format string."""
    # Format examples: pcm_44100, pcm_22050, mp3_44100_128
    parts = output_format.split('_')
    for part in parts:
        if part.isdigit() and int(part) >= 8000:
            return int(part)
    return 44100  # Default


class TTSProcessor:
    """Synthesizes speech from text using ElevenLabs TTS API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the TTS processor.

        Args:
            api_key: ElevenLabs API key. If not provided, reads from
                     ELEVENLABS_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key required. Set ELEVENLABS_API_KEY "
                "environment variable or pass api_key parameter."
            )

        self.client = ElevenLabs(api_key=self.api_key)

    def synthesize(
        self,
        text: str,
        voice_id: str,
        config: Optional[TTSConfig] = None
    ) -> bytes:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID
            config: TTS configuration

        Returns:
            Audio data as bytes
        """
        config = config or TTSConfig()

        # Build voice settings
        voice_settings = {
            "stability": config.stability,
            "similarity_boost": config.similarity_boost,
            "style": config.style,
            "use_speaker_boost": config.use_speaker_boost,
        }

        # Call TTS API
        audio_stream = self.client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=config.model_id,
            output_format=config.output_format,
            voice_settings=voice_settings,
        )

        # Collect streamed response into bytes
        return b''.join(audio_stream)

    def synthesize_section(
        self,
        lyrics: str,
        voice_id: str,
        config: Optional[TTSConfig] = None
    ) -> Tuple[bytes, float]:
        """
        Synthesize audio for a song section.

        Args:
            lyrics: Lyrics text to synthesize
            voice_id: Voice ID to use
            config: TTS configuration

        Returns:
            Tuple of (audio_bytes, duration_seconds)
        """
        if not lyrics or not lyrics.strip():
            return b'', 0.0

        config = config or TTSConfig()
        audio_bytes = self.synthesize(lyrics, voice_id, config)

        # Calculate duration from audio bytes (PCM 16-bit mono)
        sample_rate = _get_sample_rate_from_format(config.output_format)
        bytes_per_sample = 2  # 16-bit
        num_samples = len(audio_bytes) // bytes_per_sample
        duration = num_samples / sample_rate

        return audio_bytes, duration

    def save_audio(
        self,
        audio_bytes: bytes,
        output_path: Union[str, Path],
        config: Optional[TTSConfig] = None
    ) -> None:
        """
        Save synthesized audio to a file.

        For PCM format, wraps raw bytes in WAV container.
        For other formats (mp3), saves directly.

        Args:
            audio_bytes: Synthesized audio bytes
            output_path: Path to save the output file
            config: TTSConfig used (to determine format)
        """
        config = config or TTSConfig()
        output_path = Path(output_path)

        # Check if PCM format - needs WAV wrapping
        if config.output_format.startswith('pcm_'):
            sample_rate = _get_sample_rate_from_format(config.output_format)
            self._save_pcm_as_wav(audio_bytes, output_path, sample_rate)
        else:
            # MP3 or other format - save directly
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)

    def _save_pcm_as_wav(
        self,
        pcm_bytes: bytes,
        output_path: Path,
        sample_rate: int = 44100,
        channels: int = 1,
        sample_width: int = 2  # 16-bit
    ) -> None:
        """
        Wrap raw PCM bytes in a WAV container.

        Args:
            pcm_bytes: Raw PCM audio data (16-bit signed, little-endian)
            output_path: Output WAV file path
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            sample_width: Bytes per sample (2 for 16-bit)
        """
        # Ensure .wav extension
        if output_path.suffix.lower() != '.wav':
            output_path = output_path.with_suffix('.wav')

        with wave.open(str(output_path), 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)

    def get_voice_info(self, voice_id: str) -> Optional[dict]:
        """
        Get extended voice information for AI selection.

        Args:
            voice_id: Voice ID to look up

        Returns:
            Voice metadata dict or None if not found
        """
        return AVAILABLE_VOICES_EXTENDED.get(voice_id)

    def list_voices_by_mood(self, mood: str) -> list:
        """
        Get voices that match a specific mood.

        Args:
            mood: Mood to match (e.g., "powerful", "calm", "upbeat")

        Returns:
            List of (voice_id, voice_info) tuples that match the mood
        """
        matches = []
        for voice_id, info in AVAILABLE_VOICES_EXTENDED.items():
            if mood.lower() in [m.lower() for m in info.get("moods", [])]:
                matches.append((voice_id, info))
        return matches

    def list_voices_by_energy(self, energy_level: str) -> list:
        """
        Get voices that match a specific energy level.

        Args:
            energy_level: Energy level ("low", "medium", "high")

        Returns:
            List of (voice_id, voice_info) tuples that match the energy
        """
        matches = []
        for voice_id, info in AVAILABLE_VOICES_EXTENDED.items():
            if energy_level.lower() in [e.lower() for e in info.get("energy_match", [])]:
                matches.append((voice_id, info))
        return matches

    def get_forced_alignment(
        self,
        audio_path: Union[str, Path],
        text: str
    ) -> ForcedAlignmentResult:
        """
        Get word and character timing for audio aligned to text.

        Uses ElevenLabs Forced Alignment API to get precise timing
        information for each word and character in the audio.

        Args:
            audio_path: Path to audio file
            text: Text transcript to align with audio

        Returns:
            ForcedAlignmentResult with word and character timings
        """
        audio_path = Path(audio_path)

        with open(audio_path, 'rb') as f:
            result = self.client.forced_alignment.create(
                file=f,
                text=text
            )

        # Convert to our dataclasses
        words = [
            WordTiming(
                text=w.text,
                start=w.start,
                end=w.end,
                loss=w.loss
            )
            for w in result.words
        ]

        characters = [
            CharTiming(
                text=c.text,
                start=c.start,
                end=c.end
            )
            for c in result.characters
        ]

        return ForcedAlignmentResult(
            words=words,
            characters=characters,
            loss=result.loss
        )

    def get_forced_alignment_from_bytes(
        self,
        audio_bytes: bytes,
        text: str,
        sample_rate: int = 44100
    ) -> ForcedAlignmentResult:
        """
        Get word and character timing from audio bytes aligned to text.

        Args:
            audio_bytes: Raw PCM audio bytes
            text: Text transcript to align with audio
            sample_rate: Sample rate of the audio

        Returns:
            ForcedAlignmentResult with word and character timings
        """
        import tempfile

        # Create a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            self._save_pcm_as_wav(audio_bytes, tmp_path, sample_rate)

        try:
            result = self.get_forced_alignment(tmp_path, text)
        finally:
            # Clean up temp file
            tmp_path.unlink(missing_ok=True)

        return result

    def synthesize_with_alignment(
        self,
        text: str,
        voice_id: str,
        config: Optional[TTSConfig] = None
    ) -> Tuple[bytes, float, ForcedAlignmentResult]:
        """
        Synthesize text to speech and get word timing.

        Combines TTS synthesis with forced alignment to get both
        the audio and precise word timing in a single operation.

        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID
            config: TTS configuration

        Returns:
            Tuple of (audio_bytes, duration_seconds, alignment_result)
        """
        config = config or TTSConfig()

        # Synthesize the audio
        audio_bytes, duration = self.synthesize_section(text, voice_id, config)

        if not audio_bytes:
            return b'', 0.0, ForcedAlignmentResult([], [], 0.0)

        # Get forced alignment
        sample_rate = _get_sample_rate_from_format(config.output_format)
        alignment = self.get_forced_alignment_from_bytes(
            audio_bytes, text, sample_rate
        )

        return audio_bytes, duration, alignment
