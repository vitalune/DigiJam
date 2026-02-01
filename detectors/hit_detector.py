"""
Hit detection using velocity analysis of wrist/foot world landmarks.
Uses body-relative zone classification based on shoulder and hip positions.
"""
from dataclasses import dataclass, field
from collections import deque
from typing import Optional, Tuple, Dict
from datetime import datetime
import time


@dataclass
class HitEvent:
    """Represents a detected drum hit."""
    timestamp: str  # ISO-8601 format
    player_id: int
    hand: str  # "left", "right", "left_foot", "right_foot"
    instrument: str  # "drums"
    action: str  # "hi-hat", "snare", "crash", "kick"
    world_coords_meters: Dict[str, float]  # {"x": float, "y": float, "z": float}
    velocity: float  # Hit velocity in m/s (for volume control)
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
            "hand": self.hand,
            "instrument": self.instrument,
            "action": self.action,
            "world_coords_meters": self.world_coords_meters,
            "velocity": round(self.velocity, 4)
        }


@dataclass
class LimbHistory:
    """Tracks limb position history for velocity calculation."""
    positions_y: deque = field(default_factory=lambda: deque(maxlen=10))
    positions_x: deque = field(default_factory=lambda: deque(maxlen=10))
    positions_z: deque = field(default_factory=lambda: deque(maxlen=10))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=10))
    last_hit_time: float = 0.0
    was_moving_down: bool = False
    peak_downward_velocity: float = 0.0  # Track peak velocity for hit intensity


class HitDetector:
    """
    Detects drum hits based on velocity analysis and body-relative zones.

    Algorithm:
    1. Track wrist/foot y-position over time (world coordinates in meters)
    2. Calculate velocity = delta_y / delta_time
    3. Detect velocity sign change: positive (downward) -> negative (upward)
    4. Apply debouncing (minimum time between hits)
    5. Classify action based on body-relative thresholds

    Body-Relative Classification:
    - Hi-Hat: Dominant hand above shoulders
    - Crash: Non-dominant hand above shoulders
    - Snare: Non-dominant hand between shoulder and hip, near center
    - Kick: Foot downward motion after lift
    """

    # Detection parameters - tuned for easier triggering
    VELOCITY_THRESHOLD = 0.15      # Minimum downward velocity (m/s) before hit
    DEBOUNCE_TIME = 0.10           # Minimum seconds between hits
    MIN_REVERSAL_VELOCITY = -0.03  # Minimum upward velocity to confirm reversal
    SNARE_CENTER_THRESHOLD = 0.40  # Max x-distance from center for snare (meters)

    # Kick detection parameters - requires explicit foot motion
    KICK_VELOCITY_THRESHOLD = 0.20  # Threshold for foot motion (higher = more explicit)
    KICK_DEBOUNCE_TIME = 0.15       # Debounce for kicks

    def __init__(self, dominant_hand: str = "right"):
        """
        Initialize hit detector with dexterity setting.

        Args:
            dominant_hand: "right" or "left" - the player's dominant hand
        """
        self.dominant_hand = dominant_hand
        self.hat_hand = dominant_hand  # Hi-hat played with dominant hand
        self.snare_hand = "left" if dominant_hand == "right" else "right"

        # Track history per player per limb
        # Key: (player_id, limb) -> LimbHistory
        # limb can be: "left", "right", "left_foot", "right_foot"
        self.limb_histories: Dict[Tuple[int, str], LimbHistory] = {}

    def _get_history(self, player_id: int, limb: str) -> LimbHistory:
        """Get or create limb history for player/limb combination."""
        key = (player_id, limb)
        if key not in self.limb_histories:
            self.limb_histories[key] = LimbHistory()
        return self.limb_histories[key]

    def _calculate_velocity(self, history: LimbHistory) -> Optional[float]:
        """Calculate y-velocity from recent positions."""
        if len(history.positions_y) < 2:
            return None

        # Use last two positions for velocity
        y_current = history.positions_y[-1]
        y_previous = history.positions_y[-2]
        t_current = history.timestamps[-1]
        t_previous = history.timestamps[-2]

        dt = t_current - t_previous
        if dt <= 0:
            return None

        return (y_current - y_previous) / dt

    def classify_action_relative(
        self,
        hand: str,
        wrist_y_normalized: float,
        body_refs: Dict,
        world_x: float
    ) -> Optional[str]:
        """
        Classify action using body-relative thresholds.

        Args:
            hand: "left" or "right"
            wrist_y_normalized: Wrist y-coordinate from pose_landmarks (0-1)
            body_refs: Dict with "nose_y", "shoulder_y", "hip_y" (normalized)
            world_x: Wrist x-coordinate in meters (for center detection)

        Returns:
            Action string ("hi-hat", "crash", "snare") or None
        """
        if wrist_y_normalized is None or body_refs is None:
            return None

        shoulder_y = body_refs["shoulder_y"]
        hip_y = body_refs["hip_y"]

        # Above shoulders = hi-hat (dominant) or crash (non-dominant)
        # Using shoulders instead of nose for easier triggering
        if wrist_y_normalized < shoulder_y:
            if hand == self.hat_hand:
                return "hi-hat"
            else:
                return "crash"

        # Between shoulder and hip = snare (non-dominant only)
        if hand == self.snare_hand:
            if shoulder_y <= wrist_y_normalized <= hip_y:
                # Check if near center (x close to 0)
                if abs(world_x) < self.SNARE_CENTER_THRESHOLD:
                    return "snare"

        return None

    def get_current_zone(
        self,
        hand: str,
        wrist_y_normalized: float,
        body_refs: Dict,
        world_x: float
    ) -> Optional[str]:
        """Get the current zone for display purposes (without requiring a hit)."""
        return self.classify_action_relative(hand, wrist_y_normalized, body_refs, world_x)

    def update(
        self,
        player_id: int,
        hand: str,  # "left" or "right"
        world_x: float,
        world_y: float,
        world_z: float,
        wrist_y_normalized: float,
        body_refs: Dict,
        current_time: float = None
    ) -> Optional[HitEvent]:
        """
        Update wrist position and detect hits.

        Args:
            player_id: Unique identifier for the person
            hand: "left" or "right"
            world_x, world_y, world_z: World coordinates in meters
            wrist_y_normalized: Normalized y-coordinate for body-relative comparison
            body_refs: Dict with body reference points
            current_time: Timestamp (defaults to time.time())

        Returns:
            HitEvent if a hit was detected, None otherwise
        """
        if current_time is None:
            current_time = time.time()

        history = self._get_history(player_id, hand)

        # Get previous velocity before adding new position
        prev_velocity = self._calculate_velocity(history)

        # Add new position
        history.positions_y.append(world_y)
        history.positions_x.append(world_x)
        history.positions_z.append(world_z)
        history.timestamps.append(current_time)

        # Get current velocity
        curr_velocity = self._calculate_velocity(history)

        if prev_velocity is None or curr_velocity is None:
            return None

        # Track if we're moving downward fast enough
        if prev_velocity > self.VELOCITY_THRESHOLD:
            history.was_moving_down = True
            # Track peak velocity for hit intensity
            if prev_velocity > history.peak_downward_velocity:
                history.peak_downward_velocity = prev_velocity

        # Detect hit: was moving down fast, now moving up
        # In world coords: positive velocity = down, negative = up
        if (history.was_moving_down and
                curr_velocity < self.MIN_REVERSAL_VELOCITY):

            # Capture the peak velocity before resetting
            hit_velocity = history.peak_downward_velocity

            history.was_moving_down = False
            history.peak_downward_velocity = 0.0

            # Check debounce
            if current_time - history.last_hit_time < self.DEBOUNCE_TIME:
                return None

            # Classify which drum was hit using body-relative zones
            action = self.classify_action_relative(
                hand, wrist_y_normalized, body_refs, world_x
            )
            if action is None:
                return None  # Not in any valid drum zone

            # Record hit
            history.last_hit_time = current_time

            return HitEvent(
                timestamp=datetime.now().isoformat(),
                player_id=player_id,
                hand=hand,
                instrument="drums",
                action=action,
                world_coords_meters={
                    "x": round(world_x, 4),
                    "y": round(world_y, 4),
                    "z": round(world_z, 4)
                },
                velocity=hit_velocity,
                raw_timestamp=current_time
            )

        return None

    def update_foot(
        self,
        player_id: int,
        foot: str,  # "left_foot" or "right_foot"
        world_x: float,
        world_y: float,
        world_z: float,
        current_time: float = None
    ) -> Optional[HitEvent]:
        """
        Update foot position and detect kick hits.

        Kick detection: Foot moving downward (positive y velocity) after lift.

        Args:
            player_id: Unique identifier for the person
            foot: "left_foot" or "right_foot"
            world_x, world_y, world_z: World coordinates in meters
            current_time: Timestamp (defaults to time.time())

        Returns:
            HitEvent if a kick was detected, None otherwise
        """
        if current_time is None:
            current_time = time.time()

        history = self._get_history(player_id, foot)

        # Get previous velocity before adding new position
        prev_velocity = self._calculate_velocity(history)

        # Add new position
        history.positions_y.append(world_y)
        history.positions_x.append(world_x)
        history.positions_z.append(world_z)
        history.timestamps.append(current_time)

        # Get current velocity
        curr_velocity = self._calculate_velocity(history)

        if prev_velocity is None or curr_velocity is None:
            return None

        # For kick: detect when foot was lifted (negative velocity = up)
        # and now stomping down (positive velocity = down)
        if prev_velocity < -self.KICK_VELOCITY_THRESHOLD:
            history.was_moving_down = False  # Mark as lifted
            history.peak_downward_velocity = 0.0

        # Track peak downward velocity during stomp
        if curr_velocity > self.KICK_VELOCITY_THRESHOLD:
            if curr_velocity > history.peak_downward_velocity:
                history.peak_downward_velocity = curr_velocity

        # Detect kick: was lifted, now moving down fast
        if (not history.was_moving_down and
                curr_velocity > self.KICK_VELOCITY_THRESHOLD):

            # Capture velocity for this kick
            hit_velocity = curr_velocity

            history.was_moving_down = True

            # Check debounce
            if current_time - history.last_hit_time < self.KICK_DEBOUNCE_TIME:
                return None

            # Record kick
            history.last_hit_time = current_time

            return HitEvent(
                timestamp=datetime.now().isoformat(),
                player_id=player_id,
                hand=foot,
                instrument="drums",
                action="kick",
                world_coords_meters={
                    "x": round(world_x, 4),
                    "y": round(world_y, 4),
                    "z": round(world_z, 4)
                },
                velocity=hit_velocity,
                raw_timestamp=current_time
            )

        return None

    def reset_player(self, player_id: int):
        """Clear history for a player (when they leave frame)."""
        keys_to_remove = [k for k in self.limb_histories if k[0] == player_id]
        for key in keys_to_remove:
            del self.limb_histories[key]

    def reset_all(self):
        """Clear all history."""
        self.limb_histories.clear()
