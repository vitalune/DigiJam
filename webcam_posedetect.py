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
"""
from webcam_recorder import WebcamRecorder


def main():
    """Main entry point with instrument and dexterity selection."""
    # Prompt for instrument selection
    instrument = WebcamRecorder.prompt_instrument()
    print(f"\nSelected: {instrument.upper()}")

    # Prompt for dexterity selection
    dominant_hand = WebcamRecorder.prompt_dexterity()
    print(f"\nDominant hand: {dominant_hand.upper()}")

    print(f"\nStarting {instrument.upper()} classifier...")

    # Create and run recorder
    recorder = WebcamRecorder(
        output_dir="output",
        instrument=instrument,
        dominant_hand=dominant_hand
    )
    recorder.run()


if __name__ == "__main__":
    main()
