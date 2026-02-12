#!/usr/bin/env python3
"""
Video Generator - Creates music videos by looping short video clips.

Randomly selects and concatenates video clips from the short_videos directory,
then overlays the final audio track to create a complete music video.

Usage:
    python video_generator.py --audio output/final.wav --output output/video.mp4
    python video_generator.py --audio output/final.wav --duration 30
"""

import argparse
import random
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Default directories
SHORT_VIDEOS_DIR = Path("short_videos")
OUTPUT_DIR = Path("output/videos")


class ShortVideoLooper:
    """Creates music videos by looping short video clips."""

    def __init__(self, videos_dir: Path = SHORT_VIDEOS_DIR):
        """
        Initialize the video looper.

        Args:
            videos_dir: Directory containing source video clips
        """
        self.videos_dir = videos_dir
        self.available_videos = self._scan_videos()

        if not self.available_videos:
            raise ValueError(f"No MP4 videos found in {videos_dir}")

    def _scan_videos(self) -> List[Path]:
        """Find all MP4 files in the videos directory."""
        if not self.videos_dir.exists():
            return []
        return list(self.videos_dir.glob("*.mp4"))

    def _get_video_duration(self, video_path: Path) -> float:
        """
        Get video duration using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds
        """
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        return float(result.stdout.strip())

    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        Get audio duration using ffprobe.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds
        """
        return self._get_video_duration(audio_path)  # Same ffprobe command works

    def _create_video_list(self, target_duration: float) -> List[Path]:
        """
        Create randomized list of videos to fill target duration.

        Args:
            target_duration: Target total duration in seconds

        Returns:
            List of video paths to concatenate
        """
        videos = []
        current_duration = 0.0

        # Cache durations to avoid repeated ffprobe calls
        duration_cache = {}

        while current_duration < target_duration:
            video = random.choice(self.available_videos)

            if video not in duration_cache:
                duration_cache[video] = self._get_video_duration(video)

            videos.append(video)
            current_duration += duration_cache[video]

        return videos

    def _ensure_consistent_format(
        self,
        video_list: List[Path],
        temp_dir: Path
    ) -> List[Path]:
        """
        Re-encode videos to ensure consistent format for concatenation.

        This prevents errors when videos have different codecs/resolutions.

        Args:
            video_list: List of source video paths
            temp_dir: Directory for temporary re-encoded files

        Returns:
            List of re-encoded video paths
        """
        temp_dir.mkdir(parents=True, exist_ok=True)
        reencoded = []

        for i, video in enumerate(video_list):
            temp_path = temp_dir / f"segment_{i:04d}.mp4"

            # Re-encode with consistent settings
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(video),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-r", "30",  # Force 30fps
                    "-s", "1920x1080",  # Force 1080p
                    "-an",  # Remove audio (we'll add our own)
                    str(temp_path)
                ],
                capture_output=True,
                check=True
            )

            reencoded.append(temp_path)

        return reencoded

    def generate(
        self,
        audio_path: Path,
        output_path: Path,
        audio_duration: Optional[float] = None
    ) -> Path:
        """
        Generate music video by concatenating random clips with audio.

        Args:
            audio_path: Path to audio file to overlay
            output_path: Path for output video
            audio_duration: Override duration (auto-detected if None)

        Returns:
            Path to generated video
        """
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get audio duration if not provided
        if audio_duration is None:
            audio_duration = self._get_audio_duration(audio_path)

        print(f"Target duration: {audio_duration:.2f}s")
        print(f"Available source videos: {len(self.available_videos)}")

        # Create list of videos to loop
        video_list = self._create_video_list(audio_duration)
        print(f"Selected {len(video_list)} video segments")

        # Create temp directory for working files
        temp_dir = output_path.parent / f".temp_{output_path.stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Re-encode for consistent format
            print("Re-encoding segments for consistency...")
            reencoded_videos = self._ensure_consistent_format(video_list, temp_dir)

            # Write concat list file
            concat_file = temp_dir / "concat.txt"
            with open(concat_file, "w") as f:
                for video in reencoded_videos:
                    f.write(f"file '{video.absolute()}'\n")

            # Concatenate videos
            print("Concatenating video segments...")
            temp_video = temp_dir / "concatenated.mp4"

            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-c", "copy",
                    str(temp_video)
                ],
                capture_output=True,
                check=True
            )

            # Add audio and trim to exact duration
            print("Adding audio track...")
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(temp_video),
                    "-i", str(audio_path),
                    "-map", "0:v",
                    "-map", "1:a",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-t", str(audio_duration),
                    "-shortest",
                    str(output_path)
                ],
                capture_output=True,
                check=True
            )

            print(f"Generated video: {output_path}")
            return output_path

        finally:
            # Cleanup temp files
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


def get_output_path(filename: str) -> Path:
    """Get full output path for a video file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR / filename


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate music videos by looping short video clips",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate video from audio file
    python video_generator.py --audio output/final.wav

    # Specify output path
    python video_generator.py --audio output/final.wav --output my_video.mp4

    # Use custom source videos directory
    python video_generator.py --audio output/final.wav --videos-dir my_clips/

    # Override duration
    python video_generator.py --audio output/final.wav --duration 60
        """
    )

    parser.add_argument(
        "-a", "--audio",
        type=str,
        required=True,
        help="Input audio file (WAV or MP3)"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output video path (default: output/videos/music_video_TIMESTAMP.mp4)"
    )

    parser.add_argument(
        "-d", "--duration",
        type=float,
        default=None,
        help="Override audio duration (seconds)"
    )

    parser.add_argument(
        "--videos-dir",
        type=str,
        default=str(SHORT_VIDEOS_DIR),
        help=f"Directory containing source video clips (default: {SHORT_VIDEOS_DIR})"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed progress"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Validate input audio
    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Error: Audio file not found: {audio_path}")
        return 1

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = get_output_path(f"music_video_{timestamp}.mp4")

    try:
        # Create video generator
        looper = ShortVideoLooper(Path(args.videos_dir))

        # Generate video
        result = looper.generate(
            audio_path=audio_path,
            output_path=output_path,
            audio_duration=args.duration
        )

        print(f"\nSuccess! Video saved to: {result}")
        return 0

    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg: {e}")
        if e.stderr:
            print(f"stderr: {e.stderr.decode()}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
