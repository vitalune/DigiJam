"""
Drum action classifier combining multi-person tracking and hit detection.
Uses body-relative zone classification for reliable action detection.
"""
import cv2
import json
import os
from datetime import datetime
from typing import List, Optional, Callable
import time

from multi_person_tracker import MultiPersonTracker, PersonPose
from detectors.hit_detector import HitDetector, HitEvent
import mp_drawing_compat


class DrumClassifier:
    """
    Real-time drum action classification from video/webcam.

    Combines:
    - Multi-person pose tracking
    - World landmark extraction (meters)
    - Velocity-based hit detection
    - Body-relative zone classification

    Actions (body-relative):
    - Hi-Hat: Dominant hand above nose
    - Crash: Non-dominant hand above nose
    - Snare: Non-dominant hand between shoulder and hip, near center
    - Kick: Foot downward motion after lift
    """

    def __init__(
        self,
        dominant_hand: str = "right",
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        max_persons: int = 4,
        on_hit_callback: Optional[Callable[[HitEvent], None]] = None,
        tracker: Optional[MultiPersonTracker] = None
    ):
        """
        Initialize drum classifier.

        Args:
            dominant_hand: "right" or "left" - player's dominant hand
            model_complexity: Pose model complexity (0=lite, 1=full, 2=heavy)
            min_detection_confidence: Minimum confidence for pose detection
            min_tracking_confidence: Minimum confidence for tracking
            max_persons: Maximum number of people to track
            on_hit_callback: Optional callback when hit is detected
            tracker: Optional external tracker (for multi-player sessions)
        """
        self.dominant_hand = dominant_hand

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

        self.hit_detector = HitDetector(dominant_hand=dominant_hand)
        self.on_hit_callback = on_hit_callback

        # Drawing utilities (compat layer)
        self.mp_drawing_compat = mp_drawing_compat

        # Track recent actions for display
        self.recent_actions: dict = {}  # player_id -> {"action": str, "hand": str}
        self.action_display_frames = 20  # How long to show action
        self.action_frame_counts: dict = {}  # player_id -> frames remaining

        # Current zone tracking for display (even without hits)
        self.current_zones: dict = {}  # player_id -> {"left": zone, "right": zone}

        # Hit log
        self.hit_log: List[HitEvent] = []

        # Timing for relative timestamps
        self.start_time: Optional[float] = None  # Raw timestamp of first hit
        self.end_time: Optional[float] = None    # Raw timestamp of last hit

        # Last processed persons (for drawing without reprocessing)
        self._last_persons: List[PersonPose] = []
        self._last_body_refs: dict = {}  # player_id -> body_refs

    def process_frame(self, frame, current_time: float = None) -> List[HitEvent]:
        """
        Process a single frame and detect drum hits.

        Args:
            frame: BGR image from OpenCV
            current_time: Timestamp for hit detection

        Returns:
            List of HitEvent objects detected in this frame
        """
        if current_time is None:
            current_time = time.time()

        hits_this_frame = []

        # Get poses for all people
        persons = self.tracker.process_frame(frame)
        self._last_persons = persons

        for person in persons:
            player_id = person.player_id
            self.current_zones[player_id] = {"left": None, "right": None}

            # Get body references (normalized) for zone classification
            body_refs = self.tracker.get_body_references(person)
            self._last_body_refs[player_id] = body_refs

            # Get normalized wrist y-coordinates
            wrist_normalized = self.tracker.get_wrist_normalized_y(person)

            # Get wrist world coordinates for velocity
            left_wrist, right_wrist = self.tracker.get_wrist_world_coords(person)

            # Check for hits on left hand
            if left_wrist and wrist_normalized and wrist_normalized.get("left") is not None:
                # Track current zone for display
                zone = self.hit_detector.get_current_zone(
                    hand="left",
                    wrist_y_normalized=wrist_normalized["left"],
                    body_refs=body_refs,
                    world_x=left_wrist["x"]
                )
                self.current_zones[player_id]["left"] = zone

                hit = self.hit_detector.update(
                    player_id=player_id,
                    hand="left",
                    world_x=left_wrist["x"],
                    world_y=left_wrist["y"],
                    world_z=left_wrist["z"],
                    wrist_y_normalized=wrist_normalized["left"],
                    body_refs=body_refs,
                    current_time=current_time
                )
                if hit:
                    hits_this_frame.append(hit)
                    self._record_hit(hit)

            # Check for hits on right hand
            if right_wrist and wrist_normalized and wrist_normalized.get("right") is not None:
                # Track current zone for display
                zone = self.hit_detector.get_current_zone(
                    hand="right",
                    wrist_y_normalized=wrist_normalized["right"],
                    body_refs=body_refs,
                    world_x=right_wrist["x"]
                )
                self.current_zones[player_id]["right"] = zone

                hit = self.hit_detector.update(
                    player_id=player_id,
                    hand="right",
                    world_x=right_wrist["x"],
                    world_y=right_wrist["y"],
                    world_z=right_wrist["z"],
                    wrist_y_normalized=wrist_normalized["right"],
                    body_refs=body_refs,
                    current_time=current_time
                )
                if hit:
                    hits_this_frame.append(hit)
                    self._record_hit(hit)

            # Check for kick hits on feet
            left_foot, right_foot = self.tracker.get_foot_world_coords(person)

            if left_foot:
                kick = self.hit_detector.update_foot(
                    player_id=player_id,
                    foot="left_foot",
                    world_x=left_foot["x"],
                    world_y=left_foot["y"],
                    world_z=left_foot["z"],
                    current_time=current_time
                )
                if kick:
                    hits_this_frame.append(kick)
                    self._record_hit(kick)

            if right_foot:
                kick = self.hit_detector.update_foot(
                    player_id=player_id,
                    foot="right_foot",
                    world_x=right_foot["x"],
                    world_y=right_foot["y"],
                    world_z=right_foot["z"],
                    current_time=current_time
                )
                if kick:
                    hits_this_frame.append(kick)
                    self._record_hit(kick)

        # Decay action display counters
        self._decay_action_display()

        return hits_this_frame

    def _record_hit(self, hit: HitEvent):
        """Record a hit and trigger callback."""
        self.hit_log.append(hit)
        self.recent_actions[hit.player_id] = {
            "action": hit.action,
            "hand": hit.hand
        }
        self.action_frame_counts[hit.player_id] = self.action_display_frames

        # Track start_time and end_time for relative timestamps
        if self.start_time is None:
            self.start_time = hit.raw_timestamp
        self.end_time = hit.raw_timestamp

        if self.on_hit_callback:
            self.on_hit_callback(hit)

        # Print to console as JSON
        print(json.dumps(hit.to_dict()))

    def _decay_action_display(self):
        """Reduce action display counters."""
        for player_id in list(self.action_frame_counts.keys()):
            self.action_frame_counts[player_id] -= 1
            if self.action_frame_counts[player_id] <= 0:
                del self.action_frame_counts[player_id]
                if player_id in self.recent_actions:
                    del self.recent_actions[player_id]

    def draw_overlay(self, frame, persons: List[PersonPose] = None):
        """
        Draw skeleton and action labels on frame.

        Args:
            frame: BGR image to draw on (modified in place)
            persons: List of PersonPose (if None, uses last processed)
        """
        if persons is None:
            persons = self._last_persons

        h, w = frame.shape[:2]

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

                # Add recent hit action if available
                if player_id in self.recent_actions:
                    action_info = self.recent_actions[player_id]
                    label += f": {action_info['action'].upper()}"

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

                # Determine text color based on recent action
                text_color = (255, 255, 255)  # Default white
                if player_id in self.recent_actions:
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

                # Draw current zone indicators on wrists
                self._draw_zone_indicators(frame, person, w, h)

        # Draw dexterity indicator
        self._draw_dexterity_indicator(frame, w, h)

    def _draw_zone_indicators(self, frame, person: PersonPose, w: int, h: int):
        """Draw zone indicators near the wrists."""
        if not person.pose_landmarks:
            return

        player_id = person.player_id
        zones = self.current_zones.get(player_id, {})

        landmarks = person.pose_landmarks.landmark

        # Left wrist indicator
        left_zone = zones.get("left")
        if left_zone:
            left_wrist = landmarks[15]
            lx = int(left_wrist.x * w)
            ly = int(left_wrist.y * h)
            cv2.putText(
                frame,
                left_zone.upper(),
                (lx - 30, ly - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 0),
                1
            )

        # Right wrist indicator
        right_zone = zones.get("right")
        if right_zone:
            right_wrist = landmarks[16]
            rx = int(right_wrist.x * w)
            ry = int(right_wrist.y * h)
            cv2.putText(
                frame,
                right_zone.upper(),
                (rx - 30, ry - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 0),
                1
            )

    def _draw_dexterity_indicator(self, frame, w: int, h: int):
        """Draw dominant hand indicator in corner."""
        text = f"Dominant: {self.dominant_hand.upper()}"
        cv2.putText(
            frame,
            text,
            (w - 180, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1
        )

    def save_hit_log(self, output_path: str):
        """Save all detected hits to JSON file with relative timestamps."""
        # Calculate end_time relative to start_time
        relative_end_time = None
        if self.start_time is not None and self.end_time is not None:
            relative_end_time = round(self.end_time - self.start_time, 4)

        data = {
            "session_timestamp": datetime.now().isoformat(),
            "instrument": "drums",
            "dominant_hand": self.dominant_hand,
            "total_hits": len(self.hit_log),
            "end_time": relative_end_time,
            "hits": [hit.to_dict(start_time=self.start_time) for hit in self.hit_log]
        }
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(self.hit_log)} hits to {output_path}")

    def clear_hit_log(self):
        """Clear the hit log and reset timing."""
        self.hit_log.clear()
        self.start_time = None
        self.end_time = None
        print("Hit log cleared")

    def process_poses(self, persons: List[PersonPose], current_time: float = None) -> List[HitEvent]:
        """
        Process pre-detected poses (for multi-player mode with shared tracker).

        Args:
            persons: List of PersonPose objects from shared tracker
            current_time: Timestamp for hit detection

        Returns:
            List of HitEvent objects detected
        """
        if current_time is None:
            current_time = time.time()

        self._last_persons = persons
        hits_this_frame = []

        for person in persons:
            player_id = person.player_id

            # Get body reference points and wrist coordinates
            body_refs = self.tracker.get_body_references(person)
            left_wrist, right_wrist = self.tracker.get_wrist_world_coords(person)
            left_foot, right_foot = self.tracker.get_foot_world_coords(person)

            if body_refs:
                self._last_body_refs[player_id] = body_refs

            # Get normalized y for body-relative zone classification
            wrist_y = self.tracker.get_wrist_normalized_y(person)

            # Update zone tracking for display (even without hits)
            self.current_zones[player_id] = {"left": None, "right": None}
            if body_refs and wrist_y:
                if left_wrist and wrist_y.get("left") is not None:
                    self.current_zones[player_id]["left"] = self.hit_detector.get_current_zone(
                        hand="left",
                        wrist_y_normalized=wrist_y["left"],
                        body_refs=body_refs,
                        world_x=left_wrist["x"]
                    )
                if right_wrist and wrist_y.get("right") is not None:
                    self.current_zones[player_id]["right"] = self.hit_detector.get_current_zone(
                        hand="right",
                        wrist_y_normalized=wrist_y["right"],
                        body_refs=body_refs,
                        world_x=right_wrist["x"]
                    )

            # Process left wrist
            if left_wrist and body_refs and wrist_y:
                hit = self.hit_detector.update(
                    player_id=player_id,
                    hand="left",
                    world_x=left_wrist["x"],
                    world_y=left_wrist["y"],
                    world_z=left_wrist["z"],
                    body_refs=body_refs,
                    wrist_y_normalized=wrist_y.get("left"),
                    current_time=current_time
                )
                if hit:
                    hits_this_frame.append(hit)
                    self._record_hit(hit)

            # Process right wrist
            if right_wrist and body_refs and wrist_y:
                hit = self.hit_detector.update(
                    player_id=player_id,
                    hand="right",
                    world_x=right_wrist["x"],
                    world_y=right_wrist["y"],
                    world_z=right_wrist["z"],
                    body_refs=body_refs,
                    wrist_y_normalized=wrist_y.get("right"),
                    current_time=current_time
                )
                if hit:
                    hits_this_frame.append(hit)
                    self._record_hit(hit)

            # Process feet for kicks
            if left_foot:
                kick = self.hit_detector.update_foot(
                    player_id=player_id,
                    foot="left_foot",
                    world_x=left_foot["x"],
                    world_y=left_foot["y"],
                    world_z=left_foot["z"],
                    current_time=current_time
                )
                if kick:
                    hits_this_frame.append(kick)
                    self._record_hit(kick)

            if right_foot:
                kick = self.hit_detector.update_foot(
                    player_id=player_id,
                    foot="right_foot",
                    world_x=right_foot["x"],
                    world_y=right_foot["y"],
                    world_z=right_foot["z"],
                    current_time=current_time
                )
                if kick:
                    hits_this_frame.append(kick)
                    self._record_hit(kick)

        # Decay action display counters
        self._decay_action_display()

        return hits_this_frame

    def close(self):
        """Release resources."""
        if self._owns_tracker:
            self.tracker.close()
