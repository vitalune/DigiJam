"""
High AI Support Pipeline - Complete automated vocals generation.

Orchestrates the full workflow for high AI support mode:
1. Generate main melody (user's instrumental as background)
2. Analyze sections and generate complete lyrics
3. Select voices for each section
4. Synthesize vocals using TTS
5. Mix vocals at section timestamps

No user recording needed - fully automated vocal generation.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass

import numpy as np
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyze_wav import AudioFeatures, SongStructure, FeatureExtractor
from compose_music import MusicComposer, MelodyMixer, CompositionConfig, AI_VOLUME_PRESETS
from vocals.vocal_config import TTSConfig
from vocals.tts_processor import TTSProcessor
from vocals.lyrics_generator import LyricsGenerator
from vocals.voice_selector import VoiceSelector
from vocals.vocal_mixer import SectionMixer


# Load environment variables
load_dotenv()


@dataclass
class HighAIPipelineConfig:
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


class HighAIPipeline:
    """
    Complete pipeline for high AI support mode.

    Generates vocals entirely through AI - no user recording needed.
    """

    def __init__(
        self,
        elevenlabs_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None
    ):
        """
        Initialize the high AI pipeline.

        Args:
            elevenlabs_api_key: ElevenLabs API key for TTS and music generation
            anthropic_api_key: Anthropic API key for Claude (lyrics/voice selection)
        """
        # Initialize components
        self.composer = MusicComposer(api_key=elevenlabs_api_key)
        self.melody_mixer = MelodyMixer()
        self.tts_processor = TTSProcessor(api_key=elevenlabs_api_key)
        self.lyrics_generator = LyricsGenerator(api_key=anthropic_api_key)
        self.voice_selector = VoiceSelector(api_key=anthropic_api_key)
        self.section_mixer = SectionMixer()
        self.feature_extractor = FeatureExtractor()

    def process(
        self,
        instrumental_path: str,
        output_path: str,
        config: Optional[HighAIPipelineConfig] = None,
        session_config_path: Optional[str] = None,
        verbose: bool = False
    ) -> Dict:
        """
        Run the complete high AI pipeline.

        Args:
            instrumental_path: Path to user's instrumental audio file
            output_path: Path to save the final mixed audio
            config: Pipeline configuration
            session_config_path: Optional path to session config for BPM/key
            verbose: Print progress information

        Returns:
            Dict with pipeline results and metadata
        """
        config = config or HighAIPipelineConfig()
        tts_config = config.tts_config or TTSConfig()
        results = {}

        # Step 1: Extract features from instrumental
        if verbose:
            print("\n[1/6] Extracting audio features...")

        config_path = Path(session_config_path) if session_config_path else None
        features = self.feature_extractor.extract(instrumental_path, config_path)
        results["features"] = {
            "bpm": features.tempo_bpm,
            "key": features.key,
            "duration": features.duration_seconds,
        }

        if verbose:
            print(f"  BPM: {features.tempo_bpm}, Key: {features.key}")
            print(f"  Duration: {features.duration_seconds:.1f}s")

        # Step 2: Generate main melody
        if verbose:
            print("\n[2/6] Generating main melody...")

        # Build composition prompt
        from compose_music import build_complementary_prompt
        from analyze_wav import MusicDescriber

        try:
            describer = MusicDescriber()
            description = describer.describe(features)
        except ValueError:
            # No API key - use fallback
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

        # Step 3: Mix melody with instrumental (high AI volumes)
        if verbose:
            print("\n[3/6] Mixing melody with instrumental...")

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

        # Step 4: Analyze sections and generate lyrics
        if verbose:
            print("\n[4/6] Analyzing sections and generating lyrics...")
            if config.lyrics_prompt:
                print(f"  User lyrics request: {config.lyrics_prompt[:50]}...")

        structure = self.lyrics_generator.create_song_structure(
            features=features,
            ai_support_level="high",
            genre=config.genre,
            mood_description=config.mood_description or description,
            lyrics_prompt=config.lyrics_prompt,
        )

        results["sections"] = [
            {"name": s.name, "start": s.start_time, "end": s.end_time, "lyrics": s.lyrics}
            for s in structure.sections
        ]

        if verbose:
            print(f"  Found {len(structure.sections)} sections")
            for s in structure.sections:
                print(f"    {s.name}: {s.start_time:.1f}s - {s.end_time:.1f}s")

        # Step 5: Select voices and synthesize vocals
        if verbose:
            print("\n[5/6] Synthesizing vocals for each section...")

        # Select voices
        structure = self.voice_selector.select_voices_for_structure(
            structure,
            use_ai=config.use_ai_voice_selection
        )

        # Synthesize each section
        section_audio = {}
        for section in structure.get_ai_sections():
            if not section.lyrics or not section.voice_id:
                continue

            if verbose:
                print(f"  Synthesizing {section.name} with voice {section.voice_id[:8]}...")

            audio_bytes, duration = self.tts_processor.synthesize_section(
                lyrics=section.lyrics,
                voice_id=section.voice_id,
                config=tts_config
            )

            if audio_bytes:
                # Convert bytes to numpy array
                audio_np = self._pcm_to_numpy(audio_bytes, tts_config.sample_rate)
                section_audio[section.name] = audio_np

        # Step 6: Mix vocals into main track
        if verbose:
            print("\n[6/6] Mixing vocals into final track...")

        final_audio = self.section_mixer.mix_from_structure(
            main_track=main_track,
            section_audio=section_audio,
            sections=structure.sections,
            vocal_volume=config.vocal_volume,
            duck_amount=config.duck_amount,
        )

        # Normalize and export
        final_audio = self.melody_mixer.normalize(final_audio)
        self.melody_mixer.export(final_audio, Path(output_path))

        results["output_path"] = output_path
        results["mode"] = "high"

        if verbose:
            print(f"\nComplete! Saved to: {output_path}")

        return results

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
    """Example usage of high AI pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="High AI Support Pipeline")
    parser.add_argument("input", help="Path to instrumental audio file")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--genre", default="pop", help="Music genre")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    output_path = args.output or f"output/high_ai_{Path(args.input).stem}.wav"

    pipeline = HighAIPipeline()
    config = HighAIPipelineConfig(genre=args.genre)

    results = pipeline.process(
        instrumental_path=args.input,
        output_path=output_path,
        config=config,
        verbose=args.verbose
    )

    print(f"\nResults: {results}")


if __name__ == "__main__":
    main()
