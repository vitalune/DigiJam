"""
Piano detection using zone-based chord tracking and upward velocity hit detection.
Includes auto-calibration for piano length based on hand spread.
"""
from dataclasses import dataclass, field
from collections import deque
from typing import Optional, Dict, Tuple, List
from datetime import datetime
import time


@dataclass
class PianoEvent:
    """Represents a detected piano hit."""
    timestamp: str           # ISO-8601
    player_id: int
    instrument: str = "piano"
    hand: str = "right"      # "right" for chord, "left" for bass
    action: str = "chord"    # "chord" or "bass"
    chord: int = 1           # Chord number 1-7 (right hand zone)
    octave: int = 1          # Octave for bass (left hand zone determines this)
    intensity: float = 0.0   # Hit velocity for volume
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
            "hand": self.hand,
            "action": self.action,
            "chord": self.chord,
            "octave": self.octave,
            "intensity": round(self.intensity, 4)
        }


@dataclass
class HandHistory:
    """Tracks hand position history for velocity calculation."""
    positions_y: deque = field(default_factory=lambda: deque(maxlen=10))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=10))
    last_hit_time: float = 0.0
    was_moving_up: bool = False
    peak_upward_velocity: float = 0.0


class PianoDetector:
    """
    Detects piano hits based on upward velocity and tracks chord/octave zones.

    Calibration:
    - Left hand x at calibration = zone 1 (for left hand bass)
    - Right hand x at calibration = zone 7 (for right hand chord)
    - Piano divided into 7 equal zones

    Zone Calculation:
    - Left hand (bass): starts at zone 1, increases as x decreases (moves left/outward)
    - Right hand (chord): starts at zone 7, decreases as x increases (moves right/outward)

    Octave Logic (Left Hand):
    - Zone 1 -> Octave 1 & 2
    - Zone 2 -> Octave 2 & 3
    - etc.

    Hit Detection:
    - Negative y-velocity (upward motion) triggers hit
    - Left hand hit ignored if in same zone as right hand
    """

    # Detection parameters
    HIT_VELOCITY_THRESHOLD = 0.15   # Minimum upward velocity (m/s) for hit
    DEBOUNCE_TIME = 0.12            # Minimum seconds between hits per hand
    MIN_REVERSAL_VELOCITY = 0.05    # Minimum downward velocity to confirm reversal

    # Zone parameters
    NUM_ZONES = 7
    MIN_PIANO_LENGTH = 0.1          # Minimum 10cm piano

    def __init__(self, auto_calibrate: bool = True):
        """
        Initialize piano detector.

        Args:
            auto_calibrate: If True, calibrate on first frame. If False, require manual calibration.
        """
        # Calibration state
        self.auto_calibrate = auto_calibrate
        self.is_calibrated = False
        self.left_origin: float = 0.0       # Left hand x at calibration (zone 1 for bass)
        self.right_origin: float = 0.0      # Right hand x at calibration (zone 7 for chord)
        self.piano_length: float = 0.0      # Distance from left to right hand

        # Track history per player per hand
        self.hand_histories: Dict[Tuple[int, str], HandHistory] = {}

        # Current state
        self.current_right_zone: int = 7    # 1-7 (starts at 7)
        self.current_left_zone: int = 1     # 1-7 (starts at 1)

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

    def calibrate(self, left_hand_x: float, right_hand_x: float):
        """
        Calibrate piano dimensions.

        Args:
            left_hand_x: Left hand x-coordinate (becomes zone 1 origin for bass)
            right_hand_x: Right hand x-coordinate (becomes zone 7 origin for chord)
        """
        self.left_origin = left_hand_x
        self.right_origin = right_hand_x
        self.piano_length = abs(right_hand_x - left_hand_x)

        if self.piano_length < self.MIN_PIANO_LENGTH:
            print("Warning: Piano too short, please spread hands wider")
            return

        self.is_calibrated = True
        print(f"Piano calibrated:")
        print(f"  Left origin (zone 1): {left_hand_x:.3f}m")
        print(f"  Right origin (zone 7): {right_hand_x:.3f}m")
        print(f"  Piano length: {self.piano_length:.3f}m")
        print(f"  Zone width: {self.piano_length / self.NUM_ZONES:.3f}m")

    def reset_calibration(self):
        """Clear calibration to recalibrate on next frame."""
        self.is_calibrated = False
        self.left_origin = 0.0
        self.right_origin = 0.0
        self.piano_length = 0.0
        self.current_right_zone = 7  # Reset to default zone 7
        self.current_left_zone = 1   # Reset to default zone 1
        self.hand_histories.clear()
        print("Piano calibration reset - show both hands spread apart to recalibrate")

    def get_left_zone(self, left_hand_x: float) -> int:
        """
        Calculate zone (1-7) for left hand (bass).

        Left hand starts at zone 1 at calibration position.
        As x decreases (moves left), zone increases toward 7.

        Args:
            left_hand_x: Left hand x-coordinate in meters

        Returns:
            Zone number 1-7
        """
        if not self.is_calibrated or self.piano_length <= 0:
            return 1

        # Calculate displacement from left_origin (positive = moved left)
        displacement = self.left_origin - left_hand_x

        # Clamp to valid range [0, piano_length]
        displacement = max(0.0, min(displacement, self.piano_length))

        # Calculate fraction (0.0 to 1.0) and map to zones 1-7
        # Add small epsilon to avoid floating point issues at boundaries
        fraction = displacement / self.piano_length
        zone = int(fraction * self.NUM_ZONES + 0.0001) + 1

        # Clamp to 1-7
        return max(1, min(zone, self.NUM_ZONES))

    def get_right_zone(self, right_hand_x: float) -> int:
        """
        Calculate zone (1-7) for right hand (chord).

        Right hand starts at zone 7 at calibration position.
        As x increases (moves right), zone decreases toward 1.

        Args:
            right_hand_x: Right hand x-coordinate in meters

        Returns:
            Zone number 1-7
        """
        if not self.is_calibrated or self.piano_length <= 0:
            return 7

        # Calculate displacement from right_origin (positive = moved right)
        displacement = right_hand_x - self.right_origin

        # Clamp to valid range [0, piano_length]
        displacement = max(0.0, min(displacement, self.piano_length))

        # Calculate fraction (0.0 to 1.0) and map to zones 7-1
        # Add small epsilon to avoid floating point issues at boundaries
        fraction = displacement / self.piano_length
        zone = self.NUM_ZONES - int(fraction * self.NUM_ZONES + 0.0001)

        # Clamp to 1-7
        return max(1, min(zone, self.NUM_ZONES))

    def get_octave_from_zone(self, zone: int) -> int:
        """
        Get base octave from zone number.

        Zone 1 -> octave 1 (plays octave 1 & 2)
        Zone 2 -> octave 2 (plays octave 2 & 3)
        etc.

        Args:
            zone: Zone number 1-7

        Returns:
            Base octave number
        """
        return zone

    def update(
        self,
        player_id: int,
        left_hand_x: float,
        left_hand_y: float,
        left_hand_z: float,
        right_hand_x: float,
        right_hand_y: float,
        right_hand_z: float,
        current_time: float = None
    ) -> List[PianoEvent]:
        """
        Update hand positions and detect piano hits.

        Auto-calibrates on first call with valid data.
        Hit triggers on upward motion (negative y-velocity).

        Args:
            player_id: Unique identifier for the person
            left_hand_x/y/z: Left hand world coordinates (meters)
            right_hand_x/y/z: Right hand world coordinates (meters)
            current_time: Timestamp (defaults to time.time())

        Returns:
            List of PianoEvent objects (may include both chord and bass hits)
        """
        if current_time is None:
            current_time = time.time()

        events = []

        # Auto-calibrate if enabled and needed
        if not self.is_calibrated:
            if self.auto_calibrate:
                self.calibrate(left_hand_x, right_hand_x)
            return events

        # Update current zones using hand-specific calculations
        self.current_right_zone = self.get_right_zone(right_hand_x)
        self.current_left_zone = self.get_left_zone(left_hand_x)

        # Check for right hand (chord) hit
        right_hit = self._check_hit(
            player_id=player_id,
            hand="right",
            hand_y=right_hand_y,
            current_time=current_time
        )

        if right_hit:
            events.append(PianoEvent(
                timestamp=datetime.now().isoformat(),
                player_id=player_id,
                hand="right",
                action="chord",
                chord=self.current_right_zone,
                octave=0,  # Not applicable for chord
                intensity=right_hit,
                raw_timestamp=current_time
            ))

        # Check for left hand (bass) hit
        # Only if left hand is NOT in same zone as right hand
        if self.current_left_zone != self.current_right_zone:
            left_hit = self._check_hit(
                player_id=player_id,
                hand="left",
                hand_y=left_hand_y,
                current_time=current_time
            )

            if left_hit:
                events.append(PianoEvent(
                    timestamp=datetime.now().isoformat(),
                    player_id=player_id,
                    hand="left",
                    action="bass",
                    chord=self.current_right_zone,  # Root note of current chord
                    octave=self.get_octave_from_zone(self.current_left_zone),
                    intensity=left_hit,
                    raw_timestamp=current_time
                ))

        return events

    def _check_hit(
        self,
        player_id: int,
        hand: str,
        hand_y: float,
        current_time: float
    ) -> Optional[float]:
        """
        Check if a hit occurred for given hand.

        Hit detection: Upward motion (negative y-velocity) followed by reversal.

        Args:
            player_id: Player identifier
            hand: "left" or "right"
            hand_y: Hand y-coordinate in meters
            current_time: Current timestamp

        Returns:
            Hit intensity (velocity) if hit detected, None otherwise
        """
        history = self._get_history(player_id, hand)

        # Get previous velocity before adding new position
        prev_velocity = self._calculate_velocity(history)

        # Add new position
        history.positions_y.append(hand_y)
        history.timestamps.append(current_time)

        # Get current velocity
        curr_velocity = self._calculate_velocity(history)

        if prev_velocity is None or curr_velocity is None:
            return None

        # Track if we're moving upward fast enough (negative velocity = up)
        if prev_velocity < -self.HIT_VELOCITY_THRESHOLD:
            history.was_moving_up = True
            # Track peak velocity for hit intensity
            if prev_velocity < history.peak_upward_velocity:
                history.peak_upward_velocity = prev_velocity

        # Detect hit: was moving up fast, now moving down (reversal)
        if (history.was_moving_up and
                curr_velocity > self.MIN_REVERSAL_VELOCITY):

            # Capture peak velocity for intensity
            hit_intensity = abs(history.peak_upward_velocity)

            # Reset state
            history.was_moving_up = False
            history.peak_upward_velocity = 0.0

            # Check debounce
            if current_time - history.last_hit_time < self.DEBOUNCE_TIME:
                return None

            # Record hit
            history.last_hit_time = current_time

            return hit_intensity

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
