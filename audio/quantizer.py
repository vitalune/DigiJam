"""
Time grid quantization for DigiJam Audio Engine.

Implements grid building and binary search snapping for musical timing.
"""

import bisect
from dataclasses import dataclass
from typing import List


@dataclass
class QuantizationGrid:
    """Defines a time grid for quantization."""
    name: str
    interval: float  # Seconds between grid points
    grid_points: List[float]  # Pre-computed grid times


def build_grid(bpm: float, duration: float, subdivision: str) -> QuantizationGrid:
    """
    Build a time grid based on BPM and subdivision.

    Grid construction (per specification):
    - Set step based on subdivision
    - Create array where grid[i] = i * step
    - Continue while i * step <= duration

    Args:
        bpm: Beats per minute
        duration: Total duration in seconds (use end_time from JSON)
        subdivision: '16th', 'quarter', or 'half'

    Returns:
        QuantizationGrid with pre-computed grid points
    """
    beat_duration = 60.0 / bpm

    if subdivision == '16th':
        step = beat_duration / 4  # (60/BPM) / 4
    elif subdivision == 'half':
        step = beat_duration * 2  # (60/BPM) * 2
    else:  # quarter (default)
        step = beat_duration  # 60/BPM

    # Build grid points from 0 to duration
    # Per spec: while i * step <= duration
    points = []
    i = 0
    while i * step <= duration:
        points.append(round(i * step, 6))  # Round to avoid float precision issues
        i += 1

    return QuantizationGrid(name=subdivision, interval=step, grid_points=points)


def snap_to_grid(timestamp: float, grid: QuantizationGrid) -> float:
    """
    Snap a timestamp to the nearest grid point using binary search.

    Algorithm (per specification):
    - If t <= first grid point, return first
    - If t >= last grid point, return last
    - Binary search to find first index j where grid[j] >= t
    - Compare grid[j] with grid[j-1]
    - Return whichever is closer; ties go to earlier (left) value

    Args:
        timestamp: Event timestamp in seconds
        grid: QuantizationGrid to snap to

    Returns:
        Quantized timestamp (nearest grid point)
    """
    points = grid.grid_points

    if not points:
        return timestamp

    # Edge cases
    if timestamp <= points[0]:
        return points[0]
    if timestamp >= points[-1]:
        return points[-1]

    # Binary search for insertion point
    # bisect_left returns first index where points[idx] >= timestamp
    idx = bisect.bisect_left(points, timestamp)

    # Compare distances to left and right points
    left = points[idx - 1]
    right = points[idx]

    dist_left = timestamp - left
    dist_right = right - timestamp

    # Ties go to earlier value (left)
    if dist_left <= dist_right:
        return left
    return right


# Grid assignment rules by instrument/action
GRID_RULES = {
    'drums': {
        'hi-hat': '16th',   # 16th notes
        'kick': 'quarter',   # Quarter notes
        'snare': 'quarter',  # Quarter notes
        'crash': 'quarter',  # Quarter notes
    },
    'guitar': {
        'strum': 'quarter',  # Quarter notes
    },
    'piano': {
        'chord': 'half',     # Half notes
        'bass': 'half',      # Half notes
    },
}


def get_grid_for_event(instrument: str, action: str) -> str:
    """
    Get the subdivision type for a given instrument/action.

    Args:
        instrument: 'drums', 'guitar', or 'piano'
        action: Action type (e.g., 'hi-hat', 'strum', 'chord')

    Returns:
        Subdivision string: '16th', 'quarter', or 'half'
    """
    instrument_rules = GRID_RULES.get(instrument, {})
    return instrument_rules.get(action, 'quarter')  # Default to quarter notes
