"""
JSON loading and event parsing for DigiJam Audio Engine.

Loads session JSON files and converts them to unified AudioEvent objects.
Handles both old (ISO timestamp) and new (relative float) formats.
Supports key-based chord and note selection for piano and guitar.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from .music_theory import (
    chord_zone_to_notes,
    bass_zone_to_note,
    guitar_zone_to_note,
    fret_to_note,
    DEFAULT_KEY
)


def _parse_timestamp(timestamp_value, first_timestamp_ref: List[Optional[datetime]]) -> float:
    """
    Parse a timestamp value, handling both old (ISO string) and new (float) formats.

    For old format, tracks the first timestamp seen and returns relative time.

    Args:
        timestamp_value: Either a float (new format) or ISO string (old format)
        first_timestamp_ref: Mutable list containing first seen datetime for relative calc

    Returns:
        Timestamp in seconds (relative to session start)
    """
    if isinstance(timestamp_value, (int, float)):
        return float(timestamp_value)

    # Old format: ISO string like "2026-01-31T17:45:57.944322"
    try:
        dt = datetime.fromisoformat(timestamp_value)
        if first_timestamp_ref[0] is None:
            first_timestamp_ref[0] = dt
        # Calculate relative time from first event
        delta = dt - first_timestamp_ref[0]
        return delta.total_seconds()
    except (ValueError, TypeError):
        return 0.0


@dataclass
class AudioEvent:
    """Unified event structure for audio rendering."""
    timestamp: float          # Original timestamp (seconds from session start)
    quantized_time: float     # Quantized timestamp (seconds) - set by quantizer
    instrument: str           # 'drums', 'guitar', 'piano'
    action: str               # 'kick', 'strum', 'chord', etc.
    notes: List[str]          # List of note names to play (e.g., ['C4', 'E4', 'G4'])
    velocity: float           # 0.0 to 1.0 normalized volume
    raw_data: Dict[str, Any] = field(default_factory=dict)  # Original JSON data


def load_drums_session(filepath: str) -> Tuple[List[AudioEvent], float]:
    """
    Load drums JSON and convert to AudioEvents.

    Drums don't use notes - the action type directly maps to a sample.

    Args:
        filepath: Path to drums session JSON file

    Returns:
        Tuple of (list of AudioEvent, end_time in seconds)
    """
    with open(filepath) as f:
        data = json.load(f)

    events = []
    first_timestamp = None
    # Support both 'hits' (single-player) and 'events' (multi-player) keys
    raw_events = data.get('hits', []) or data.get('events', [])
    for hit in raw_events:
        # Handle various timestamp formats
        # Priority: raw_timestamp (unix) > timestamp (if float) > timestamp (if ISO string)
        if 'raw_timestamp' in hit:
            timestamp = float(hit['raw_timestamp'])
        else:
            timestamp = hit.get('timestamp', 0)
            if isinstance(timestamp, str):
                timestamp = 0.0
            else:
                timestamp = float(timestamp)

        # Track first timestamp for relative time calculation
        if first_timestamp is None:
            first_timestamp = timestamp
        timestamp = timestamp - first_timestamp

        # Normalize velocity (raw values range ~0.1 to 3.5)
        raw_velocity = hit.get('velocity', 0.5)
        velocity = min(1.0, raw_velocity / 3.0)

        events.append(AudioEvent(
            timestamp=timestamp,
            quantized_time=0.0,  # Set by quantizer
            instrument='drums',
            action=hit.get('action', 'kick'),
            notes=[],  # Drums use action for sample selection, not notes
            velocity=velocity,
            raw_data=hit
        ))

    # Get end_time (may be None in old format)
    end_time = data.get('end_time')
    if end_time is None and events:
        end_time = max(e.timestamp for e in events)
    elif end_time is None:
        end_time = 0.0

    return events, float(end_time)


def load_guitar_session(filepath: str, key: str = None) -> Tuple[List[AudioEvent], float]:
    """
    Load guitar JSON and convert to AudioEvents.

    Guitar zones are converted to root notes based on the key.
    Falls back to fret-based conversion for old format files.

    Args:
        filepath: Path to guitar session JSON file
        key: Musical key (overrides key from file if provided)

    Returns:
        Tuple of (list of AudioEvent, end_time in seconds)
    """
    with open(filepath) as f:
        data = json.load(f)

    # Get key from file if not provided
    session_key = key or data.get('key', DEFAULT_KEY)

    events = []
    first_timestamp = None
    # Support both 'strums' (single-player) and 'events' (multi-player) keys
    raw_events = data.get('strums', []) or data.get('events', [])
    for strum in raw_events:
        # Handle various timestamp formats
        if 'raw_timestamp' in strum:
            timestamp = float(strum['raw_timestamp'])
        else:
            timestamp = strum.get('timestamp', 0)
            if isinstance(timestamp, str):
                timestamp = 0.0
            else:
                timestamp = float(timestamp)

        # Track first timestamp for relative time calculation
        if first_timestamp is None:
            first_timestamp = timestamp
        timestamp = timestamp - first_timestamp

        # Check for zone (new format) or fret (old format)
        if 'zone' in strum:
            # New zone-based format
            zone = strum.get('zone', 1)
            note = guitar_zone_to_note(zone, session_key, octave=3)
        else:
            # Old fret-based format (backward compatibility)
            fret = strum.get('fret', 0)
            note = fret_to_note(fret)

        # Normalize intensity (raw values range ~0.5 to 2.5)
        raw_intensity = strum.get('intensity', 0.5)
        velocity = min(1.0, raw_intensity / 2.5)

        events.append(AudioEvent(
            timestamp=timestamp,
            quantized_time=0.0,
            instrument='guitar',
            action='strum',
            notes=[note],
            velocity=velocity,
            raw_data=strum
        ))

    # Get end_time
    end_time = data.get('end_time')
    if end_time is None and events:
        end_time = max(e.timestamp for e in events)
    elif end_time is None:
        end_time = 0.0

    return events, float(end_time)


def load_piano_session(filepath: str, key: str = None) -> Tuple[List[AudioEvent], float]:
    """
    Load piano JSON and convert to AudioEvents.

    Piano chord zones are converted to note triads based on the key.
    Bass zones are converted to root notes.

    Args:
        filepath: Path to piano session JSON file
        key: Musical key (overrides key from file if provided)

    Returns:
        Tuple of (list of AudioEvent, end_time in seconds)
    """
    with open(filepath) as f:
        data = json.load(f)

    # Get key from file if not provided
    session_key = key or data.get('key', DEFAULT_KEY)

    events = []
    first_timestamp = None
    # Support both 'hits' (single-player) and 'events' (multi-player) keys
    raw_events = data.get('hits', []) or data.get('events', [])
    for hit in raw_events:
        # Handle various timestamp formats
        if 'raw_timestamp' in hit:
            timestamp = float(hit['raw_timestamp'])
        else:
            timestamp = hit.get('timestamp', 0)
            if isinstance(timestamp, str):
                timestamp = 0.0
            else:
                timestamp = float(timestamp)

        # Track first timestamp for relative time calculation
        if first_timestamp is None:
            first_timestamp = timestamp
        timestamp = timestamp - first_timestamp

        action = hit.get('action', 'chord')
        chord_zone = hit.get('chord', 1)
        octave_zone = hit.get('octave', 4)

        # Convert to notes based on action type and key
        if action == 'chord':
            notes = chord_zone_to_notes(chord_zone, session_key)
        else:  # bass
            notes = [bass_zone_to_note(chord_zone, octave_zone, session_key)]

        # Normalize intensity (raw values range ~0.1 to 5.0)
        raw_intensity = hit.get('intensity', 0.5)
        velocity = min(1.0, raw_intensity / 2.0)

        events.append(AudioEvent(
            timestamp=timestamp,
            quantized_time=0.0,
            instrument='piano',
            action=action,
            notes=notes,
            velocity=velocity,
            raw_data=hit
        ))

    # Get end_time
    end_time = data.get('end_time')
    if end_time is None and events:
        end_time = max(e.timestamp for e in events)
    elif end_time is None:
        end_time = 0.0

    return events, float(end_time)
