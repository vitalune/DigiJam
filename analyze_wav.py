#!/usr/bin/env python3
"""
WAV Audio Analyzer - Extracts musical features and generates natural language descriptions.

Uses librosa for spectral feature extraction and reads BPM/key from session config files.
Claude API provides intelligent music analysis for prompting music generation models.

Session configs are stored as output/session_config_NNN.json with incrementing numbers.
The analyzer automatically uses the most recent (highest numbered) config file.

Usage:
    python analyze_wav.py track.wav
    python analyze_wav.py track.wav --verbose
    python analyze_wav.py track.wav --json
    python analyze_wav.py track.wav --config output/session_config_005.json
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import numpy as np
import librosa
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default output directory for session configs
OUTPUT_DIR = Path("output")


class SessionConfigManager:
    """Manages session config files with incrementing numbers."""

    CONFIG_PATTERN = re.compile(r"session_config_(\d+)\.json$")

    def __init__(self, output_dir: Path = OUTPUT_DIR):
        self.output_dir = output_dir

    def find_latest_config(self) -> Optional[Path]:
        """
        Find the most recent session config file.

        Looks for files matching session_config_NNN.json pattern and returns
        the one with the highest number. Falls back to session_config.json.

        Returns:
            Path to the latest config file, or None if not found
        """
        if not self.output_dir.exists():
            return None

        # Find all numbered config files
        numbered_configs = []
        for f in self.output_dir.iterdir():
            match = self.CONFIG_PATTERN.match(f.name)
            if match:
                num = int(match.group(1))
                numbered_configs.append((num, f))

        if numbered_configs:
            # Return highest numbered config
            numbered_configs.sort(key=lambda x: x[0], reverse=True)
            return numbered_configs[0][1]

        # Fall back to unnumbered config
        fallback = self.output_dir / "session_config.json"
        if fallback.exists():
            return fallback

        return None

    def get_next_config_path(self) -> Path:
        """
        Get the path for the next numbered config file.

        Returns:
            Path for the next config (e.g., session_config_001.json)
        """
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # Find highest existing number
        max_num = 0
        for f in self.output_dir.iterdir():
            match = self.CONFIG_PATTERN.match(f.name)
            if match:
                max_num = max(max_num, int(match.group(1)))

        next_num = max_num + 1
        return self.output_dir / f"session_config_{next_num:03d}.json"

    def read_config(self, config_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """
        Read a session config file.

        Args:
            config_path: Specific config path, or None to use latest

        Returns:
            Config dict or None if not found
        """
        if config_path is None:
            config_path = self.find_latest_config()

        if config_path is None or not config_path.exists():
            return None

        with open(config_path, 'r') as f:
            return json.load(f)

    def get_bpm_and_key(self, config_path: Optional[Path] = None) -> Tuple[Optional[float], Optional[str], Optional[Path]]:
        """
        Extract BPM and key from session config.

        Args:
            config_path: Specific config path, or None to use latest

        Returns:
            Tuple of (bpm, key, config_path_used)
        """
        if config_path is None:
            config_path = self.find_latest_config()

        config = self.read_config(config_path)
        if config is None:
            return None, None, None

        bpm = config.get("bpm")
        key = config.get("key")

        return bpm, key, config_path


def convert_key_format(key: str) -> str:
    """
    Convert session config key format to librosa format.

    Args:
        key: Key in format like "E Minor" or "A Major"

    Returns:
        Key in format like "E:min" or "A:maj"
    """
    if not key:
        return "C:maj"

    parts = key.strip().split()
    if len(parts) >= 2:
        root = parts[0]
        mode = parts[1].lower()
        if mode.startswith("min"):
            return f"{root}:min"
        elif mode.startswith("maj"):
            return f"{root}:maj"

    return key


@dataclass
class AudioFeatures:
    """Extracted musical features from audio analysis."""

    # Tempo and rhythm (from session config)
    tempo_bpm: float
    onset_strength_mean: float
    onset_strength_std: float
    zero_crossing_rate_mean: float

    # Tonal (from session config)
    key: str
    key_source: str  # "session_config" or "estimated"

    # Spectral characteristics (from librosa analysis)
    spectral_centroid_mean: float
    spectral_centroid_std: float
    spectral_bandwidth_mean: float
    spectral_rolloff_mean: float

    # Dynamics (from librosa analysis)
    rms_energy_mean: float
    rms_energy_std: float
    dynamic_range_db: float

    # Duration
    duration_seconds: float
    sample_rate: int

    # Config source
    config_file: Optional[str] = None


@dataclass
class SongSection:
    """Represents a section of a song with timing and content for vocals generation."""

    name: str                           # "intro", "verse1", "chorus1", "bridge", "outro"
    start_time: float                   # Start time in seconds
    end_time: float                     # End time in seconds
    mood: str                           # "building", "energetic", "contemplative", "triumphant"
    energy_level: str                   # "low", "medium", "high"
    lyrics: Optional[str] = None        # Lyrics text (None for instrumental sections)
    voice_id: Optional[str] = None      # Selected voice ID for TTS
    suggested_voice_style: str = ""     # "warm", "powerful", "soft", etc.
    is_user_section: bool = False       # For medium mode: True = gap for user participation

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.end_time - self.start_time


@dataclass
class SongStructure:
    """Complete song structure with all sections for AI vocals generation."""

    total_duration: float
    bpm: float
    key: str
    sections: List[SongSection] = field(default_factory=list)

    def get_vocal_sections(self) -> List[SongSection]:
        """Return only sections that have lyrics (non-user sections for medium mode)."""
        return [s for s in self.sections if s.lyrics and not s.is_user_section]

    def get_user_sections(self) -> List[SongSection]:
        """Return only sections marked for user participation (medium mode)."""
        return [s for s in self.sections if s.is_user_section]

    def get_ai_sections(self) -> List[SongSection]:
        """Return only sections where AI generates vocals."""
        return [s for s in self.sections if s.lyrics and not s.is_user_section]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_duration": self.total_duration,
            "bpm": self.bpm,
            "key": self.key,
            "sections": [asdict(s) for s in self.sections],
        }


class FeatureExtractor:
    """Extracts musical features from audio using librosa and session config."""

    # Key name mappings
    KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def __init__(self, sr: int = 22050, config_manager: Optional[SessionConfigManager] = None):
        """
        Initialize feature extractor.

        Args:
            sr: Target sample rate for analysis
            config_manager: Session config manager for BPM/key retrieval
        """
        self.sr = sr
        self.config_manager = config_manager or SessionConfigManager()

    def extract(self, filepath: str, config_path: Optional[Path] = None) -> AudioFeatures:
        """
        Extract all musical features from an audio file.

        BPM and key are read from session config file. Other features
        are extracted via librosa analysis.

        Args:
            filepath: Path to WAV audio file
            config_path: Optional specific config file path

        Returns:
            AudioFeatures dataclass with extracted features
        """
        # Load audio
        y, sr = librosa.load(filepath, sr=self.sr)
        duration = len(y) / sr

        # Get BPM and key from session config
        bpm, key_raw, config_used = self.config_manager.get_bpm_and_key(config_path)

        if bpm is not None and key_raw is not None:
            tempo = float(bpm)
            key = convert_key_format(key_raw)
            key_source = "session_config"
            config_file = str(config_used) if config_used else None
        else:
            # Fallback to estimation if no config found
            tempo, _, _ = self._extract_rhythm(y, sr)
            key, _ = self._estimate_key(y, sr)
            key_source = "estimated"
            config_file = None

        # Extract rhythm features (onset strength, ZCR)
        _, onset_mean, onset_std = self._extract_rhythm(y, sr)
        zcr = self._extract_zcr(y)

        # Extract spectral features
        centroid_mean, centroid_std, bandwidth, rolloff = self._extract_spectral(y, sr)

        # Extract dynamics
        rms_mean, rms_std, dynamic_range = self._extract_dynamics(y)

        return AudioFeatures(
            tempo_bpm=round(tempo, 1),
            onset_strength_mean=round(onset_mean, 4),
            onset_strength_std=round(onset_std, 4),
            zero_crossing_rate_mean=round(zcr, 4),
            key=key,
            key_source=key_source,
            spectral_centroid_mean=round(centroid_mean, 1),
            spectral_centroid_std=round(centroid_std, 1),
            spectral_bandwidth_mean=round(bandwidth, 1),
            spectral_rolloff_mean=round(rolloff, 1),
            rms_energy_mean=round(rms_mean, 6),
            rms_energy_std=round(rms_std, 6),
            dynamic_range_db=round(dynamic_range, 1),
            duration_seconds=round(duration, 2),
            sample_rate=sr,
            config_file=config_file
        )

    def _extract_rhythm(self, y: np.ndarray, sr: int) -> Tuple[float, float, float]:
        """Extract tempo and onset features."""
        # Tempo estimation
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        # Onset strength
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_mean = float(np.mean(onset_env))
        onset_std = float(np.std(onset_env))

        return tempo, onset_mean, onset_std

    def _estimate_key(self, y: np.ndarray, sr: int) -> Tuple[str, float]:
        """Estimate musical key using chroma features."""
        # Compute chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        # Average chroma over time
        chroma_mean = np.mean(chroma, axis=1)

        # Find strongest pitch class
        key_idx = int(np.argmax(chroma_mean))
        key_name = self.KEY_NAMES[key_idx]

        # Confidence based on how dominant the key is
        confidence = float(chroma_mean[key_idx] / np.sum(chroma_mean))

        # Simple major/minor detection using relative minor relationship
        # Check if minor third above tonic is stronger than major third
        minor_third_idx = (key_idx + 3) % 12
        major_third_idx = (key_idx + 4) % 12

        if chroma_mean[minor_third_idx] > chroma_mean[major_third_idx]:
            key_name += ":min"
        else:
            key_name += ":maj"

        return key_name, confidence

    def _extract_zcr(self, y: np.ndarray) -> float:
        """Extract zero-crossing rate (percussiveness indicator)."""
        zcr = librosa.feature.zero_crossing_rate(y)
        return float(np.mean(zcr))

    def _extract_spectral(self, y: np.ndarray, sr: int) -> Tuple[float, float, float, float]:
        """Extract spectral features (brightness, bandwidth, rolloff)."""
        # Spectral centroid (brightness)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        centroid_mean = float(np.mean(centroid))
        centroid_std = float(np.std(centroid))

        # Spectral bandwidth
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        bandwidth_mean = float(np.mean(bandwidth))

        # Spectral rolloff
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        rolloff_mean = float(np.mean(rolloff))

        return centroid_mean, centroid_std, bandwidth_mean, rolloff_mean

    def _extract_dynamics(self, y: np.ndarray) -> Tuple[float, float, float]:
        """Extract RMS energy and dynamic range."""
        rms = librosa.feature.rms(y=y)
        rms_mean = float(np.mean(rms))
        rms_std = float(np.std(rms))

        # Dynamic range in dB
        rms_max = float(np.max(rms))
        rms_min = float(np.min(rms[rms > 0])) if np.any(rms > 0) else 1e-10
        dynamic_range = 20 * np.log10(rms_max / rms_min) if rms_min > 0 else 0

        return rms_mean, rms_std, dynamic_range


class MusicDescriber:
    """Generates natural language descriptions using Claude API."""

    ANALYSIS_PROMPT = """You are a music analyst. Based on the following extracted audio features, provide a concise 2-3 sentence description of the track suitable for prompting a music generation model.

Focus on:
- Genre (primary + potential subgenre)
- Mood/vibe (3-5 descriptive words)
- Energy profile and rhythm characteristics
- Tonal qualities that inform melodic choices

Audio Features:
{features_json}

Feature Interpretation Guide:
- tempo_bpm: Track speed from session config (60-80 slow, 80-120 moderate, 120-140 upbeat, 140+ fast)
- key: Musical key from session config - USE THIS EXACTLY for melodic compatibility
- key_source: Where the key came from ("session_config" = authoritative, "estimated" = fallback)
- spectral_centroid_mean: Brightness (1000-2000 Hz = warm/mellow, 2000-4000 Hz = bright, 4000+ Hz = very bright/harsh)
- zero_crossing_rate_mean: Percussiveness (0.02-0.05 = smooth, 0.05-0.1 = moderate, 0.1+ = percussive)
- onset_strength_mean: Rhythmic intensity (0.5-1.0 = gentle, 1.0-2.0 = moderate, 2.0+ = intense)
- dynamic_range_db: Dynamics (0-10 dB = compressed, 10-20 dB = moderate, 20+ dB = dynamic)

IMPORTANT: The BPM and key values are authoritative when key_source is "session_config". Use them exactly in your description.

Output format: A natural language description like:
"Upbeat electronic track with house influences, bright and energetic with a driving four-on-the-floor rhythm. Mood: euphoric, danceable, summery. Key: A minor at 128 BPM suggests minor-key melodies with energetic progressions."

Provide ONLY the description, no preamble or explanation."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the music describer.

        Args:
            api_key: Anthropic API key. If not provided, reads from ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Import anthropic here to avoid import errors if not installed
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install anthropic")

    def describe(self, features: AudioFeatures) -> str:
        """
        Generate a natural language description of the track.

        Args:
            features: Extracted audio features

        Returns:
            Natural language description string
        """
        features_json = json.dumps(asdict(features), indent=2)
        prompt = self.ANALYSIS_PROMPT.format(features_json=features_json)

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text.strip()


def analyze_audio(
    filepath: str,
    verbose: bool = False,
    output_json: bool = False,
    config_path: Optional[str] = None
) -> str:
    """
    Full analysis pipeline: extract features and generate description.

    Args:
        filepath: Path to WAV audio file
        verbose: If True, print feature details
        output_json: If True, output raw JSON instead of description
        config_path: Optional path to specific session config file

    Returns:
        Natural language description or JSON string
    """
    # Extract features
    extractor = FeatureExtractor()

    if verbose:
        print(f"Analyzing: {filepath}")
        config_manager = SessionConfigManager()
        latest = config_manager.find_latest_config()
        if config_path:
            print(f"Using config: {config_path}")
        elif latest:
            print(f"Using latest config: {latest}")
        else:
            print("No session config found, using estimated values")
        print("Extracting features...")

    config_p = Path(config_path) if config_path else None
    features = extractor.extract(filepath, config_p)

    if verbose:
        print("\nExtracted Features:")
        for key, value in asdict(features).items():
            print(f"  {key}: {value}")
        print()

    if output_json:
        return json.dumps(asdict(features), indent=2)

    # Generate description
    if verbose:
        print("Generating description via Claude API...")

    describer = MusicDescriber()
    description = describer.describe(features)

    return description


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze WAV audio and generate natural language descriptions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic analysis (uses latest session_config_NNN.json)
    python analyze_wav.py track.wav

    # Verbose output with feature details
    python analyze_wav.py track.wav --verbose

    # Use specific config file
    python analyze_wav.py track.wav --config output/session_config_005.json

    # Output raw features as JSON (no Claude API call)
    python analyze_wav.py track.wav --json

    # List available config files
    python analyze_wav.py --list-configs
        """
    )

    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        help="Input WAV audio file"
    )

    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        help="Path to specific session config file (default: latest session_config_NNN.json)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed feature extraction info"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw features as JSON instead of description"
    )

    parser.add_argument(
        "--list-configs",
        action="store_true",
        help="List available session config files and exit"
    )

    return parser.parse_args()


def list_config_files() -> None:
    """List all available session config files."""
    config_manager = SessionConfigManager()

    print("\nAvailable session config files:")
    print("=" * 50)

    if not OUTPUT_DIR.exists():
        print("  (no output directory found)")
        return

    # Find numbered configs
    numbered = []
    unnumbered = None

    for f in sorted(OUTPUT_DIR.iterdir()):
        if f.name == "session_config.json":
            unnumbered = f
        else:
            match = SessionConfigManager.CONFIG_PATTERN.match(f.name)
            if match:
                numbered.append((int(match.group(1)), f))

    numbered.sort(key=lambda x: x[0], reverse=True)

    if numbered:
        for num, path in numbered:
            marker = " (latest)" if num == numbered[0][0] else ""
            # Read BPM and key
            config = config_manager.read_config(path)
            if config:
                bpm = config.get("bpm", "?")
                key = config.get("key", "?")
                print(f"  [{num:03d}] {path.name}{marker} - {bpm} BPM, {key}")
            else:
                print(f"  [{num:03d}] {path.name}{marker}")

    if unnumbered:
        config = config_manager.read_config(unnumbered)
        fallback_marker = " (fallback)" if not numbered else ""
        if config:
            bpm = config.get("bpm", "?")
            key = config.get("key", "?")
            print(f"  [---] {unnumbered.name}{fallback_marker} - {bpm} BPM, {key}")
        else:
            print(f"  [---] {unnumbered.name}{fallback_marker}")

    if not numbered and not unnumbered:
        print("  (no config files found)")

    print("=" * 50)


def main():
    """Main entry point."""
    args = parse_args()

    # Handle --list-configs
    if args.list_configs:
        list_config_files()
        return 0

    # Require input file for analysis
    if not args.input:
        print("Error: input file required")
        print("Use --help for usage information")
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return 1

    if not input_path.suffix.lower() == '.wav':
        print(f"Warning: Expected WAV file, got {input_path.suffix}")

    try:
        result = analyze_audio(
            str(input_path),
            verbose=args.verbose,
            output_json=args.json,
            config_path=args.config
        )
        print(result)
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error analyzing audio: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
