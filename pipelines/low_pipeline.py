"""
Low AI Support Pipeline - User-driven with AI voice transformation.

Orchestrates the workflow for low AI support mode:
1. Extract audio features from instrumental
2. Generate subtle background melody (low volume)
3. Transform user's recorded vocals to selected voice style
4. Mix transformed vocals with instrumental + melody
5. Generate music video

User recording required - AI enhances with voice transformation.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, List, Union
from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
from scipy.io import wavfile
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyze_wav import AudioFeatures, FeatureExtractor, MusicDescriber
from compose_music import MusicComposer, MelodyMixer, CompositionConfig, AI_VOLUME_PRESETS, build_complementary_prompt
from vocals.vocal_config import TTSConfig
from vocals.vocal_mixer import VocalMixer
from video_generator import ShortVideoLooper


# Load environment variables
load_dotenv()


@dataclass
class PipelineResult:
    """Result from pipeline processing."""
    video_path: Path
    audio_path: Path
    duration: float
    sections: List[Dict] = field(default_factory=list)
    features: Dict = field(default_factory=dict)
    mode: str = "low"


@dataclass
class LowPipelineConfig:
    """Configuration for low AI pipeline."""

    # Melody generation
    melody_length_ms: Optional[int] = None
    force_instrumental: bool = True

    # Voice transformation settings
    voice_id: str = ""  # Target voice for transformation
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0

    # Mixing settings
    vocal_volume: float = 1.0
    melody_volume: float = 0.2  # Lower for low AI mode
    instrumental_volume: float = 0.8


class LowPipeline:
    """
    Pipeline for low AI support mode.

    User-driven with AI voice transformation and subtle melody.
    """

    def __init__(
        self,
        elevenlabs_api_key: Optional[str] = None,
        output_dir: Path = Path("output")
    ):
        """
        Initialize the low AI pipeline.

        Args:
            elevenlabs_api_key: ElevenLabs API key for voice transformation
            output_dir: Base output directory
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.api_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key required. Set ELEVENLABS_API_KEY "
                "environment variable or pass elevenlabs_api_key parameter."
            )

        # Initialize components
        self.feature_extractor = FeatureExtractor()
        self.composer = MusicComposer(api_key=self.api_key)
        self.melody_mixer = MelodyMixer()
        self.vocal_mixer = VocalMixer()
        self.video_looper = ShortVideoLooper()

        # Initialize ElevenLabs client for speech-to-speech
        from elevenlabs.client import ElevenLabs
        self.elevenlabs = ElevenLabs(api_key=self.api_key)

    def transform_voice(
        self,
        audio_data: Union[bytes, np.ndarray],
        voice_id: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0
    ) -> bytes:
        """
        Transform audio to a different voice using ElevenLabs Speech-to-Speech.

        Args:
            audio_data: Source audio (bytes or numpy array)
            voice_id: Target voice ID
            stability: Voice stability (0-1)
            similarity_boost: Similarity to original voice (0-1)
            style: Style exaggeration (0-1)

        Returns:
            Transformed audio as bytes
        """
        # Convert numpy array to WAV bytes if needed
        if isinstance(audio_data, np.ndarray):
            audio_bytes = self._numpy_to_wav_bytes(audio_data)
        else:
            audio_bytes = audio_data

        # Call ElevenLabs Speech-to-Speech API
        audio_stream = self.elevenlabs.speech_to_speech.convert(
            voice_id=voice_id,
            audio=BytesIO(audio_bytes),
            model_id="eleven_english_sts_v2",
            voice_settings={
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": True,
            },
            output_format="mp3_44100_128",
        )

        # Collect streamed response
        return b''.join(audio_stream)

    def _numpy_to_wav_bytes(self, audio: np.ndarray, sample_rate: int = 44100) -> bytes:
        """Convert numpy array to WAV bytes."""
        # Ensure audio is in correct format
        if audio.dtype != np.int16:
            audio = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

        # Create WAV file in memory
        buffer = BytesIO()
        wavfile.write(buffer, sample_rate, audio)
        buffer.seek(0)
        return buffer.read()

    def _load_user_vocals(self, vocals_path: Union[str, Path, bytes]) -> np.ndarray:
        """Load user vocals from file or bytes."""
        if isinstance(vocals_path, bytes):
            return self.vocal_mixer.load_audio_bytes(vocals_path)
        return self.vocal_mixer.load_audio(vocals_path)

    def process(
        self,
        session_id: str,
        instrumental_path: str,
        user_vocals: Union[str, Path, bytes],
        voice_id: str,
        bpm: float = 120,
        key: str = "C Major",
        config: Optional[LowPipelineConfig] = None,
        session_config_path: Optional[str] = None,
        verbose: bool = False
    ) -> PipelineResult:
        """
        Run the low AI pipeline.

        Args:
            session_id: Unique session identifier
            instrumental_path: Path to user's instrumental audio file
            user_vocals: User's recorded vocals (path or bytes)
            voice_id: Target voice for transformation
            bpm: BPM of the track
            key: Musical key
            config: Pipeline configuration
            session_config_path: Optional path to session config
            verbose: Print progress information

        Returns:
            PipelineResult with paths to generated files and metadata
        """
        config = config or LowPipelineConfig(voice_id=voice_id)
        if not config.voice_id:
            config.voice_id = voice_id

        # Prepare output paths
        audio_output = self.output_dir / f"{session_id}_final.wav"
        video_output = self.output_dir / "videos" / f"{session_id}_video.mp4"
        video_output.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: Extract features from instrumental
        if verbose:
            print("\n[1/6] Extracting audio features...")

        config_path = Path(session_config_path) if session_config_path else None
        features = self.feature_extractor.extract(instrumental_path, config_path)

        if bpm:
            features.tempo_bpm = bpm
        if key:
            features.key = key

        if verbose:
            print(f"  BPM: {features.tempo_bpm}, Key: {features.key}")
            print(f"  Duration: {features.duration_seconds:.1f}s")

        # Step 2: Generate subtle background melody
        if verbose:
            print("\n[2/6] Generating background melody...")

        try:
            describer = MusicDescriber()
            description = describer.describe(features)
        except ValueError:
            energy = "high energy" if features.onset_strength_mean > 1.5 else "moderate energy"
            brightness = "bright" if features.spectral_centroid_mean > 2500 else "warm"
            description = f"{energy} {brightness} track in {features.key} at {features.tempo_bpm} BPM"

        prompt = build_complementary_prompt(features, description)

        composition_config = CompositionConfig(
            output_format="mp3_44100_128",
            force_instrumental=config.force_instrumental,
            music_length_ms=config.melody_length_ms,
        )

        melody_bytes = self.composer.compose_from_prompt(prompt, composition_config)

        # Step 3: Mix melody with instrumental (low AI volumes)
        if verbose:
            print("\n[3/6] Mixing melody with instrumental...")

        instrumental_audio = self.melody_mixer.load_wav(Path(instrumental_path))

        melody_audio = self.melody_mixer.load_audio_bytes(
            melody_bytes,
            format_hint="mp3_44100_128",
            pcm_sample_rate=44100,
            pcm_channels=2
        )

        # Use low AI volumes (subtle melody)
        volumes = AI_VOLUME_PRESETS["low"]
        backing_track = self.melody_mixer.mix(
            original=instrumental_audio,
            melody=melody_audio,
            melody_volume=config.melody_volume or volumes["melody"],
            original_volume=config.instrumental_volume or volumes["instrumental"]
        )

        if verbose:
            print(f"  Melody volume: {volumes['melody']:.0%}")
            print(f"  Instrumental volume: {volumes['instrumental']:.0%}")

        # Step 4: Load and transform user vocals
        if verbose:
            print("\n[4/6] Transforming user vocals...")
            print(f"  Target voice: {config.voice_id}")

        user_vocals_audio = self._load_user_vocals(user_vocals)

        # Convert to WAV bytes for API
        transformed_bytes = self.transform_voice(
            audio_data=user_vocals_audio,
            voice_id=config.voice_id,
            stability=config.stability,
            similarity_boost=config.similarity_boost,
            style=config.style
        )

        # Convert transformed audio back to numpy
        transformed_audio = np.frombuffer(transformed_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        if verbose:
            print(f"  Transformed {len(user_vocals_audio) / 44100:.1f}s of vocals")

        # Step 5: Mix transformed vocals with backing track
        if verbose:
            print("\n[5/6] Mixing final audio...")

        final_audio = self.vocal_mixer.mix(
            instrumental=backing_track,
            vocal=transformed_audio,
            vocal_offset=0.0,
            vocal_volume=config.vocal_volume,
            instrumental_volume=1.0  # Already mixed
        )

        # Normalize and export
        final_audio = self.vocal_mixer.normalize(final_audio)
        self.vocal_mixer.export(final_audio, audio_output)

        if verbose:
            print(f"  Audio saved to: {audio_output}")

        # Step 6: Generate music video
        if verbose:
            print("\n[6/6] Generating music video...")

        video_path = self.video_looper.generate(
            audio_path=audio_output,
            output_path=video_output,
            audio_duration=features.duration_seconds
        )

        if verbose:
            print(f"  Video saved to: {video_path}")
            print(f"\nComplete! Session: {session_id}")

        return PipelineResult(
            video_path=video_path,
            audio_path=audio_output,
            duration=features.duration_seconds,
            sections=[],  # No sections in low mode
            features={
                "bpm": features.tempo_bpm,
                "key": features.key,
                "duration": features.duration_seconds,
            },
            mode="low"
        )


def main():
    """Command line interface for low AI pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Low AI Support Pipeline")
    parser.add_argument("input", help="Path to instrumental audio file")
    parser.add_argument("--vocals", required=True, help="Path to user vocals file")
    parser.add_argument("--voice-id", required=True, help="Target voice ID")
    parser.add_argument("-o", "--output", help="Output directory", default="output")
    parser.add_argument("--session-id", help="Session ID", default="test_session")
    parser.add_argument("--bpm", type=float, help="BPM of the track")
    parser.add_argument("--key", help="Musical key")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    pipeline = LowPipeline(output_dir=Path(args.output))
    config = LowPipelineConfig(voice_id=args.voice_id)

    result = pipeline.process(
        session_id=args.session_id,
        instrumental_path=args.input,
        user_vocals=args.vocals,
        voice_id=args.voice_id,
        bpm=args.bpm or 120,
        key=args.key or "C Major",
        config=config,
        verbose=args.verbose
    )

    print(f"\nResults:")
    print(f"  Video: {result.video_path}")
    print(f"  Audio: {result.audio_path}")
    print(f"  Duration: {result.duration:.1f}s")


if __name__ == "__main__":
    main()
