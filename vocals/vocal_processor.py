"""
ElevenLabs Voice Changer API integration.

Transforms audio from one voice to another using the ElevenLabs
speech-to-speech API.
"""

import os
import struct
import wave
from io import BytesIO
from typing import Optional, Union
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from .vocal_config import VocalConfig


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


class VocalProcessor:
    """Processes vocals using ElevenLabs Voice Changer API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the vocal processor.

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

    def transform_voice(
        self,
        audio_path: Union[str, Path],
        config: Optional[VocalConfig] = None
    ) -> bytes:
        """
        Transform voice in an audio file using ElevenLabs Voice Changer.

        Args:
            audio_path: Path to the input audio file
            config: Voice transformation configuration

        Returns:
            Transformed audio as bytes
        """
        config = config or VocalConfig()

        with open(audio_path, 'rb') as f:
            audio_data = BytesIO(f.read())

        return self._call_api(audio_data, config)

    def transform_voice_bytes(
        self,
        audio_bytes: bytes,
        config: Optional[VocalConfig] = None
    ) -> bytes:
        """
        Transform voice from audio bytes using ElevenLabs Voice Changer.

        Args:
            audio_bytes: Input audio as bytes
            config: Voice transformation configuration

        Returns:
            Transformed audio as bytes
        """
        config = config or VocalConfig()
        audio_data = BytesIO(audio_bytes)

        return self._call_api(audio_data, config)

    def _call_api(self, audio_data: BytesIO, config: VocalConfig) -> bytes:
        """
        Make the API call to ElevenLabs Voice Changer.

        Args:
            audio_data: Audio data as BytesIO
            config: Voice transformation configuration

        Returns:
            Transformed audio as bytes
        """
        audio_stream = self.client.speech_to_speech.convert(
            voice_id=config.voice_id,
            audio=audio_data,
            model_id=config.model_id,
            output_format=config.output_format,
            remove_background_noise=config.remove_background_noise,
        )

        # Collect streamed response into bytes
        return b''.join(audio_stream)

    def save_transformed(
        self,
        audio_bytes: bytes,
        output_path: Union[str, Path],
        config: Optional[VocalConfig] = None
    ) -> None:
        """
        Save transformed audio to a file.

        For PCM format, wraps raw bytes in WAV container.
        For other formats (mp3), saves directly.

        Args:
            audio_bytes: Transformed audio bytes
            output_path: Path to save the output file
            config: VocalConfig used (to determine format)
        """
        config = config or VocalConfig()
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

    def transform_and_save(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        config: Optional[VocalConfig] = None
    ) -> None:
        """
        Transform audio and save to file in one step.

        Args:
            input_path: Path to input audio file
            output_path: Path to save transformed audio
            config: Voice transformation configuration
        """
        transformed = self.transform_voice(input_path, config)
        self.save_transformed(transformed, output_path)
