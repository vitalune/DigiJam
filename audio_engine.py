#!/usr/bin/env python3
"""
DigiJam Audio Engine - Post-processing script to render session recordings to WAV.

Reads JSON session files from drums, guitar, and piano classifiers,
quantizes events to a musical time grid, pitch-shifts melodic instrument samples,
and renders a final mixed WAV file.

Usage:
    python audio_engine.py --drums output/drums_session.json \\
                           --guitar output/guitar_session.json \\
                           --piano output/piano_session.json \\
                           --bpm 120 \\
                           --key "C Major" \\
                           --output output/mixed.wav

Examples:
    # Render drums only at 100 BPM
    python audio_engine.py --drums output/drums_session.json --bpm 100 --output drums_only.wav

    # Render all instruments at 120 BPM in A Minor
    python audio_engine.py --drums output/drums.json --guitar output/guitar.json \\
                           --piano output/piano.json --bpm 120 --key "A Minor" --output full_mix.wav

    # Render without quantization (raw timing)
    python audio_engine.py --drums output/drums.json --no-quantize --output raw_timing.wav
"""

import argparse
import sys
from pathlib import Path
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from audio.loader import (
    AudioEvent,
    load_drums_session,
    load_guitar_session,
    load_piano_session
)
from audio.quantizer import build_grid, snap_to_grid, get_grid_for_event
from audio.mixer import AudioMixer
from audio.music_theory import AVAILABLE_KEYS, DEFAULT_KEY


def main():
    parser = argparse.ArgumentParser(
        description='DigiJam Audio Engine - Render gesture sessions to WAV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Input files
    parser.add_argument('--drums', type=str, help='Path to drums session JSON')
    parser.add_argument('--guitar', type=str, help='Path to guitar session JSON')
    parser.add_argument('--piano', type=str, help='Path to piano session JSON')

    # Audio settings
    parser.add_argument('--bpm', type=float, default=120.0,
                        help='Tempo in beats per minute (default: 120)')
    parser.add_argument('--sample-rate', type=int, default=44100,
                        help='Output sample rate in Hz (default: 44100)')
    parser.add_argument('--key', type=str, default=None,
                        help=f'Musical key for guitar/piano (default: read from session file, or {DEFAULT_KEY}). '
                             f'Available: {", ".join(AVAILABLE_KEYS[:6])}...')

    # Output settings
    parser.add_argument('--output', '-o', type=str, default='output/mixed.wav',
                        help='Output WAV file path (default: output/mixed.wav)')
    parser.add_argument('--soundpack', type=str, default='soundpack',
                        help='Soundpack directory path (default: soundpack)')

    # Processing options
    parser.add_argument('--no-quantize', action='store_true',
                        help='Disable quantization (use raw event timing)')
    parser.add_argument('--normalize', type=float, default=-1.0,
                        help='Normalize output to this headroom in dB (default: -1.0)')

    args = parser.parse_args()

    # Validate at least one input
    if not any([args.drums, args.guitar, args.piano]):
        parser.error('At least one session file is required (--drums, --guitar, or --piano)')

    # Validate key if provided
    if args.key and args.key not in AVAILABLE_KEYS:
        parser.error(f'Invalid key: {args.key}. Available keys: {", ".join(AVAILABLE_KEYS)}')

    print(f"DigiJam Audio Engine")
    print(f"====================")
    print(f"BPM: {args.bpm}")
    print(f"Sample Rate: {args.sample_rate} Hz")
    print(f"Key: {args.key or '(from session files)'}")
    print(f"Quantization: {'Disabled' if args.no_quantize else 'Enabled'}")
    print()

    # Collect all events and find max duration
    all_events: List[AudioEvent] = []
    max_end_time = 0.0

    if args.drums:
        if not Path(args.drums).exists():
            print(f"Error: Drums file not found: {args.drums}")
            sys.exit(1)
        events, end_time = load_drums_session(args.drums)
        all_events.extend(events)
        max_end_time = max(max_end_time, end_time)
        print(f"Loaded {len(events)} drum events from {args.drums}")

    if args.guitar:
        if not Path(args.guitar).exists():
            print(f"Error: Guitar file not found: {args.guitar}")
            sys.exit(1)
        events, end_time = load_guitar_session(args.guitar, key=args.key)
        all_events.extend(events)
        max_end_time = max(max_end_time, end_time)
        print(f"Loaded {len(events)} guitar events from {args.guitar}")

    if args.piano:
        if not Path(args.piano).exists():
            print(f"Error: Piano file not found: {args.piano}")
            sys.exit(1)
        events, end_time = load_piano_session(args.piano, key=args.key)
        all_events.extend(events)
        max_end_time = max(max_end_time, end_time)
        print(f"Loaded {len(events)} piano events from {args.piano}")

    if not all_events:
        print("No events loaded. Check your session files.")
        sys.exit(1)

    print(f"\nTotal events: {len(all_events)}")
    print(f"Duration: {max_end_time:.2f} seconds")

    # Build quantization grids
    print(f"\nBuilding quantization grids...")
    grids = {
        '16th': build_grid(args.bpm, max_end_time, '16th'),
        'quarter': build_grid(args.bpm, max_end_time, 'quarter'),
        'half': build_grid(args.bpm, max_end_time, 'half'),
    }

    for name, grid in grids.items():
        print(f"  {name}: {len(grid.grid_points)} points, interval={grid.interval:.4f}s")

    # Quantize events
    print(f"\nQuantizing events...")
    for event in all_events:
        if args.no_quantize:
            event.quantized_time = event.timestamp
        else:
            grid_type = get_grid_for_event(event.instrument, event.action)
            event.quantized_time = snap_to_grid(event.timestamp, grids[grid_type])

    # Sort by quantized time
    all_events.sort(key=lambda e: e.quantized_time)

    # Initialize mixer and load samples
    print(f"\nLoading samples from {args.soundpack}...")
    mixer = AudioMixer(args.soundpack, sample_rate=args.sample_rate)
    mixer.load_samples()
    print(f"Loaded {len(mixer.samples)} samples")

    # Render
    print(f"\nRendering audio...")
    audio = mixer.render(all_events, max_end_time)
    print(f"  Raw buffer: {len(audio)} samples ({len(audio)/args.sample_rate:.2f}s)")

    # Normalize
    print(f"  Normalizing to {args.normalize} dB headroom...")
    audio = mixer.normalize(audio, headroom_db=args.normalize)

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export
    print(f"\nExporting to {args.output}...")
    mixer.export_wav(audio, args.output)

    print(f"\nDone! Output: {args.output}")
    print(f"  Duration: {len(audio)/args.sample_rate:.2f}s")
    print(f"  Sample rate: {args.sample_rate} Hz")
    print(f"  Channels: 1 (mono)")


if __name__ == '__main__':
    main()
