"""
Vocal mixer for combining transformed vocals with instrumental tracks.

Provides timing alignment and volume control for vocal integration.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample
from pathlib import Path
from typing import Union, Optional
import io
import wave


class VocalMixer:
    """Mixes vocal tracks with instrumental tracks."""

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize the vocal mixer.

        Args:
            sample_rate: Output sample rate (default 44100 Hz)
        """
        self.sample_rate = sample_rate

    def load_audio(self, filepath: Union[str, Path]) -> np.ndarray:
        """
        Load a WAV audio file as numpy array.

        Args:
            filepath: Path to WAV audio file

        Returns:
            Audio data as float32 numpy array
        """
        filepath = Path(filepath)
        return self._load_wav(filepath)

    def _load_wav(self, filepath: Path) -> np.ndarray:
        """Load WAV file and convert to float32 mono."""
        rate, data = wavfile.read(filepath)

        # Convert to float32
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype == np.uint8:
            data = (data.astype(np.float32) - 128) / 128.0
        elif data.dtype != np.float32:
            data = data.astype(np.float32)

        # Convert to mono if stereo
        if len(data.shape) > 1:
            data = data.mean(axis=1)

        # Resample if needed (e.g., 22050 Hz vocals to 44100 Hz)
        if rate != self.sample_rate:
            new_len = int(len(data) * self.sample_rate / rate)
            data = resample(data, new_len).astype(np.float32)
            print(f"Resampled audio from {rate}Hz to {self.sample_rate}Hz")

        return data

    def load_audio_bytes(self, audio_bytes: bytes) -> np.ndarray:
        """
        Load WAV audio from bytes.

        Args:
            audio_bytes: WAV audio data as bytes

        Returns:
            Audio data as float32 numpy array
        """
        # Read WAV from bytes using wave module
        with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
            rate = wav_file.getframerate()
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            n_frames = wav_file.getnframes()
            raw_data = wav_file.readframes(n_frames)

        # Convert to numpy array based on sample width
        if sample_width == 2:  # 16-bit
            data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:  # 32-bit
            data = np.frombuffer(raw_data, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            data = np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

        # Convert to mono if stereo
        if n_channels > 1:
            data = data.reshape(-1, n_channels).mean(axis=1)

        # Resample if needed
        if rate != self.sample_rate:
            new_len = int(len(data) * self.sample_rate / rate)
            data = resample(data, new_len).astype(np.float32)

        return data

    def mix(
        self,
        instrumental: np.ndarray,
        vocal: np.ndarray,
        vocal_offset: float = 0.0,
        vocal_volume: float = 1.0,
        instrumental_volume: float = 1.0
    ) -> np.ndarray:
        """
        Mix vocal track with instrumental track.

        Args:
            instrumental: Instrumental audio as numpy array
            vocal: Vocal audio as numpy array
            vocal_offset: Time offset for vocals in seconds (positive = delay)
            vocal_volume: Volume multiplier for vocals (0.0 to 1.0+)
            instrumental_volume: Volume multiplier for instrumental (0.0 to 1.0+)

        Returns:
            Mixed audio as numpy array
        """
        # Apply volume adjustments
        instrumental = instrumental * instrumental_volume
        vocal = vocal * vocal_volume

        # Calculate offset in samples
        offset_samples = int(vocal_offset * self.sample_rate)

        # Calculate required output length
        vocal_end = len(vocal) + max(0, offset_samples)
        output_length = max(len(instrumental), vocal_end)

        # Create output buffer
        output = np.zeros(output_length, dtype=np.float32)

        # Add instrumental
        output[:len(instrumental)] += instrumental

        # Add vocal with offset
        if offset_samples >= 0:
            # Positive offset - vocals start after instrumental start
            end_pos = min(offset_samples + len(vocal), output_length)
            vocal_samples = end_pos - offset_samples
            output[offset_samples:end_pos] += vocal[:vocal_samples]
        else:
            # Negative offset - trim beginning of vocals
            trim = -offset_samples
            if trim < len(vocal):
                output[:len(vocal) - trim] += vocal[trim:]

        return output

    def mix_files(
        self,
        instrumental_path: Union[str, Path],
        vocal_path: Union[str, Path],
        vocal_offset: float = 0.0,
        vocal_volume: float = 1.0,
        instrumental_volume: float = 1.0
    ) -> np.ndarray:
        """
        Load and mix audio files.

        Args:
            instrumental_path: Path to instrumental audio file
            vocal_path: Path to vocal audio file
            vocal_offset: Time offset for vocals in seconds
            vocal_volume: Volume multiplier for vocals
            instrumental_volume: Volume multiplier for instrumental

        Returns:
            Mixed audio as numpy array
        """
        instrumental = self.load_audio(instrumental_path)
        vocal = self.load_audio(vocal_path)

        return self.mix(
            instrumental, vocal,
            vocal_offset=vocal_offset,
            vocal_volume=vocal_volume,
            instrumental_volume=instrumental_volume
        )

    def normalize(self, audio: np.ndarray, headroom_db: float = -1.0) -> np.ndarray:
        """
        Normalize audio to avoid clipping.

        Args:
            audio: Audio buffer to normalize
            headroom_db: Target peak level in dB (default -1 dB)

        Returns:
            Normalized audio
        """
        peak = np.max(np.abs(audio))
        if peak > 0:
            target = 10 ** (headroom_db / 20)
            audio = audio * (target / peak)
        return audio

    def export(self, audio: np.ndarray, filepath: Union[str, Path]) -> None:
        """
        Export audio to WAV file.

        Args:
            audio: Audio data as float32 numpy array
            filepath: Output file path
        """
        # Clip to avoid overflow
        audio = np.clip(audio, -1.0, 1.0)

        # Convert to int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # Write file
        wavfile.write(filepath, self.sample_rate, audio_int16)
