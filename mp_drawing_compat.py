"""
Compatibility layer for MediaPipe drawing utilities.
Bridges the old mp.solutions API to the new Tasks API.
"""
from mediapipe.tasks.python.vision import (
    drawing_utils,
    drawing_styles,
    PoseLandmarksConnections,
)


def draw_pose_landmarks(image, pose_landmarks_compat, connections=None, landmark_drawing_spec=None):
    """
    Draw pose landmarks on an image.

    Args:
        image: BGR image (numpy array)
        pose_landmarks_compat: _LandmarkListCompat wrapper with .landmark list
        connections: Optional connections (uses POSE_LANDMARKS by default)
        landmark_drawing_spec: Optional drawing spec mapping
    """
    if pose_landmarks_compat is None:
        return

    landmarks = pose_landmarks_compat.landmark

    if connections is None:
        connections = PoseLandmarksConnections.POSE_LANDMARKS

    if landmark_drawing_spec is None:
        landmark_drawing_spec = drawing_styles.get_default_pose_landmarks_style()

    drawing_utils.draw_landmarks(
        image,
        landmarks,
        connections,
        landmark_drawing_spec,
    )


# Expose connections for code that references mp_pose.POSE_CONNECTIONS
POSE_CONNECTIONS = PoseLandmarksConnections.POSE_LANDMARKS
get_default_pose_landmarks_style = drawing_styles.get_default_pose_landmarks_style
