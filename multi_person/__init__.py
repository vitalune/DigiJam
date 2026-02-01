"""Multi-person detection and session management for DigiJam."""

from .yolo_detector import YOLOPersonDetector, BoundingBox, is_yolo_available
from .role_assigner import RoleAssigner, RoleAssignment, validate_role_assignment

# Lazy import for MultiSessionManager to avoid cv2 dependency at import time
def get_session_manager():
    """Get MultiSessionManager class (lazy import to avoid cv2 at module load)."""
    from .session_manager import MultiSessionManager
    return MultiSessionManager

__all__ = [
    'YOLOPersonDetector',
    'BoundingBox',
    'is_yolo_available',
    'RoleAssigner',
    'RoleAssignment',
    'validate_role_assignment',
    'get_session_manager',
]
