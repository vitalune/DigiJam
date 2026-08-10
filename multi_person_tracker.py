"""
Multi-person pose tracking using MediaPipe Pose Landmarker (Tasks API).
Wraps single-person detection with player ID tracking.

Supports true multi-person detection via YOLO + MediaPipe pipeline.
"""
import cv2
import mediapipe as mp
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, TYPE_CHECKING
from pathlib import Path

from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    PoseLandmarker,
    PoseLandmarkerOptions,
    RunningMode,
)

if TYPE_CHECKING:
    from multi_person.yolo_detector import YOLOPersonDetector, BoundingBox

# Path to the pose landmarker model
_MODEL_PATH = str(Path(__file__).parent / "pose_landmarker.task")


@dataclass
class PersonPose:
    """Pose data for a single detected person."""
    player_id: int
    bbox: Tuple[int, int, int, int]  # x, y, width, height in pixels
    pose_landmarks: any  # list of NormalizedLandmark (new API)
    pose_world_landmarks: any  # list of Landmark (new API)
    confidence: float


class _LandmarkListCompat:
    """Compatibility wrapper so code using .landmark[i] still works."""
    def __init__(self, landmark_list):
        self.landmark = landmark_list


class MultiPersonTracker:
    """
    Tracks people and their poses with unique player IDs.

    Currently uses single-person detection (MediaPipe Pose).
    Architecture supports future multi-person expansion.

    World Coordinate System:
    - Origin: hip center (midpoint between left/right hip)
    - Units: meters
    - X: negative = subject's left, positive = subject's right
    - Y: negative = up (above hip), positive = down (below hip)
    - Z: negative = away from camera, positive = toward camera
    """

    # Landmark indices
    NOSE_IDX = 0
    LEFT_SHOULDER_IDX = 11
    RIGHT_SHOULDER_IDX = 12
    LEFT_WRIST_IDX = 15
    RIGHT_WRIST_IDX = 16
    LEFT_INDEX_IDX = 19
    RIGHT_INDEX_IDX = 20
    LEFT_HIP_IDX = 23
    RIGHT_HIP_IDX = 24
    LEFT_FOOT_INDEX_IDX = 31
    RIGHT_FOOT_INDEX_IDX = 32

    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        max_persons: int = 4,
        yolo_detector: Optional['YOLOPersonDetector'] = None
    ):
        """
        Initialize multi-person tracker.

        Args:
            model_complexity: Pose model complexity (0=lite, 1=full, 2=heavy)
            min_detection_confidence: Minimum confidence for pose detection
            min_tracking_confidence: Minimum confidence for tracking
            max_persons: Maximum number of people to track
            yolo_detector: Optional YOLO detector for true multi-person detection
        """
        self.max_persons = max_persons
        self.yolo_detector = yolo_detector

        # Use IMAGE mode for YOLO crops (each crop is independent),
        # VIDEO mode for sequential frame processing
        running_mode = RunningMode.IMAGE if yolo_detector is not None else RunningMode.VIDEO

        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=running_mode,
            num_poses=max_persons,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.pose = PoseLandmarker.create_from_options(options)
        self._running_mode = running_mode
        self._timestamp_ms = 0

        # Player ID tracking
        self.next_player_id = 1
        self.active_players: Dict[int, Tuple[float, float]] = {}  # id -> (cx, cy)
        self.player_timeout_frames = 30  # Frames before player ID is recycled
        self.player_last_seen: Dict[int, int] = {}  # id -> frame_count
        self.frame_count = 0

        # Store last detection for drawing
        self.last_persons: List[PersonPose] = []

    def _assign_player_id(self, centroid: Tuple[float, float]) -> int:
        """
        Assign a player ID based on centroid proximity.
        Uses simple nearest-neighbor matching with distance threshold.
        """
        cx, cy = centroid
        DISTANCE_THRESHOLD = 150  # pixels

        # Find closest existing player
        best_id = None
        best_distance = float('inf')

        for player_id, (px, py) in self.active_players.items():
            distance = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            if distance < best_distance and distance < DISTANCE_THRESHOLD:
                best_distance = distance
                best_id = player_id

        if best_id is not None:
            # Update existing player position
            self.active_players[best_id] = (cx, cy)
            self.player_last_seen[best_id] = self.frame_count
            return best_id
        else:
            # Assign new player ID
            new_id = self.next_player_id
            self.next_player_id += 1
            self.active_players[new_id] = (cx, cy)
            self.player_last_seen[new_id] = self.frame_count
            return new_id

    def _cleanup_stale_players(self):
        """Remove players not seen for a while."""
        stale_ids = [
            pid for pid, last_frame in self.player_last_seen.items()
            if self.frame_count - last_frame > self.player_timeout_frames
        ]
        for pid in stale_ids:
            del self.active_players[pid]
            del self.player_last_seen[pid]

    def _detect(self, mp_image: mp.Image):
        """Run pose detection using the appropriate mode."""
        if self._running_mode == RunningMode.IMAGE:
            return self.pose.detect(mp_image)
        else:
            self._timestamp_ms += 33  # ~30 fps
            return self.pose.detect_for_video(mp_image, self._timestamp_ms)

    def process_frame(self, frame: np.ndarray) -> List[PersonPose]:
        """
        Process a frame and return poses for all detected people.

        Args:
            frame: BGR image from OpenCV

        Returns:
            List of PersonPose objects for each detected person
        """
        self.frame_count += 1
        self._cleanup_stale_players()

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = frame.shape[:2]

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        results = self._detect(mp_image)

        persons = []

        for i in range(len(results.pose_landmarks)):
            landmarks = results.pose_landmarks[i]
            world_landmarks = results.pose_world_landmarks[i]

            # Wrap in compat object so .landmark[idx] access works
            pose_lm = _LandmarkListCompat(landmarks)
            pose_wlm = _LandmarkListCompat(world_landmarks)

            # Calculate centroid from hip landmarks for player ID
            left_hip = landmarks[self.LEFT_HIP_IDX]
            right_hip = landmarks[self.RIGHT_HIP_IDX]
            cx = (left_hip.x + right_hip.x) / 2 * width
            cy = (left_hip.y + right_hip.y) / 2 * height

            player_id = self._assign_player_id((cx, cy))

            person = PersonPose(
                player_id=player_id,
                bbox=(0, 0, width, height),
                pose_landmarks=pose_lm,
                pose_world_landmarks=pose_wlm,
                confidence=1.0
            )
            persons.append(person)

        self.last_persons = persons
        return persons

    def process_frame_multi(self, frame: np.ndarray) -> List[PersonPose]:
        """
        Process frame with true multi-person detection using YOLO + MediaPipe.

        If yolo_detector is not configured, falls back to single-person detection.

        Args:
            frame: BGR image from OpenCV

        Returns:
            List of PersonPose objects for each detected person, sorted by x-position
        """
        if self.yolo_detector is None:
            return self.process_frame(frame)

        self.frame_count += 1
        self._cleanup_stale_players()

        height, width = frame.shape[:2]
        persons = []

        # Step 1: YOLO person detection (returns boxes sorted by x-center)
        bboxes = self.yolo_detector.detect(frame, max_persons=self.max_persons)

        for bbox in bboxes:
            # Step 2: Crop person region with padding
            pad = 20
            x1 = max(0, bbox.x - pad)
            y1 = max(0, bbox.y - pad)
            x2 = min(width, bbox.x + bbox.w + pad)
            y2 = min(height, bbox.y + bbox.h + pad)

            crop = frame[y1:y2, x1:x2]

            if crop.size == 0:
                continue

            # Step 3: Run MediaPipe Pose on crop
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop_rgb)
            results = self.pose.detect(mp_image)

            if not results.pose_landmarks:
                continue

            landmarks = results.pose_landmarks[0]
            world_landmarks = results.pose_world_landmarks[0]

            # Step 4: Transform normalized landmarks to original frame coordinates
            transformed = self._transform_landmarks_to_frame(
                landmarks, x1, y1, x2 - x1, y2 - y1, width, height
            )

            pose_lm = _LandmarkListCompat(transformed)
            pose_wlm = _LandmarkListCompat(world_landmarks)

            # Step 5: Calculate centroid and assign player ID
            left_hip = transformed[self.LEFT_HIP_IDX]
            right_hip = transformed[self.RIGHT_HIP_IDX]
            cx = (left_hip.x + right_hip.x) / 2 * width
            cy = (left_hip.y + right_hip.y) / 2 * height

            player_id = self._assign_player_id((cx, cy))

            person = PersonPose(
                player_id=player_id,
                bbox=(bbox.x, bbox.y, bbox.w, bbox.h),
                pose_landmarks=pose_lm,
                pose_world_landmarks=pose_wlm,
                confidence=bbox.confidence
            )
            persons.append(person)

        self.last_persons = persons
        return persons

    def _transform_landmarks_to_frame(
        self,
        landmarks: list,
        crop_x: int,
        crop_y: int,
        crop_w: int,
        crop_h: int,
        frame_w: int,
        frame_h: int
    ) -> list:
        """
        Transform normalized landmarks from crop coordinates to full frame coordinates.

        Args:
            landmarks: List of NormalizedLandmark
            crop_x, crop_y: Top-left corner of crop in frame
            crop_w, crop_h: Size of crop
            frame_w, frame_h: Size of original frame

        Returns:
            Modified landmarks with coordinates relative to full frame
        """
        for landmark in landmarks:
            pixel_x = landmark.x * crop_w
            pixel_y = landmark.y * crop_h

            frame_pixel_x = pixel_x + crop_x
            frame_pixel_y = pixel_y + crop_y

            landmark.x = frame_pixel_x / frame_w
            landmark.y = frame_pixel_y / frame_h

        return landmarks

    def reset_player_ids(self):
        """Reset all player IDs and tracking state."""
        self.next_player_id = 1
        self.active_players.clear()
        self.player_last_seen.clear()
        self.frame_count = 0

    def get_wrist_world_coords(
        self,
        person: PersonPose
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Extract left and right wrist world coordinates.

        Args:
            person: PersonPose object

        Returns:
            Tuple of (left_wrist_coords, right_wrist_coords)
            Each is {"x": float, "y": float, "z": float} or None
        """
        if not person.pose_world_landmarks:
            return None, None

        landmarks = person.pose_world_landmarks.landmark

        left_wrist = landmarks[self.LEFT_WRIST_IDX]
        right_wrist = landmarks[self.RIGHT_WRIST_IDX]

        # Only return if visibility is good
        MIN_VISIBILITY = 0.5

        left_coords = None
        if left_wrist.visibility > MIN_VISIBILITY:
            left_coords = {
                "x": left_wrist.x,
                "y": left_wrist.y,
                "z": left_wrist.z
            }

        right_coords = None
        if right_wrist.visibility > MIN_VISIBILITY:
            right_coords = {
                "x": right_wrist.x,
                "y": right_wrist.y,
                "z": right_wrist.z
            }

        return left_coords, right_coords

    def get_index_finger_world_coords(
        self,
        person: PersonPose
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Extract left and right index finger tip world coordinates.
        Alternative to wrist for more precise drumstick tip tracking.

        Args:
            person: PersonPose object

        Returns:
            Tuple of (left_index_coords, right_index_coords)
        """
        if not person.pose_world_landmarks:
            return None, None

        landmarks = person.pose_world_landmarks.landmark

        left_index = landmarks[self.LEFT_INDEX_IDX]
        right_index = landmarks[self.RIGHT_INDEX_IDX]

        MIN_VISIBILITY = 0.3  # Index fingers often have lower visibility

        left_coords = None
        if left_index.visibility > MIN_VISIBILITY:
            left_coords = {
                "x": left_index.x,
                "y": left_index.y,
                "z": left_index.z
            }

        right_coords = None
        if right_index.visibility > MIN_VISIBILITY:
            right_coords = {
                "x": right_index.x,
                "y": right_index.y,
                "z": right_index.z
            }

        return left_coords, right_coords

    def get_nose_position(self, person: PersonPose) -> Optional[Tuple[int, int]]:
        """Get nose position in pixel coordinates for label placement."""
        if not person.pose_landmarks:
            return None

        nose = person.pose_landmarks.landmark[self.NOSE_IDX]
        return nose

    def get_body_references(self, person: PersonPose) -> Optional[Dict]:
        """
        Extract normalized body reference points for zone classification.

        Uses pose_landmarks (normalized 0-1) for scale-invariant height comparisons.

        Returns:
            Dict with {"nose_y", "shoulder_y", "hip_y"} or None if landmarks unavailable
        """
        if not person.pose_landmarks:
            return None

        landmarks = person.pose_landmarks.landmark

        nose = landmarks[self.NOSE_IDX]
        left_shoulder = landmarks[self.LEFT_SHOULDER_IDX]
        right_shoulder = landmarks[self.RIGHT_SHOULDER_IDX]
        left_hip = landmarks[self.LEFT_HIP_IDX]
        right_hip = landmarks[self.RIGHT_HIP_IDX]

        # Average shoulders and hips for more stable reference
        shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        hip_y = (left_hip.y + right_hip.y) / 2

        return {
            "nose_y": nose.y,
            "shoulder_y": shoulder_y,
            "hip_y": hip_y
        }

    def get_wrist_normalized_y(self, person: PersonPose) -> Optional[Dict]:
        """
        Get normalized y-coordinates of wrists for body-relative comparison.

        Returns:
            Dict with {"left": y, "right": y} or None if landmarks unavailable
        """
        if not person.pose_landmarks:
            return None

        landmarks = person.pose_landmarks.landmark

        left_wrist = landmarks[self.LEFT_WRIST_IDX]
        right_wrist = landmarks[self.RIGHT_WRIST_IDX]

        MIN_VISIBILITY = 0.5

        result = {"left": None, "right": None}

        if left_wrist.visibility > MIN_VISIBILITY:
            result["left"] = left_wrist.y

        if right_wrist.visibility > MIN_VISIBILITY:
            result["right"] = right_wrist.y

        return result

    def get_foot_world_coords(
        self,
        person: PersonPose
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Extract left and right foot index world coordinates for kick detection.

        Args:
            person: PersonPose object

        Returns:
            Tuple of (left_foot_coords, right_foot_coords)
            Each is {"x": float, "y": float, "z": float} or None
        """
        if not person.pose_world_landmarks:
            return None, None

        landmarks = person.pose_world_landmarks.landmark

        left_foot = landmarks[self.LEFT_FOOT_INDEX_IDX]
        right_foot = landmarks[self.RIGHT_FOOT_INDEX_IDX]

        MIN_VISIBILITY = 0.3  # Feet often have lower visibility

        left_coords = None
        if left_foot.visibility > MIN_VISIBILITY:
            left_coords = {
                "x": left_foot.x,
                "y": left_foot.y,
                "z": left_foot.z
            }

        right_coords = None
        if right_foot.visibility > MIN_VISIBILITY:
            right_coords = {
                "x": right_foot.x,
                "y": right_foot.y,
                "z": right_foot.z
            }

        return left_coords, right_coords

    def close(self):
        """Release resources."""
        try:
            self.pose.close()
        except Exception:
            pass
