"""
Strum detection for guitar using velocity analysis of wrist world landmarks.
Uses zone-based detection (7 zones) for chord root note selection.
"""
from dataclasses import dataclass, field
from collections import deque
from typing import Optional, Dict, Tuple
from datetime import datetime
import time


@dataclass
class StrumEvent:
    """Represents a detected guitar strum."""
    timestamp: str  # ISO-8601 format
    player_id: int
    instrument: str = "guitar"
    action: str = "strum"
    zone: int = 1  # Current zone (1-7) at strum time - determines root note
    intensity: float = 0.0  # Strum velocity for volume control
    raw_timestamp: float = 0.0  # Raw time.time() value for relative timestamp calculation

    def to_dict(self, start_time: float = None) -> dict:
        """Convert to dictionary for JSON serialization.

        Args:
            start_time: If provided, timestamp will be relative to this value (in seconds)
        """
        if start_time is not None and self.raw_timestamp > 0:
            timestamp_value = round(self.raw_timestamp - start_time, 4)
        else:
            timestamp_value = self.timestamp

        return {
            "timestamp": timestamp_value,
            "player_id": self.player_id,
            "instrument": self.instrument,
            "action": self.action,
            "zone": self.zone,
            "intensity": round(self.intensity, 4)
        }


@dataclass
class HandHistory:
    """Tracks hand position history for velocity calculation."""
    positions_y: deque = field(default_factory=lambda: deque(maxlen=10))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=10))
    last_strum_time: float = 0.0
    was_moving_down: bool = False
    peak_downward_velocity: float = 0.0


class StrumDetector:
    """
    Detects guitar strums based on velocity analysis and tracks zone position.

    Algorithm:
    1. Auto-calibrate zone boundaries on first frame (like piano)
    2. Track strum hand y-position over time (world coordinates in meters)
    3. Calculate velocity = delta_y / delta_time
    4. Detect strum when: downward velocity > threshold AND displacement > threshold
    5. Calculate zone (1-7) from fret hand x-position relative to calibrated boundaries

    Zone Calculation:
    - The fret hand x-range is divided into 7 equal zones
    - Zone 1 is at the leftmost position, Zone 7 at rightmost
    - Each zone corresponds to a chord root note in the selected key
    """

    # Detection parameters
    STRUM_VELOCITY_THRESHOLD = 0.15  # Minimum downward velocity (m/s) for strum
    STRUM_DISPLACEMENT_THRESHOLD = 0.10  # Minimum displacement from resting (meters)
    DEBOUNCE_TIME = 0.15  # Minimum seconds between strums
    MIN_REVERSAL_VELOCITY = -0.05  # Minimum upward velocity to confirm reversal

    # Zone parameters
    NUM_ZONES = 7  # Number of zones (matching 7 diatonic chords)

    def __init__(self, dominant_hand: str = "right"):
        """
        Initialize strum detector with dexterity setting.

        Args:
            dominant_hand: "right" or "left" - the strumming hand
        """
        self.dominant_hand = dominant_hand
        self.strum_hand = dominant_hand
        self.fret_hand = "left" if dominant_hand == "right" else "right"

        # Calibration state (zone boundaries)
        self.is_calibrated = False
        self.left_boundary: Optional[float] = None   # Leftmost x position (zone 1)
        self.right_boundary: Optional[float] = None  # Rightmost x position (zone 7)
        self.strum_resting_y: Optional[float] = None  # Strum hand resting y position

        # Track history per player
        # Key: (player_id, hand) -> HandHistory
        self.hand_histories: Dict[Tuple[int, str], HandHistory] = {}

        # Current state
        self.current_zone: int = 1

    def _get_history(self, player_id: int, hand: str) -> HandHistory:
        """Get or create hand history for player/hand combination."""
        key = (player_id, hand)
        if key not in self.hand_histories:
            self.hand_histories[key] = HandHistory()
        return self.hand_histories[key]

    def _calculate_velocity(self, history: HandHistory) -> Optional[float]:
        """Calculate y-velocity from recent positions."""
        if len(history.positions_y) < 2:
            return None

        y_current = history.positions_y[-1]
        y_previous = history.positions_y[-2]
        t_current = history.timestamps[-1]
        t_previous = history.timestamps[-2]

        dt = t_current - t_previous
        if dt <= 0:
            return None

        return (y_current - y_previous) / dt

    def calibrate(self, left_x: float, right_x: float, strum_hand_y: float = None):
        """
        Set zone boundaries for guitar neck.

        Args:
            left_x: X-coordinate of leftmost position (zone 1)
            right_x: X-coordinate of rightmost position (zone 7)
            strum_hand_y: Y-coordinate of strum hand (becomes resting position)
        """
        # Ensure left is actually less than right
        if left_x > right_x:
            left_x, right_x = right_x, left_x

        self.left_boundary = left_x
        self.right_boundary = right_x
        if strum_hand_y is not None:
            self.strum_resting_y = strum_hand_y
        self.is_calibrated = True
        print(f"Guitar calibrated: left={left_x:.3f}m, right={right_x:.3f}m")

    def reset_calibration(self):
        """Clear calibration to recalibrate on next frame."""
        self.is_calibrated = False
        self.left_boundary = None
        self.right_boundary = None
        self.strum_resting_y = None
        self.current_zone = 1
        # Clear histories to start fresh
        self.hand_histories.clear()
        print("Guitar calibration reset - show both hands to recalibrate")

    def get_current_zone(self, fret_hand_x: float) -> int:
        """
        Calculate zone number (1-7) from hand position.

        Args:
            fret_hand_x: Current x-coordinate of fret hand

        Returns:
            Zone number (1 to 7)
        """
        if not self.is_calibrated or self.left_boundary is None or self.right_boundary is None:
            return 1

        total_width = self.right_boundary - self.left_boundary
        if total_width <= 0:
            return 1

        # Calculate position as percentage across the range
        position = fret_hand_x - self.left_boundary
        percentage = position / total_width

        # Map to zone 1-7
        zone = int(percentage * self.NUM_ZONES) + 1
        # Clamp to valid range
        return max(1, min(self.NUM_ZONES, zone))

    def update(
        self,
        player_id: int,
        strum_hand_x: float,
        strum_hand_y: float,
        strum_hand_z: float,
        fret_hand_x: float,
        fret_hand_y: float,
        fret_hand_z: float,
        current_time: float = None
    ) -> Optional[StrumEvent]:
        """
        Update hand positions and detect strums.

        Auto-calibrates on first call with valid data.

        Args:
            player_id: Unique identifier for the person
            strum_hand_x, strum_hand_y, strum_hand_z: Strum hand world coordinates (meters)
            fret_hand_x, fret_hand_y, fret_hand_z: Fret hand world coordinates (meters)
            current_time: Timestamp (defaults to time.time())

        Returns:
            StrumEvent if a strum was detected, None otherwise
        """
        if current_time is None:
            current_time = time.time()

        # Auto-calibrate if needed
        if not self.is_calibrated:
            # Use both hand positions to establish boundaries
            # The fret hand typically moves along the x-axis
            self.calibrate(fret_hand_x - 0.15, fret_hand_x + 0.15, strum_hand_y)
            return None

        # Update current zone
        self.current_zone = self.get_current_zone(fret_hand_x)

        # Get history for strum hand
        history = self._get_history(player_id, self.strum_hand)

        # Get previous velocity before adding new position
        prev_velocity = self._calculate_velocity(history)

        # Add new position
        history.positions_y.append(strum_hand_y)
        history.timestamps.append(current_time)

        # Get current velocity
        curr_velocity = self._calculate_velocity(history)

        if prev_velocity is None or curr_velocity is None:
            return None

        # Calculate displacement from resting position
        displacement = strum_hand_y - self.strum_resting_y if self.strum_resting_y else 0

        # Track if we're moving downward fast enough
        if prev_velocity > self.STRUM_VELOCITY_THRESHOLD:
            history.was_moving_down = True
            # Track peak velocity for strum intensity
            if prev_velocity > history.peak_downward_velocity:
                history.peak_downward_velocity = prev_velocity

        # Detect strum: was moving down fast, now moving up (reversal)
        # AND displacement threshold met
        if (history.was_moving_down and
                curr_velocity < self.MIN_REVERSAL_VELOCITY and
                displacement > self.STRUM_DISPLACEMENT_THRESHOLD):

            # Capture peak velocity for intensity
            strum_intensity = history.peak_downward_velocity

            # Reset state
            history.was_moving_down = False
            history.peak_downward_velocity = 0.0

            # Check debounce
            if current_time - history.last_strum_time < self.DEBOUNCE_TIME:
                return None

            # Record strum
            history.last_strum_time = current_time

            return StrumEvent(
                timestamp=datetime.now().isoformat(),
                player_id=player_id,
                zone=self.current_zone,
                intensity=strum_intensity,
                raw_timestamp=current_time
            )

        return None

    def reset_player(self, player_id: int):
        """Clear history for a player (when they leave frame)."""
        keys_to_remove = [k for k in self.hand_histories if k[0] == player_id]
        for key in keys_to_remove:
            del self.hand_histories[key]

    def reset_all(self):
        """Clear all history and calibration."""
        self.hand_histories.clear()
        self.reset_calibration()
