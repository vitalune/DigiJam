#!/usr/bin/env python3
"""
ElevenLabs Music Composer - Generates complementary melodies for existing tracks.

Uses the audio analyzer to extract features and generate descriptions, then
prompts ElevenLabs music API to compose a melody that complements the original track.
Automatically mixes the generated melody with the input track at a lower volume.

Usage:
    python compose_music.py track.wav
    python compose_music.py track.wav --length 30000
    python compose_music.py track.wav --melody-volume 0.3
    python compose_music.py --prompt "upbeat jazz piano at 120 BPM in C major"
"""

import argparse
import io
import json
import os
import sys
import tempfile
import wave
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import requests
import soundfile as sf
from scipy.io import wavfile
from scipy.signal import resample
from dotenv import load_dotenv

# Import from our analyzer
from analyze_wav import (
    FeatureExtractor,
    SessionConfigManager,
    MusicDescriber,
    AudioFeatures,
    OUTPUT_DIR,
)

# Load environment variables
load_dotenv()

# Output directory for generated music
MUSIC_OUTPUT_DIR = Path("output/music")

# AI support level volume presets for melody/instrumental mixing
AI_VOLUME_PRESETS: Dict[str, Dict[str, float]] = {
    "low":    {"melody": 0.2, "instrumental": 1.0},   # Melody as subtle background
    "medium": {"melody": 0.5, "instrumental": 0.6},   # Balanced collaboration
    "high":   {"melody": 0.7, "instrumental": 0.4},   # Melody as primary
}


@dataclass
class CompositionConfig:
    """Configuration for music composition."""

    # Basic settings
    output_format: str = "mp3_44100_128"
    model_id: str = "music_v1"
    force_instrumental: bool = True

    # Length in milliseconds (3000-600000)
    music_length_ms: Optional[int] = None

    # Advanced options
    with_timestamps: bool = False
    sign_with_c2pa: bool = False


@dataclass
class SongSection:
    """A section of a composition plan."""

    section_name: str
    positive_local_styles: List[str]
    negative_local_styles: List[str]
    duration_ms: int
    lines: List[str]


@dataclass
class CompositionPlan:
    """Detailed composition plan for structured music generation."""

    positive_global_styles: List[str]
    negative_global_styles: List[str]
    sections: List[SongSection]


class MusicComposer:
    """Composes music using ElevenLabs music API."""

    API_URL = "https://api.elevenlabs.io/v1/music/detailed"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the music composer.

        Args:
            api_key: ElevenLabs API key. If not provided, reads from ELEVENLABS_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key required. Set ELEVENLABS_API_KEY environment variable "
                "or pass api_key parameter."
            )

    def compose_from_prompt(
        self,
        prompt: str,
        config: Optional[CompositionConfig] = None
    ) -> bytes:
        """
        Compose music from a text prompt.

        Args:
            prompt: Natural language description of desired music
            config: Composition configuration

        Returns:
            Audio data as bytes
        """
        config = config or CompositionConfig()

        payload = {
            "prompt": prompt,
            "model_id": config.model_id,
            "force_instrumental": config.force_instrumental,
            "with_timestamps": config.with_timestamps,
            "sign_with_c2pa": config.sign_with_c2pa,
        }

        if config.music_length_ms:
            payload["music_length_ms"] = config.music_length_ms

        return self._call_api(payload, config.output_format)

    def compose_from_plan(
        self,
        plan: CompositionPlan,
        config: Optional[CompositionConfig] = None
    ) -> bytes:
        """
        Compose music from a detailed composition plan.

        Args:
            plan: Structured composition plan
            config: Composition configuration

        Returns:
            Audio data as bytes
        """
        config = config or CompositionConfig()

        sections_data = []
        for section in plan.sections:
            sections_data.append({
                "section_name": section.section_name,
                "positive_local_styles": section.positive_local_styles,
                "negative_local_styles": section.negative_local_styles,
                "duration_ms": section.duration_ms,
                "lines": section.lines,
            })

        payload = {
            "composition_plan": {
                "positive_global_styles": plan.positive_global_styles,
                "negative_global_styles": plan.negative_global_styles,
                "sections": sections_data,
            },
            "model_id": config.model_id,
            "with_timestamps": config.with_timestamps,
            "sign_with_c2pa": config.sign_with_c2pa,
        }

        return self._call_api(payload, config.output_format)

    def _call_api(self, payload: Dict[str, Any], output_format: str) -> bytes:
        """
        Make the API call to ElevenLabs music endpoint.

        Args:
            payload: Request payload
            output_format: Desired output format

        Returns:
            Audio data as bytes
        """
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }

        params = {"output_format": output_format}

        response = requests.post(
            self.API_URL,
            headers=headers,
            params=params,
            json=payload,
            timeout=300  # 5 minute timeout for long compositions
        )

        if response.status_code != 200:
            error_msg = f"ElevenLabs API error: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f" - {error_detail}"
            except Exception:
                error_msg += f" - {response.text}"
            raise RuntimeError(error_msg)

        return response.content

    def save_audio(
        self,
        audio_bytes: bytes,
        output_path: Path,
        config: Optional[CompositionConfig] = None
    ) -> None:
        """
        Save composed audio to a file.

        Args:
            audio_bytes: Audio data
            output_path: Path to save the file
            config: Composition config (for format detection)
        """
        config = config or CompositionConfig()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if audio already has WAV header (even if we requested PCM)
        has_wav_header = len(audio_bytes) >= 4 and audio_bytes[:4] == b'RIFF'

        if has_wav_header:
            # Already a WAV file - save directly
            if output_path.suffix.lower() != '.wav':
                output_path = output_path.with_suffix('.wav')
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)
        elif config.output_format.startswith("pcm_"):
            # Raw PCM - wrap in WAV container
            sample_rate = int(config.output_format.split("_")[1])
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
        channels: int = 2,
        sample_width: int = 2
    ) -> None:
        """Wrap raw PCM bytes in a WAV container."""
        if output_path.suffix.lower() != '.wav':
            output_path = output_path.with_suffix('.wav')

        # Ensure byte alignment: bytes must be multiple of (sample_width * channels)
        bytes_per_frame = sample_width * channels
        byte_count = len(pcm_bytes)
        remainder = byte_count % bytes_per_frame
        if remainder != 0:
            pcm_bytes = pcm_bytes[:byte_count - remainder]

        with wave.open(str(output_path), 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)


class MelodyMixer:
    """Mixes generated melody with original track."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

    def load_wav(self, filepath: Path) -> np.ndarray:
        """Load WAV file as float32 numpy array."""
        rate, data = wavfile.read(filepath)

        # Convert to float32
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype != np.float32:
            data = data.astype(np.float32)

        # Convert to mono if stereo
        if len(data.shape) > 1:
            data = data.mean(axis=1)

        # Resample if needed
        if rate != self.sample_rate:
            new_len = int(len(data) * self.sample_rate / rate)
            data = resample(data, new_len).astype(np.float32)

        return data

    def load_audio_bytes(
        self,
        audio_bytes: bytes,
        format_hint: str = "pcm",
        pcm_sample_rate: int = 44100,
        pcm_channels: int = 2
    ) -> np.ndarray:
        """
        Load audio from bytes (WAV/PCM/MP3) as float32 numpy array.

        Args:
            audio_bytes: Raw audio bytes
            format_hint: Format hint (pcm_* or mp3_*)
            pcm_sample_rate: Sample rate for raw PCM (when no WAV header)
            pcm_channels: Number of channels for raw PCM

        Returns:
            Audio as float32 numpy array
        """
        # Detect actual format from magic bytes
        has_wav_header = len(audio_bytes) >= 4 and audio_bytes[:4] == b'RIFF'
        has_mp3_id3 = len(audio_bytes) >= 3 and audio_bytes[:3] == b'ID3'
        has_mp3_sync = len(audio_bytes) >= 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0

        if has_wav_header:
            # Parse as WAV file
            with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
                rate = wav_file.getframerate()
                n_channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                raw_data = wav_file.readframes(wav_file.getnframes())

            # Convert to numpy array based on sample width
            if sample_width == 2:
                data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 4:
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

        elif has_mp3_id3 or has_mp3_sync:
            # MP3 file - use soundfile to decode
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                data, rate = sf.read(tmp_path, dtype='float32')

                # Convert to mono if stereo
                if len(data.shape) > 1:
                    data = data.mean(axis=1)

                # Resample if needed
                if rate != self.sample_rate:
                    new_len = int(len(data) * self.sample_rate / rate)
                    data = resample(data, new_len).astype(np.float32)
            finally:
                os.unlink(tmp_path)

        elif format_hint.startswith("pcm_"):
            # Raw PCM - 16-bit signed little-endian
            # Ensure byte count is a multiple of (2 bytes * channels) for proper alignment
            bytes_per_frame = 2 * pcm_channels  # 2 bytes per sample * channels
            byte_count = len(audio_bytes)
            remainder = byte_count % bytes_per_frame
            if remainder != 0:
                audio_bytes = audio_bytes[:byte_count - remainder]

            data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # Convert to mono if stereo
            if pcm_channels > 1:
                data = data.reshape(-1, pcm_channels).mean(axis=1)

            # Resample if needed
            if pcm_sample_rate != self.sample_rate:
                new_len = int(len(data) * self.sample_rate / pcm_sample_rate)
                data = resample(data, new_len).astype(np.float32)

        elif format_hint.startswith("mp3_"):
            # MP3 format hint but no magic bytes detected - try decoding anyway
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                data, rate = sf.read(tmp_path, dtype='float32')

                # Convert to mono if stereo
                if len(data.shape) > 1:
                    data = data.mean(axis=1)

                # Resample if needed
                if rate != self.sample_rate:
                    new_len = int(len(data) * self.sample_rate / rate)
                    data = resample(data, new_len).astype(np.float32)
            finally:
                os.unlink(tmp_path)
        else:
            raise ValueError(f"Unsupported audio format: {format_hint}")

        return data

    def mix(
        self,
        original: np.ndarray,
        melody: np.ndarray,
        melody_volume: float = 0.3,
        original_volume: float = 1.0
    ) -> np.ndarray:
        """
        Mix melody with original track.

        Args:
            original: Original track audio
            melody: Generated melody audio
            melody_volume: Volume multiplier for melody (default 0.3 = 30%)
            original_volume: Volume multiplier for original (default 1.0)

        Returns:
            Mixed audio as numpy array
        """
        # Apply volumes
        original = original * original_volume
        melody = melody * melody_volume

        # Pad shorter array to match lengths
        if len(melody) < len(original):
            melody = np.pad(melody, (0, len(original) - len(melody)))
        elif len(original) < len(melody):
            original = np.pad(original, (0, len(melody) - len(original)))

        # Mix
        mixed = original + melody

        return mixed

    def mix_with_ai_level(
        self,
        original: np.ndarray,
        melody: np.ndarray,
        ai_support_level: str = "low"
    ) -> np.ndarray:
        """
        Mix melody with original track using AI support level presets.

        Args:
            original: Original track audio (user's instrumental)
            melody: Generated melody audio
            ai_support_level: "low", "medium", or "high"

        Returns:
            Mixed audio as numpy array
        """
        preset = AI_VOLUME_PRESETS.get(ai_support_level, AI_VOLUME_PRESETS["low"])
        return self.mix(
            original=original,
            melody=melody,
            melody_volume=preset["melody"],
            original_volume=preset["instrumental"]
        )

    def normalize(self, audio: np.ndarray, target_peak: float = 0.95, max_gain: float = 10.0) -> np.ndarray:
        """Normalize audio to target peak level with gain limiting."""
        peak = np.max(np.abs(audio))
        if peak > 0:
            gain = target_peak / peak
            # Limit maximum amplification to prevent boosting noise into static
            gain = min(gain, max_gain)
            audio = audio * gain
        # Clip to valid range to prevent overflow
        audio = np.clip(audio, -1.0, 1.0)
        return audio

    def export(self, audio: np.ndarray, filepath: Path) -> None:
        """Export audio to WAV file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Clip to valid range before conversion to prevent int16 overflow
        audio = np.clip(audio, -1.0, 1.0)

        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)

        wavfile.write(str(filepath), self.sample_rate, audio_int16)


def build_complementary_prompt(features: AudioFeatures, description: str) -> str:
    """
    Build a prompt for generating music that complements an analyzed track.

    Args:
        features: Extracted audio features
        description: Natural language description from Claude

    Returns:
        Prompt string for ElevenLabs music API
    """
    # Extract key info
    key = features.key
    bpm = features.tempo_bpm

    # Build the prompt
    prompt_parts = [
        f"Compose an instrumental melody at {bpm} BPM in {key}.",
        f"Style: {description}",
        "Create a complementary melodic line that would blend well with the described track.",
        "Focus on melodic hooks and harmonically compatible progressions.",
    ]

    return " ".join(prompt_parts)


def analyze_and_compose(
    input_path: str,
    config: CompositionConfig,
    config_path: Optional[str] = None,
    verbose: bool = False
) -> bytes:
    """
    Full pipeline: analyze audio and compose complementary melody.

    Args:
        input_path: Path to input WAV file
        config: Composition configuration
        config_path: Optional session config path
        verbose: Print detailed output

    Returns:
        Composed audio as bytes
    """
    # Step 1: Extract features
    if verbose:
        print("\n[1/3] Extracting audio features...")

    extractor = FeatureExtractor()
    config_p = Path(config_path) if config_path else None
    features = extractor.extract(input_path, config_p)

    if verbose:
        print(f"  BPM: {features.tempo_bpm}")
        print(f"  Key: {features.key} (source: {features.key_source})")
        print(f"  Duration: {features.duration_seconds}s")

    # Step 2: Generate description via Claude
    if verbose:
        print("\n[2/3] Generating music description via Claude...")

    try:
        describer = MusicDescriber()
        description = describer.describe(features)
        if verbose:
            print(f"  Description: {description[:100]}...")
    except ValueError as e:
        # No Claude API key - use fallback description
        if verbose:
            print(f"  Warning: {e}")
            print("  Using fallback description based on features...")

        # Build fallback description from features
        energy = "high energy" if features.onset_strength_mean > 1.5 else "moderate energy"
        brightness = "bright" if features.spectral_centroid_mean > 2500 else "warm"
        description = f"{energy} {brightness} track in {features.key} at {features.tempo_bpm} BPM"

    # Step 3: Compose melody
    if verbose:
        print("\n[3/3] Composing complementary melody via ElevenLabs...")

    prompt = build_complementary_prompt(features, description)

    if verbose:
        print(f"  Prompt: {prompt[:100]}...")

    composer = MusicComposer()
    audio = composer.compose_from_prompt(prompt, config)

    return audio


def ensure_output_dir() -> Path:
    """Ensure the music output directory exists."""
    MUSIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return MUSIC_OUTPUT_DIR


def get_output_path(filename: str) -> Path:
    """Get full output path for a file in the music output directory."""
    ensure_output_dir()
    return MUSIC_OUTPUT_DIR / filename


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Compose complementary melodies using ElevenLabs music API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze track and compose + mix melody (default melody volume: 30%)
    python compose_music.py track.wav

    # Custom melody volume (0.0-1.0)
    python compose_music.py track.wav --melody-volume 0.4

    # Specify length (in milliseconds)
    python compose_music.py track.wav --length 30000

    # Save melody only (no mixing)
    python compose_music.py track.wav --no-mix

    # Direct prompt (no analysis, no mixing)
    python compose_music.py --prompt "upbeat jazz piano at 120 BPM in C major"

    # Use specific session config for BPM/key
    python compose_music.py track.wav --config output/session_config_001.json
        """
    )

    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        help="Input WAV audio file to analyze"
    )

    parser.add_argument(
        "-p", "--prompt",
        type=str,
        default=None,
        help="Direct text prompt for music generation (skips analysis)"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output file path (default: output/music/melody_TIMESTAMP.mp3)"
    )

    parser.add_argument(
        "-l", "--length",
        type=int,
        default=None,
        help="Music length in milliseconds (3000-600000)"
    )

    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        help="Path to session config file for BPM/key"
    )

    parser.add_argument(
        "--format",
        type=str,
        default="mp3_44100_128",
        choices=[
            "mp3_22050_32", "mp3_44100_64", "mp3_44100_128", "mp3_44100_192",
            "pcm_22050", "pcm_44100", "wav"
        ],
        help="Output audio format (default: mp3_44100_128)"
    )

    parser.add_argument(
        "--vocals",
        action="store_true",
        help="Allow vocals in generated music (default: instrumental only)"
    )

    parser.add_argument(
        "-m", "--melody-volume",
        type=float,
        default=0.3,
        help="Melody volume when mixing (0.0-1.0, default: 0.3)"
    )

    parser.add_argument(
        "--no-mix",
        action="store_true",
        help="Save melody only without mixing with input track"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed progress information"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output composition info as JSON"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Require either input file or direct prompt
    if not args.input and not args.prompt:
        print("Error: Either input file or --prompt is required")
        print("Use --help for usage information")
        return 1

    # Build config
    # Use PCM format when mixing is needed (no ffmpeg dependency)
    if args.input and not args.no_mix:
        # Force MP3 format for mixing
        output_format = "mp3_44100_128"
    else:
        output_format = args.format if args.format != "wav" else "mp3_44100_128"

    config = CompositionConfig(
        output_format=output_format,
        force_instrumental=not args.vocals,
        music_length_ms=args.length,
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".wav" if args.format.startswith("pcm") or args.format == "wav" else ".mp3"
        output_path = get_output_path(f"melody_{timestamp}{ext}")

    try:
        if args.prompt:
            # Direct prompt mode (no mixing possible without input)
            if args.verbose:
                print(f"\nComposing from prompt: {args.prompt}")

            composer = MusicComposer()
            melody_audio = composer.compose_from_prompt(args.prompt, config)

            # Save melody only
            composer.save_audio(melody_audio, output_path, config)

            if args.json:
                info = {
                    "mode": "direct_prompt",
                    "prompt": args.prompt,
                    "output": str(output_path),
                    "format": config.output_format,
                    "length_ms": config.music_length_ms,
                }
                print(json.dumps(info, indent=2))

            if args.verbose or not args.json:
                print(f"\nSaved melody: {output_path}")
        else:
            # Analysis + composition + mixing mode
            input_path = Path(args.input)
            if not input_path.exists():
                print(f"Error: File not found: {input_path}")
                return 1

            if args.verbose:
                print(f"\nAnalyzing: {input_path}")

            melody_audio = analyze_and_compose(
                str(input_path),
                config,
                config_path=args.config,
                verbose=args.verbose
            )

            # Mix with original track unless --no-mix
            if not args.no_mix:
                if args.verbose:
                    print(f"\n[4/4] Mixing melody with original track (melody volume: {args.melody_volume:.0%})...")

                mixer = MelodyMixer()

                # Load original track
                original_audio = mixer.load_wav(input_path)

                # Load generated melody (PCM 44100Hz stereo from ElevenLabs)
                melody_np = mixer.load_audio_bytes(
                    melody_audio,
                    format_hint=config.output_format,
                    pcm_sample_rate=44100,
                    pcm_channels=2
                )

                # Mix
                mixed_audio = mixer.mix(
                    original_audio,
                    melody_np,
                    melody_volume=args.melody_volume,
                    original_volume=1.0
                )

                # Normalize
                mixed_audio = mixer.normalize(mixed_audio)

                # Update output path to WAV for mixed output
                if not output_path.suffix.lower() == '.wav':
                    output_path = output_path.with_suffix('.wav')

                # Export mixed
                mixer.export(mixed_audio, output_path)

                if args.verbose or not args.json:
                    print(f"\nSaved mixed track: {output_path}")

                # Also save melody separately
                melody_path = output_path.with_name(output_path.stem + "_melody" + (".mp3" if "mp3" in config.output_format else ".wav"))
                composer = MusicComposer()
                composer.save_audio(melody_audio, melody_path, config)

                if args.verbose:
                    print(f"Saved melody only: {melody_path}")
            else:
                # Save melody only
                composer = MusicComposer()
                composer.save_audio(melody_audio, output_path, config)

                if args.verbose or not args.json:
                    print(f"\nSaved melody: {output_path}")

            if args.json:
                extractor = FeatureExtractor()
                config_p = Path(args.config) if args.config else None
                features = extractor.extract(str(input_path), config_p)
                info = {
                    "mode": "analysis_and_mix" if not args.no_mix else "analysis",
                    "input": str(input_path),
                    "features": {
                        "bpm": features.tempo_bpm,
                        "key": features.key,
                        "config_file": features.config_file,
                    },
                    "output": str(output_path),
                    "melody_volume": args.melody_volume if not args.no_mix else None,
                    "format": config.output_format,
                    "length_ms": config.music_length_ms,
                }
                print(json.dumps(info, indent=2))

        return 0

    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error composing music: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
