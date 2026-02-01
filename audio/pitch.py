"""
Pitch shifting and sample selection for DigiJam Audio Engine.

Implements the closest-sample selection algorithm and resampling-based
pitch shifting.
"""

import numpy as np
from scipy.signal import resample
from typing import Tuple, List

from .music_theory import (
    parse_note,
    note_to_midi,
    SAME_OCTAVE_DISTANCE,
    NEXT_OCTAVE_DISTANCE
)


def find_closest_sample(target_note: str, available_octaves: List[int]) -> Tuple[str, int]:
    """
    Find the closest C sample and calculate semitone shift.

    Algorithm (per specification):
    - For target note in octave O with note name N:
      - Distance to C in same octave O: SAME_OCTAVE_DISTANCE[N]
      - Distance to C in next octave O+1: NEXT_OCTAVE_DISTANCE[N]
    - Pick whichever is closer; ties go to same octave (earlier value)
    - Return the sample note and shift amount

    Args:
        target_note: Note name like 'Ab4', 'C5', 'F#3'
        available_octaves: List of octaves where C samples exist
                          (e.g., [3,4,5,6] for guitar, [2,3,4,5,6,7,8] for piano)

    Returns:
        Tuple of (sample_note, semitone_shift) where:
        - sample_note: The C sample to use (e.g., 'C4')
        - semitone_shift: Positive = pitch up, negative = pitch down
    """
    note_name, octave = parse_note(target_note)

    # Get distances to C in same octave and next octave
    if note_name not in SAME_OCTAVE_DISTANCE:
        raise ValueError(f"Unknown note name '{note_name}' — not found in SAME_OCTAVE_DISTANCE")
    dist_same = SAME_OCTAVE_DISTANCE[note_name]
    dist_next = NEXT_OCTAVE_DISTANCE[note_name]

    best_sample = None
    best_shift = None
    min_distance = float('inf')

    # Check C in same octave (shift UP from C)
    if octave in available_octaves:
        if dist_same < min_distance or (dist_same == min_distance and best_sample is None):
            best_sample = f"C{octave}"
            best_shift = dist_same  # Positive = pitch up from C
            min_distance = dist_same

    # Check C in next octave (shift DOWN from C)
    if (octave + 1) in available_octaves:
        if dist_next < min_distance:  # Strict less than for tie-breaking
            best_sample = f"C{octave + 1}"
            best_shift = -dist_next  # Negative = pitch down from C
            min_distance = dist_next

    # Fallback: find closest available sample if exact octaves not available
    if best_sample is None:
        target_midi = note_to_midi(target_note)
        for avail_oct in sorted(available_octaves):
            sample_midi = note_to_midi(f"C{avail_oct}")
            shift = target_midi - sample_midi
            if abs(shift) < min_distance:
                best_sample = f"C{avail_oct}"
                best_shift = shift
                min_distance = abs(shift)

    # Final fallback
    if best_sample is None and available_octaves:
        best_sample = f"C{available_octaves[0]}"
        best_shift = 0

    return best_sample, best_shift


def pitch_shift(audio: np.ndarray, semitones: int, sample_rate: int) -> np.ndarray:
    """
    Pitch shift audio by resampling.

    This uses simple resampling which changes both pitch and duration.
    For short percussive/plucked samples, this is acceptable.

    Algorithm:
    - To shift up N semitones: resample to shorter length (higher pitch)
    - To shift down N semitones: resample to longer length (lower pitch)
    - Ratio = 2^(semitones/12)

    Args:
        audio: Audio samples as numpy array (float32)
        semitones: Number of semitones to shift (positive = up, negative = down)
        sample_rate: Original sample rate (used for reference, not modified)

    Returns:
        Pitch-shifted audio at modified length
    """
    if semitones == 0:
        return audio.copy()

    # Calculate pitch ratio
    # Shifting up means higher frequency = shorter wavelength = fewer samples
    ratio = 2 ** (semitones / 12.0)

    # New length after pitch shift
    # Higher pitch (ratio > 1) = shorter audio
    # Lower pitch (ratio < 1) = longer audio
    new_length = int(len(audio) * ratio)

    if new_length <= 0:
        return np.zeros(1, dtype=audio.dtype)

    # Resample to new length
    shifted = resample(audio, new_length)

    return shifted.astype(audio.dtype)