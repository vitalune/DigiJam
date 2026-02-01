"""
Audio mixing and rendering for DigiJam Audio Engine.

Loads WAV samples, applies pitch shifting, and mixes events to output.
"""

import numpy as np
from scipy.io import wavfile
from typing import Dict, List, Optional
from pathlib import Path

from .pitch import find_closest_sample, pitch_shift
from .loader import AudioEvent


class AudioMixer:
    """Loads samples and mixes events into final output."""

    # Available sample octaves by instrument
    PIANO_OCTAVES = [2, 3, 4, 5, 6, 7, 8]
    GUITAR_OCTAVES = [3, 4, 5, 6]

    def __init__(self, soundpack_dir: str, sample_rate: int = 44100):
        """
        Initialize the audio mixer.

        Args:
            soundpack_dir: Path to soundpack directory
            sample_rate: Output sample rate (default 44100 Hz)
        """
        self.soundpack_dir = Path(soundpack_dir)
        self.sample_rate = sample_rate
        self.samples: Dict[str, np.ndarray] = {}

    def load_samples(self):
        """Pre-load all samples from soundpack."""
        # Drums - direct action-to-file mapping
        drum_files = {
            'kick': 'kick.wav',
            'hi-hat': 'hi-hat.wav',
            'snare': 'snare.wav',
            'crash': 'guitar.wav',  # Crash is stored as guitar.wav (mislabeled)
        }

        for action, filename in drum_files.items():
            path = self.soundpack_dir / 'drums' / filename
            if path.exists():
                self.samples[f'drums_{action}'] = self._load_wav(path)
                print(f"  Loaded: drums/{filename} -> drums_{action}")

        # Guitar C samples
        for octave in self.GUITAR_OCTAVES:
            path = self.soundpack_dir / 'guitar' / f'C{octave}.wav'
            if path.exists():
                self.samples[f'guitar_C{octave}'] = self._load_wav(path)
                print(f"  Loaded: guitar/C{octave}.wav")

        # Piano C samples
        for octave in self.PIANO_OCTAVES:
            path = self.soundpack_dir / 'piano' / f'C{octave}.wav'
            if path.exists():
                self.samples[f'piano_C{octave}'] = self._load_wav(path)
                print(f"  Loaded: piano/C{octave}.wav")

    def _load_wav(self, path: Path) -> np.ndarray:
        """
        Load WAV file and convert to float32 mono.

        Args:
            path: Path to WAV file

        Returns:
            Audio data as float32 numpy array
        """
        rate, data = wavfile.read(path)

        # Convert to float32 (normalize based on bit depth)
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

        # Resample if needed
        if rate != self.sample_rate:
            from scipy.signal import resample
            new_len = int(len(data) * self.sample_rate / rate)
            data = resample(data, new_len).astype(np.float32)

        return data

    def render(self, events: List[AudioEvent], duration: float) -> np.ndarray:
        """
        Render all events to a single audio buffer.

        Args:
            events: List of AudioEvent objects with quantized_time set
            duration: Total duration in seconds

        Returns:
            Mixed audio as numpy array (float32)
        """
        # Create output buffer (add 3 seconds for sample tails)
        total_samples = int((duration + 3.0) * self.sample_rate)
        output = np.zeros(total_samples, dtype=np.float32)

        for event in events:
            sample_start = int(event.quantized_time * self.sample_rate)

            if event.instrument == 'drums':
                self._render_drums(output, event, sample_start)
            elif event.instrument == 'guitar':
                self._render_guitar(output, event, sample_start)
            elif event.instrument == 'piano':
                self._render_piano(output, event, sample_start)

        return output

    def _render_drums(self, output: np.ndarray, event: AudioEvent, start: int):
        """Render a drum hit to the output buffer."""
        key = f'drums_{event.action}'
        if key in self.samples:
            sample = self.samples[key] * event.velocity
            self._mix_in(output, sample, start)

    def _render_guitar(self, output: np.ndarray, event: AudioEvent, start: int):
        """Render a guitar strum to the output buffer."""
        for note in event.notes:
            sample_note, shift = find_closest_sample(note, self.GUITAR_OCTAVES)
            key = f'guitar_{sample_note}'

            if key in self.samples:
                sample = self.samples[key].copy()
                if shift != 0:
                    sample = pitch_shift(sample, shift, self.sample_rate)
                sample = sample * event.velocity
                self._mix_in(output, sample, start)

    def _render_piano(self, output: np.ndarray, event: AudioEvent, start: int):
        """Render piano notes to the output buffer."""
        # Each note in a chord is rendered independently
        for note in event.notes:
            sample_note, shift = find_closest_sample(note, self.PIANO_OCTAVES)
            key = f'piano_{sample_note}'

            if key in self.samples:
                sample = self.samples[key].copy()
                if shift != 0:
                    sample = pitch_shift(sample, shift, self.sample_rate)
                sample = sample * event.velocity
                self._mix_in(output, sample, start)

    def _mix_in(self, output: np.ndarray, sample: np.ndarray, start: int):
        """Add sample to output buffer at given position."""
        if start < 0:
            # Trim sample if start is negative
            sample = sample[-start:]
            start = 0

        end = min(start + len(sample), len(output))
        sample_len = end - start

        if sample_len > 0:
            output[start:end] += sample[:sample_len]

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

    def export_wav(self, audio: np.ndarray, output_path: str):
        """
        Export audio to WAV file.

        Args:
            audio: Audio data as float32 numpy array
            output_path: Output file path
        """
        # Clip to avoid overflow
        audio = np.clip(audio, -1.0, 1.0)

        # Convert to int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # Write file
        wavfile.write(output_path, self.sample_rate, audio_int16)
