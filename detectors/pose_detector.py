"""
Body Movement Tracking using MediaPipe Pose
Tracks and documents body movements using machine vision.
"""

import cv2
import mediapipe as mp
import json
import os
from datetime import datetime


class PoseDetector:
    """Detects human body pose using MediaPipe and exports landmark data."""

    # MediaPipe landmark names for reference
    LANDMARK_NAMES = [
        "nose", "left_eye_inner", "left_eye", "left_eye_outer",
        "right_eye_inner", "right_eye", "right_eye_outer",
        "left_ear", "right_ear", "mouth_left", "mouth_right",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_pinky", "right_pinky",
        "left_index", "right_index", "left_thumb", "right_thumb",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle", "left_heel", "right_heel",
        "left_foot_index", "right_foot_index"
    ]

    def __init__(self, model_complexity=2, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        """
        Initialize the pose detector.

        Args:
            model_complexity: 0=lite, 1=full, 2=heavy (most accurate)
            min_detection_confidence: Minimum confidence for detection
            min_tracking_confidence: Minimum confidence for tracking
        """
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        # Default pose instance for images
        self.pose = self.mp_pose.Pose(
            static_image_mode=True,
            model_complexity=model_complexity,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

    def _extract_landmarks(self, pose_landmarks):
        """Extract landmark data as a list of dictionaries."""
        landmarks = []
        for idx, landmark in enumerate(pose_landmarks.landmark):
            landmarks.append({
                "id": idx,
                "name": self.LANDMARK_NAMES[idx],
                "x": round(landmark.x, 6),
                "y": round(landmark.y, 6),
                "z": round(landmark.z, 6),
                "visibility": round(landmark.visibility, 4)
            })
        return landmarks

    def process_image(self, image_path, output_dir="output"):
        """
        Process a single image and return pose landmarks.

        Args:
            image_path: Path to the input image
            output_dir: Directory to save outputs

        Returns:
            List of landmarks or None if no pose detected
        """
        os.makedirs(output_dir, exist_ok=True)

        # Read image
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not read image at {image_path}")
            return None

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Process with MediaPipe
        results = self.pose.process(image_rgb)

        if results.pose_landmarks:
            # Draw landmarks on image
            self.mp_drawing.draw_landmarks(
                image,
                results.pose_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
            )

            # Extract landmark data
            landmarks = self._extract_landmarks(results.pose_landmarks)

            # Save annotated image
            base_name = os.path.basename(image_path)
            name_without_ext = os.path.splitext(base_name)[0]
            ext = os.path.splitext(base_name)[1]

            output_image = os.path.join(output_dir, f"pose_{name_without_ext}{ext}")
            cv2.imwrite(output_image, image)

            # Save JSON data
            json_path = os.path.join(output_dir, f"pose_{name_without_ext}.json")
            output_data = {
                "source": image_path,
                "timestamp": datetime.now().isoformat(),
                "landmarks": landmarks,
                "landmark_count": len(landmarks)
            }
            with open(json_path, 'w') as f:
                json.dump(output_data, f, indent=2)

            print(f"Processed: {image_path}")
            print(f"  Output image: {output_image}")
            print(f"  JSON data: {json_path}")
            print(f"  Landmarks detected: {len(landmarks)}")

            return landmarks
        else:
            print(f"No pose detected in {image_path}")
            return None

    def process_video(self, video_path, output_dir="output", show_progress=True):
        """
        Process video and extract pose data for each frame.

        Args:
            video_path: Path to the input video
            output_dir: Directory to save outputs
            show_progress: Whether to print progress updates

        Returns:
            List of frame data with landmarks
        """
        os.makedirs(output_dir, exist_ok=True)

        # Create a separate pose instance for video (no segmentation to avoid resolution issues)
        video_pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=self.model_complexity,
            enable_segmentation=False,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence
        )

        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video at {video_path}")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Setup output video
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_video = os.path.join(output_dir, f"pose_{base_name}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

        all_frames_data = []
        frame_count = 0
        frames_with_pose = 0

        print(f"Processing video: {video_path}")
        print(f"  Resolution: {width}x{height}")
        print(f"  FPS: {fps}")
        print(f"  Total frames: {total_frames}")
        print()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = video_pose.process(frame_rgb)

            frame_data = {
                "frame": frame_count,
                "timestamp": round(frame_count / fps, 4)
            }

            if results.pose_landmarks:
                # Draw landmarks
                self.mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
                )

                frame_data["landmarks"] = self._extract_landmarks(results.pose_landmarks)
                frames_with_pose += 1
            else:
                frame_data["landmarks"] = None

            all_frames_data.append(frame_data)
            out.write(frame)
            frame_count += 1

            if show_progress and frame_count % 100 == 0:
                pct = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                print(f"  Progress: {frame_count}/{total_frames} frames ({pct:.1f}%)")

        cap.release()
        out.release()
        video_pose.close()

        # Save all frame data to JSON
        json_path = os.path.join(output_dir, f"pose_{base_name}_data.json")
        output_data = {
            "source": video_path,
            "timestamp": datetime.now().isoformat(),
            "fps": fps,
            "resolution": {"width": width, "height": height},
            "total_frames": frame_count,
            "frames_with_pose": frames_with_pose,
            "frames": all_frames_data
        }
        with open(json_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        print()
        print(f"Video processing complete!")
        print(f"  Output video: {output_video}")
        print(f"  JSON data: {json_path}")
        print(f"  Total frames: {frame_count}")
        print(f"  Frames with pose: {frames_with_pose} ({(frames_with_pose/frame_count)*100:.1f}%)")

        return all_frames_data

    def realtime_webcam(self):
        """Real-time pose detection from webcam."""
        # Create a separate pose instance for webcam
        webcam_pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,  # Use lighter model for real-time
            enable_segmentation=False,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence
        )

        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("Error: Could not open webcam")
            webcam_pose.close()
            return

        print("Starting real-time pose detection...")
        print("Press 'q' to quit")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = webcam_pose.process(frame_rgb)

            if results.pose_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
                )

            cv2.imshow('Pose Detection - Press Q to quit', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        webcam_pose.close()
        print("Webcam session ended")

    def close(self):
        """Release resources."""
        self.pose.close()


def main():
    """Main function to demonstrate pose detection."""
    detector = PoseDetector()

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")

    # Process sample image
    sample_image = os.path.join(script_dir, "sample_image.jpg")
    if os.path.exists(sample_image):
        print("=" * 50)
        print("Processing sample image...")
        print("=" * 50)
        detector.process_image(sample_image, output_dir)
        print()
    else:
        print(f"Sample image not found at {sample_image}")

    # Process sample video
    sample_video = os.path.join(script_dir, "sample_video.mp4")
    if os.path.exists(sample_video):
        print("=" * 50)
        print("Processing sample video...")
        print("=" * 50)
        detector.process_video(sample_video, output_dir)
        print()
    else:
        print(f"Sample video not found at {sample_video}")

    detector.close()

    print("=" * 50)
    print("Done! Check the 'output' directory for results.")
    print("=" * 50)


if __name__ == "__main__":
    main()
