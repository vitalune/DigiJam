"""
YOLO-based person detection for multi-person pose tracking.

Uses ultralytics YOLO for fast, accurate person bounding box detection.
Returns boxes sorted by x-center (left to right) for role assignment.
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


@dataclass
class BoundingBox:
    """Bounding box for a detected person."""
    x: int          # Top-left x coordinate
    y: int          # Top-left y coordinate
    w: int          # Width
    h: int          # Height
    confidence: float
    x_center: float  # Center x for sorting

    @property
    def area(self) -> int:
        return self.w * self.h


class YOLOPersonDetector:
    """
    Wraps YOLO for multi-person bounding box detection.

    Detects people in a frame and returns their bounding boxes
    sorted by x-center coordinate (left to right in camera view).

    Attributes:
        model: YOLO model instance
        confidence_threshold: Minimum confidence for detection
        person_class_id: COCO class ID for person (0)
    """

    PERSON_CLASS_ID = 0  # COCO dataset class ID for person

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.5,
        min_box_area: int = 5000
    ):
        """
        Initialize YOLO person detector.

        Args:
            model_path: Path to YOLO model weights (default: yolov8n.pt for speed)
            confidence: Minimum confidence threshold for detections
            min_box_area: Minimum bounding box area in pixels (filters noise)
        """
        if not YOLO_AVAILABLE:
            raise ImportError(
                "ultralytics package not found. Install with: pip install ultralytics"
            )

        self.model = YOLO(model_path)
        self.confidence_threshold = confidence
        self.min_box_area = min_box_area

    def detect(self, frame: np.ndarray, max_persons: int = 4) -> List[BoundingBox]:
        """
        Detect people in frame and return bounding boxes sorted left-to-right.

        Args:
            frame: BGR image from OpenCV (np.ndarray)
            max_persons: Maximum number of people to return

        Returns:
            List of BoundingBox objects sorted by x_center (left to right)
        """
        # Run YOLO inference
        results = self.model(
            frame,
            conf=self.confidence_threshold,
            classes=[self.PERSON_CLASS_ID],  # Only detect persons
            verbose=False
        )

        boxes = []
        for result in results:
            for box in result.boxes:
                # Extract coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                x, y = int(x1), int(y1)
                w, h = int(x2 - x1), int(y2 - y1)
                conf = float(box.conf[0])

                # Filter by area (remove small detections / noise)
                if w * h < self.min_box_area:
                    continue

                x_center = x + w / 2

                boxes.append(BoundingBox(
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    confidence=conf,
                    x_center=x_center
                ))

        # Sort by x_center (left to right)
        boxes.sort(key=lambda b: b.x_center)

        # Limit to max_persons
        return boxes[:max_persons]

    def detect_with_frame_info(
        self,
        frame: np.ndarray,
        max_persons: int = 4
    ) -> tuple:
        """
        Detect people and return boxes with frame dimensions.

        Args:
            frame: BGR image from OpenCV
            max_persons: Maximum number of people to return

        Returns:
            Tuple of (List[BoundingBox], frame_height, frame_width)
        """
        h, w = frame.shape[:2]
        boxes = self.detect(frame, max_persons)
        return boxes, h, w


def is_yolo_available() -> bool:
    """Check if YOLO (ultralytics) is available."""
    return YOLO_AVAILABLE
