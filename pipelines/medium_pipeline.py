"""
Medium AI Support Pipeline - Collaborative AI + User vocals.

Orchestrates the workflow for medium AI support mode:
1. Extract audio features from instrumental
2. Generate melody at balanced volume (50/50)
3. Analyze sections and generate partial lyrics with gaps
4. AI sings lead sections, user fills in chorus/gaps
5. Transform and mix user vocals for their sections
6. Mix AI vocals + user vocals with instrumental
7. Generate music video

Collaborative mode - AI handles verses, user handles choruses.
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

from analyze_wav import AudioFeatures, SongStructure, FeatureExtractor, MusicDescriber
from compose_music import MusicComposer, MelodyMixer, CompositionConfig, AI_VOLUME_PRESETS, build_complementary_prompt
from vocals.vocal_config import TTSConfig
from vocals.tts_processor import TTSProcessor
from vocals.lyrics_generator import LyricsGenerator
from vocals.voice_selector import VoiceSelector
from vocals.vocal_mixer import VocalMixer, SectionMixer
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
    mode: str = "medium"


@dataclass
class MediumPipelineConfig:
    """Configuration for medium AI pipeline."""

    # Melody generation
    melody_length_ms: Optional[int] = None
    force_instrumental: bool = True

    # Lyrics generation
    genre: str = "pop"
    mood_description: str = ""
    lyrics_prompt: str = ""

    # Voice settings
    voice_id: str = ""  # Target voice for both AI and user transformation
    use_ai_voice_selection: bool = True

    # TTS settings
    tts_config: Optional[TTSConfig] = None

    # Voice transformation settings (for user vocals)
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0

    # Mixing settings
    ai_vocal_volume: float = 0.85
    user_vocal_volume: float = 1.0
    duck_amount: float = 0.3


class MediumPipeline:
    """
    Pipeline for medium AI support mode.

    Collaborative mode with AI and user vocals.
    """

    def __init__(
        self,
        elevenlabs_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        output_dir: Path = Path("output")
    ):
        """
        Initialize the medium AI pipeline.

        Args:
            elevenlabs_api_key: ElevenLabs API key
            anthropic_api_key: Anthropic API key for Claude
            output_dir: Base output directory
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.elevenlabs_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.elevenlabs_key:
            raise ValueError("ElevenLabs API key required.")

        # Initialize components
        self.feature_extractor = FeatureExtractor()
        self.composer = MusicComposer(api_key=self.elevenlabs_key)
        self.melody_mixer = MelodyMixer()
        self.lyrics_generator = LyricsGenerator(api_key=anthropic_api_key)
        self.voice_selector = VoiceSelector(api_key=anthropic_api_key)
        self.tts_processor = TTSProcessor(api_key=self.elevenlabs_key)
        self.vocal_mixer = VocalMixer()
        self.section_mixer = SectionMixer()
        self.video_looper = ShortVideoLooper()

        # Initialize ElevenLabs client for speech-to-speech
        from elevenlabs.client import ElevenLabs
        self.elevenlabs = ElevenLabs(api_key=self.elevenlabs_key)

    def transform_voice(
        self,
        audio_data: Union[bytes, np.ndarray],
        voice_id: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0
    ) -> bytes:
        """Transform audio to a different voice using ElevenLabs Speech-to-Speech."""
        if isinstance(audio_data, np.ndarray):
            audio_bytes = self._numpy_to_wav_bytes(audio_data)
        else:
            audio_bytes = audio_data

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

        return b''.join(audio_stream)

    def _numpy_to_wav_bytes(self, audio: np.ndarray, sample_rate: int = 44100) -> bytes:
        """Convert numpy array to WAV bytes."""
        if audio.dtype != np.int16:
            audio = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

        buffer = BytesIO()
        wavfile.write(buffer, sample_rate, audio)
        buffer.seek(0)
        return buffer.read()

    def _load_user_vocals(self, vocals_path: Union[str, Path, bytes]) -> np.ndarray:
        """Load user vocals from file or bytes."""
        if isinstance(vocals_path, bytes):
            return self.vocal_mixer.load_audio_bytes(vocals_path)
        return self.vocal_mixer.load_audio(vocals_path)

    def _pcm_to_numpy(self, audio_bytes: bytes, sample_rate: int = 44100) -> np.ndarray:
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

    def process(
        self,
        session_id: str,
        instrumental_path: str,
        user_vocals: Union[str, Path, bytes],
        voice_id: str,
        lyrics_prompt: str = "",
        bpm: float = 120,
        key: str = "C Major",
        config: Optional[MediumPipelineConfig] = None,
        session_config_path: Optional[str] = None,
        verbose: bool = False
    ) -> PipelineResult:
        """
        Run the medium AI pipeline.

        Args:
            session_id: Unique session identifier
            instrumental_path: Path to user's instrumental audio file
            user_vocals: User's recorded vocals (path or bytes)
            voice_id: Target voice for AI and user transformation
            lyrics_prompt: Description of desired lyrics theme
            bpm: BPM of the track
            key: Musical key
            config: Pipeline configuration
            session_config_path: Optional path to session config
            verbose: Print progress information

        Returns:
            PipelineResult with paths to generated files and metadata
        """
        config = config or MediumPipelineConfig(
            voice_id=voice_id,
            lyrics_prompt=lyrics_prompt
        )
        if not config.voice_id:
            config.voice_id = voice_id
        if not config.lyrics_prompt:
            config.lyrics_prompt = lyrics_prompt

        tts_config = config.tts_config or TTSConfig()

        # Prepare output paths
        audio_output = self.output_dir / f"{session_id}_final.wav"
        video_output = self.output_dir / "videos" / f"{session_id}_video.mp4"
        video_output.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: Extract features
        if verbose:
            print("\n[1/8] Extracting audio features...")

        config_path = Path(session_config_path) if session_config_path else None
        features = self.feature_extractor.extract(instrumental_path, config_path)

        if bpm:
            features.tempo_bpm = bpm
        if key:
            features.key = key

        if verbose:
            print(f"  BPM: {features.tempo_bpm}, Key: {features.key}")
            print(f"  Duration: {features.duration_seconds:.1f}s")

        # Step 2: Generate melody
        if verbose:
            print("\n[2/8] Generating melody...")

        try:
            describer = MusicDescriber()
            description = describer.describe(features)
        except ValueError:
            energy = "high energy" if features.onset_strength_mean > 1.5 else "moderate energy"
            brightness = "bright" if features.spectral_centroid_mean > 2500 else "warm"
            description = f"{energy} {brightness} track"

        prompt = build_complementary_prompt(features, description)

        composition_config = CompositionConfig(
            output_format="mp3_44100_128",
            force_instrumental=config.force_instrumental,
            music_length_ms=config.melody_length_ms,
        )

        melody_bytes = self.composer.compose_from_prompt(prompt, composition_config)

        # Step 3: Mix melody with instrumental (medium volumes - balanced)
        if verbose:
            print("\n[3/8] Mixing melody with instrumental...")

        instrumental_audio = self.melody_mixer.load_wav(Path(instrumental_path))

        melody_audio = self.melody_mixer.load_audio_bytes(
            melody_bytes,
            format_hint="mp3_44100_128",
            pcm_sample_rate=44100,
            pcm_channels=2
        )

        # Use medium AI volumes (balanced)
        volumes = AI_VOLUME_PRESETS["medium"]
        backing_track = self.melody_mixer.mix(
            original=instrumental_audio,
            melody=melody_audio,
            melody_volume=volumes["melody"],
            original_volume=volumes["instrumental"]
        )

        if verbose:
            print(f"  Melody volume: {volumes['melody']:.0%}")
            print(f"  Instrumental volume: {volumes['instrumental']:.0%}")

        # Step 4: Generate partial lyrics with gaps
        if verbose:
            print("\n[4/8] Generating partial lyrics with gaps...")
            if config.lyrics_prompt:
                print(f"  Theme: {config.lyrics_prompt[:50]}...")

        structure = self.lyrics_generator.create_song_structure(
            features=features,
            ai_support_level="medium",  # This generates lyrics with gaps
            genre=config.genre,
            mood_description=config.mood_description or description,
            lyrics_prompt=config.lyrics_prompt,
        )

        ai_sections = [s for s in structure.sections if not s.is_user_section and s.lyrics]
        user_sections = [s for s in structure.sections if s.is_user_section]

        if verbose:
            print(f"  Total sections: {len(structure.sections)}")
            print(f"  AI sections: {len(ai_sections)}")
            print(f"  User sections: {len(user_sections)}")

        # Step 5: Select voices for AI sections
        if verbose:
            print("\n[5/8] Selecting voices...")

        if config.voice_id:
            for section in ai_sections:
                section.voice_id = config.voice_id
        elif config.use_ai_voice_selection:
            structure = self.voice_selector.select_voices_for_structure(
                structure,
                use_ai=True
            )

        # Step 6: Synthesize AI vocals
        if verbose:
            print("\n[6/8] Synthesizing AI vocals...")

        ai_section_audio = {}
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
                ai_section_audio[section.name] = audio_np

        # Mix AI vocals into backing track
        main_track = self.section_mixer.mix_from_structure(
            main_track=backing_track,
            section_audio=ai_section_audio,
            sections=structure.sections,
            vocal_volume=config.ai_vocal_volume,
            duck_amount=config.duck_amount,
        )

        # Step 7: Transform and mix user vocals
        if verbose:
            print("\n[7/8] Processing user vocals...")

        user_vocals_audio = self._load_user_vocals(user_vocals)

        if verbose:
            print(f"  Loaded {len(user_vocals_audio) / 44100:.1f}s of user vocals")
            print(f"  Transforming to voice: {config.voice_id}")

        # Transform user vocals to match AI voice style
        transformed_bytes = self.transform_voice(
            audio_data=user_vocals_audio,
            voice_id=config.voice_id,
            stability=config.stability,
            similarity_boost=config.similarity_boost,
            style=config.style
        )

        transformed_audio = np.frombuffer(transformed_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Mix user vocals on top (they fill in the gaps)
        final_audio = self.section_mixer.add_user_vocals(
            main_track=main_track,
            user_vocals=transformed_audio,
            vocal_volume=config.user_vocal_volume,
            duck_amount=0.2  # Light ducking for user vocals
        )

        # Normalize and export
        final_audio = self.vocal_mixer.normalize(final_audio)
        self.vocal_mixer.export(final_audio, audio_output)

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

        return PipelineResult(
            video_path=video_path,
            audio_path=audio_output,
            duration=features.duration_seconds,
            sections=[
                {
                    "name": s.name,
                    "start": s.start_time,
                    "end": s.end_time,
                    "lyrics": s.lyrics,
                    "is_user_section": s.is_user_section
                }
                for s in structure.sections
            ],
            features={
                "bpm": features.tempo_bpm,
                "key": features.key,
                "duration": features.duration_seconds,
            },
            mode="medium"
        )


def main():
    """Command line interface for medium AI pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Medium AI Support Pipeline")
    parser.add_argument("input", help="Path to instrumental audio file")
    parser.add_argument("--vocals", required=True, help="Path to user vocals file")
    parser.add_argument("--voice-id", required=True, help="Target voice ID")
    parser.add_argument("--lyrics-prompt", help="Theme for lyrics generation")
    parser.add_argument("-o", "--output", help="Output directory", default="output")
    parser.add_argument("--session-id", help="Session ID", default="test_session")
    parser.add_argument("--genre", default="pop", help="Music genre")
    parser.add_argument("--bpm", type=float, help="BPM of the track")
    parser.add_argument("--key", help="Musical key")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    pipeline = MediumPipeline(output_dir=Path(args.output))
    config = MediumPipelineConfig(
        voice_id=args.voice_id,
        lyrics_prompt=args.lyrics_prompt or "",
        genre=args.genre,
    )

    result = pipeline.process(
        session_id=args.session_id,
        instrumental_path=args.input,
        user_vocals=args.vocals,
        voice_id=args.voice_id,
        lyrics_prompt=args.lyrics_prompt or "",
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
