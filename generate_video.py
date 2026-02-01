#!/usr/bin/env python3
"""
Music Video Generator - Creates anime-style music videos using Google Veo 3.1 API.

Generates music videos featuring an all-girl band where each member represents
an instrumental track. Band member count matches the number of active instruments.
Characters perform instrument-specific animations synchronized to the song's BPM.

Uses session config for instruments/BPM and optionally Claude analysis for mood.

Usage:
    python generate_video.py
    python generate_video.py --audio output/mixed.wav
    python generate_video.py --config output/session_config_001.json
    python generate_video.py --aspect-ratio 9:16 --resolution 1080p
    python generate_video.py --audio output/mixed.wav --composite
    python generate_video.py --dry-run -v
"""

import argparse
import base64
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

# Import from project modules
from session_config import SessionConfig
from analyze_wav import (
    AudioFeatures,
    MusicDescriber,
    FeatureExtractor,
    SessionConfigManager,
)

# Load environment variables
load_dotenv()

# Output directory for generated videos
VIDEO_OUTPUT_DIR = Path("output/videos")

# Reference images directory
DEFAULT_IMAGE_DIR = Path("video-images")


@dataclass
class VideoGenerationConfig:
    """Configuration for music video generation."""

    # Video settings
    aspect_ratio: str = "16:9"  # "16:9" (landscape) or "9:16" (portrait)
    resolution: str = "720p"  # "720p", "1080p", "4k"

    # Model selection
    model_id: str = "veo-3.1-generate-preview"

    # Generation options
    seed: Optional[int] = None
    negative_prompt: Optional[str] = None


@dataclass
class BandMember:
    """Represents a band member in the generated video."""

    instrument: str
    position: str  # "stage left", "center stage", "stage right"
    character_description: str
    animation_style: str


class ReferenceImageManager:
    """Manages reference images for character/background consistency."""

    MAX_IMAGES = 3  # Veo 3.1 API limit
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

    def __init__(self, image_dir: Path = DEFAULT_IMAGE_DIR):
        """
        Initialize the reference image manager.

        Args:
            image_dir: Directory containing reference images
        """
        self.image_dir = image_dir

    def discover_images(self) -> List[Path]:
        """
        Find all valid image files in the directory.

        Returns:
            List of image paths, sorted by name
        """
        if not self.image_dir.exists():
            return []

        images = []
        for f in sorted(self.image_dir.iterdir()):
            if f.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                images.append(f)

        return images

    def categorize_images(self, images: List[Path]) -> Dict[str, List[Path]]:
        """
        Categorize images into girl group and background images.

        Args:
            images: List of image paths

        Returns:
            Dictionary with 'girls' and 'background' categories
        """
        categorized = {
            'girls': [],
            'background': []
        }

        for img in images:
            filename_lower = img.name.lower()
            if any(keyword in filename_lower for keyword in ['girls', 'girl', 'characters', 'character']):
                categorized['girls'].append(img)
            elif 'background' in filename_lower:
                categorized['background'].append(img)

        return categorized

    def load_image_bytes(self, path: Path) -> bytes:
        """Load image file as bytes."""
        with open(path, 'rb') as f:
            return f.read()

    def get_mime_type(self, path: Path) -> str:
        """Get MIME type for an image file."""
        ext = path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
        }
        return mime_types.get(ext, 'image/jpeg')

    def prepare_references(self, paths: Optional[List[Path]] = None) -> List[Dict[str, Any]]:
        """
        Prepare reference images for API call.
        Randomly selects one girl group photo and one background photo.

        Args:
            paths: Specific image paths, or None to auto-discover and randomly select

        Returns:
            List of reference image dicts (1 girl group + 1 background)
        """
        if paths is None:
            # Auto-discover and categorize images
            all_images = self.discover_images()
            categorized = self.categorize_images(all_images)

            # Randomly select one from each category
            selected_paths = []
            if categorized['girls']:
                selected_paths.append(random.choice(categorized['girls']))
            if categorized['background']:
                selected_paths.append(random.choice(categorized['background']))

            paths = selected_paths

        references = []
        for path in paths[:self.MAX_IMAGES]:
            image_bytes = self.load_image_bytes(path)
            mime_type = self.get_mime_type(path)
            references.append({
                'path': str(path),
                'bytes': image_bytes,
                'mime_type': mime_type,
            })

        return references


class PromptBuilder:
    """Builds dynamic prompts based on session config and audio analysis."""

    BASE_TEMPLATE = """Generate an anime-style music video featuring an all-girl band, \
where each band member represents one instrumental track in the song. \
The number of band members dynamically matches the number of active instruments. \
Each character performs instrument-specific animations that are rhythmically \
synchronized to the song's BPM, with movements, cuts, and camera transitions \
quantized to the beat."""

    INSTRUMENT_ANIMATIONS = {
        "drums": "energetic drumstick movements, head bobbing, arm raises on crashes, intense focus",
        "guitar": "strumming motions, power chord poses, headbanging, passionate expressions",
        "piano": "graceful finger movements, swaying to the music, emotional expressions, elegant posture"
    }

    INSTRUMENT_CHARACTERS = {
        "drums": "energetic drummer with short spiky hair and a confident stance",
        "guitar": "lead guitarist with long flowing hair and rock star attitude",
        "piano": "elegant pianist with braided hair and graceful demeanor"
    }

    POSITION_LABELS = {
        1: ["center stage"],
        2: ["stage left", "stage right"],
        3: ["stage left", "center stage", "stage right"]
    }

    def __init__(self):
        pass

    def build_band_members(self, instruments: List[str]) -> List[BandMember]:
        """
        Create BandMember descriptions based on instruments.

        Args:
            instruments: List of instrument names

        Returns:
            List of BandMember objects
        """
        num_members = len(instruments)
        positions = self.POSITION_LABELS.get(num_members, ["center stage"] * num_members)

        members = []
        for i, instrument in enumerate(instruments):
            position = positions[i] if i < len(positions) else "on stage"
            members.append(BandMember(
                instrument=instrument,
                position=position,
                character_description=self.INSTRUMENT_CHARACTERS.get(
                    instrument,
                    f"talented {instrument} player"
                ),
                animation_style=self.INSTRUMENT_ANIMATIONS.get(
                    instrument,
                    f"rhythmic {instrument} playing motions"
                )
            ))

        return members

    def build_rhythm_description(self, bpm: float) -> str:
        """
        Create rhythm synchronization description from BPM.

        Args:
            bpm: Beats per minute

        Returns:
            Rhythm description string
        """
        beat_ms = 60000 / bpm  # milliseconds per beat
        bar_ms = beat_ms * 4  # assuming 4/4 time

        # Describe tempo feel
        if bpm < 80:
            tempo_feel = "slow, deliberate"
        elif bpm < 110:
            tempo_feel = "moderate, groovy"
        elif bpm < 130:
            tempo_feel = "upbeat, energetic"
        else:
            tempo_feel = "fast, intense"

        return (
            f"Video cuts and animations synchronized to {bpm:.0f} BPM ({tempo_feel} tempo). "
            f"Camera movements quantized to every 2 beats ({beat_ms * 2:.0f}ms intervals). "
            f"Scene changes aligned to bar boundaries (every {bar_ms:.0f}ms). "
            f"Instrument strikes and animations timed to beat subdivisions."
        )

    def build_mood_description(
        self,
        key: str,
        audio_features: Optional[AudioFeatures] = None,
        claude_description: Optional[str] = None
    ) -> str:
        """
        Build mood/atmosphere description.

        Args:
            key: Musical key
            audio_features: Optional extracted audio features
            claude_description: Optional Claude-generated description

        Returns:
            Mood description string
        """
        # Start with key-based mood
        is_minor = "minor" in key.lower() or "min" in key.lower()
        base_mood = "melancholic, emotional depth" if is_minor else "bright, uplifting energy"

        if claude_description:
            return f"{claude_description}"

        if audio_features:
            # Build from features
            energy = "high energy" if audio_features.onset_strength_mean > 1.5 else "moderate energy"
            brightness = "bright tones" if audio_features.spectral_centroid_mean > 2500 else "warm tones"
            return f"{energy}, {brightness}, {base_mood}, {key} tonality"

        return f"{base_mood}, {key} tonality"

    def build_camera_directions(self, num_members: int, bpm: float) -> str:
        """
        Generate camera movement/cut descriptions.

        Args:
            num_members: Number of band members
            bpm: Beats per minute for timing

        Returns:
            Camera direction string
        """
        cuts_per_bar = "on every bar (4 beats)" if bpm < 120 else "on every 2 bars (8 beats)"

        if num_members == 1:
            return (
                f"Dynamic camera angles: close-ups on instrument and face, "
                f"medium shots showing full performance, occasional wide establishing shots. "
                f"Camera cuts {cuts_per_bar}."
            )
        elif num_members == 2:
            return (
                f"Alternating shots between both members, occasional two-shots showing interaction. "
                f"Close-ups synchronized to solos, wide shots on crescendos. "
                f"Camera cuts {cuts_per_bar}."
            )
        else:
            return (
                f"Rotating camera between all three members, group shots on choruses. "
                f"Individual close-ups during instrument features, dramatic lighting shifts on key changes. "
                f"Camera cuts {cuts_per_bar}."
            )

    def build_full_prompt(
        self,
        session_config: SessionConfig,
        audio_features: Optional[AudioFeatures] = None,
        claude_description: Optional[str] = None
    ) -> str:
        """
        Assemble the complete video generation prompt.

        Args:
            session_config: Session configuration with instruments and BPM
            audio_features: Optional audio features from analysis
            claude_description: Optional Claude-generated mood description

        Returns:
            Complete prompt string
        """
        instruments = session_config.instruments
        bpm = session_config.bpm
        key = session_config.key
        num_members = len(instruments)

        # Build band members
        members = self.build_band_members(instruments)

        # Build sections
        band_lineup = "\n".join([
            f"- {m.position.upper()}: {m.character_description.capitalize()}, "
            f"performing {m.animation_style}."
            for m in members
        ])

        rhythm_desc = self.build_rhythm_description(bpm)
        mood_desc = self.build_mood_description(key, audio_features, claude_description)
        camera_desc = self.build_camera_directions(num_members, bpm)

        # Assemble full prompt
        prompt = f"""Generate an anime-style music video featuring an all-girl band with {num_members} member{'s' if num_members > 1 else ''}.

BAND LINEUP:
{band_lineup}

SCENE: Neon-lit concert venue with dynamic lighting matching the beat. Cyberpunk aesthetic with vibrant pink, purple, and cyan colors.

RHYTHM: {rhythm_desc}

MOOD: {mood_desc}

CAMERA: {camera_desc}

Style: High-quality anime animation, expressive characters, dynamic performance energy, rhythmic visual synchronization."""

        return prompt


class MusicVideoGenerator:
    """Main class for generating music videos via Veo 3.1 API."""

    API_POLL_INTERVAL = 10  # seconds

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the video generator.

        Args:
            api_key: Google API key. If not provided, reads from GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self._init_client()

    def _init_client(self):
        """Initialize the google-genai client."""
        try:
            from google import genai
            self.genai = genai
            self.client = genai.Client(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "google-genai package required. Install with: pip install google-genai"
            )

    def generate(
        self,
        prompt: str,
        config: VideoGenerationConfig,
        reference_images: Optional[List[Dict[str, Any]]] = None,
        verbose: bool = False
    ) -> Path:
        """
        Generate a music video from prompt.

        Args:
            prompt: Full video generation prompt
            config: Video generation configuration
            reference_images: Optional reference image data
            verbose: Print progress information

        Returns:
            Path to the generated video file
        """
        from google.genai import types

        # Build generation config
        gen_config_params = {
            "aspect_ratio": config.aspect_ratio,
            "resolution": config.resolution,
        }

        # Add reference images if provided
        if reference_images:
            refs = []
            for img_data in reference_images:
                image = types.Image(
                    image_bytes=img_data['bytes'],
                    mime_type=img_data['mime_type']
                )
                refs.append(types.VideoGenerationReferenceImage(
                    image=image,
                    reference_type="asset"
                ))
            gen_config_params["reference_images"] = refs

        gen_config = types.GenerateVideosConfig(**gen_config_params)

        if verbose:
            print(f"  Model: {config.model_id}")
            print(f"  Aspect ratio: {config.aspect_ratio}")
            print(f"  Resolution: {config.resolution}")
            if reference_images:
                print(f"  Reference images: {len(reference_images)}")

        # Start generation
        if verbose:
            print("\n  Starting video generation...")

        operation = self.client.models.generate_videos(
            model=config.model_id,
            prompt=prompt,
            config=gen_config,
        )

        # Poll until complete
        operation = self._poll_operation(operation, verbose)

        # Get output path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = ensure_output_dir() / f"music_video_{timestamp}.mp4"

        # Download and save
        if verbose:
            print(f"\n  Downloading video to {output_path}...")

        # Check if response contains videos
        if not operation.response or not hasattr(operation.response, 'generated_videos'):
            raise RuntimeError(f"Video generation failed: No videos in response. Operation: {operation}")

        if not operation.response.generated_videos or len(operation.response.generated_videos) == 0:
            raise RuntimeError(f"Video generation failed: Empty videos list. Response: {operation.response}")

        generated_video = operation.response.generated_videos[0]
        self.client.files.download(file=generated_video.video)
        generated_video.video.save(str(output_path))

        return output_path

    def _poll_operation(self, operation: Any, verbose: bool = False) -> Any:
        """
        Poll operation until complete.

        Args:
            operation: The generation operation
            verbose: Print progress

        Returns:
            Completed operation
        """
        poll_count = 0
        while not operation.done:
            poll_count += 1
            if verbose:
                print(f"  Waiting for video generation... (poll #{poll_count})")
            time.sleep(self.API_POLL_INTERVAL)
            operation = self.client.operations.get(operation)

        return operation


def ensure_output_dir() -> Path:
    """Ensure the video output directory exists."""
    VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return VIDEO_OUTPUT_DIR


def get_output_path(filename: str) -> Path:
    """Get full output path for a file in the video output directory."""
    return ensure_output_dir() / filename


def generate_music_video(
    session_config_path: Optional[str] = None,
    audio_path: Optional[str] = None,
    image_dir: Optional[str] = None,
    output_path: Optional[str] = None,
    config: Optional[VideoGenerationConfig] = None,
    dry_run: bool = False,
    verbose: bool = False
) -> Optional[Path]:
    """
    Full pipeline: load session config, analyze audio, build prompt, generate video.

    Args:
        session_config_path: Path to session config JSON (auto-detects latest if None)
        audio_path: Path to WAV file for analysis (optional)
        image_dir: Directory containing reference images
        output_path: Output video path (auto-generated if None)
        config: Video generation configuration
        dry_run: If True, only build and display prompt
        verbose: Print detailed progress

    Returns:
        Path to the generated video file, or None if dry_run
    """
    config = config or VideoGenerationConfig()

    # Step 1: Load session config
    if verbose:
        print("\n[1/4] Loading session configuration...")

    if session_config_path:
        session_config = SessionConfig.load(Path(session_config_path))
        if verbose:
            print(f"  Loaded: {session_config_path}")
    else:
        session_config = SessionConfig.load_latest()
        if session_config is None:
            raise ValueError(
                "No session config found. Create one or specify with --config"
            )
        if verbose:
            print("  Loaded latest session config")

    if verbose:
        print(f"  Players: {session_config.num_players}")
        print(f"  Instruments: {', '.join(session_config.instruments)}")
        print(f"  BPM: {session_config.bpm}")
        print(f"  Key: {session_config.key}")

    # Step 2: Analyze audio (optional)
    audio_features = None
    claude_description = None

    if audio_path:
        if verbose:
            print("\n[2/4] Analyzing audio for mood/style...")

        try:
            extractor = FeatureExtractor()
            audio_features = extractor.extract(audio_path)

            if verbose:
                print(f"  Duration: {audio_features.duration_seconds}s")
                print(f"  Spectral centroid: {audio_features.spectral_centroid_mean:.1f} Hz")

            # Get Claude description
            try:
                describer = MusicDescriber()
                claude_description = describer.describe(audio_features)
                if verbose:
                    print(f"  Claude analysis: {claude_description[:80]}...")
            except ValueError:
                if verbose:
                    print("  (Claude API unavailable, using feature-based mood)")

        except Exception as e:
            if verbose:
                print(f"  Warning: Could not analyze audio: {e}")
    else:
        if verbose:
            print("\n[2/4] Skipping audio analysis (no audio file provided)")

    # Step 3: Build prompt
    if verbose:
        print("\n[3/4] Building video generation prompt...")

    prompt_builder = PromptBuilder()
    prompt = prompt_builder.build_full_prompt(
        session_config,
        audio_features,
        claude_description
    )

    if verbose or dry_run:
        print("\n" + "=" * 60)
        print("GENERATED PROMPT:")
        print("=" * 60)
        print(prompt)
        print("=" * 60 + "\n")

    if dry_run:
        print("Dry run complete. No video generated.")
        return None

    # Step 4: Load reference images
    if verbose:
        print("[4/4] Loading reference images and generating video...")

    img_dir = Path(image_dir) if image_dir else DEFAULT_IMAGE_DIR
    image_manager = ReferenceImageManager(img_dir)
    reference_images = image_manager.prepare_references()

    if verbose and reference_images:
        print(f"  Found {len(reference_images)} reference images:")
        for ref in reference_images:
            print(f"    - {ref['path']}")

    # Generate video
    generator = MusicVideoGenerator()
    video_path = generator.generate(
        prompt=prompt,
        config=config,
        reference_images=reference_images if reference_images else None,
        verbose=verbose
    )

    return video_path


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate anime-style music videos using Google Veo 3.1 API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate video using latest session config (auto-detect)
    python generate_video.py

    # Use specific session config
    python generate_video.py --config output/session_config_001.json

    # Include audio analysis for mood-based generation
    python generate_video.py --audio output/mixed.wav

    # Generate with audio analysis and create final composited video
    python generate_video.py --audio output/mixed.wav --composite --resolution 4k -v

    # Portrait mode for mobile/TikTok
    python generate_video.py --aspect-ratio 9:16

    # High resolution output
    python generate_video.py --resolution 1080p

    # Custom output path
    python generate_video.py -o my_music_video.mp4

    # Use custom reference images directory
    python generate_video.py --images video-images/

    # Direct prompt mode (skip session config)
    python generate_video.py --prompt "Anime girl playing electric guitar..."

    # Composite with different audio file
    python generate_video.py --composite --final-audio output/final_mix.mp3

    # Preview prompt without generating (dry run)
    python generate_video.py --dry-run -v
        """
    )

    # Input options
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        help="Path to session config JSON (default: latest session_config_NNN.json)"
    )

    parser.add_argument(
        "-a", "--audio",
        type=str,
        default=None,
        help="Path to WAV file for mood/style analysis via Claude"
    )

    parser.add_argument(
        "--images",
        type=str,
        default="video-images",
        help="Directory containing reference images (default: video-images/)"
    )

    parser.add_argument(
        "-p", "--prompt",
        type=str,
        default=None,
        help="Direct prompt for video generation (skips session config)"
    )

    # Output options
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output video file path (default: output/videos/music_video_TIMESTAMP.mp4)"
    )

    # Video settings
    parser.add_argument(
        "--aspect-ratio",
        type=str,
        choices=["16:9", "9:16"],
        default="16:9",
        help="Video aspect ratio (default: 16:9)"
    )

    parser.add_argument(
        "--resolution",
        type=str,
        choices=["720p", "1080p", "4k"],
        default="720p",
        help="Video resolution (default: 720p)"
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use faster model (veo-3.1-fast-generate-preview)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility"
    )

    parser.add_argument(
        "--negative-prompt",
        type=str,
        default=None,
        help="Describe elements to avoid in the video"
    )

    # Output modes
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed progress information"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output generation info as JSON"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and display prompt without generating video"
    )

    # Compositing options
    parser.add_argument(
        "--composite",
        action="store_true",
        help="Composite final video with music audio (loops video if needed)"
    )

    parser.add_argument(
        "--final-audio",
        type=str,
        default=None,
        help="Audio file for final composition (default: uses --audio if provided)"
    )

    return parser.parse_args()


def get_media_duration(file_path: str) -> float:
    """
    Get duration of a media file in seconds using ffprobe.

    Args:
        file_path: Path to media file

    Returns:
        Duration in seconds
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def composite_video_with_audio(
    video_path: Path,
    audio_path: str,
    output_path: Optional[Path] = None,
    verbose: bool = False
) -> Path:
    """
    Composite video with audio, looping video if needed to match audio length.

    Args:
        video_path: Path to generated video file
        audio_path: Path to audio file (WAV or MP3)
        output_path: Output path for final video (auto-generated if None)
        verbose: Print progress information

    Returns:
        Path to final composited video
    """
    if verbose:
        print("\n[Final Step] Compositing video with music...")

    # Get durations
    video_duration = get_media_duration(str(video_path))
    audio_duration = get_media_duration(audio_path)

    if verbose:
        print(f"  Video duration: {video_duration:.2f}s")
        print(f"  Audio duration: {audio_duration:.2f}s")

    # Generate output path if not provided
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = ensure_output_dir() / f"final_music_video_{timestamp}.mp4"

    # Calculate how many times to loop the video
    loops_needed = int(audio_duration / video_duration) + 1

    if verbose:
        print(f"  Looping video {loops_needed}x to match audio length")
        print(f"  Output: {output_path}")

    # Build ffmpeg command
    # Strategy: Create a concat filter to loop the video, then overlay audio
    if loops_needed == 1:
        # No looping needed, just replace audio
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-i', audio_path,
            '-map', '0:v',  # Use video from first input
            '-map', '1:a',  # Use audio from second input
            '-c:v', 'copy',  # Copy video codec (no re-encoding)
            '-c:a', 'aac',   # Encode audio as AAC
            '-b:a', '192k',  # Audio bitrate
            '-shortest',     # End when shortest stream ends
            '-y',            # Overwrite output file
            str(output_path)
        ]
    else:
        # Loop video to match audio length
        # Create a filter that loops the video
        cmd = [
            'ffmpeg',
            '-stream_loop', str(loops_needed - 1),  # Loop N-1 times (plays N times total)
            '-i', str(video_path),
            '-i', audio_path,
            '-map', '0:v',
            '-map', '1:a',
            '-c:v', 'libx264',  # Re-encode video for looping
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            '-y',
            str(output_path)
        ]

    if verbose:
        print("  Running ffmpeg...")

    # Run ffmpeg
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    if verbose:
        print(f"  ✓ Final video created: {output_path}")
        file_size = output_path.stat().st_size / (1024 * 1024)
        print(f"  File size: {file_size:.1f} MB")

    return output_path


def main():
    """Main entry point."""
    args = parse_args()

    # Build config
    model_id = "veo-3.1-fast-generate-preview" if args.fast else "veo-3.1-generate-preview"
    config = VideoGenerationConfig(
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        model_id=model_id,
        seed=args.seed,
        negative_prompt=args.negative_prompt,
    )

    try:
        if args.prompt:
            # Direct prompt mode
            if args.verbose:
                print(f"\nDirect prompt mode")
                print(f"Prompt: {args.prompt[:100]}...")

            if args.dry_run:
                print("\n" + "=" * 60)
                print("PROMPT:")
                print("=" * 60)
                print(args.prompt)
                print("=" * 60)
                print("\nDry run complete. No video generated.")
                return 0

            # Load reference images
            image_manager = ReferenceImageManager(Path(args.images))
            reference_images = image_manager.prepare_references()

            # Generate
            generator = MusicVideoGenerator()
            video_path = generator.generate(
                prompt=args.prompt,
                config=config,
                reference_images=reference_images if reference_images else None,
                verbose=args.verbose
            )

            # Composite with audio if requested
            final_video_path = video_path
            if args.composite:
                composite_audio = args.final_audio or args.audio
                if not composite_audio:
                    print("Error: --composite requires --audio or --final-audio")
                    return 1

                final_video_path = composite_video_with_audio(
                    video_path=video_path,
                    audio_path=composite_audio,
                    verbose=args.verbose
                )

            if args.json:
                info = {
                    "mode": "direct_prompt",
                    "prompt": args.prompt,
                    "generated_video": str(video_path),
                    "final_video": str(final_video_path) if args.composite else str(video_path),
                    "composited": args.composite,
                    "config": asdict(config),
                }
                print(json.dumps(info, indent=2))
            else:
                if args.composite:
                    print(f"\n✓ Generated video: {video_path}")
                    print(f"✓ Final composited video: {final_video_path}")
                else:
                    print(f"\nGenerated video: {video_path}")

        else:
            # Session config mode
            video_path = generate_music_video(
                session_config_path=args.config,
                audio_path=args.audio,
                image_dir=args.images,
                output_path=args.output,
                config=config,
                dry_run=args.dry_run,
                verbose=args.verbose
            )

            if video_path:
                # Composite with audio if requested
                final_video_path = video_path
                if args.composite:
                    # Determine which audio to use
                    composite_audio = args.final_audio or args.audio
                    if not composite_audio:
                        print("Error: --composite requires --audio or --final-audio")
                        return 1

                    final_video_path = composite_video_with_audio(
                        video_path=video_path,
                        audio_path=composite_audio,
                        verbose=args.verbose
                    )

                if args.json:
                    # Load session config for JSON output
                    if args.config:
                        session_config = SessionConfig.load(Path(args.config))
                    else:
                        session_config = SessionConfig.load_latest()

                    info = {
                        "mode": "session_config",
                        "session_config": args.config or "latest",
                        "instruments": session_config.instruments if session_config else [],
                        "bpm": session_config.bpm if session_config else None,
                        "key": session_config.key if session_config else None,
                        "audio_analyzed": args.audio is not None,
                        "generated_video": str(video_path),
                        "final_video": str(final_video_path) if args.composite else str(video_path),
                        "composited": args.composite,
                        "config": asdict(config),
                    }
                    print(json.dumps(info, indent=2))
                else:
                    if args.composite:
                        print(f"\n✓ Generated video: {video_path}")
                        print(f"✓ Final composited video: {final_video_path}")
                    else:
                        print(f"\nGenerated video: {video_path}")

        return 0

    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except RuntimeError as e:
        print(f"API Error: {e}")
        return 1
    except Exception as e:
        print(f"Error generating video: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
