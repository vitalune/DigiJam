#!/usr/bin/env python3
"""
Live webcam feed with instrument-specific pose detection and action classification.

Usage:
    python webcam_posedetect.py

Controls:
    'r' - Start recording
    's' - Stop recording
    'q' - Quit
    'c' - Clear hit log
    'g' - Recalibrate guitar (guitar mode)
    'p' - Recalibrate piano (piano mode)
"""
from webcam_recorder import WebcamRecorder
from audio.music_theory import DEFAULT_KEY


def main():
    """Main entry point with instrument, dexterity, and key selection."""
    # Prompt for instrument selection
    instrument = WebcamRecorder.prompt_instrument()
    print(f"\nSelected: {instrument.upper()}")

    # Prompt for dexterity selection
    dominant_hand = WebcamRecorder.prompt_dexterity()
    print(f"\nDominant hand: {dominant_hand.upper()}")

    # Prompt for key (only for guitar and piano)
    if instrument in ["guitar", "piano"]:
        key = WebcamRecorder.prompt_key()
        print(f"\nKey: {key}")
    else:
        key = DEFAULT_KEY

    print(f"\nStarting {instrument.upper()} classifier...")

    # Create and run recorder
    recorder = WebcamRecorder(
        output_dir="output",
        instrument=instrument,
        dominant_hand=dominant_hand,
        key=key
    )
    recorder.run()


if __name__ == "__main__":
    main()
