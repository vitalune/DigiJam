"""
Guitar action classifier combining multi-person tracking and strum detection.
Uses zone-based detection (7 zones) for chord root note selection.
"""
import cv2
import json
import os
from datetime import datetime
from typing import List, Optional, Callable
import time
import sys
from pathlib import Path

# Add parent directory for audio imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multi_person_tracker import MultiPersonTracker, PersonPose
from detectors.strum_detector import StrumDetector, StrumEvent
from audio.music_theory import KEY_CHORD_NAMES, DEFAULT_KEY, get_zone_note
import mp_drawing_compat


class GuitarClassifier:
    """
    Real-time guitar action classification from video/webcam.

    Combines:
    - Multi-person pose tracking
    - World landmark extraction (meters)
    - Velocity-based strum detection
    - Zone-based chord root note tracking (7 zones)

    Actions:
    - Strum: Dominant hand downward motion with sufficient velocity and displacement
    - Zone tracking: Non-dominant hand x-position determines which chord root to play
    """

    def __init__(
        self,
        dominant_hand: str = "right",
        key: str = DEFAULT_KEY,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        max_persons: int = 4,
        on_strum_callback: Optional[Callable[[StrumEvent], None]] = None,
        tracker: Optional[MultiPersonTracker] = None
    ):
        """
        Initialize guitar classifier.

        Args:
            dominant_hand: "right" or "left" - the strumming hand
            key: Musical key (e.g., 'C Major', 'A Minor')
            model_complexity: Pose model complexity (0=lite, 1=full, 2=heavy)
            min_detection_confidence: Minimum confidence for pose detection
            min_tracking_confidence: Minimum confidence for tracking
            max_persons: Maximum number of people to track
            on_strum_callback: Optional callback when strum is detected
            tracker: Optional external tracker (for multi-player sessions)
        """
        self.dominant_hand = dominant_hand
        self.key = key

        # Use external tracker if provided, else create own
        if tracker is not None:
            self.tracker = tracker
            self._owns_tracker = False
        else:
            self.tracker = MultiPersonTracker(
                model_complexity=model_complexity,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                max_persons=max_persons
            )
            self._owns_tracker = True

        self.strum_detector = StrumDetector(dominant_hand=dominant_hand)
        self.on_strum_callback = on_strum_callback

        # Drawing utilities (compat layer)
        self.mp_drawing_compat = mp_drawing_compat

        # Track recent strums for display
        self.recent_strums: dict = {}  # player_id -> {"zone": int, "intensity": float}
        self.strum_display_frames = 20  # How long to show strum indicator
        self.strum_frame_counts: dict = {}  # player_id -> frames remaining

        # Strum log
        self.strum_log: List[StrumEvent] = []

        # Timing for relative timestamps
        self.start_time: Optional[float] = None  # Raw timestamp of first strum
        self.end_time: Optional[float] = None    # Raw timestamp of last strum

        # Last processed persons (for drawing without reprocessing)
        self._last_persons: List[PersonPose] = []

    def get_chord_name(self, zone: int) -> str:
        """Get chord name for current zone and key."""
        key_names = KEY_CHORD_NAMES.get(self.key, KEY_CHORD_NAMES[DEFAULT_KEY])
        return key_names.get(zone, key_names[1])

    def get_root_note(self, zone: int) -> str:
        """Get root note for current zone and key.

        Zone 1 (leftmost) maps to the first scale degree.
        Zone 7 (rightmost) maps to the seventh scale degree.
        """
        return get_zone_note(zone, self.key)

    def process_frame(self, frame, current_time: float = None) -> List[StrumEvent]:
        """
        Process a single frame and detect guitar strums.

        Args:
            frame: BGR image from OpenCV
            current_time: Timestamp for strum detection

        Returns:
            List of StrumEvent objects detected in this frame
        """
        if current_time is None:
            current_time = time.time()

        strums_this_frame = []

        # Get poses for all people
        persons = self.tracker.process_frame(frame)
        self._last_persons = persons

        for person in persons:
            player_id = person.player_id

            # Get wrist world coordinates
            left_wrist, right_wrist = self.tracker.get_wrist_world_coords(person)

            # Need both hands for guitar tracking
            if not left_wrist or not right_wrist:
                continue

            # Determine which is strum/fret based on dexterity
            if self.dominant_hand == "right":
                strum_wrist = right_wrist
                fret_wrist = left_wrist
            else:
                strum_wrist = left_wrist
                fret_wrist = right_wrist

            # Update strum detector
            strum = self.strum_detector.update(
                player_id=player_id,
                strum_hand_x=strum_wrist["x"],
                strum_hand_y=strum_wrist["y"],
                strum_hand_z=strum_wrist["z"],
                fret_hand_x=fret_wrist["x"],
                fret_hand_y=fret_wrist["y"],
                fret_hand_z=fret_wrist["z"],
                current_time=current_time
            )

            if strum:
                strums_this_frame.append(strum)
                self._record_strum(strum)

        # Decay strum display counters
        self._decay_strum_display()

        return strums_this_frame

    def _record_strum(self, strum: StrumEvent):
        """Record a strum and trigger callback."""
        self.strum_log.append(strum)
        self.recent_strums[strum.player_id] = {
            "zone": strum.zone,
            "intensity": strum.intensity
        }
        self.strum_frame_counts[strum.player_id] = self.strum_display_frames

        # Track start_time and end_time for relative timestamps
        if self.start_time is None:
            self.start_time = strum.raw_timestamp
        self.end_time = strum.raw_timestamp

        if self.on_strum_callback:
            self.on_strum_callback(strum)

        # Print to console as JSON
        print(json.dumps(strum.to_dict()))

    def _decay_strum_display(self):
        """Reduce strum display counters."""
        for player_id in list(self.strum_frame_counts.keys()):
            self.strum_frame_counts[player_id] -= 1
            if self.strum_frame_counts[player_id] <= 0:
                del self.strum_frame_counts[player_id]
                if player_id in self.recent_strums:
                    del self.recent_strums[player_id]

    def draw_overlay(self, frame, persons: List[PersonPose] = None):
        """
        Draw skeleton, calibration status, and zone indicator on frame.

        Args:
            frame: BGR image to draw on (modified in place)
            persons: List of PersonPose (if None, uses last processed)
        """
        if persons is None:
            persons = self._last_persons

        h, w = frame.shape[:2]

        # Draw calibration status at top
        if not self.strum_detector.is_calibrated:
            cv2.putText(
                frame,
                "CALIBRATING - Show both hands",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )
        else:
            # Show current zone and chord name
            zone = self.strum_detector.current_zone
            chord_name = self.get_chord_name(zone)
            root_note = self.get_root_note(zone)
            cv2.putText(
                frame,
                f"Zone {zone}: {chord_name} (Root: {root_note})",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )
            # Show key
            cv2.putText(
                frame,
                f"Key: {self.key}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 200),
                1
            )

        for person in persons:
            player_id = person.player_id

            # Draw skeleton
            if person.pose_landmarks:
                self.mp_drawing_compat.draw_pose_landmarks(frame, person.pose_landmarks)

                # Get nose position for label
                nose = person.pose_landmarks.landmark[0]
                label_x = int(nose.x * w)
                label_y = int(nose.y * h) - 40

                # Build label text
                label = f"Player {player_id}"

                # Add recent strum info if available
                if player_id in self.recent_strums:
                    strum_info = self.recent_strums[player_id]
                    zone = strum_info['zone']
                    chord_name = self.get_chord_name(zone)
                    label += f": STRUM ({chord_name})"

                # Draw label with background
                (text_w, text_h), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2
                )

                # Clamp to screen bounds
                label_x = max(5, min(label_x, w - text_w - 10))
                label_y = max(text_h + 10, label_y)

                # Background rectangle
                cv2.rectangle(
                    frame,
                    (label_x - 5, label_y - text_h - 5),
                    (label_x + text_w + 5, label_y + 5),
                    (0, 0, 0),
                    -1
                )

                # Determine text color based on recent strum
                text_color = (255, 255, 255)  # Default white
                if player_id in self.recent_strums:
                    text_color = (0, 255, 0)  # Green for recent strum

                cv2.putText(
                    frame,
                    label,
                    (label_x, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    text_color,
                    2
                )

        # Draw dexterity and hand assignment indicator
        self._draw_hand_indicator(frame, w, h)

        # Draw zone indicator at bottom
        self._draw_zone_indicator(frame, w, h)

    def _draw_hand_indicator(self, frame, w: int, h: int):
        """Draw hand assignment indicator in corner."""
        strum_hand = self.dominant_hand.capitalize()
        fret_hand = "Left" if self.dominant_hand == "right" else "Right"
        text = f"Strum: {strum_hand} | Zone: {fret_hand}"
        cv2.putText(
            frame,
            text,
            (w - 250, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1
        )

    def _draw_zone_indicator(self, frame, w: int, h: int):
        """Draw visual zone indicator at bottom of screen."""
        if not self.strum_detector.is_calibrated:
            return

        # Draw 7 zones as colored boxes
        zone_width = w // 7
        y_start = h - 40
        y_end = h - 10

        for i in range(7):
            x_start = i * zone_width
            x_end = (i + 1) * zone_width

            # Highlight current zone
            is_current = (i + 1) == self.strum_detector.current_zone

            if is_current:
                color = (0, 255, 0)    # Green for current zone
            else:
                color = (50, 50, 50)   # Dark gray

            cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), color, -1)
            cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), (200, 200, 200), 1)

            # Zone number and chord name
            chord_name = self.get_chord_name(i + 1)
            cv2.putText(
                frame,
                f"{i + 1}",
                (x_start + zone_width // 2 - 5, y_start + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1
            )
            cv2.putText(
                frame,
                chord_name,
                (x_start + zone_width // 2 - 15, y_start + 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (180, 180, 180),
                1
            )

    def reset_calibration(self):
        """Reset calibration (user pressed 'g')."""
        self.strum_detector.reset_calibration()

    def save_strum_log(self, output_path: str):
        """Save all detected strums to JSON file with relative timestamps."""
        # Calculate end_time relative to start_time
        relative_end_time = None
        if self.start_time is not None and self.end_time is not None:
            relative_end_time = round(self.end_time - self.start_time, 4)

        data = {
            "session_timestamp": datetime.now().isoformat(),
            "instrument": "guitar",
            "dominant_hand": self.dominant_hand,
            "key": self.key,
            "total_strums": len(self.strum_log),
            "end_time": relative_end_time,
            "strums": [strum.to_dict(start_time=self.start_time) for strum in self.strum_log]
        }
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(self.strum_log)} strums to {output_path}")

    def clear_strum_log(self):
        """Clear the strum log and reset timing."""
        self.strum_log.clear()
        self.start_time = None
        self.end_time = None
        print("Strum log cleared")

    def process_poses(self, persons: List[PersonPose], current_time: float = None) -> List[StrumEvent]:
        """
        Process pre-detected poses (for multi-player mode with shared tracker).

        Args:
            persons: List of PersonPose objects from shared tracker
            current_time: Timestamp for strum detection

        Returns:
            List of StrumEvent objects detected
        """
        if current_time is None:
            current_time = time.time()

        self._last_persons = persons
        strums_this_frame = []

        for person in persons:
            player_id = person.player_id

            # Get wrist world coordinates
            left_wrist, right_wrist = self.tracker.get_wrist_world_coords(person)

            # Need both hands for guitar tracking
            if not left_wrist or not right_wrist:
                continue

            # Determine which is strum/fret based on dexterity
            if self.dominant_hand == "right":
                strum_wrist = right_wrist
                fret_wrist = left_wrist
            else:
                strum_wrist = left_wrist
                fret_wrist = right_wrist

            # Update strum detector
            strum = self.strum_detector.update(
                player_id=player_id,
                strum_hand_x=strum_wrist["x"],
                strum_hand_y=strum_wrist["y"],
                strum_hand_z=strum_wrist["z"],
                fret_hand_x=fret_wrist["x"],
                fret_hand_y=fret_wrist["y"],
                fret_hand_z=fret_wrist["z"],
                current_time=current_time
            )

            if strum:
                strums_this_frame.append(strum)
                self._record_strum(strum)

        # Decay strum display counters
        self._decay_strum_display()

        return strums_this_frame

    def close(self):
        """Release resources."""
        if self._owns_tracker:
            self.tracker.close()
