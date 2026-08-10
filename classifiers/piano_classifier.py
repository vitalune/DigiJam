"""
Piano action classifier combining multi-person tracking and zone-based detection.
Uses manual calibration (3-second countdown) for piano length and upward velocity for hit detection.
Supports all 24 major/minor keys.
"""
import cv2
import json
from datetime import datetime
from typing import List, Optional, Callable
import time
import sys
from pathlib import Path

# Add parent directory for audio imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multi_person_tracker import MultiPersonTracker, PersonPose
from detectors.piano_detector import PianoDetector, PianoEvent
from audio.music_theory import KEY_CHORD_NAMES, DEFAULT_KEY
import mp_drawing_compat


class PianoClassifier:
    """
    Real-time piano action classification from video/webcam.

    Combines:
    - Multi-person pose tracking
    - World landmark extraction (meters)
    - Zone-based chord and octave tracking
    - Upward velocity-based hit detection
    - Key-based chord selection (all 24 major/minor keys)

    Actions:
    - Chord (right hand): Zone 1-7 determines chord number in the selected key
    - Bass (left hand): Plays root note octave based on zone
    """

    def __init__(
        self,
        key: str = DEFAULT_KEY,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        max_persons: int = 4,
        on_hit_callback: Optional[Callable[[PianoEvent], None]] = None,
        tracker: Optional[MultiPersonTracker] = None,
        auto_calibrate: bool = False
    ):
        """
        Initialize piano classifier.

        Args:
            key: Musical key (e.g., 'C Major', 'A Minor')
            model_complexity: Pose model complexity (0=lite, 1=full, 2=heavy)
            min_detection_confidence: Minimum confidence for pose detection
            min_tracking_confidence: Minimum confidence for tracking
            max_persons: Maximum number of people to track
            on_hit_callback: Optional callback when piano hit is detected
            tracker: Optional external tracker (for multi-player sessions)
            auto_calibrate: If True, auto-calibrate on first frame (for multi-player)
        """
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

        # Auto-calibrate for multi-player, manual calibration for single-player
        self.piano_detector = PianoDetector(auto_calibrate=auto_calibrate)
        self.on_hit_callback = on_hit_callback

        # Store last known hand positions for calibration
        self._last_left_wrist: Optional[dict] = None
        self._last_right_wrist: Optional[dict] = None

        # Drawing utilities (compat layer)
        self.mp_drawing_compat = mp_drawing_compat

        # Track recent hits for display
        self.recent_hits: dict = {}  # player_id -> hit info
        self.hit_display_frames = 20  # How long to show hit indicator
        self.hit_frame_counts: dict = {}  # player_id -> frames remaining

        # Hit log
        self.hit_log: List[PianoEvent] = []

        # Timing for relative timestamps
        self.start_time: Optional[float] = None  # Raw timestamp of first hit
        self.end_time: Optional[float] = None    # Raw timestamp of last hit

        # Last processed persons (for drawing without reprocessing)
        self._last_persons: List[PersonPose] = []

    def get_chord_name(self, zone: int) -> str:
        """Get chord name for current zone and key."""
        key_names = KEY_CHORD_NAMES.get(self.key, KEY_CHORD_NAMES[DEFAULT_KEY])
        return key_names.get(zone, key_names.get(1, "?"))

    @property
    def is_calibrated(self) -> bool:
        """Check if piano is calibrated."""
        return self.piano_detector.is_calibrated

    @property
    def current_chord(self) -> int:
        """Get current chord number (1-7) based on right hand zone."""
        return self.piano_detector.current_right_zone

    @property
    def current_octave(self) -> int:
        """Get current octave based on left hand zone."""
        return self.piano_detector.get_octave_from_zone(
            self.piano_detector.current_left_zone
        )

    def process_frame(self, frame, current_time: float = None) -> List[PianoEvent]:
        """
        Process a single frame and detect piano hits.

        Args:
            frame: BGR image from OpenCV
            current_time: Timestamp for hit detection

        Returns:
            List of PianoEvent objects detected in this frame
        """
        if current_time is None:
            current_time = time.time()

        hits_this_frame = []

        # Get poses for all people
        persons = self.tracker.process_frame(frame)
        self._last_persons = persons

        for person in persons:
            player_id = person.player_id

            # Get wrist world coordinates
            left_wrist, right_wrist = self.tracker.get_wrist_world_coords(person)

            # Store last known positions for calibration
            if left_wrist:
                self._last_left_wrist = left_wrist
            if right_wrist:
                self._last_right_wrist = right_wrist

            # Need both hands for piano
            if not left_wrist or not right_wrist:
                continue

            # Update piano detector
            events = self.piano_detector.update(
                player_id=player_id,
                left_hand_x=left_wrist["x"],
                left_hand_y=left_wrist["y"],
                left_hand_z=left_wrist["z"],
                right_hand_x=right_wrist["x"],
                right_hand_y=right_wrist["y"],
                right_hand_z=right_wrist["z"],
                current_time=current_time
            )

            for event in events:
                hits_this_frame.append(event)
                self._record_hit(event)

        # Decay hit display counters
        self._decay_hit_display()

        return hits_this_frame

    def _record_hit(self, hit: PianoEvent):
        """Record a hit and trigger callback."""
        self.hit_log.append(hit)
        self.recent_hits[hit.player_id] = {
            "action": hit.action,
            "hand": hit.hand,
            "chord": hit.chord,
            "octave": hit.octave
        }
        self.hit_frame_counts[hit.player_id] = self.hit_display_frames

        # Track start_time and end_time for relative timestamps
        if self.start_time is None:
            self.start_time = hit.raw_timestamp
        self.end_time = hit.raw_timestamp

        if self.on_hit_callback:
            self.on_hit_callback(hit)

        # Print to console as JSON
        print(json.dumps(hit.to_dict()))

    def _decay_hit_display(self):
        """Reduce hit display counters."""
        for player_id in list(self.hit_frame_counts.keys()):
            self.hit_frame_counts[player_id] -= 1
            if self.hit_frame_counts[player_id] <= 0:
                del self.hit_frame_counts[player_id]
                if player_id in self.recent_hits:
                    del self.recent_hits[player_id]

    def draw_overlay(self, frame, persons: List[PersonPose] = None):
        """
        Draw skeleton, calibration status, and zone indicators on frame.

        Args:
            frame: BGR image to draw on (modified in place)
            persons: List of PersonPose (if None, uses last processed)
        """
        if persons is None:
            persons = self._last_persons

        h, w = frame.shape[:2]

        # Draw calibration status or current state
        if not self.piano_detector.is_calibrated:
            cv2.putText(
                frame,
                "CALIBRATING - Spread hands apart",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )
        else:
            # Show current chord and key
            chord_name = self.get_chord_name(self.current_chord)
            cv2.putText(
                frame,
                f"Chord: {chord_name} (Zone {self.current_chord})",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            # Show key
            cv2.putText(
                frame,
                f"Key: {self.key}",
                (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1
            )

            # Show left hand zone/octave status
            left_zone = self.piano_detector.current_left_zone
            right_zone = self.piano_detector.current_right_zone

            if left_zone == right_zone:
                bass_text = f"Bass: Zone {left_zone} (IGNORED - same as chord)"
                bass_color = (128, 128, 128)
            else:
                bass_text = f"Bass: Zone {left_zone} -> Octave {left_zone}&{left_zone+1}"
                bass_color = (0, 200, 200)

            cv2.putText(
                frame,
                bass_text,
                (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                bass_color,
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

                # Add recent hit info
                if player_id in self.recent_hits:
                    hit_info = self.recent_hits[player_id]
                    if hit_info["action"] == "chord":
                        chord_name = self.get_chord_name(hit_info["chord"])
                        label += f": {chord_name} CHORD"
                    else:
                        label += f": BASS (Oct {hit_info['octave']})"

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

                # Determine text color based on recent hit
                text_color = (255, 255, 255)  # Default white
                if player_id in self.recent_hits:
                    text_color = (0, 255, 0)  # Green for recent hit

                cv2.putText(
                    frame,
                    label,
                    (label_x, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    text_color,
                    2
                )

        # Draw zone indicator at bottom
        self._draw_zone_indicator(frame, w, h)

    def _draw_zone_indicator(self, frame, w: int, h: int):
        """Draw visual zone indicator above guitar zones (for multi-player)."""
        if not self.piano_detector.is_calibrated:
            return

        # Draw 7 zones as colored boxes (positioned above guitar zones)
        zone_width = w // 7
        y_start = h - 80
        y_end = h - 50

        for i in range(7):
            x_start = i * zone_width
            x_end = (i + 1) * zone_width

            # Highlight current zones
            is_right_zone = (i + 1) == self.piano_detector.current_right_zone
            is_left_zone = (i + 1) == self.piano_detector.current_left_zone

            if is_right_zone and is_left_zone:
                color = (0, 165, 255)  # Orange for overlap (left hand ignored)
            elif is_right_zone:
                color = (0, 255, 0)    # Green for right hand (chord)
            elif is_left_zone:
                color = (255, 255, 0)  # Cyan for left hand (bass)
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
        """Reset calibration (user pressed 'p')."""
        self.piano_detector.reset_calibration()
        self._last_left_wrist = None
        self._last_right_wrist = None

    def get_current_hand_positions(self) -> Optional[tuple]:
        """
        Get the last known hand positions for manual calibration.

        Returns:
            Tuple of (left_x, right_x) or None if positions not available
        """
        if self._last_left_wrist and self._last_right_wrist:
            return (self._last_left_wrist["x"], self._last_right_wrist["x"])
        return None

    def calibrate_now(self) -> bool:
        """
        Manually trigger calibration with current hand positions.

        Returns:
            True if calibration succeeded, False if hand positions not available
        """
        positions = self.get_current_hand_positions()
        if positions:
            left_x, right_x = positions
            self.piano_detector.calibrate(left_x, right_x)
            return self.piano_detector.is_calibrated
        return False

    def save_hit_log(self, output_path: str):
        """Save all detected hits to JSON file with relative timestamps."""
        # Calculate end_time relative to start_time
        relative_end_time = None
        if self.start_time is not None and self.end_time is not None:
            relative_end_time = round(self.end_time - self.start_time, 4)

        data = {
            "session_timestamp": datetime.now().isoformat(),
            "instrument": "piano",
            "key": self.key,
            "total_hits": len(self.hit_log),
            "end_time": relative_end_time,
            "hits": [hit.to_dict(start_time=self.start_time) for hit in self.hit_log]
        }
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(self.hit_log)} piano hits to {output_path}")

    def clear_hit_log(self):
        """Clear the hit log and reset timing."""
        self.hit_log.clear()
        self.start_time = None
        self.end_time = None
        print("Piano hit log cleared")

    def process_poses(self, persons: List[PersonPose], current_time: float = None) -> List[PianoEvent]:
        """
        Process pre-detected poses (for multi-player mode with shared tracker).

        Args:
            persons: List of PersonPose objects from shared tracker
            current_time: Timestamp for hit detection

        Returns:
            List of PianoEvent objects detected
        """
        if current_time is None:
            current_time = time.time()

        self._last_persons = persons
        hits_this_frame = []

        for person in persons:
            player_id = person.player_id

            # Get wrist world coordinates
            left_wrist, right_wrist = self.tracker.get_wrist_world_coords(person)

            # Store last known positions for calibration
            if left_wrist:
                self._last_left_wrist = left_wrist
            if right_wrist:
                self._last_right_wrist = right_wrist

            # Need both hands for piano
            if not left_wrist or not right_wrist:
                continue

            # Update piano detector
            events = self.piano_detector.update(
                player_id=player_id,
                left_hand_x=left_wrist["x"],
                left_hand_y=left_wrist["y"],
                left_hand_z=left_wrist["z"],
                right_hand_x=right_wrist["x"],
                right_hand_y=right_wrist["y"],
                right_hand_z=right_wrist["z"],
                current_time=current_time
            )

            for event in events:
                hits_this_frame.append(event)
                self._record_hit(event)

        # Decay hit display counters
        self._decay_hit_display()

        return hits_this_frame

    def close(self):
        """Release resources."""
        if self._owns_tracker:
            self.tracker.close()
