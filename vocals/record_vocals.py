#!/usr/bin/env python3
"""
Vocal recording and processing pipeline.

Records vocals with background instrumental playback, transforms via ElevenLabs
Voice Changer, and mixes into a synchronized master track.

All output files are saved to output/vocals/ directory.

Usage:
    python -m vocals.record_vocals --instrumental path/to/instrumental.wav
    python -m vocals.record_vocals -i instrumental.wav -o final_mix.wav --voice 3
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vocals.vocal_config import (
    VocalConfig,
    RecordingConfig,
    select_voice,
    get_voice_by_index,
    display_voice_options,
)
from vocals.vocal_recorder import VocalRecorder
from vocals.vocal_processor import VocalProcessor
from vocals.vocal_mixer import VocalMixer


# Default output directory for all vocal files
OUTPUT_DIR = Path("output/vocals")


def ensure_output_dir() -> Path:
    """Ensure the output directory exists and return its path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def get_output_path(filename: str) -> Path:
    """Get full output path for a file in the vocals output directory."""
    ensure_output_dir()
    return OUTPUT_DIR / filename


def get_timestamped_filename(base: str, ext: str = ".wav") -> str:
    """Generate a timestamped filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{timestamp}{ext}"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Record vocals with background instrumental and process through ElevenLabs Voice Changer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive voice selection, play instrumental while recording
    # Output saved to output/vocals/
    python -m vocals.record_vocals -i track.wav

    # Use voice #3, specify output filename
    python -m vocals.record_vocals -i track.wav -o my_song.wav --voice 3

    # Just show available voices
    python -m vocals.record_vocals --list-voices
        """
    )

    parser.add_argument(
        "-i", "--instrumental",
        type=str,
        help="Path to instrumental audio file (WAV or MP3)"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output filename for final mixed track (saved to output/vocals/)"
    )

    parser.add_argument(
        "--voice",
        type=int,
        choices=range(1, 11),
        metavar="1-10",
        help="Voice number (1-10). If not specified, shows interactive selection."
    )

    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available voices and exit"
    )

    parser.add_argument(
        "--vocal-offset",
        type=float,
        default=0.0,
        help="Vocal offset in seconds for mixing (default: 0.0)"
    )

    parser.add_argument(
        "--vocal-volume",
        type=float,
        default=1.0,
        help="Vocal volume multiplier (default: 1.0)"
    )

    parser.add_argument(
        "--instrumental-volume",
        type=float,
        default=0.8,
        help="Instrumental volume multiplier in final mix (default: 0.8)"
    )

    parser.add_argument(
        "--no-background-noise-removal",
        action="store_true",
        help="Disable background noise removal in voice transformation"
    )

    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="Keep the raw recorded vocals file (not deleted after processing)"
    )

    return parser.parse_args()


def main():
    """Main entry point for vocal recording pipeline."""
    args = parse_args()

    # List voices and exit if requested
    if args.list_voices:
        display_voice_options()
        return 0

    # Require instrumental file
    if not args.instrumental:
        print("Error: --instrumental (-i) is required.")
        print("Use --help for usage information.")
        return 1

    instrumental_path = Path(args.instrumental)
    if not instrumental_path.exists():
        print(f"Error: Instrumental file not found: {instrumental_path}")
        return 1

    # Check for API key
    if not os.getenv("ELEVENLABS_API_KEY"):
        print("Error: ELEVENLABS_API_KEY environment variable not set.")
        print("Set it in your .env file or export it:")
        print("  export ELEVENLABS_API_KEY=your_api_key")
        return 1

    # Ensure output directory exists
    ensure_output_dir()

    # Generate output filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_vocals_path = get_output_path(f"raw_vocals_{timestamp}.wav")
    transformed_vocals_path = get_output_path(f"acapella_{timestamp}.wav")

    if args.output:
        final_mix_path = get_output_path(args.output)
    else:
        final_mix_path = get_output_path(f"final_mix_{timestamp}.wav")

    print("\n" + "=" * 60)
    print("        VOCAL RECORDING & PROCESSING PIPELINE")
    print("=" * 60)
    print(f"\nOutput directory: {OUTPUT_DIR.absolute()}")

    # Step 1: Voice Selection
    print("\n[1/5] Voice Selection")
    print("-" * 40)

    if args.voice:
        vocal_config = get_voice_by_index(args.voice)
        print(f"Using voice #{args.voice}")
    else:
        vocal_config = select_voice()

    # Configure noise removal
    vocal_config.remove_background_noise = not args.no_background_noise_removal

    # Step 2: Load instrumental and prepare recorder
    print("\n[2/5] Loading Instrumental")
    print("-" * 40)

    recorder = VocalRecorder()
    duration = recorder.load_instrumental(instrumental_path)
    print(f"Instrumental duration: {duration:.2f}s")

    # Step 3: Record vocals
    print("\n[3/5] Recording Vocals")
    print("-" * 40)
    print("The instrumental will play in the background.")
    print("Sing/speak into your microphone.")

    input("\nPress Enter to start recording...")

    recorder.start_recording(play_instrumental=True)

    input()  # Wait for Enter to stop

    recorder.stop_recording()
    recorder.save_recording(str(raw_vocals_path))

    # Step 4: Transform voice
    print("\n[4/5] Transforming Voice via ElevenLabs")
    print("-" * 40)
    print("Sending to ElevenLabs Voice Changer API...")

    processor = VocalProcessor()
    transformed_audio = processor.transform_voice(str(raw_vocals_path), vocal_config)
    processor.save_transformed(transformed_audio, str(transformed_vocals_path), vocal_config)
    print(f"Voice-changed acapella saved to: {transformed_vocals_path}")

    # Step 5: Mix with instrumental
    print("\n[5/5] Mixing Final Track")
    print("-" * 40)

    mixer = VocalMixer()
    final_audio = mixer.mix_files(
        instrumental_path=instrumental_path,
        vocal_path=str(transformed_vocals_path),
        vocal_offset=args.vocal_offset,
        vocal_volume=args.vocal_volume,
        instrumental_volume=args.instrumental_volume,
    )

    # Normalize and export
    final_audio = mixer.normalize(final_audio)
    mixer.export(final_audio, str(final_mix_path))

    # Optionally remove raw vocals
    if not args.keep_raw:
        raw_vocals_path.unlink()
        print(f"Removed temporary file: {raw_vocals_path}")

    print("\n" + "=" * 60)
    print("        PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\nFiles saved to {OUTPUT_DIR.absolute()}:")
    print(f"  Acapella (voice-changed): {transformed_vocals_path.name}")
    print(f"  Final mix:                {final_mix_path.name}")
    if args.keep_raw:
        print(f"  Raw vocals:               {raw_vocals_path.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
