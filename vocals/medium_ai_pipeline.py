"""
Medium AI Support Pipeline - Collaborative vocals with user participation.

Orchestrates a two-phase workflow for medium AI support mode:

Phase 1 (AI Generation):
1. Generate main melody (balanced with user's instrumental)
2. Analyze sections and generate lyrics with intentional gaps
3. Select voices for AI sections only
4. Synthesize vocals using TTS (leaving gaps for user)
5. Mix AI vocals at section timestamps
6. Return master track with gaps for user recording

Phase 2 (User Participation):
7. User records vocals to fill in the gaps
8. Transform user vocals with voice changer
9. Mix user vocals into final track

This mode encourages collaboration between AI and user.
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
from vocals.vocal_config import TTSConfig, VocalConfig
from vocals.tts_processor import TTSProcessor
from vocals.lyrics_generator import LyricsGenerator
from vocals.voice_selector import VoiceSelector
from vocals.vocal_mixer import SectionMixer, VocalMixer
from vocals.vocal_processor import VocalProcessor


# Load environment variables
load_dotenv()


@dataclass
class MediumAIPipelineConfig:
    """Configuration for medium AI pipeline."""

    # Melody generation
    melody_length_ms: Optional[int] = None
    force_instrumental: bool = True

    # Lyrics generation
    genre: str = "pop"
    mood_description: str = ""
    lyrics_prompt: str = ""  # User's description of what lyrics should be about

    # TTS settings
    tts_config: Optional[TTSConfig] = None

    # AI vocal mixing settings
    ai_vocal_volume: float = 0.85
    duck_amount: float = 0.3

    # User vocal settings
    user_vocal_volume: float = 1.0
    user_duck_amount: float = 0.2

    # Voice transformation for user vocals
    transform_user_vocals: bool = True
    user_voice_config: Optional[VocalConfig] = None

    # Voice selection
    use_ai_voice_selection: bool = True


class MediumAIPipeline:
    """
    Two-phase pipeline for medium AI support mode.

    Phase 1: Generate AI vocals with gaps
    Phase 2: Integrate user-recorded vocals
    """

    def __init__(
        self,
        elevenlabs_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None
    ):
        """
        Initialize the medium AI pipeline.

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
        self.vocal_mixer = VocalMixer()
        self.vocal_processor = VocalProcessor(api_key=elevenlabs_api_key)
        self.feature_extractor = FeatureExtractor()

    def phase1_generate_master_with_gaps(
        self,
        instrumental_path: str,
        output_path: str,
        config: Optional[MediumAIPipelineConfig] = None,
        session_config_path: Optional[str] = None,
        verbose: bool = False
    ) -> Dict:
        """
        Phase 1: Generate master track with AI vocals and gaps for user.

        Args:
            instrumental_path: Path to user's instrumental audio file
            output_path: Path to save the master track with gaps
            config: Pipeline configuration
            session_config_path: Optional path to session config for BPM/key
            verbose: Print progress information

        Returns:
            Dict with pipeline results including user_sections for phase 2
        """
        config = config or MediumAIPipelineConfig()
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

        # Step 2: Generate melody
        if verbose:
            print("\n[2/6] Generating melody...")

        from compose_music import build_complementary_prompt
        from analyze_wav import MusicDescriber

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

        # Step 3: Mix melody with instrumental (medium AI volumes)
        if verbose:
            print("\n[3/6] Mixing melody with instrumental...")

        instrumental_audio = self.melody_mixer.load_wav(Path(instrumental_path))
        melody_audio = self.melody_mixer.load_audio_bytes(
            melody_bytes,
            format_hint="mp3_44100_128",
            pcm_sample_rate=44100,
            pcm_channels=2
        )

        # Mix with medium AI volumes
        volumes = AI_VOLUME_PRESETS["medium"]
        main_track = self.melody_mixer.mix(
            original=instrumental_audio,
            melody=melody_audio,
            melody_volume=volumes["melody"],
            original_volume=volumes["instrumental"]
        )

        if verbose:
            print(f"  Melody volume: {volumes['melody']:.0%}")
            print(f"  Instrumental volume: {volumes['instrumental']:.0%}")

        # Step 4: Analyze sections and generate lyrics WITH GAPS
        if verbose:
            print("\n[4/6] Analyzing sections and generating lyrics with gaps...")
            if config.lyrics_prompt:
                print(f"  User lyrics request: {config.lyrics_prompt[:50]}...")

        structure = self.lyrics_generator.create_song_structure(
            features=features,
            ai_support_level="medium",  # This creates gaps
            genre=config.genre,
            mood_description=config.mood_description or description,
            lyrics_prompt=config.lyrics_prompt,
        )

        # Separate AI sections and user sections
        ai_sections = structure.get_ai_sections()
        user_sections = structure.get_user_sections()

        results["ai_sections"] = [
            {"name": s.name, "start": s.start_time, "end": s.end_time, "lyrics": s.lyrics}
            for s in ai_sections
        ]
        results["user_sections"] = [
            {"name": s.name, "start": s.start_time, "end": s.end_time, "mood": s.mood}
            for s in user_sections
        ]

        if verbose:
            print(f"  AI sections: {len(ai_sections)}")
            print(f"  User sections (gaps): {len(user_sections)}")
            for s in user_sections:
                print(f"    {s.name}: {s.start_time:.1f}s - {s.end_time:.1f}s ({s.mood})")

        # Step 5: Synthesize AI vocals for non-gap sections
        if verbose:
            print("\n[5/6] Synthesizing AI vocals...")

        # Select voices for AI sections
        structure = self.voice_selector.select_voices_for_structure(
            structure,
            use_ai=config.use_ai_voice_selection
        )

        section_audio = {}
        for section in ai_sections:
            if not section.lyrics or not section.voice_id:
                continue

            if verbose:
                print(f"  Synthesizing {section.name}...")

            audio_bytes, duration = self.tts_processor.synthesize_section(
                lyrics=section.lyrics,
                voice_id=section.voice_id,
                config=tts_config
            )

            if audio_bytes:
                audio_np = self._pcm_to_numpy(audio_bytes, tts_config.sample_rate)
                section_audio[section.name] = audio_np

        # Step 6: Mix AI vocals into main track (leaving gaps)
        if verbose:
            print("\n[6/6] Creating master track with gaps...")

        master_track = self.section_mixer.mix_from_structure(
            main_track=main_track,
            section_audio=section_audio,
            sections=structure.sections,
            vocal_volume=config.ai_vocal_volume,
            duck_amount=config.duck_amount,
        )

        # Normalize and export
        master_track = self.melody_mixer.normalize(master_track)
        self.melody_mixer.export(master_track, Path(output_path))

        results["master_track_path"] = output_path
        results["structure"] = structure.to_dict()
        results["mode"] = "medium"
        results["phase"] = 1

        if verbose:
            print(f"\nPhase 1 complete! Master track saved to: {output_path}")
            print(f"User should record vocals for {len(user_sections)} gap section(s)")

        return results

    def phase2_add_user_vocals(
        self,
        master_track_path: str,
        user_vocals_path: str,
        output_path: str,
        config: Optional[MediumAIPipelineConfig] = None,
        verbose: bool = False
    ) -> Dict:
        """
        Phase 2: Add user-recorded vocals to the master track.

        Args:
            master_track_path: Path to master track from phase 1
            user_vocals_path: Path to user's recorded vocals
            output_path: Path to save the final mixed audio
            config: Pipeline configuration
            verbose: Print progress information

        Returns:
            Dict with final results
        """
        config = config or MediumAIPipelineConfig()
        results = {}

        # Step 1: Load master track
        if verbose:
            print("\n[1/3] Loading master track...")

        master_audio = self.vocal_mixer.load_audio(master_track_path)

        # Step 2: Process user vocals
        if verbose:
            print("\n[2/3] Processing user vocals...")

        user_vocals = self.vocal_mixer.load_audio(user_vocals_path)

        # Optionally transform user vocals
        if config.transform_user_vocals and config.user_voice_config:
            if verbose:
                print("  Transforming user voice...")

            transformed_bytes = self.vocal_processor.transform_voice(
                user_vocals_path,
                config.user_voice_config
            )

            # Convert transformed bytes to numpy
            user_vocals = self.vocal_mixer.load_audio_bytes(
                self._wrap_pcm_in_wav(transformed_bytes, 22050)
            )

        # Step 3: Mix user vocals into master
        if verbose:
            print("\n[3/3] Mixing user vocals into final track...")

        final_audio = self.section_mixer.add_user_vocals(
            main_track=master_audio,
            user_vocals=user_vocals,
            vocal_volume=config.user_vocal_volume,
            duck_amount=config.user_duck_amount,
        )

        # Normalize and export
        final_audio = self.melody_mixer.normalize(final_audio)
        self.melody_mixer.export(final_audio, Path(output_path))

        results["output_path"] = output_path
        results["mode"] = "medium"
        results["phase"] = 2

        if verbose:
            print(f"\nPhase 2 complete! Final track saved to: {output_path}")

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

    def _wrap_pcm_in_wav(self, pcm_bytes: bytes, sample_rate: int) -> bytes:
        """Wrap raw PCM bytes in a WAV container."""
        import wave
        import io

        output = io.BytesIO()
        with wave.open(output, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)

        return output.getvalue()


def main():
    """Example usage of medium AI pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Medium AI Support Pipeline")
    parser.add_argument("input", help="Path to instrumental audio file")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--user-vocals", help="Path to user vocals (for phase 2)")
    parser.add_argument("--genre", default="pop", help="Music genre")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    pipeline = MediumAIPipeline()
    config = MediumAIPipelineConfig(genre=args.genre)

    if args.user_vocals:
        # Phase 2: Add user vocals
        output_path = args.output or f"output/medium_ai_final_{Path(args.input).stem}.wav"
        results = pipeline.phase2_add_user_vocals(
            master_track_path=args.input,
            user_vocals_path=args.user_vocals,
            output_path=output_path,
            config=config,
            verbose=args.verbose
        )
    else:
        # Phase 1: Generate master with gaps
        output_path = args.output or f"output/medium_ai_master_{Path(args.input).stem}.wav"
        results = pipeline.phase1_generate_master_with_gaps(
            instrumental_path=args.input,
            output_path=output_path,
            config=config,
            verbose=args.verbose
        )

    print(f"\nResults: {results}")


if __name__ == "__main__":
    main()
