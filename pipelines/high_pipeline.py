"""
High AI Support Pipeline - Complete automated music video generation.

Orchestrates the full workflow for high AI support mode:
1. Extract audio features from instrumental
2. Generate main melody (complementary to instrumental)
3. Mix melody with instrumental at high AI volumes
4. Analyze sections and generate complete lyrics
5. Select voices for each section
6. Synthesize vocals using TTS
7. Mix vocals at section timestamps with ducking
8. Generate music video by looping short videos

No user recording needed - fully automated generation.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field

import numpy as np
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyze_wav import AudioFeatures, SongStructure, FeatureExtractor, MusicDescriber
from compose_music import MusicComposer, MelodyMixer, CompositionConfig, AI_VOLUME_PRESETS, build_complementary_prompt
from vocals.vocal_config import TTSConfig
from vocals.tts_processor import TTSProcessor
from vocals.lyrics_generator import LyricsGenerator
from vocals.voice_selector import VoiceSelector
from vocals.vocal_mixer import SectionMixer
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
    mode: str = "high"


@dataclass
class HighPipelineConfig:
    """Configuration for high AI pipeline."""

    # Melody generation
    melody_length_ms: Optional[int] = None
    force_instrumental: bool = True

    # Lyrics generation
    genre: str = "pop"
    mood_description: str = ""
    lyrics_prompt: str = ""  # User's description of what lyrics should be about

    # TTS settings
    tts_config: Optional[TTSConfig] = None

    # Mixing settings
    vocal_volume: float = 0.85
    duck_amount: float = 0.3

    # Voice selection
    use_ai_voice_selection: bool = True
    voice_id: Optional[str] = None  # Force specific voice for all sections


class HighPipeline:
    """
    Complete pipeline for high AI support mode.

    Generates complete music video with AI-generated vocals.
    No user recording needed.
    """

    def __init__(
        self,
        elevenlabs_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        output_dir: Path = Path("output")
    ):
        """
        Initialize the high AI pipeline.

        Args:
            elevenlabs_api_key: ElevenLabs API key for TTS and music generation
            anthropic_api_key: Anthropic API key for Claude (lyrics/voice selection)
            output_dir: Base output directory
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.feature_extractor = FeatureExtractor()
        self.composer = MusicComposer(api_key=elevenlabs_api_key)
        self.melody_mixer = MelodyMixer()
        self.lyrics_generator = LyricsGenerator(api_key=anthropic_api_key)
        self.voice_selector = VoiceSelector(api_key=anthropic_api_key)
        self.tts_processor = TTSProcessor(api_key=elevenlabs_api_key)
        self.section_mixer = SectionMixer()
        self.video_looper = ShortVideoLooper()

    def process(
        self,
        session_id: str,
        instrumental_path: str,
        bpm: float = 120,
        key: str = "C Major",
        config: Optional[HighPipelineConfig] = None,
        session_config_path: Optional[str] = None,
        verbose: bool = False
    ) -> PipelineResult:
        """
        Run the complete high AI pipeline.

        Args:
            session_id: Unique session identifier
            instrumental_path: Path to user's instrumental audio file
            bpm: BPM of the track (from session config)
            key: Musical key (from session config)
            config: Pipeline configuration
            session_config_path: Optional path to session config for BPM/key override
            verbose: Print progress information

        Returns:
            PipelineResult with paths to generated files and metadata
        """
        config = config or HighPipelineConfig()
        tts_config = config.tts_config or TTSConfig()

        # Prepare output paths
        audio_output = self.output_dir / f"{session_id}_final.wav"
        video_output = self.output_dir / "videos" / f"{session_id}_video.mp4"
        video_output.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: Extract features from instrumental
        if verbose:
            print("\n[1/8] Extracting audio features...")

        config_path = Path(session_config_path) if session_config_path else None
        features = self.feature_extractor.extract(instrumental_path, config_path)

        # Use provided BPM/key if available, else use extracted
        if bpm:
            features.tempo_bpm = bpm
        if key:
            features.key = key

        if verbose:
            print(f"  BPM: {features.tempo_bpm}, Key: {features.key}")
            print(f"  Duration: {features.duration_seconds:.1f}s")

        # Step 2: Get music description for melody generation
        if verbose:
            print("\n[2/8] Analyzing track mood...")

        try:
            describer = MusicDescriber()
            description = describer.describe(features)
        except ValueError:
            # No API key - use fallback description
            energy = "high energy" if features.onset_strength_mean > 1.5 else "moderate energy"
            brightness = "bright" if features.spectral_centroid_mean > 2500 else "warm"
            description = f"{energy} {brightness} track in {features.key} at {features.tempo_bpm} BPM"

        if verbose:
            print(f"  Description: {description[:80]}...")

        # Step 3: Generate main melody
        if verbose:
            print("\n[3/8] Generating main melody...")

        prompt = build_complementary_prompt(features, description)

        composition_config = CompositionConfig(
            output_format="mp3_44100_128",
            force_instrumental=config.force_instrumental,
            music_length_ms=config.melody_length_ms,
        )

        melody_bytes = self.composer.compose_from_prompt(prompt, composition_config)

        # Step 4: Mix melody with instrumental
        if verbose:
            print("\n[4/8] Mixing melody with instrumental...")

        # Load instrumental
        instrumental_audio = self.melody_mixer.load_wav(Path(instrumental_path))

        # Load melody
        melody_audio = self.melody_mixer.load_audio_bytes(
            melody_bytes,
            format_hint="mp3_44100_128",
            pcm_sample_rate=44100,
            pcm_channels=2
        )

        # Mix with high AI volumes
        volumes = AI_VOLUME_PRESETS["high"]
        main_track = self.melody_mixer.mix(
            original=instrumental_audio,
            melody=melody_audio,
            melody_volume=volumes["melody"],
            original_volume=volumes["instrumental"]
        )

        if verbose:
            print(f"  Melody volume: {volumes['melody']:.0%}")
            print(f"  Instrumental volume: {volumes['instrumental']:.0%}")

        # Step 5: Analyze sections and generate lyrics
        if verbose:
            print("\n[5/8] Analyzing sections and generating lyrics...")
            if config.lyrics_prompt:
                print(f"  User lyrics request: {config.lyrics_prompt[:50]}...")

        structure = self.lyrics_generator.create_song_structure(
            features=features,
            ai_support_level="high",
            genre=config.genre,
            mood_description=config.mood_description or description,
            lyrics_prompt=config.lyrics_prompt,
        )

        if verbose:
            print(f"  Found {len(structure.sections)} sections")
            for s in structure.sections:
                print(f"    {s.name}: {s.start_time:.1f}s - {s.end_time:.1f}s")

        # Step 6: Select voices for each section
        if verbose:
            print("\n[6/8] Selecting voices for sections...")

        if config.voice_id:
            # Use forced voice for all sections
            for section in structure.sections:
                if not section.is_user_section and section.lyrics:
                    section.voice_id = config.voice_id
        else:
            # AI voice selection
            structure = self.voice_selector.select_voices_for_structure(
                structure,
                use_ai=config.use_ai_voice_selection
            )

        # Step 7: Synthesize vocals and mix
        if verbose:
            print("\n[7/8] Synthesizing and mixing vocals...")

        # Synthesize each section
        section_audio = {}
        for section in structure.get_ai_sections():
            if not section.lyrics or not section.voice_id:
                continue

            if verbose:
                voice_name = section.voice_id[:8]
                print(f"  Synthesizing {section.name} with voice {voice_name}...")

            audio_bytes, duration = self.tts_processor.synthesize_section(
                lyrics=section.lyrics,
                voice_id=section.voice_id,
                config=tts_config
            )

            if audio_bytes:
                # Convert bytes to numpy array
                audio_np = self._pcm_to_numpy(audio_bytes, tts_config.sample_rate)
                section_audio[section.name] = audio_np

        # Mix vocals into main track with ducking
        final_audio = self.section_mixer.mix_from_structure(
            main_track=main_track,
            section_audio=section_audio,
            sections=structure.sections,
            vocal_volume=config.vocal_volume,
            duck_amount=config.duck_amount,
        )

        # Normalize and export audio
        final_audio = self.melody_mixer.normalize(final_audio)
        self.melody_mixer.export(final_audio, audio_output)

        if verbose:
            print(f"  Audio saved to: {audio_output}")

        # Step 8: Generate music video
        if verbose:
            print("\n[8/8] Generating music video...")

        video_path = self.video_looper.generate(
            audio_path=audio_output,
            output_path=video_output,
            audio_duration=features.duration_seconds
        )

        if verbose:
            print(f"  Video saved to: {video_path}")
            print(f"\nComplete! Session: {session_id}")

        # Build result
        return PipelineResult(
            video_path=video_path,
            audio_path=audio_output,
            duration=features.duration_seconds,
            sections=[
                {
                    "name": s.name,
                    "start": s.start_time,
                    "end": s.end_time,
                    "lyrics": s.lyrics
                }
                for s in structure.sections
            ],
            features={
                "bpm": features.tempo_bpm,
                "key": features.key,
                "duration": features.duration_seconds,
            },
            mode="high"
        )

    def _pcm_to_numpy(self, audio_bytes: bytes, sample_rate: int) -> np.ndarray:
        """Convert audio bytes (PCM or MP3) to numpy array."""
        import tempfile
        import os
        import soundfile as sf

        # Detect MP3 format
        has_mp3_id3 = len(audio_bytes) >= 3 and audio_bytes[:3] == b'ID3'
        has_mp3_sync = len(audio_bytes) >= 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0

        if has_mp3_id3 or has_mp3_sync:
            # MP3 - decode using soundfile
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            try:
                audio, rate = sf.read(tmp_path, dtype='float32')
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)
                if rate != 44100:
                    from scipy.signal import resample
                    new_len = int(len(audio) * 44100 / rate)
                    audio = resample(audio, new_len).astype(np.float32)
            finally:
                os.unlink(tmp_path)
        else:
            # Raw PCM
            audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if sample_rate != 44100:
                from scipy.signal import resample
                new_len = int(len(audio) * 44100 / sample_rate)
                audio = resample(audio, new_len).astype(np.float32)

        return audio


def main():
    """Command line interface for high AI pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="High AI Support Pipeline")
    parser.add_argument("input", help="Path to instrumental audio file")
    parser.add_argument("-o", "--output", help="Output directory", default="output")
    parser.add_argument("--session-id", help="Session ID", default="test_session")
    parser.add_argument("--genre", default="pop", help="Music genre")
    parser.add_argument("--lyrics-prompt", help="Description of desired lyrics")
    parser.add_argument("--bpm", type=float, help="BPM of the track")
    parser.add_argument("--key", help="Musical key")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    pipeline = HighPipeline(output_dir=Path(args.output))
    config = HighPipelineConfig(
        genre=args.genre,
        lyrics_prompt=args.lyrics_prompt or "",
    )

    result = pipeline.process(
        session_id=args.session_id,
        instrumental_path=args.input,
        bpm=args.bpm or 120,
        key=args.key or "C Major",
        config=config,
        verbose=args.verbose
    )

    print(f"\nResults:")
    print(f"  Video: {result.video_path}")
    print(f"  Audio: {result.audio_path}")
    print(f"  Duration: {result.duration:.1f}s")
    print(f"  Sections: {len(result.sections)}")


if __name__ == "__main__":
    main()
