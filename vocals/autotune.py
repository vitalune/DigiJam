#!/usr/bin/env python3
"""
Autotune module for pitch correction.

Tunes vocals to a specified musical key using:
1. Pitch detection (PYIN algorithm)
2. Pitch correction to nearest scale degree
3. Pitch shifting (PSOLA algorithm)

Usage:
    python -m vocals.autotune input.wav --key "C:min"
    python -m vocals.autotune input.wav --key "A:min" --retune-speed 50 --low-latency
"""

import argparse
import copy
import json
import re
import sys
import os
from dataclasses import dataclass
from typing import Optional, Tuple, List
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf
import scipy.signal as sig

# PSOLA library for pitch shifting
try:
    import psola
    PSOLA_AVAILABLE = True
except ImportError:
    PSOLA_AVAILABLE = False
    psola = None
    print("Warning: psola library not installed. Autotune will be disabled. Install with: pip install psola")


SEMITONES_IN_OCTAVE = 12

# Default output directory for all vocal/autotune files
OUTPUT_DIR = Path("output/vocals")


def ensure_output_dir() -> Path:
    """Ensure the output directory exists and return its path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def get_output_path(filename: str) -> Path:
    """Get full output path for a file in the vocals output directory."""
    ensure_output_dir()
    return OUTPUT_DIR / filename


# Session config directory
SESSION_CONFIG_DIR = Path("output")


def normalize_key_format(key: str) -> Optional[str]:
    """
    Normalize key to librosa format, accepting multiple input formats.

    Accepts:
        - Librosa format: "E:min", "C:maj"
        - Session config format: "E Minor", "C Major"

    Args:
        key: Key in any supported format

    Returns:
        Key in librosa format (e.g., "E:min") or None if invalid
    """
    if not key:
        return None

    key = key.strip()

    # Already in librosa format?
    if ":" in key:
        # Validate it's a known key
        if key in ["C:maj", "C#:maj", "D:maj", "D#:maj", "E:maj", "F:maj",
                   "F#:maj", "G:maj", "G#:maj", "A:maj", "A#:maj", "B:maj",
                   "C:min", "C#:min", "D:min", "D#:min", "E:min", "F:min",
                   "F#:min", "G:min", "G#:min", "A:min", "A#:min", "B:min"]:
            return key
        return None

    # Try session config format ("E Minor", "C Major")
    parts = key.split()
    if len(parts) >= 2:
        root = parts[0]
        mode = parts[1].lower()
        if mode.startswith("min"):
            return f"{root}:min"
        elif mode.startswith("maj"):
            return f"{root}:maj"

    return None


def get_key_from_session_config() -> Optional[str]:
    """
    Read the key from the latest session config file.

    Returns:
        Key in librosa format (e.g., "E:min") or None if not found
    """
    if not SESSION_CONFIG_DIR.exists():
        return None

    # Find numbered config files
    config_pattern = re.compile(r"session_config_(\d+)\.json$")
    numbered_configs = []

    for f in SESSION_CONFIG_DIR.iterdir():
        match = config_pattern.match(f.name)
        if match:
            numbered_configs.append((int(match.group(1)), f))

    config_path = None

    if numbered_configs:
        # Use highest numbered config
        numbered_configs.sort(key=lambda x: x[0], reverse=True)
        config_path = numbered_configs[0][1]
    else:
        # Fallback to unnumbered config
        fallback = SESSION_CONFIG_DIR / "session_config.json"
        if fallback.exists():
            config_path = fallback

    if config_path is None:
        return None

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        key_raw = config.get("key")
        if key_raw:
            key = normalize_key_format(key_raw)
            if key:
                print(f"Using key from {config_path.name}: {key_raw} -> {key}")
                return key
    except (json.JSONDecodeError, IOError):
        pass

    return None


@dataclass
class AutotuneConfig:
    """Configuration for autotune processing."""

    key: str = "C:maj"  # Musical key (e.g., "C:maj", "A:min", "F#:maj")
    fmin: float = 65.41  # C2 - minimum frequency for pitch detection
    fmax: float = 2093.0  # C7 - maximum frequency for pitch detection
    frame_length: int = 2048
    hop_length: Optional[int] = None  # Defaults to frame_length // 4
    correction_strength: float = 1.0  # 0.0 = no correction, 1.0 = full correction
    smoothing_kernel: int = 15  # Median filter kernel size for smoothing

    # Retune speed: 0 = slowest (natural), 100 = fastest (robotic T-Pain effect)
    # Internally maps to smoothing and correction response
    retune_speed: int = 50

    # Low latency mode: smaller frames for faster processing
    low_latency: bool = False

    def __post_init__(self):
        """Apply retune speed and latency settings."""
        self._apply_retune_speed()
        self._apply_latency_mode()

    def _apply_retune_speed(self):
        """
        Convert retune speed (0-100) to internal parameters.

        Speed 0: Very slow correction, natural sounding
        Speed 50: Moderate correction, balanced
        Speed 100: Instant correction, robotic "Cher effect"
        """
        # Map retune speed to smoothing kernel (higher speed = less smoothing)
        # Speed 0 -> kernel 21, Speed 100 -> kernel 1
        max_kernel = 21
        min_kernel = 1
        self.smoothing_kernel = max(
            min_kernel,
            max_kernel - int((self.retune_speed / 100) * (max_kernel - min_kernel))
        )
        # Ensure odd
        if self.smoothing_kernel % 2 == 0:
            self.smoothing_kernel += 1

        # Map retune speed to correction strength
        # Speed 0 -> strength 0.3, Speed 100 -> strength 1.0
        min_strength = 0.3
        max_strength = 1.0
        self.correction_strength = min_strength + (self.retune_speed / 100) * (max_strength - min_strength)

    def _apply_latency_mode(self):
        """Apply low latency settings if enabled."""
        if self.low_latency:
            self.frame_length = 1024  # Smaller frame for faster processing
            self.hop_length = 256  # Smaller hop for more responsive pitch tracking


class PitchDetector:
    """Detects pitch in audio using the PYIN algorithm."""

    def __init__(self, config: AutotuneConfig):
        self.config = config
        self.hop_length = config.hop_length or config.frame_length // 4

    def detect(self, audio: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Detect pitch in audio signal.

        Args:
            audio: Audio time series (mono)
            sr: Sample rate

        Returns:
            Tuple of (f0, voiced_flag, voiced_prob)
            - f0: Fundamental frequency estimates (Hz)
            - voiced_flag: Boolean array indicating voiced frames
            - voiced_prob: Probability of voicing
        """
        f0, voiced_flag, voiced_prob = librosa.pyin(
            audio,
            fmin=self.config.fmin,
            fmax=self.config.fmax,
            sr=sr,
            frame_length=self.config.frame_length,
            hop_length=self.hop_length
        )
        return f0, voiced_flag, voiced_prob


def _modular_semitone_distance(a: float, b: float) -> float:
    """
    Compute the shortest distance between two pitch classes on the
    chromatic circle (0-12), accounting for wraparound.

    Returns a signed value: positive if b is above a (shortest path),
    negative if b is below a.
    """
    diff = (a - b) % SEMITONES_IN_OCTAVE
    if diff > SEMITONES_IN_OCTAVE / 2:
        diff -= SEMITONES_IN_OCTAVE
    return diff


class PitchCorrector:
    """Corrects pitch to the nearest note in a musical scale."""

    def __init__(self, config: AutotuneConfig):
        self.config = config
        self.scale_degrees = self._get_scale_degrees()

    def _get_scale_degrees(self) -> np.ndarray:
        """Get the scale degrees for the configured key."""
        degrees = librosa.key_to_degrees(self.config.key)
        return degrees

    def get_closest_pitch(self, frequency: float) -> float:
        """
        Find the closest pitch in the scale to the given frequency.

        Uses modular distance on the chromatic circle so that wraparound
        between 11 and 0 is handled correctly.

        Args:
            frequency: Input frequency in Hz

        Returns:
            Corrected frequency in Hz (or NaN if input is NaN)
        """
        if np.isnan(frequency):
            return np.nan

        # Convert to MIDI note number
        midi_note = librosa.hz_to_midi(frequency)

        # Get the pitch class (0-11.999...)
        pitch_class = midi_note % SEMITONES_IN_OCTAVE

        # Find closest degree using modular distance
        best_diff = None
        for degree in self.scale_degrees:
            diff = _modular_semitone_distance(pitch_class, degree)
            if best_diff is None or abs(diff) < abs(best_diff):
                best_diff = diff

        # Apply correction strength
        corrected_midi = midi_note - (best_diff * self.config.correction_strength)

        return librosa.midi_to_hz(corrected_midi)

    def correct(self, f0: np.ndarray) -> np.ndarray:
        """
        Correct all pitches to the nearest scale degree.

        Args:
            f0: Array of fundamental frequencies

        Returns:
            Array of corrected frequencies
        """
        corrected = np.array([self.get_closest_pitch(f) for f in f0])

        # Apply median filter for temporal smoothing
        if self.config.smoothing_kernel > 1:
            # Record original NaN positions before filtering
            nan_mask = np.isnan(corrected)

            # Interpolate over NaNs so medfilt doesn't produce artifacts
            valid = ~nan_mask
            if valid.any() and nan_mask.any():
                indices = np.arange(len(corrected))
                corrected[nan_mask] = np.interp(
                    indices[nan_mask],
                    indices[valid],
                    corrected[valid],
                )

            smoothed = sig.medfilt(corrected, kernel_size=self.config.smoothing_kernel)

            # Restore original NaN positions
            smoothed[nan_mask] = np.nan

            return smoothed

        return corrected


class PitchShifter:
    """Shifts pitch using PSOLA algorithm."""

    def __init__(self, config: AutotuneConfig):
        self.config = config

    def shift(self, audio: np.ndarray, sr: int, target_pitch: np.ndarray) -> np.ndarray:
        """
        Shift audio pitch to target frequencies.

        Args:
            audio: Input audio time series
            sr: Sample rate
            target_pitch: Target pitch for each frame

        Returns:
            Pitch-shifted audio
        """
        if not PSOLA_AVAILABLE:
            print("Warning: psola not available, returning original audio")
            return audio

        return psola.vocode(
            audio,
            sample_rate=int(sr),
            target_pitch=target_pitch,
            fmin=self.config.fmin,
            fmax=self.config.fmax
        )


class Autotuner:
    """Main autotune processor combining detection, correction, and shifting."""

    def __init__(self, config: Optional[AutotuneConfig] = None):
        """
        Initialize the autotuner.

        Args:
            config: Autotune configuration. Uses defaults if not provided.
        """
        self.config = config or AutotuneConfig()
        self._build_components()

    def _build_components(self):
        """Build internal components from current config."""
        self.detector = PitchDetector(self.config)
        self.corrector = PitchCorrector(self.config)
        self.shifter = PitchShifter(self.config)

    def process(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Apply autotune to audio.

        Args:
            audio: Input audio time series (mono)
            sr: Sample rate

        Returns:
            Autotuned audio
        """
        # 1. Detect pitch
        f0, voiced_flag, voiced_prob = self.detector.detect(audio, sr)

        # 2. Correct pitch to scale
        corrected_f0 = self.corrector.correct(f0)

        # 3. Shift pitch
        output = self.shifter.shift(audio, sr, corrected_f0)

        return output

    def process_file(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        key: Optional[str] = None
    ) -> str:
        """
        Process an audio file and save the result.

        Args:
            input_path: Path to input audio file
            output_path: Path to save output audio file (defaults to output/vocals/)
            key: Musical key (overrides config if provided)

        Returns:
            Path to the saved output file
        """
        # Update key if provided — rebuild all components so they stay in sync
        if key:
            self.config = copy.deepcopy(self.config)
            self.config.key = key
            self._build_components()

        # Default output path
        if output_path is None:
            input_name = Path(input_path).stem
            output_path = str(get_output_path(f"{input_name}_autotuned.wav"))

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Load audio
        audio, sr = librosa.load(input_path, sr=None, mono=True)
        print(f"Loaded: {input_path}")
        print(f"  Sample rate: {sr} Hz")
        print(f"  Duration: {len(audio) / sr:.2f}s")
        print(f"  Key: {self.config.key}")
        print(f"  Retune speed: {self.config.retune_speed}")
        print(f"  Low latency: {self.config.low_latency}")

        # Process
        print("Processing...")
        output = self.process(audio, sr)

        # Save
        sf.write(output_path, output, sr)
        print(f"Saved: {output_path}")

        return output_path


# Available keys for reference
AVAILABLE_KEYS = [
    # Major keys
    "C:maj", "C#:maj", "D:maj", "D#:maj", "E:maj", "F:maj",
    "F#:maj", "G:maj", "G#:maj", "A:maj", "A#:maj", "B:maj",
    # Minor keys
    "C:min", "C#:min", "D:min", "D#:min", "E:min", "F:min",
    "F#:min", "G:min", "G#:min", "A:min", "A#:min", "B:min",
]


def autotune_audio(input_path: str, output_path: str, config: AutotuneConfig) -> str:
    """
    Simple wrapper function to autotune an audio file.

    Args:
        input_path: Path to input audio file
        output_path: Path to save output audio file
        config: Autotune configuration

    Returns:
        Path to the saved output file
    """
    autotuner = Autotuner(config)
    return autotuner.process_file(input_path, output_path)


def display_available_keys() -> None:
    """Display available musical keys."""
    print("\nAvailable keys (both formats accepted):")
    print("  Major: C:maj (or 'C Major'), C#:maj, D:maj, etc.")
    print("  Minor: C:min (or 'C Minor'), C#:min, D:min, etc.")
    print("\nAll keys:")
    print("  " + ", ".join(k for k in AVAILABLE_KEYS if ":maj" in k))
    print("  " + ", ".join(k for k in AVAILABLE_KEYS if ":min" in k))


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autotune vocals to a specified musical key",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Autotune using key from session config (auto-detected)
    python -m vocals.autotune vocals.wav

    # FULL PIPELINE: Autotune + mix with instrumental (key auto-detected)
    python -m vocals.autotune vocals.wav -i instrumental.wav

    # Override key manually
    python -m vocals.autotune vocals.wav --key "C:min"

    # Full pipeline with custom output and settings
    python -m vocals.autotune vocals.wav -i beat.wav -o song.wav -k "F#:min" -r 80

    # Fast retune speed (robotic T-Pain effect)
    python -m vocals.autotune vocals.wav --retune-speed 100

    # Slow retune (natural sounding)
    python -m vocals.autotune vocals.wav --retune-speed 20

    # List available keys
    python -m vocals.autotune --list-keys
        """
    )

    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        help="Input vocals audio file (WAV)"
    )

    parser.add_argument(
        "-i", "--instrumental",
        type=str,
        default=None,
        help="Instrumental file to mix with autotuned vocals (enables full pipeline)"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output audio file (default: output/vocals/<input>_autotuned.wav or _mixed.wav)"
    )

    parser.add_argument(
        "-k", "--key",
        type=str,
        default=None,
        help="Musical key for pitch correction, e.g. 'E:min' or 'E Minor' (default: auto-detect from session config)"
    )

    parser.add_argument(
        "--vocal-volume",
        type=float,
        default=1.0,
        help="Vocal volume in mix (default: 1.0)"
    )

    parser.add_argument(
        "--instrumental-volume",
        type=float,
        default=0.8,
        help="Instrumental volume in mix (default: 0.8)"
    )

    parser.add_argument(
        "--vocal-offset",
        type=float,
        default=0.0,
        help="Vocal offset in seconds for mixing (default: 0.0)"
    )

    parser.add_argument(
        "-r", "--retune-speed",
        type=int,
        default=50,
        choices=range(0, 101),
        metavar="0-100",
        help="Retune speed: 0=slow/natural, 100=fast/robotic (default: 50)"
    )

    parser.add_argument(
        "-l", "--low-latency",
        action="store_true",
        help="Enable low latency mode (faster processing, smaller buffers)"
    )

    parser.add_argument(
        "-s", "--strength",
        type=float,
        default=None,
        help="Override correction strength 0.0-1.0 (normally set by retune-speed)"
    )

    parser.add_argument(
        "--list-keys",
        action="store_true",
        help="List available musical keys and exit"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    if args.list_keys:
        display_available_keys()
        return 0

    if not args.input:
        print("Error: input file required")
        print("Use --help for usage information")
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    # Check instrumental if provided
    instrumental_path = None
    if args.instrumental:
        instrumental_path = Path(args.instrumental)
        if not instrumental_path.exists():
            print(f"Error: Instrumental file not found: {instrumental_path}")
            return 1

    # Determine key: user-provided > session config > default
    if args.key is not None:
        # Normalize user-provided key (accepts "E Minor" or "E:min")
        key = normalize_key_format(args.key)
        if key is None:
            print(f"Error: Invalid key '{args.key}'")
            display_available_keys()
            return 1
    else:
        key = get_key_from_session_config()
        if key is None:
            key = "C:maj"
            print(f"No session config found, using default key: {key}")

    # Create config
    config = AutotuneConfig(
        key=key,
        retune_speed=args.retune_speed,
        low_latency=args.low_latency
    )

    # Override strength if provided (after __post_init__ has set it from retune_speed)
    if args.strength is not None:
        config.correction_strength = max(0.0, min(1.0, args.strength))

    # Determine if full pipeline or autotune only
    full_pipeline = instrumental_path is not None

    print("\n" + "=" * 50)
    if full_pipeline:
        print("    AUTOTUNE + MIX PIPELINE")
    else:
        print("        AUTOTUNE PROCESSOR")
    print(f"    Key: {key}")
    print("=" * 50)

    # Step 1: Autotune
    print("\n[1/2] Autotuning vocals..." if full_pipeline else "\nProcessing...")

    autotuner = Autotuner(config)

    # For full pipeline, use temp path for autotuned vocals
    if full_pipeline:
        input_name = input_path.stem
        autotuned_path = str(get_output_path(f"{input_name}_autotuned.wav"))
        autotuner.process_file(args.input, autotuned_path)

        # Step 2: Mix with instrumental
        print("\n[2/2] Mixing with instrumental...")

        # Import mixer here to avoid circular imports
        from vocals.vocal_mixer import VocalMixer

        mixer = VocalMixer()
        final_audio = mixer.mix_files(
            instrumental_path=str(instrumental_path),
            vocal_path=autotuned_path,
            vocal_offset=args.vocal_offset,
            vocal_volume=args.vocal_volume,
            instrumental_volume=args.instrumental_volume,
        )

        # Normalize
        final_audio = mixer.normalize(final_audio)

        # Determine output path
        if args.output:
            output_path = str(get_output_path(args.output))
        else:
            output_path = str(get_output_path(f"{input_name}_mixed.wav"))

        mixer.export(final_audio, output_path)

        print(f"\nFiles saved to {OUTPUT_DIR}:")
        print(f"  Autotuned vocals: {Path(autotuned_path).name}")
        print(f"  Final mix:        {Path(output_path).name}")
    else:
        # Autotune only
        output_path = autotuner.process_file(args.input, args.output)
        print(f"\nOutput saved to: {output_path}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())