"""
Vocal mixer for combining transformed vocals with instrumental tracks.

Provides timing alignment and volume control for vocal integration.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample
from pathlib import Path
from typing import Union, Optional, Dict, List
import io
import wave
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


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


class SectionMixer:
    """Mixes TTS vocals into tracks at section-specific timestamps with ducking."""

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize the section mixer.

        Args:
            sample_rate: Output sample rate (default 44100 Hz)
        """
        self.sample_rate = sample_rate

    def mix_section_vocals(
        self,
        main_track: np.ndarray,
        section_audio: Dict[str, np.ndarray],
        section_timings: Dict[str, tuple],
        vocal_volume: float = 0.85,
        duck_amount: float = 0.3,
        crossfade_ms: float = 50.0
    ) -> np.ndarray:
        """
        Mix section vocals into main track at precise timestamps with ducking.

        Args:
            main_track: Main instrumental+melody track
            section_audio: Dict mapping section_name -> audio array
            section_timings: Dict mapping section_name -> (start_time, end_time) in seconds
            vocal_volume: Volume multiplier for vocals (default 0.85)
            duck_amount: How much to reduce instrumental during vocals (0.3 = 30% reduction)
            crossfade_ms: Crossfade duration in milliseconds for smooth transitions

        Returns:
            Final mixed audio as numpy array
        """
        output = main_track.copy()
        crossfade_samples = int(crossfade_ms * self.sample_rate / 1000)

        for section_name, vocals in section_audio.items():
            if section_name not in section_timings:
                continue

            start_time, end_time = section_timings[section_name]
            start_sample = int(start_time * self.sample_rate)
            end_sample = start_sample + len(vocals)

            # Ensure we don't exceed track length
            if start_sample >= len(output):
                continue

            if end_sample > len(output):
                vocals = vocals[:len(output) - start_sample]
                end_sample = len(output)

            # Create ducking envelope for this section
            duck_envelope = self._create_duck_envelope(
                len(vocals),
                duck_amount,
                crossfade_samples
            )

            # Apply ducking to main track in this region
            output[start_sample:end_sample] *= duck_envelope

            # Add vocals
            output[start_sample:end_sample] += vocals * vocal_volume

        return output

    def _create_duck_envelope(
        self,
        length: int,
        duck_amount: float,
        crossfade_samples: int
    ) -> np.ndarray:
        """
        Create a ducking envelope for smooth volume reduction.

        Args:
            length: Length of the envelope in samples
            duck_amount: Amount to duck (0.3 = reduce by 30%)
            crossfade_samples: Fade in/out duration

        Returns:
            Envelope as numpy array (values from duck_amount to 1.0)
        """
        envelope = np.ones(length) * (1.0 - duck_amount)

        # Fade in at start (1.0 -> ducked level)
        if crossfade_samples > 0 and crossfade_samples < length // 2:
            fade_in = np.linspace(1.0, 1.0 - duck_amount, crossfade_samples)
            envelope[:crossfade_samples] = fade_in

            # Fade out at end (ducked level -> 1.0)
            fade_out = np.linspace(1.0 - duck_amount, 1.0, crossfade_samples)
            envelope[-crossfade_samples:] = fade_out

        return envelope.astype(np.float32)

    def mix_from_structure(
        self,
        main_track: np.ndarray,
        section_audio: Dict[str, np.ndarray],
        sections: List,
        vocal_volume: float = 0.85,
        duck_amount: float = 0.3
    ) -> np.ndarray:
        """
        Mix section vocals using SongSection objects for timing.

        Args:
            main_track: Main instrumental+melody track
            section_audio: Dict mapping section_name -> audio array
            sections: List of SongSection objects
            vocal_volume: Volume multiplier for vocals
            duck_amount: How much to reduce instrumental during vocals

        Returns:
            Final mixed audio as numpy array
        """
        # Build timing dict from sections
        section_timings = {}
        for section in sections:
            if hasattr(section, 'name') and hasattr(section, 'start_time') and hasattr(section, 'end_time'):
                # Skip user sections (no AI vocals)
                if hasattr(section, 'is_user_section') and section.is_user_section:
                    continue
                section_timings[section.name] = (section.start_time, section.end_time)

        return self.mix_section_vocals(
            main_track=main_track,
            section_audio=section_audio,
            section_timings=section_timings,
            vocal_volume=vocal_volume,
            duck_amount=duck_amount,
        )

    def add_user_vocals(
        self,
        main_track: np.ndarray,
        user_vocals: np.ndarray,
        vocal_volume: float = 1.0,
        duck_amount: float = 0.2
    ) -> np.ndarray:
        """
        Add user-recorded vocals on top of AI-generated track (for medium mode).

        Args:
            main_track: Main track with AI vocals already mixed
            user_vocals: User's recorded vocals (full track length or partial)
            vocal_volume: Volume multiplier for user vocals
            duck_amount: How much to duck existing audio during user vocals

        Returns:
            Final mixed audio
        """
        # Detect where user vocals are (non-silent regions)
        threshold = 0.01
        has_audio = np.abs(user_vocals) > threshold

        # Dilate the mask to catch attack/decay
        from scipy.ndimage import binary_dilation
        structure = np.ones(int(0.1 * self.sample_rate))  # 100ms dilation
        has_audio = binary_dilation(has_audio, structure=structure)

        # Create output
        output = main_track.copy()

        # Ensure arrays match length
        if len(user_vocals) < len(output):
            user_vocals = np.pad(user_vocals, (0, len(output) - len(user_vocals)))
        elif len(user_vocals) > len(output):
            user_vocals = user_vocals[:len(output)]
            has_audio = has_audio[:len(output)]

        # Apply ducking where user vocals are present
        output[has_audio] *= (1.0 - duck_amount)

        # Add user vocals
        output += user_vocals * vocal_volume

        return output
