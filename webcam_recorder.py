"""
Webcam recording with real-time instrument action classification.
Supports drums and guitar with recording sessions.
"""
import cv2
import os
import json
import time
from datetime import datetime
from typing import Optional, List, Union

from drum_classifier import DrumClassifier
from guitar_classifier import GuitarClassifier
from hit_detector import HitEvent
from strum_detector import StrumEvent


class WebcamRecorder:
    """
    Real-time webcam recording with instrument classification.

    Features:
    - Instrument selection (drums, guitar)
    - Dexterity selection (dominant hand)
    - Live pose skeleton display
    - Real-time action classification
    - Recording with stop key ('r' or 's')
    - JSON output of all detected actions
    - Video output with overlay
    """

    # Available instruments
    INSTRUMENTS = ["drums", "guitar"]

    def __init__(
        self,
        output_dir: str = "output",
        instrument: str = "drums",
        dominant_hand: str = "right"
    ):
        """
        Initialize webcam recorder.

        Args:
            output_dir: Directory to save outputs
            instrument: Instrument being played
            dominant_hand: "right" or "left" - player's dominant hand
        """
        self.output_dir = output_dir
        self.instrument = instrument
        self.dominant_hand = dominant_hand
        os.makedirs(output_dir, exist_ok=True)

        # Classifier will be initialized when run() is called
        self.classifier: Optional[Union[DrumClassifier, GuitarClassifier]] = None

        # Recording state
        self.is_recording = False
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.session_hits: List[HitEvent] = []  # For drums
        self.session_strums: List[StrumEvent] = []  # For guitar
        self.session_start_time: Optional[float] = None
        self.frame_count = 0
        self.video_path: Optional[str] = None
        self.json_path: Optional[str] = None

    def _on_hit(self, hit: HitEvent):
        """Callback when drum hit is detected during recording."""
        if self.is_recording:
            self.session_hits.append(hit)

    def _on_strum(self, strum: StrumEvent):
        """Callback when guitar strum is detected during recording."""
        if self.is_recording:
            self.session_strums.append(strum)

    def _start_recording(self, frame, fps: float):
        """Start a new recording session."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.video_path = os.path.join(
            self.output_dir,
            f"{self.instrument}_session_{timestamp}.mp4"
        )
        self.json_path = os.path.join(
            self.output_dir,
            f"{self.instrument}_session_{timestamp}.json"
        )

        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(
            self.video_path, fourcc, fps, (w, h)
        )

        self.is_recording = True
        self.session_hits = []
        self.session_strums = []

        # Clear the appropriate log
        if self.instrument == "drums":
            self.classifier.clear_hit_log()
        elif self.instrument == "guitar":
            self.classifier.clear_strum_log()

        self.session_start_time = time.time()
        self.frame_count = 0

        print(f"\n{'='*50}")
        print(f"RECORDING STARTED")
        print(f"Instrument: {self.instrument}")
        print(f"Press 'r' or 's' to stop recording")
        print(f"{'='*50}\n")

    def _stop_recording(self):
        """Stop recording and save outputs."""
        if not self.is_recording:
            return

        self.is_recording = False

        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

        # Save JSON based on instrument
        duration = time.time() - self.session_start_time

        if self.instrument == "drums":
            self.classifier.save_hit_log(self.json_path)
            action_count = len(self.classifier.hit_log)
            action_name = "Hits"
        elif self.instrument == "guitar":
            self.classifier.save_strum_log(self.json_path)
            action_count = len(self.classifier.strum_log)
            action_name = "Strums"
        else:
            action_count = 0
            action_name = "Actions"

        print(f"\n{'='*50}")
        print(f"RECORDING STOPPED")
        print(f"Duration: {duration:.1f} seconds")
        print(f"Frames: {self.frame_count}")
        print(f"{action_name} detected: {action_count}")
        print(f"Video saved: {self.video_path}")
        print(f"Data saved: {self.json_path}")
        print(f"{'='*50}\n")

    @staticmethod
    def prompt_instrument() -> str:
        """
        Prompt user to select an instrument.

        Returns:
            Selected instrument name
        """
        print("\n" + "=" * 50)
        print("INSTRUMENT SELECTION")
        print("=" * 50)
        print("\nAvailable instruments:")
        for i, inst in enumerate(WebcamRecorder.INSTRUMENTS, 1):
            print(f"  {i}. {inst.capitalize()}")

        print("\nMore instruments coming soon!")
        print("-" * 50)

        while True:
            try:
                choice = input(f"\nWhich instrument? [1-{len(WebcamRecorder.INSTRUMENTS)}]: ").strip()
                if choice == "":
                    return WebcamRecorder.INSTRUMENTS[0]  # Default to first instrument
                idx = int(choice) - 1
                if 0 <= idx < len(WebcamRecorder.INSTRUMENTS):
                    return WebcamRecorder.INSTRUMENTS[idx]
                print(f"Please enter a number between 1 and {len(WebcamRecorder.INSTRUMENTS)}")
            except ValueError:
                print("Please enter a valid number")

    @staticmethod
    def prompt_dexterity() -> str:
        """
        Prompt user to select their dominant hand.

        Returns:
            "right" or "left"
        """
        print("\n" + "=" * 50)
        print("DEXTERITY SELECTION")
        print("=" * 50)
        print("\nWhich is your dominant hand?")
        print("  1. Right (default)")
        print("  2. Left")
        print("-" * 50)

        while True:
            try:
                choice = input("\nSelect [1-2]: ").strip()
                if choice == "" or choice == "1":
                    return "right"
                if choice == "2":
                    return "left"
                print("Please enter 1 or 2")
            except ValueError:
                print("Please enter a valid number")

    def run(self, skip_prompt: bool = False):
        """
        Run the webcam recorder.

        Args:
            skip_prompt: If True, skip instrument selection prompt

        Controls:
        - 'q': Quit
        - 'r' or 's': Start/Stop recording
        - 'c': Clear action log
        - 'g': Recalibrate guitar (guitar mode only)
        """
        # Initialize appropriate classifier based on instrument
        if self.instrument == "drums":
            self.classifier = DrumClassifier(
                dominant_hand=self.dominant_hand,
                model_complexity=1,
                on_hit_callback=self._on_hit
            )
        elif self.instrument == "guitar":
            self.classifier = GuitarClassifier(
                dominant_hand=self.dominant_hand,
                model_complexity=1,
                on_strum_callback=self._on_strum
            )

        # Determine hand assignments based on dexterity
        strum_hand = self.dominant_hand
        fret_hand = "left" if self.dominant_hand == "right" else "right"
        hat_hand = self.dominant_hand
        snare_hand = "left" if self.dominant_hand == "right" else "right"

        # Show instrument-specific controls
        print("\n" + "=" * 50)
        print(f"{self.instrument.upper()} ACTION CLASSIFIER")
        print("=" * 50)
        print(f"\nInstrument: {self.instrument.upper()}")
        print(f"Dominant hand: {self.dominant_hand.upper()}")

        if self.instrument == "drums":
            print("\nDrum Actions (body-relative):")
            print(f"  Hi-Hat:  {hat_hand.capitalize()} hand above shoulders")
            print(f"  Crash:   {snare_hand.capitalize()} hand above shoulders")
            print(f"  Snare:   {snare_hand.capitalize()} hand at chest level, center")
            print(f"  Kick:    Either foot stomp")
            print("\nHit velocity is tracked for volume control.")
            print("\nControls:")
            print("  'r' or 's' - Start/Stop recording")
            print("  'q' - Quit")
            print("  'c' - Clear hit log")
        elif self.instrument == "guitar":
            print("\nGuitar Actions:")
            print(f"  Strum:   {strum_hand.capitalize()} hand downward motion")
            print(f"  Fret:    {fret_hand.capitalize()} hand position (5cm per fret)")
            print("\nAuto-calibrates on first frame with both hands visible.")
            print("Strum intensity is tracked for volume control.")
            print("\nControls:")
            print("  'r' or 's' - Start/Stop recording")
            print("  'q' - Quit")
            print("  'c' - Clear strum log")
            print("  'g' - Recalibrate fret position")

        print("=" * 50 + "\n")

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open webcam")
            return

        # Get actual FPS from camera, default to 30 if not available
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        print("Starting webcam feed...")
        print("Press 'r' or 's' to start recording\n")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame")
                break

            current_time = time.time()

            # Process frame for classification
            hits = self.classifier.process_frame(frame, current_time)

            # Draw overlay
            self.classifier.draw_overlay(frame)

            # Draw recording indicator
            if self.is_recording:
                # Red recording dot
                cv2.circle(frame, (30, 30), 15, (0, 0, 255), -1)
                cv2.putText(
                    frame,
                    "REC",
                    (55, 38),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )

                # Frame counter with instrument-specific action count
                elapsed = time.time() - self.session_start_time
                if self.instrument == "drums":
                    action_count = len(self.classifier.hit_log)
                    action_name = "hits"
                elif self.instrument == "guitar":
                    action_count = len(self.classifier.strum_log)
                    action_name = "strums"
                else:
                    action_count = 0
                    action_name = "actions"

                cv2.putText(
                    frame,
                    f"{elapsed:.1f}s | {self.frame_count} frames | {action_count} {action_name}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1
                )

                # Write frame to video
                self.video_writer.write(frame)
                self.frame_count += 1
            else:
                # Show ready indicator
                cv2.putText(
                    frame,
                    "READY - Press 'r' to record",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            # Draw instructions at bottom
            h = frame.shape[0]
            if self.instrument == "guitar":
                instruction_text = f"GUITAR | 'r'=record 's'=stop 'g'=recalibrate 'q'=quit"
            else:
                instruction_text = f"DRUMS | 'r'=record 's'=stop 'q'=quit"

            cv2.putText(
                frame,
                instruction_text,
                (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1
            )

            # Show frame
            window_name = f'{self.instrument.capitalize()} Classifier'
            cv2.imshow(window_name, frame)

            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                if not self.is_recording:
                    self._start_recording(frame, fps)
            elif key == ord('s'):
                if self.is_recording:
                    self._stop_recording()
            elif key == ord('c'):
                # Clear the appropriate log
                if self.instrument == "drums":
                    self.classifier.clear_hit_log()
                elif self.instrument == "guitar":
                    self.classifier.clear_strum_log()
            elif key == ord('g') and self.instrument == "guitar":
                # Recalibrate guitar
                self.classifier.reset_calibration()

        # Cleanup
        if self.is_recording:
            self._stop_recording()

        cap.release()
        cv2.destroyAllWindows()
        self.classifier.close()
        print("\nSession ended")


def main():
    """Main entry point with instrument and dexterity selection."""
    # Prompt for instrument
    instrument = WebcamRecorder.prompt_instrument()
    print(f"\nSelected: {instrument.upper()}")

    # Prompt for dexterity
    dominant_hand = WebcamRecorder.prompt_dexterity()
    print(f"\nDominant hand: {dominant_hand.upper()}")

    recorder = WebcamRecorder(
        output_dir="output",
        instrument=instrument,
        dominant_hand=dominant_hand
    )
    recorder.run()


if __name__ == "__main__":
    main()
