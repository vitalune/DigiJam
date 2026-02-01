"""
Strum detection for guitar using velocity analysis of wrist world landmarks.
Includes auto-calibration for fret position tracking.
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
    fret: int = 0  # Current fret at strum time
    intensity: float = 0.0  # Strum velocity for volume control

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "player_id": self.player_id,
            "instrument": self.instrument,
            "action": self.action,
            "fret": self.fret,
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
    Detects guitar strums based on velocity analysis and tracks fret position.

    Algorithm:
    1. Auto-calibrate fret origin and strum resting position on first frame
    2. Track strum hand y-position over time (world coordinates in meters)
    3. Calculate velocity = delta_y / delta_time
    4. Detect strum when: downward velocity > threshold AND displacement > threshold
    5. Calculate fret from fret hand x-position relative to calibrated origin

    Fret Calculation:
    - Every 5cm (0.05m) of movement from origin = +1 fret
    - current_fret = round(abs(fret_hand_x - fret_origin) / 0.05)
    """

    # Detection parameters
    STRUM_VELOCITY_THRESHOLD = 0.2  # Minimum downward velocity (m/s) for strum
    STRUM_DISPLACEMENT_THRESHOLD = 0.15  # Minimum displacement from resting (meters)
    DEBOUNCE_TIME = 0.15  # Minimum seconds between strums
    MIN_REVERSAL_VELOCITY = -0.05  # Minimum upward velocity to confirm reversal

    # Fret parameters
    FRET_SIZE = 0.05  # 5cm per fret
    MAX_FRETS = 24  # Maximum fret number

    def __init__(self, dominant_hand: str = "right"):
        """
        Initialize strum detector with dexterity setting.

        Args:
            dominant_hand: "right" or "left" - the strumming hand
        """
        self.dominant_hand = dominant_hand
        self.strum_hand = dominant_hand
        self.fret_hand = "left" if dominant_hand == "right" else "right"

        # Calibration state
        self.is_calibrated = False
        self.fret_origin: Optional[float] = None  # Fret hand x at "Fret 0"
        self.strum_resting_y: Optional[float] = None  # Strum hand resting y position

        # Track history per player
        # Key: (player_id, hand) -> HandHistory
        self.hand_histories: Dict[Tuple[int, str], HandHistory] = {}

        # Current state
        self.current_fret: int = 0

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

    def calibrate(self, fret_hand_x: float, strum_hand_y: float):
        """
        Set fret origin and strum resting position.

        Args:
            fret_hand_x: X-coordinate of fret hand (becomes Fret 0)
            strum_hand_y: Y-coordinate of strum hand (becomes resting position)
        """
        self.fret_origin = fret_hand_x
        self.strum_resting_y = strum_hand_y
        self.is_calibrated = True
        print(f"Guitar calibrated: fret_origin={fret_hand_x:.3f}m, strum_resting={strum_hand_y:.3f}m")

    def reset_calibration(self):
        """Clear calibration to recalibrate on next frame."""
        self.is_calibrated = False
        self.fret_origin = None
        self.strum_resting_y = None
        self.current_fret = 0
        # Clear histories to start fresh
        self.hand_histories.clear()
        print("Guitar calibration reset - show both hands to recalibrate")

    def get_current_fret(self, fret_hand_x: float) -> int:
        """
        Calculate fret number from hand position.

        Args:
            fret_hand_x: Current x-coordinate of fret hand

        Returns:
            Fret number (0 to MAX_FRETS)
        """
        if not self.is_calibrated or self.fret_origin is None:
            return 0

        delta_x = abs(fret_hand_x - self.fret_origin)
        fret = round(delta_x / self.FRET_SIZE)
        return min(fret, self.MAX_FRETS)

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
            self.calibrate(fret_hand_x, strum_hand_y)
            return None

        # Update current fret
        self.current_fret = self.get_current_fret(fret_hand_x)

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
        displacement = strum_hand_y - self.strum_resting_y

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
                fret=self.current_fret,
                intensity=strum_intensity
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
