"""
Multi-player session manager for DigiJam.

Orchestrates multiple simultaneous instrument classifiers, routing
pose data to the correct classifier based on player assignments.

Responsibilities:
- Create per-player classifier instances
- Route pose data to correct classifier by player ID
- Manage per-player calibration states
- Lock/unlock role assignments
- Handle player disappearance and reappearance
"""

import time
import cv2
import mediapipe as mp
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field

from session_config import SessionConfig, PlayerConfig
from multi_person_tracker import MultiPersonTracker, PersonPose
from .role_assigner import RoleAssigner, RoleAssignment
from .yolo_detector import YOLOPersonDetector


@dataclass
class PlayerState:
    """Runtime state for a single player."""
    player_id: int
    instrument: str
    position_index: int
    classifier: Any  # DrumClassifier, GuitarClassifier, or PianoClassifier
    last_seen_frame: int = 0
    is_calibrated: bool = False
    events: List[Any] = field(default_factory=list)


class MultiSessionManager:
    """
    Orchestrates multi-player session with per-player classifiers.

    Manages the lifecycle of a multi-player session including:
    - Initial role assignment based on player positions
    - Per-player classifier creation and management
    - Routing pose data to correct classifiers
    - Role locking and reassignment

    Attributes:
        config: Session configuration
        tracker: Multi-person tracker (shared across all players)
        role_assigner: Spatial role assignment logic
        players: Dict mapping player_id to PlayerState
        role_locked: Whether roles are locked (no reassignment)
    """

    DISAPPEAR_THRESHOLD_FRAMES = 30  # Frames before player is considered gone

    def __init__(
        self,
        config: SessionConfig,
        on_event_callback: Optional[Callable[[int, str, Any], None]] = None
    ):
        """
        Initialize multi-session manager.

        Args:
            config: Session configuration with instruments and settings
            on_event_callback: Optional callback(player_id, instrument, event)
                              called when any event is detected
        """
        self.config = config
        self.on_event_callback = on_event_callback

        # Initialize YOLO detector for multi-person detection
        try:
            self.yolo_detector = YOLOPersonDetector()
        except ImportError:
            print("Warning: YOLO not available, falling back to single-person mode")
            self.yolo_detector = None

        # Initialize shared tracker
        self.tracker = MultiPersonTracker(
            model_complexity=1,
            max_persons=config.num_players,
            yolo_detector=self.yolo_detector
        )

        # Initialize role assigner
        self.role_assigner = RoleAssigner(
            num_players=config.num_players,
            instruments=config.instruments,
            guitar_handedness=config.guitar_handedness
        )

        # Player state management
        self.players: Dict[int, PlayerState] = {}
        self.role_locked = False
        self.frame_count = 0

        # Position to player mapping (for reassignment)
        self.position_to_player: Dict[int, int] = {}  # position_index -> player_id

        # Calibration state
        self.calibration_complete = False
        self.awaiting_calibration = True

        # MediaPipe drawing utilities for overlay
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.mp_pose = mp.solutions.pose

    def initialize_classifiers(self):
        """
        Create classifier instances for each expected player position.

        Called after role assignment to set up classifiers with
        correct instruments and configurations.
        """
        # Import classifiers here to avoid circular imports
        from classifiers.drum_classifier import DrumClassifier
        from classifiers.guitar_classifier import GuitarClassifier
        from classifiers.piano_classifier import PianoClassifier

        for position_index, instrument in self.role_assigner._role_map.items():
            # Get player config for this position (if assigned)
            player_config = None
            for pc in self.config.players:
                if pc.position_index == position_index:
                    player_config = pc
                    break

            # Create classifier based on instrument type
            if instrument == "drums":
                classifier = DrumClassifier(
                    dominant_hand=player_config.dominant_hand if player_config else "right",
                    model_complexity=1,
                    tracker=self.tracker
                )
            elif instrument == "guitar":
                classifier = GuitarClassifier(
                    dominant_hand=player_config.dominant_hand if player_config else "right",
                    key=self.config.key,
                    model_complexity=1,
                    tracker=self.tracker
                )
            elif instrument == "piano":
                classifier = PianoClassifier(
                    key=self.config.key,
                    model_complexity=1,
                    tracker=self.tracker,
                    auto_calibrate=True  # Auto-calibrate in multi-player mode
                )
            else:
                continue

            # Store as pending (player_id will be assigned during calibration)
            # Use negative position index as temporary ID
            temp_id = -(position_index + 1)
            self.players[temp_id] = PlayerState(
                player_id=temp_id,
                instrument=instrument,
                position_index=position_index,
                classifier=classifier
            )

    def calibrate_roles(self, persons: List[PersonPose]) -> bool:
        """
        Perform initial role assignment based on detected player positions.

        Should be called when all expected players are visible in frame.

        Args:
            persons: List of detected PersonPose objects

        Returns:
            True if calibration successful, False otherwise
        """
        if len(persons) != self.config.num_players:
            return False

        # Get centroids for role assignment
        centroids = []
        for person in persons:
            # Use the tracker's centroid calculation
            left_hip_idx = self.tracker.LEFT_HIP_IDX
            right_hip_idx = self.tracker.RIGHT_HIP_IDX

            lh = person.pose_landmarks.landmark[left_hip_idx]
            rh = person.pose_landmarks.landmark[right_hip_idx]
            cx = (lh.x + rh.x) / 2
            cy = (lh.y + rh.y) / 2
            centroids.append((cx, cy))

        # Assign roles based on x-positions
        assignments = self.role_assigner.assign_roles(centroids)

        # Update player states with actual player IDs
        new_players = {}
        self.position_to_player.clear()

        for i, (person, assignment) in enumerate(zip(
            sorted(persons, key=lambda p: self._get_centroid_x(p)),
            assignments
        )):
            player_id = person.player_id
            position_index = assignment.position_index
            instrument = assignment.instrument

            # Find the classifier for this position
            temp_id = -(position_index + 1)
            if temp_id in self.players:
                state = self.players[temp_id]
                state.player_id = player_id
                new_players[player_id] = state
                self.position_to_player[position_index] = player_id

                # Update config with actual player ID
                self.config.players.append(PlayerConfig(
                    player_id=player_id,
                    instrument=instrument,
                    position_index=position_index,
                    dominant_hand=state.classifier.dominant_hand if hasattr(state.classifier, 'dominant_hand') else "right",
                    key=self.config.key
                ))

        self.players = new_players
        self.calibration_complete = True
        self.awaiting_calibration = False
        return True

    def _get_centroid_x(self, person: PersonPose) -> float:
        """Get x-coordinate of person's centroid."""
        lh = person.pose_landmarks.landmark[self.tracker.LEFT_HIP_IDX]
        rh = person.pose_landmarks.landmark[self.tracker.RIGHT_HIP_IDX]
        return (lh.x + rh.x) / 2

    def lock_roles(self):
        """Lock current role assignments (prevent reassignment)."""
        self.role_locked = True

    def unlock_roles(self):
        """Unlock roles for reassignment."""
        self.role_locked = False

    def process_frame(
        self,
        frame,
        current_time: float
    ) -> Dict[int, List[Any]]:
        """
        Process a frame and route pose data to appropriate classifiers.

        Args:
            frame: BGR image from OpenCV
            current_time: Current timestamp

        Returns:
            Dict mapping player_id to list of detected events
        """
        self.frame_count += 1

        # Detect all persons
        if self.yolo_detector:
            persons = self.tracker.process_frame_multi(frame)
        else:
            persons = self.tracker.process_frame(frame)

        # If not calibrated, wait for calibration
        if self.awaiting_calibration:
            return {}

        # Route each person to their classifier
        events_by_player: Dict[int, List[Any]] = {}

        for person in persons:
            player_id = person.player_id

            if player_id not in self.players:
                # Unknown player - could be new or reassigned
                if not self.role_locked:
                    self._try_reassign_player(person)
                continue

            state = self.players[player_id]
            state.last_seen_frame = self.frame_count

            # Process frame with this player's classifier
            # Pass single-person list to classifier
            detected_events = state.classifier.process_poses([person], current_time)

            if detected_events:
                events_by_player[player_id] = detected_events
                state.events.extend(detected_events)

                # Fire callback
                if self.on_event_callback:
                    for event in detected_events:
                        self.on_event_callback(player_id, state.instrument, event)

        # Check for disappeared players
        self._check_disappeared_players()

        return events_by_player

    def _try_reassign_player(self, person: PersonPose):
        """
        Try to reassign a new player to an open position.

        Only called when roles are unlocked.
        """
        # Find if any position is missing a player
        for pos, player_id in list(self.position_to_player.items()):
            if player_id not in self.players:
                continue

            state = self.players[player_id]
            frames_since_seen = self.frame_count - state.last_seen_frame

            if frames_since_seen > self.DISAPPEAR_THRESHOLD_FRAMES:
                # This position's player has disappeared, reassign
                new_id = person.player_id
                instrument = state.instrument

                # Transfer classifier to new player
                state.player_id = new_id
                del self.players[player_id]
                self.players[new_id] = state
                self.position_to_player[pos] = new_id

                print(f"Reassigned {instrument} from player {player_id} to {new_id}")
                break

    def _check_disappeared_players(self):
        """Check for and handle players who have disappeared."""
        for player_id, state in list(self.players.items()):
            frames_since_seen = self.frame_count - state.last_seen_frame

            if frames_since_seen > self.DISAPPEAR_THRESHOLD_FRAMES:
                if not self.role_locked:
                    print(f"Player {player_id} ({state.instrument}) disappeared")
                    # Don't remove - keep state for potential reassignment

    def draw_overlay(self, frame):
        """
        Draw combined overlay for all players.

        During calibration: draws pose landmarks with "User 1", "User 2", etc.
        After calibration: draws each classifier's overlay with user labels.

        Args:
            frame: BGR image to draw on
        """
        if self.awaiting_calibration:
            # Draw calibration overlay with user labels
            self._draw_calibration_overlay(frame)
        else:
            # Draw each player's classifier overlay
            for player_id, state in self.players.items():
                state.classifier.draw_overlay(frame)

            # Draw user labels above each detected person
            self._draw_user_labels(frame)

    def _draw_calibration_overlay(self, frame):
        """
        Draw pose tracking overlay during calibration phase.

        Shows pose landmarks for all detected persons with "User X" labels
        sorted by x-position (left to right).

        Args:
            frame: BGR image to draw on
        """
        persons = self.tracker.last_persons
        if not persons:
            return

        h, w = frame.shape[:2]

        # Sort persons by x-position (centroid) to assign user numbers
        persons_with_x = []
        for person in persons:
            if person.pose_landmarks:
                # Get hip centroid for x-position
                lh = person.pose_landmarks.landmark[self.tracker.LEFT_HIP_IDX]
                rh = person.pose_landmarks.landmark[self.tracker.RIGHT_HIP_IDX]
                cx = (lh.x + rh.x) / 2
                persons_with_x.append((cx, person))

        # Sort by x-position (left to right)
        persons_with_x.sort(key=lambda x: x[0])

        # Draw each person with user label
        for user_index, (cx, person) in enumerate(persons_with_x):
            user_num = user_index + 1  # 1-indexed user number

            # Draw skeleton
            if person.pose_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame,
                    person.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
                )

                # Get nose position for label
                nose = person.pose_landmarks.landmark[0]
                label_x = int(nose.x * w)
                label_y = int(nose.y * h) - 50

                # Build label text
                label = f"User {user_num}"

                # Get expected instrument for this position
                expected_instrument = self.role_assigner.get_role_for_position(user_index)
                if expected_instrument:
                    label += f" ({expected_instrument.upper()})"

                # Draw label with background
                (text_w, text_h), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2
                )

                # Clamp to screen bounds
                label_x = max(5, min(label_x - text_w // 2, w - text_w - 10))
                label_y = max(text_h + 10, label_y)

                # Background rectangle
                cv2.rectangle(
                    frame,
                    (label_x - 5, label_y - text_h - 5),
                    (label_x + text_w + 5, label_y + 5),
                    (0, 0, 0),
                    -1
                )

                # User label text (cyan during calibration)
                cv2.putText(
                    frame,
                    label,
                    (label_x, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (255, 255, 0),  # Cyan
                    2
                )

    def _draw_user_labels(self, frame):
        """
        Draw "User X" labels above each detected person after calibration.

        Uses position_index to determine user number (User 1 = leftmost, etc.)

        Args:
            frame: BGR image to draw on
        """
        h, w = frame.shape[:2]

        for player_id, state in self.players.items():
            # Find the corresponding person in last_persons
            person = None
            for p in self.tracker.last_persons:
                if p.player_id == player_id:
                    person = p
                    break

            if not person or not person.pose_landmarks:
                continue

            # User number is position_index + 1
            user_num = state.position_index + 1

            # Get nose position for label
            nose = person.pose_landmarks.landmark[0]
            label_x = int(nose.x * w)
            label_y = int(nose.y * h) - 80  # Above the classifier's label

            # Build label text
            label = f"User {user_num} - {state.instrument.upper()}"

            # Draw label with background
            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2
            )

            # Clamp to screen bounds
            label_x = max(5, min(label_x - text_w // 2, w - text_w - 10))
            label_y = max(text_h + 10, label_y)

            # Background rectangle
            cv2.rectangle(
                frame,
                (label_x - 5, label_y - text_h - 5),
                (label_x + text_w + 5, label_y + 5),
                (50, 50, 50),
                -1
            )

            # User label text (color based on instrument)
            color = self._get_instrument_color(state.instrument)
            cv2.putText(
                frame,
                label,
                (label_x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2
            )

    def _get_instrument_color(self, instrument: str) -> tuple:
        """Get display color for instrument."""
        colors = {
            "drums": (0, 165, 255),   # Orange
            "guitar": (0, 255, 0),    # Green
            "piano": (255, 0, 255),   # Magenta
        }
        return colors.get(instrument, (255, 255, 255))

    def get_player_events(self, player_id: int) -> List[Any]:
        """Get all events for a specific player."""
        if player_id in self.players:
            return self.players[player_id].events
        return []

    def get_all_events(self) -> Dict[int, List[Any]]:
        """Get all events grouped by player ID."""
        return {pid: state.events for pid, state in self.players.items()}

    def clear_events(self):
        """Clear all recorded events."""
        for state in self.players.values():
            state.events.clear()

    def close(self):
        """Release resources."""
        for state in self.players.values():
            if hasattr(state.classifier, 'close'):
                state.classifier.close()
        self.tracker.close()

    def describe_session(self) -> str:
        """Get human-readable description of current session state."""
        lines = [
            f"Multi-Player Session ({self.config.num_players} players)",
            f"Instruments: {', '.join(self.config.instruments)}",
            f"Key: {self.config.key}",
            f"Roles locked: {self.role_locked}",
            "",
            "Role Assignments:",
            self.role_assigner.describe_roles(),
            "",
            "Active Players:"
        ]

        for player_id, state in self.players.items():
            status = "active" if self.frame_count - state.last_seen_frame < 10 else "inactive"
            lines.append(
                f"  Player {player_id}: {state.instrument.upper()} "
                f"[{status}, {len(state.events)} events]"
            )

        return "\n".join(lines)
