"""
Music theory utilities for DigiJam Audio Engine.

Provides key-based chord mappings, MIDI conversions, and instrument-specific
note calculations for all 24 major/minor keys.
"""

from typing import List, Tuple, Dict

# Note names in chromatic order
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Semitone offsets from C (handles enharmonic equivalents including double flats)
NOTE_TO_SEMITONE = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'Fb': 4, 'E#': 5, 'F': 5, 'F#': 6, 'Gb': 6,
    'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10,
    'B': 11, 'Cb': 11, 'B#': 0,
    # Double flats
    'Bbb': 9, 'Ebb': 2, 'Abb': 6, 'Dbb': 0, 'Gbb': 5, 'Cbb': 10, 'Fbb': 3
}

# Notes that cross octave boundaries when used with a written octave number.
# Cb5 in music means "C5 lowered by a half step" = B4, so the real octave is one less.
# B#4 in music means "B4 raised by a half step" = C5, so the real octave is one more.
OCTAVE_BOUNDARY_ADJUSTMENT = {
    'Cb': -1,
    'Cbb': -1,
    'B#': 1,
}

# Semitone distances for pitch selection algorithm
# Distance from note to C in SAME octave (shift up)
SAME_OCTAVE_DISTANCE = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
    'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'Cb': 11,
    # Enharmonic equivalents
    'Fb': 4, 'E#': 5, 'B#': 0,
    # Double flats
    'Bbb': 9, 'Ebb': 2, 'Abb': 6, 'Dbb': 0, 'Gbb': 5, 'Cbb': 10, 'Fbb': 3
}

# Distance from note to C in NEXT octave (shift down)
# Rule: NEXT = 12 - SAME for all notes
NEXT_OCTAVE_DISTANCE = {
    'C': 12, 'C#': 11, 'Db': 11, 'D': 10, 'D#': 9, 'Eb': 9,
    'E': 8, 'F': 7, 'F#': 6, 'Gb': 6, 'G': 5, 'G#': 4,
    'Ab': 4, 'A': 3, 'A#': 2, 'Bb': 2, 'B': 1, 'Cb': 1,
    # Enharmonic equivalents
    'Fb': 8, 'E#': 7, 'B#': 12,
    # Double flats
    'Bbb': 3, 'Ebb': 10, 'Abb': 6, 'Dbb': 12, 'Gbb': 7, 'Cbb': 2, 'Fbb': 9
}

# Available keys for selection
AVAILABLE_KEYS = [
    'C Major', 'C Minor',
    'Db Major', 'Db Minor',
    'D Major', 'D Minor',
    'Eb Major', 'Eb Minor',
    'E Major', 'E Minor',
    'F Major', 'F Minor',
    'Gb Major', 'Gb Minor',
    'G Major', 'G Minor',
    'Ab Major', 'Ab Minor',
    'A Major', 'A Minor',
    'Bb Major', 'Bb Minor',
    'B Major', 'B Minor',
]

# Scale notes for each key (7 notes per scale, zones 1-7 map left to right)
# This is the authoritative source for zone-to-note mapping
KEY_SCALES: Dict[str, List[str]] = {
    'A Major': ['A', 'B', 'C#', 'D', 'E', 'F#', 'G#'],
    'A Minor': ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
    'Bb Major': ['Bb', 'C', 'D', 'Eb', 'F', 'G', 'A'],
    'Bb Minor': ['Bb', 'C', 'Db', 'Eb', 'F', 'Gb', 'Ab'],
    'B Major': ['B', 'C#', 'D#', 'E', 'F#', 'G#', 'A#'],
    'B Minor': ['B', 'C#', 'D', 'E', 'F#', 'G', 'A'],
    'C Major': ['C', 'D', 'E', 'F', 'G', 'A', 'B'],
    'C Minor': ['C', 'D', 'Eb', 'F', 'G', 'Ab', 'Bb'],
    'Db Major': ['Db', 'Eb', 'F', 'Gb', 'Ab', 'Bb', 'C'],
    'Db Minor': ['Db', 'Eb', 'Fb', 'Gb', 'Ab', 'Bbb', 'Cb'],
    'D Major': ['D', 'E', 'F#', 'G', 'A', 'B', 'C#'],
    'D Minor': ['D', 'E', 'F', 'G', 'A', 'Bb', 'C'],
    'Eb Major': ['Eb', 'F', 'G', 'Ab', 'Bb', 'C', 'D'],
    'Eb Minor': ['Eb', 'F', 'Gb', 'Ab', 'Bb', 'Cb', 'Db'],
    'E Major': ['E', 'F#', 'G#', 'A', 'B', 'C#', 'D#'],
    'E Minor': ['E', 'F#', 'G', 'A', 'B', 'C', 'D'],
    'F Major': ['F', 'G', 'A', 'Bb', 'C', 'D', 'E'],
    'F Minor': ['F', 'G', 'Ab', 'Bb', 'C', 'Db', 'Eb'],
    'Gb Major': ['Gb', 'Ab', 'Bb', 'Cb', 'Db', 'Eb', 'F'],
    'Gb Minor': ['Gb', 'Ab', 'Bbb', 'Cb', 'Db', 'Ebb', 'Fb'],
    'G Major': ['G', 'A', 'B', 'C', 'D', 'E', 'F#'],
    'G Minor': ['G', 'A', 'Bb', 'C', 'D', 'Eb', 'F'],
    'Ab Major': ['Ab', 'Bb', 'C', 'Db', 'Eb', 'F', 'G'],
    'Ab Minor': ['Ab', 'Bb', 'Cb', 'Db', 'Eb', 'Fb', 'Gb'],
}


def get_scale_for_key(key: str) -> List[str]:
    """
    Get the 7-note scale for a given key.

    Args:
        key: Musical key (e.g., 'C Major', 'A Minor')

    Returns:
        List of 7 note names in scale order
    """
    return KEY_SCALES.get(key, KEY_SCALES[DEFAULT_KEY])


def get_zone_note(zone: int, key: str) -> str:
    """
    Get the note for a specific zone (1-7) in the given key.

    Zone 1 is the leftmost position (first scale degree).
    Zone 7 is the rightmost position (seventh scale degree).

    Args:
        zone: Zone number 1-7
        key: Musical key (e.g., 'C Major', 'A Minor')

    Returns:
        Note name for that zone
    """
    scale = get_scale_for_key(key)
    # Clamp zone to valid range (1-7)
    zone_idx = max(0, min(6, zone - 1))
    return scale[zone_idx]

# Comprehensive chord mappings for all 24 keys
# Each key maps zones 1-7 to chord triads (I, ii, iii, IV, V, vi, vii°)
KEY_CHORD_MAPPINGS: Dict[str, Dict[int, List[str]]] = {
    # A Major
    'A Major': {
        1: ['A4', 'C#5', 'E5'],      # A
        2: ['B4', 'D5', 'F#5'],      # Bm
        3: ['C#5', 'E5', 'G#5'],     # C#m
        4: ['D5', 'F#5', 'A5'],      # D
        5: ['E5', 'G#5', 'B5'],      # E
        6: ['F#5', 'A5', 'C#6'],     # F#m
        7: ['G#5', 'B5', 'D6'],      # G#°
    },
    # A Minor
    'A Minor': {
        1: ['A4', 'C5', 'E5'],       # Am
        2: ['B4', 'D5', 'F5'],       # B°
        3: ['C5', 'E5', 'G5'],       # C
        4: ['D5', 'F5', 'A5'],       # Dm
        5: ['E5', 'G5', 'B5'],       # Em
        6: ['F5', 'A5', 'C6'],       # F
        7: ['G5', 'B5', 'D6'],       # G
    },
    # Bb Major
    'Bb Major': {
        1: ['Bb4', 'D5', 'F5'],      # Bb
        2: ['C5', 'Eb5', 'G5'],      # Cm
        3: ['D5', 'F5', 'A5'],       # Dm
        4: ['Eb5', 'G5', 'Bb5'],     # Eb
        5: ['F5', 'A5', 'C6'],       # F
        6: ['G5', 'Bb5', 'D6'],      # Gm
        7: ['A5', 'C6', 'Eb6'],      # A°
    },
    # Bb Minor
    'Bb Minor': {
        1: ['Bb4', 'Db5', 'F5'],     # Bbm
        2: ['C5', 'Eb5', 'Gb5'],     # C°
        3: ['Db5', 'F5', 'Ab5'],     # Db
        4: ['Eb5', 'Gb5', 'Bb5'],    # Ebm
        5: ['F5', 'Ab5', 'C6'],      # Fm
        6: ['Gb5', 'Bb5', 'Db6'],    # Gb
        7: ['Ab5', 'C6', 'Eb6'],     # Ab
    },
    # B Major
    'B Major': {
        1: ['B4', 'D#5', 'F#5'],     # B
        2: ['C#5', 'E5', 'G#5'],     # C#m
        3: ['D#5', 'F#5', 'A#5'],    # D#m
        4: ['E5', 'G#5', 'B5'],      # E
        5: ['F#5', 'A#5', 'C#6'],    # F#
        6: ['G#5', 'B5', 'D#6'],     # G#m
        7: ['A#5', 'C#6', 'E6'],     # A#°
    },
    # B Minor
    'B Minor': {
        1: ['B4', 'D5', 'F#5'],      # Bm
        2: ['C#5', 'E5', 'G5'],      # C#°
        3: ['D5', 'F#5', 'A5'],      # D
        4: ['E5', 'G5', 'B5'],       # Em
        5: ['F#5', 'A5', 'C#6'],     # F#m
        6: ['G5', 'B5', 'D6'],       # G
        7: ['A5', 'C#6', 'E6'],      # A
    },
    # C Major
    'C Major': {
        1: ['C4', 'E4', 'G4'],       # C
        2: ['D4', 'F4', 'A4'],       # Dm
        3: ['E4', 'G4', 'B4'],       # Em
        4: ['F4', 'A4', 'C5'],       # F
        5: ['G4', 'B4', 'D5'],       # G
        6: ['A4', 'C5', 'E5'],       # Am
        7: ['B4', 'D5', 'F5'],       # B°
    },
    # C Minor
    'C Minor': {
        1: ['C4', 'Eb4', 'G4'],      # Cm
        2: ['D4', 'F4', 'Ab4'],      # D°
        3: ['Eb4', 'G4', 'Bb4'],     # Eb
        4: ['F4', 'Ab4', 'C5'],      # Fm
        5: ['G4', 'Bb4', 'D5'],      # Gm
        6: ['Ab4', 'C5', 'Eb5'],     # Ab
        7: ['Bb4', 'D5', 'F5'],      # Bb
    },
    # Db Major
    'Db Major': {
        1: ['Db4', 'F4', 'Ab4'],     # Db
        2: ['Eb4', 'Gb4', 'Bb4'],    # Ebm
        3: ['F4', 'Ab4', 'C5'],      # Fm
        4: ['Gb4', 'Bb4', 'Db5'],    # Gb
        5: ['Ab4', 'C5', 'Eb5'],     # Ab
        6: ['Bb4', 'Db5', 'F5'],     # Bbm
        7: ['C5', 'Eb5', 'Gb5'],     # C°
    },
    # Db Minor (enharmonic to C# Minor)
    'Db Minor': {
        1: ['Db4', 'Fb4', 'Ab4'],     # Dbm
        2: ['Eb4', 'Gb4', 'A4'],     # Eb°
        3: ['E4', 'Ab4', 'B4'],      # E
        4: ['F#4', 'A4', 'C#5'],     # F#m
        5: ['G#4', 'B4', 'D#5'],     # G#m
        6: ['A4', 'C#5', 'E5'],      # A
        7: ['B4', 'D#5', 'F#5'],     # B
    },
    # D Major
    'D Major': {
        1: ['D4', 'F#4', 'A4'],      # D
        2: ['E4', 'G4', 'B4'],       # Em
        3: ['F#4', 'A4', 'C#5'],     # F#m
        4: ['G4', 'B4', 'D5'],       # G
        5: ['A4', 'C#5', 'E5'],      # A
        6: ['B4', 'D5', 'F#5'],      # Bm
        7: ['C#5', 'E5', 'G5'],      # C#°
    },
    # D Minor
    'D Minor': {
        1: ['D4', 'F4', 'A4'],       # Dm
        2: ['E4', 'G4', 'Bb4'],      # E°
        3: ['F4', 'A4', 'C5'],       # F
        4: ['G4', 'Bb4', 'D5'],      # Gm
        5: ['A4', 'C5', 'E5'],       # Am
        6: ['Bb4', 'D5', 'F5'],      # Bb
        7: ['C5', 'E5', 'G5'],       # C
    },
    # Eb Major
    'Eb Major': {
        1: ['Eb4', 'G4', 'Bb4'],     # Eb
        2: ['F4', 'Ab4', 'C5'],      # Fm
        3: ['G4', 'Bb4', 'D5'],      # Gm
        4: ['Ab4', 'C5', 'Eb5'],     # Ab
        5: ['Bb4', 'D5', 'F5'],      # Bb
        6: ['C5', 'Eb5', 'G5'],      # Cm
        7: ['D5', 'F5', 'Ab5'],      # D°
    },
    # Eb Minor
    'Eb Minor': {
        1: ['Eb4', 'Gb4', 'Bb4'],    # Ebm
        2: ['F4', 'Ab4', 'Cb5'],     # F°
        3: ['Gb4', 'Bb4', 'Db5'],    # Gb
        4: ['Ab4', 'Cb5', 'Eb5'],    # Abm
        5: ['Bb4', 'Db5', 'F5'],     # Bbm
        6: ['Cb5', 'Eb5', 'Gb5'],    # Cb
        7: ['Db5', 'F5', 'Ab5'],     # Db
    },
    # E Major
    'E Major': {
        1: ['E4', 'G#4', 'B4'],      # E
        2: ['F#4', 'A4', 'C#5'],     # F#m
        3: ['G#4', 'B4', 'D#5'],     # G#m
        4: ['A4', 'C#5', 'E5'],      # A
        5: ['B4', 'D#5', 'F#5'],     # B
        6: ['C#5', 'E5', 'G#5'],     # C#m
        7: ['D#5', 'F#5', 'A5'],     # D#°
    },
    # E Minor
    'E Minor': {
        1: ['E4', 'G4', 'B4'],       # Em
        2: ['F#4', 'A4', 'C5'],      # F#°
        3: ['G4', 'B4', 'D5'],       # G
        4: ['A4', 'C5', 'E5'],       # Am
        5: ['B4', 'D5', 'F#5'],      # Bm
        6: ['C5', 'E5', 'G5'],       # C
        7: ['D5', 'F#5', 'A5'],      # D
    },
    # F Major
    'F Major': {
        1: ['F4', 'A4', 'C5'],       # F
        2: ['G4', 'Bb4', 'D5'],      # Gm
        3: ['A4', 'C5', 'E5'],       # Am
        4: ['Bb4', 'D5', 'F5'],      # Bb
        5: ['C5', 'E5', 'G5'],       # C
        6: ['D5', 'F5', 'A5'],       # Dm
        7: ['E5', 'G5', 'Bb5'],      # E°
    },
    # F Minor
    'F Minor': {
        1: ['F4', 'Ab4', 'C5'],      # Fm
        2: ['G4', 'Bb4', 'Db5'],     # G°
        3: ['Ab4', 'C5', 'Eb5'],     # Ab
        4: ['Bb4', 'Db5', 'F5'],     # Bbm
        5: ['C5', 'Eb5', 'G5'],      # Cm
        6: ['Db5', 'F5', 'Ab5'],     # Db
        7: ['Eb5', 'G5', 'Bb5'],     # Eb
    },
    # Gb Major (enharmonic to F# Major)
    'Gb Major': {
        1: ['Gb4', 'Bb4', 'Db5'],    # Gb
        2: ['Ab4', 'Cb5', 'Eb5'],    # Abm
        3: ['Bb4', 'Db5', 'F5'],     # Bbm
        4: ['Cb5', 'Eb5', 'Gb5'],    # Cb
        5: ['Db5', 'F5', 'Ab5'],     # Db
        6: ['Eb5', 'Gb5', 'Bb5'],    # Ebm
        7: ['F5', 'Ab5', 'Cb6'],     # F°
    },
    # Gb Minor (enharmonic to F# Minor)
    'Gb Minor': {
        1: ['Gb4', 'A4', 'Db5'],     # Gbm
        2: ['Ab4', 'Cb5', 'D5'],     # Ab° (Ab + Cb + Ebb = Ab + Cb + D)
        3: ['A4', 'Db5', 'E5'],      # A
        4: ['B4', 'D5', 'F#5'],      # Bm
        5: ['C#5', 'E5', 'G#5'],     # C#m
        6: ['D5', 'F#5', 'A5'],      # D
        7: ['E5', 'G#5', 'B5'],      # E
    },
    # G Major
    'G Major': {
        1: ['G4', 'B4', 'D5'],       # G
        2: ['A4', 'C5', 'E5'],       # Am
        3: ['B4', 'D5', 'F#5'],      # Bm
        4: ['C5', 'E5', 'G5'],       # C
        5: ['D5', 'F#5', 'A5'],      # D
        6: ['E5', 'G5', 'B5'],       # Em
        7: ['F#5', 'A5', 'C6'],      # F#°
    },
    # G Minor
    'G Minor': {
        1: ['G4', 'Bb4', 'D5'],      # Gm
        2: ['A4', 'C5', 'Eb5'],      # A°
        3: ['Bb4', 'D5', 'F5'],      # Bb
        4: ['C5', 'Eb5', 'G5'],      # Cm
        5: ['D5', 'F5', 'A5'],       # Dm
        6: ['Eb5', 'G5', 'Bb5'],     # Eb
        7: ['F5', 'A5', 'C6'],       # F
    },
    # Ab Major
    'Ab Major': {
        1: ['Ab4', 'C5', 'Eb5'],     # Ab
        2: ['Bb4', 'Db5', 'F5'],     # Bbm
        3: ['C5', 'Eb5', 'G5'],      # Cm
        4: ['Db5', 'F5', 'Ab5'],     # Db
        5: ['Eb5', 'G5', 'Bb5'],     # Eb
        6: ['F5', 'Ab5', 'C6'],      # Fm
        7: ['G5', 'Bb5', 'Db6'],     # G°
    },
    # Ab Minor
    'Ab Minor': {
        1: ['Ab4', 'Cb5', 'Eb5'],    # Abm
        2: ['Bb4', 'Db5', 'Fb5'],    # Bb°
        3: ['Cb5', 'Eb5', 'Gb5'],    # Cb
        4: ['Db5', 'Fb5', 'Ab5'],    # Dbm
        5: ['Eb5', 'Gb5', 'Bb5'],    # Ebm
        6: ['Fb5', 'Ab5', 'Cb6'],    # Fb
        7: ['Gb5', 'Bb5', 'Db6'],    # Gb
    },
}

# Root notes for each chord zone per key (for bass and guitar)
KEY_ROOT_NOTES: Dict[str, Dict[int, str]] = {
    'A Major': {1: 'A', 2: 'B', 3: 'C#', 4: 'D', 5: 'E', 6: 'F#', 7: 'G#'},
    'A Minor': {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F', 7: 'G'},
    'Bb Major': {1: 'Bb', 2: 'C', 3: 'D', 4: 'Eb', 5: 'F', 6: 'G', 7: 'A'},
    'Bb Minor': {1: 'Bb', 2: 'C', 3: 'Db', 4: 'Eb', 5: 'F', 6: 'Gb', 7: 'Ab'},
    'B Major': {1: 'B', 2: 'C#', 3: 'D#', 4: 'E', 5: 'F#', 6: 'G#', 7: 'A#'},
    'B Minor': {1: 'B', 2: 'C#', 3: 'D', 4: 'E', 5: 'F#', 6: 'G', 7: 'A'},
    'C Major': {1: 'C', 2: 'D', 3: 'E', 4: 'F', 5: 'G', 6: 'A', 7: 'B'},
    'C Minor': {1: 'C', 2: 'D', 3: 'Eb', 4: 'F', 5: 'G', 6: 'Ab', 7: 'Bb'},
    'Db Major': {1: 'Db', 2: 'Eb', 3: 'F', 4: 'Gb', 5: 'Ab', 6: 'Bb', 7: 'C'},
    'Db Minor': {1: 'Db', 2: 'Eb', 3: 'E', 4: 'F#', 5: 'G#', 6: 'A', 7: 'B'},
    'D Major': {1: 'D', 2: 'E', 3: 'F#', 4: 'G', 5: 'A', 6: 'B', 7: 'C#'},
    'D Minor': {1: 'D', 2: 'E', 3: 'F', 4: 'G', 5: 'A', 6: 'Bb', 7: 'C'},
    'Eb Major': {1: 'Eb', 2: 'F', 3: 'G', 4: 'Ab', 5: 'Bb', 6: 'C', 7: 'D'},
    'Eb Minor': {1: 'Eb', 2: 'F', 3: 'Gb', 4: 'Ab', 5: 'Bb', 6: 'Cb', 7: 'Db'},
    'E Major': {1: 'E', 2: 'F#', 3: 'G#', 4: 'A', 5: 'B', 6: 'C#', 7: 'D#'},
    'E Minor': {1: 'E', 2: 'F#', 3: 'G', 4: 'A', 5: 'B', 6: 'C', 7: 'D'},
    'F Major': {1: 'F', 2: 'G', 3: 'A', 4: 'Bb', 5: 'C', 6: 'D', 7: 'E'},
    'F Minor': {1: 'F', 2: 'G', 3: 'Ab', 4: 'Bb', 5: 'C', 6: 'Db', 7: 'Eb'},
    'Gb Major': {1: 'Gb', 2: 'Ab', 3: 'Bb', 4: 'Cb', 5: 'Db', 6: 'Eb', 7: 'F'},
    'Gb Minor': {1: 'Gb', 2: 'Ab', 3: 'A', 4: 'B', 5: 'C#', 6: 'D', 7: 'E'},
    'G Major': {1: 'G', 2: 'A', 3: 'B', 4: 'C', 5: 'D', 6: 'E', 7: 'F#'},
    'G Minor': {1: 'G', 2: 'A', 3: 'Bb', 4: 'C', 5: 'D', 6: 'Eb', 7: 'F'},
    'Ab Major': {1: 'Ab', 2: 'Bb', 3: 'C', 4: 'Db', 5: 'Eb', 6: 'F', 7: 'G'},
    'Ab Minor': {1: 'Ab', 2: 'Bb', 3: 'Cb', 4: 'Db', 5: 'Eb', 6: 'Fb', 7: 'Gb'},
}

# Chord names for display per key
KEY_CHORD_NAMES: Dict[str, Dict[int, str]] = {
    'A Major': {1: 'A', 2: 'Bm', 3: 'C#m', 4: 'D', 5: 'E', 6: 'F#m', 7: 'G#dim'},
    'A Minor': {1: 'Am', 2: 'Bdim', 3: 'C', 4: 'Dm', 5: 'Em', 6: 'F', 7: 'G'},
    'Bb Major': {1: 'Bb', 2: 'Cm', 3: 'Dm', 4: 'Eb', 5: 'F', 6: 'Gm', 7: 'Adim'},
    'Bb Minor': {1: 'Bbm', 2: 'Cdim', 3: 'Db', 4: 'Ebm', 5: 'Fm', 6: 'Gb', 7: 'Ab'},
    'B Major': {1: 'B', 2: 'C#m', 3: 'D#m', 4: 'E', 5: 'F#', 6: 'G#m', 7: 'A#dim'},
    'B Minor': {1: 'Bm', 2: 'C#dim', 3: 'D', 4: 'Em', 5: 'F#m', 6: 'G', 7: 'A'},
    'C Major': {1: 'C', 2: 'Dm', 3: 'Em', 4: 'F', 5: 'G', 6: 'Am', 7: 'Bdim'},
    'C Minor': {1: 'Cm', 2: 'Ddim', 3: 'Eb', 4: 'Fm', 5: 'Gm', 6: 'Ab', 7: 'Bb'},
    'Db Major': {1: 'Db', 2: 'Ebm', 3: 'Fm', 4: 'Gb', 5: 'Ab', 6: 'Bbm', 7: 'Cdim'},
    'Db Minor': {1: 'Dbm', 2: 'Ebdim', 3: 'E', 4: 'F#m', 5: 'G#m', 6: 'A', 7: 'B'},
    'D Major': {1: 'D', 2: 'Em', 3: 'F#m', 4: 'G', 5: 'A', 6: 'Bm', 7: 'C#dim'},
    'D Minor': {1: 'Dm', 2: 'Edim', 3: 'F', 4: 'Gm', 5: 'Am', 6: 'Bb', 7: 'C'},
    'Eb Major': {1: 'Eb', 2: 'Fm', 3: 'Gm', 4: 'Ab', 5: 'Bb', 6: 'Cm', 7: 'Ddim'},
    'Eb Minor': {1: 'Ebm', 2: 'Fdim', 3: 'Gb', 4: 'Abm', 5: 'Bbm', 6: 'Cb', 7: 'Db'},
    'E Major': {1: 'E', 2: 'F#m', 3: 'G#m', 4: 'A', 5: 'B', 6: 'C#m', 7: 'D#dim'},
    'E Minor': {1: 'Em', 2: 'F#dim', 3: 'G', 4: 'Am', 5: 'Bm', 6: 'C', 7: 'D'},
    'F Major': {1: 'F', 2: 'Gm', 3: 'Am', 4: 'Bb', 5: 'C', 6: 'Dm', 7: 'Edim'},
    'F Minor': {1: 'Fm', 2: 'Gdim', 3: 'Ab', 4: 'Bbm', 5: 'Cm', 6: 'Db', 7: 'Eb'},
    'Gb Major': {1: 'Gb', 2: 'Abm', 3: 'Bbm', 4: 'Cb', 5: 'Db', 6: 'Ebm', 7: 'Fdim'},
    'Gb Minor': {1: 'Gbm', 2: 'Abdim', 3: 'A', 4: 'Bm', 5: 'C#m', 6: 'D', 7: 'E'},
    'G Major': {1: 'G', 2: 'Am', 3: 'Bm', 4: 'C', 5: 'D', 6: 'Em', 7: 'F#dim'},
    'G Minor': {1: 'Gm', 2: 'Adim', 3: 'Bb', 4: 'Cm', 5: 'Dm', 6: 'Eb', 7: 'F'},
    'Ab Major': {1: 'Ab', 2: 'Bbm', 3: 'Cm', 4: 'Db', 5: 'Eb', 6: 'Fm', 7: 'Gdim'},
    'Ab Minor': {1: 'Abm', 2: 'Bbdim', 3: 'Cb', 4: 'Dbm', 5: 'Ebm', 6: 'Fb', 7: 'Gb'},
}

# Default key for backward compatibility
DEFAULT_KEY = 'C Major'


def parse_note(note: str) -> Tuple[str, int]:
    """
    Parse a note string into name and octave.

    Args:
        note: Note string like 'C4', 'Ab5', 'F#3'

    Returns:
        Tuple of (note_name, octave)
    """
    if len(note) == 2:
        return note[0], int(note[1])
    elif len(note) == 3:
        return note[:2], int(note[2])
    else:
        raise ValueError(f"Invalid note format: {note}")


def note_to_midi(note: str) -> int:
    """
    Convert note name to MIDI number.

    Handles octave-boundary enharmonics:
    - Cb5 = B4 (MIDI 71), not B5
    - B#4 = C5 (MIDI 72), not C4

    Args:
        note: Note string like 'C4', 'Ab5'

    Returns:
        MIDI note number (C4 = 60)
    """
    name, octave = parse_note(note)
    semitone = NOTE_TO_SEMITONE.get(name, 0)
    octave_adj = OCTAVE_BOUNDARY_ADJUSTMENT.get(name, 0)
    return (octave + octave_adj + 1) * 12 + semitone


def midi_to_note(midi: int) -> str:
    """
    Convert MIDI number to note name.

    Args:
        midi: MIDI note number

    Returns:
        Note string like 'C4'
    """
    octave = midi // 12 - 1
    note_idx = midi % 12
    return f"{NOTE_NAMES[note_idx]}{octave}"


def chord_zone_to_notes(zone: int, key: str = DEFAULT_KEY) -> List[str]:
    """
    Convert piano chord zone (1-7) to list of note names for the given key.

    Args:
        zone: Chord zone number 1-7
        key: Musical key (e.g., 'C Major', 'A Minor')

    Returns:
        List of note names forming the chord triad
    """
    key_chords = KEY_CHORD_MAPPINGS.get(key, KEY_CHORD_MAPPINGS[DEFAULT_KEY])
    return key_chords.get(zone, key_chords[1])


def bass_zone_to_note(chord_zone: int, octave_zone: int, key: str = DEFAULT_KEY) -> str:
    """
    Convert bass hit to single root note for the given key.

    Bass plays the root note of the current chord in the specified octave.

    Args:
        chord_zone: Current chord zone (1-7) for root note
        octave_zone: Octave zone (1-7) determining octave
        key: Musical key (e.g., 'C Major', 'A Minor')

    Returns:
        Note name like 'C3', 'G4'
    """
    key_roots = KEY_ROOT_NOTES.get(key, KEY_ROOT_NOTES[DEFAULT_KEY])
    root = key_roots.get(chord_zone, key_roots[1])
    # Map octave zone to actual octave (zone 1 = octave 2, etc.)
    octave = octave_zone + 1
    return f"{root}{octave}"


def guitar_zone_to_note(zone: int, key: str = DEFAULT_KEY, octave: int = 3) -> str:
    """
    Convert guitar zone (1-7) to root note for the given key.

    Guitar plays the root note of the chord corresponding to the zone.
    Zone 1 (leftmost) = first scale degree, Zone 7 (rightmost) = seventh scale degree.

    Args:
        zone: Zone number 1-7
        key: Musical key (e.g., 'C Major', 'A Minor')
        octave: Octave for the note (default 3 for guitar range)

    Returns:
        Note name like 'C3', 'G3'
    """
    root = get_zone_note(zone, key)
    return f"{root}{octave}"


def get_chord_name(zone: int, key: str = DEFAULT_KEY) -> str:
    """
    Get the chord name for a zone in the given key.

    Args:
        zone: Chord zone number 1-7
        key: Musical key

    Returns:
        Chord name like 'C', 'Dm', 'Em'
    """
    key_names = KEY_CHORD_NAMES.get(key, KEY_CHORD_NAMES[DEFAULT_KEY])
    return key_names.get(zone, key_names[1])


def fret_to_note(fret: int) -> str:
    """
    Convert guitar fret (0-24) to note name.

    Based on standard guitar low E string tuning:
    - Fret 0 = E2 (MIDI 40)
    - Each fret = +1 semitone

    NOTE: This function is kept for backward compatibility but is now deprecated
    in favor of zone-based guitar playing via guitar_zone_to_note().

    Args:
        fret: Fret number 0-24

    Returns:
        Note name like 'E2', 'G3'
    """
    base_midi = 40  # E2
    midi_note = base_midi + fret
    return midi_to_note(midi_note)