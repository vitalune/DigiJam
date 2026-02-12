"""
Webcam recording with real-time instrument action classification.
Supports drums, guitar, and piano with recording sessions.
Supports all 24 major/minor keys for guitar and piano.
Supports multi-player sessions with role assignment.
"""
import cv2
import os
import json
import time
from datetime import datetime
from typing import Optional, List, Union

from classifiers.drum_classifier import DrumClassifier
from classifiers.guitar_classifier import GuitarClassifier
from classifiers.piano_classifier import PianoClassifier
from detectors.hit_detector import HitEvent
from detectors.strum_detector import StrumEvent
from detectors.piano_detector import PianoEvent
from audio.music_theory import AVAILABLE_KEYS, DEFAULT_KEY
from session_config import SessionConfig, PlayerConfig, create_single_player_config


class WebcamRecorder:
    """
    Real-time webcam recording with instrument classification.

    Features:
    - Instrument selection (drums, guitar, piano)
    - Dexterity selection (dominant hand)
    - Key selection (all 24 major/minor keys)
    - Live pose skeleton display
    - Real-time action classification
    - Recording with stop key ('r' or 's')
    - JSON output of all detected actions
    - Video output with overlay
    """

    # Available instruments
    INSTRUMENTS = ["drums", "guitar", "piano"]

    def __init__(
        self,
        output_dir: str = "output",
        instrument: str = "drums",
        dominant_hand: str = "right",
        key: str = DEFAULT_KEY
    ):
        """
        Initialize webcam recorder.

        Args:
            output_dir: Directory to save outputs
            instrument: Instrument being played
            dominant_hand: "right" or "left" - player's dominant hand
            key: Musical key (e.g., 'C Major', 'A Minor')
        """
        self.output_dir = output_dir
        self.instrument = instrument
        self.dominant_hand = dominant_hand
        self.key = key
        os.makedirs(output_dir, exist_ok=True)

        # Classifier will be initialized when run() is called
        self.classifier: Optional[Union[DrumClassifier, GuitarClassifier, PianoClassifier]] = None

        # Recording state
        self.is_recording = False
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.session_hits: List[HitEvent] = []  # For drums
        self.session_strums: List[StrumEvent] = []  # For guitar
        self.session_piano_hits: List[PianoEvent] = []  # For piano
        self.session_start_time: Optional[float] = None
        self.frame_count = 0
        self.video_path: Optional[str] = None
        self.json_path: Optional[str] = None

        # Piano calibration countdown state
        self.calibration_countdown_active = False
        self.calibration_countdown_start: Optional[float] = None
        self.CALIBRATION_COUNTDOWN_SECONDS = 5.0
        self._start_recording_after_calibration = True
        self.fps: float = 30.0  # Will be updated when webcam opens

    def _get_next_session_paths(self) -> tuple:
        """
        Get the next available session file paths for video and JSON.

        Naming scheme: [instrument]_session.ext, [instrument]_session1.ext, ...
        Ensures both video and JSON files use the same session number.

        Returns:
            Tuple of (video_path, json_path)
        """
        base_name = f"{self.instrument}_session"

        # Try without number first
        video_path = os.path.join(self.output_dir, f"{base_name}.mp4")
        json_path = os.path.join(self.output_dir, f"{base_name}.json")
        if not os.path.exists(video_path) and not os.path.exists(json_path):
            return video_path, json_path

        # Increment until we find an available pair
        counter = 1
        while True:
            video_path = os.path.join(self.output_dir, f"{base_name}{counter}.mp4")
            json_path = os.path.join(self.output_dir, f"{base_name}{counter}.json")
            if not os.path.exists(video_path) and not os.path.exists(json_path):
                return video_path, json_path
            counter += 1

    def _on_hit(self, hit: HitEvent):
        """Callback when drum hit is detected during recording."""
        if self.is_recording:
            self.session_hits.append(hit)

    def _on_strum(self, strum: StrumEvent):
        """Callback when guitar strum is detected during recording."""
        if self.is_recording:
            self.session_strums.append(strum)

    def _on_piano_hit(self, hit: PianoEvent):
        """Callback when piano hit is detected during recording."""
        if self.is_recording:
            self.session_piano_hits.append(hit)

    def _start_countdown(self, start_recording_after: bool = True):
        """
        Start 5-second countdown before recording.
        For piano: also calibrates hand positions.

        Args:
            start_recording_after: If True, start recording after countdown. If False, just recalibrate (piano only).
        """
        self.calibration_countdown_active = True
        self.calibration_countdown_start = time.time()
        self._start_recording_after_calibration = start_recording_after

        # Reset piano calibration if needed
        if self.instrument == "piano":
            self.classifier.reset_calibration()

        print("\n" + "=" * 50)
        print("GET READY!")
        print(f"Recording starts in {int(self.CALIBRATION_COUNTDOWN_SECONDS)} seconds...")
        if self.instrument == "piano":
            print("Position hands at piano boundaries")
        print("=" * 50 + "\n")

    def _check_calibration_countdown(self, frame) -> bool:
        """
        Check and update calibration countdown state.
        Works for all instruments - piano calibrates at end, others just start recording.

        Args:
            frame: Current video frame for drawing countdown

        Returns:
            True if countdown is still active, False if finished or not active
        """
        if not self.calibration_countdown_active:
            return False

        elapsed = time.time() - self.calibration_countdown_start
        remaining = self.CALIBRATION_COUNTDOWN_SECONDS - elapsed

        if remaining <= 0:
            # Countdown finished
            self.calibration_countdown_active = False

            # Piano needs calibration
            if self.instrument == "piano":
                if self.classifier.calibrate_now():
                    print("Piano calibrated successfully!")
                else:
                    print("Calibration failed - hands not detected. Try again.")
                    return False

            # Start recording for all instruments
            if self._start_recording_after_calibration:
                self._start_recording(frame, self.fps)

            return False

        # Draw semi-transparent overlay
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Large countdown number
        countdown_text = str(int(remaining) + 1)
        font_scale = 10.0
        thickness = 20
        (text_w, text_h), _ = cv2.getTextSize(
            countdown_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        text_x = (w - text_w) // 2
        text_y = (h + text_h) // 2

        cv2.putText(
            frame,
            countdown_text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness
        )

        # Draw instruction below based on instrument
        if self.instrument == "piano":
            instruction = "Position hands at piano edges"
        else:
            instruction = "GET READY!"
        inst_scale = 1.5
        (inst_w, _), _ = cv2.getTextSize(
            instruction, cv2.FONT_HERSHEY_SIMPLEX, inst_scale, 3
        )
        cv2.putText(
            frame,
            instruction,
            ((w - inst_w) // 2, h // 2 + 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            inst_scale,
            (0, 255, 255),
            3
        )

        return True

    def _start_recording(self, frame, fps: float):
        """Start a new recording session."""
        self.video_path, self.json_path = self._get_next_session_paths()

        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(
            self.video_path, fourcc, fps, (w, h)
        )

        self.is_recording = True
        self.session_hits = []
        self.session_strums = []
        self.session_piano_hits = []

        # Clear the appropriate log
        if self.instrument == "drums":
            self.classifier.clear_hit_log()
        elif self.instrument == "guitar":
            self.classifier.clear_strum_log()
        elif self.instrument == "piano":
            self.classifier.clear_hit_log()

        self.session_start_time = time.time()
        self.frame_count = 0

        print(f"\n{'='*50}")
        print(f"RECORDING STARTED")
        print(f"Instrument: {self.instrument}")
        if self.instrument in ["guitar", "piano"]:
            print(f"Key: {self.key}")
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
        elif self.instrument == "piano":
            self.classifier.save_hit_log(self.json_path)
            action_count = len(self.classifier.hit_log)
            action_name = "Hits"
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

    @staticmethod
    def prompt_key() -> str:
        """
        Prompt user to select a musical key.

        Returns:
            Selected key name (e.g., 'C Major', 'A Minor')
        """
        print("\n" + "=" * 50)
        print("KEY SELECTION")
        print("=" * 50)
        print("\nAvailable keys:")

        # Display in columns for readability
        for i, key in enumerate(AVAILABLE_KEYS, 1):
            suffix = " (default)" if key == DEFAULT_KEY else ""
            print(f"  {i:2}. {key}{suffix}")

        print("-" * 50)

        while True:
            try:
                choice = input(f"\nWhich key? [1-{len(AVAILABLE_KEYS)}]: ").strip()
                if choice == "":
                    return DEFAULT_KEY  # Default to C Major
                idx = int(choice) - 1
                if 0 <= idx < len(AVAILABLE_KEYS):
                    return AVAILABLE_KEYS[idx]
                print(f"Please enter a number between 1 and {len(AVAILABLE_KEYS)}")
            except ValueError:
                print("Please enter a valid number")

    @staticmethod
    def prompt_num_users() -> int:
        """
        Prompt user for number of players in the session.

        Returns:
            Number of players (1, 2, or 3)
        """
        print("\n" + "=" * 50)
        print("MULTI-PLAYER SESSION SETUP")
        print("=" * 50)
        print("\nHow many users will be playing?")
        print("  1. Single player (default)")
        print("  2. Two players")
        print("  3. Three players")
        print("-" * 50)

        while True:
            try:
                choice = input("\nNumber of users [1-3]: ").strip()
                if choice == "":
                    return 1
                num = int(choice)
                if 1 <= num <= 3:
                    return num
                print("Please enter 1, 2, or 3")
            except ValueError:
                print("Please enter a valid number")

    @staticmethod
    def prompt_instruments(num_users: int) -> List[str]:
        """
        Prompt user to select instruments for the session.

        For 3 players, all instruments are automatically assigned.
        For 2 players, user selects which melodic instrument to use.
        For 1 player, uses existing single instrument selection.

        Args:
            num_users: Number of players

        Returns:
            List of instruments in order of assignment
        """
        if num_users == 3:
            print("\n" + "=" * 50)
            print("INSTRUMENT ASSIGNMENT (3 PLAYERS)")
            print("=" * 50)
            print("\nWith 3 players, all instruments are used:")
            print("  - Drums (center position)")
            print("  - Guitar (position based on handedness)")
            print("  - Piano (position based on handedness)")
            print("-" * 50)
            return ["drums", "guitar", "piano"]

        elif num_users == 2:
            print("\n" + "=" * 50)
            print("INSTRUMENT SELECTION (2 PLAYERS)")
            print("=" * 50)
            print("\nWith 2 players:")
            print("  - Left player: Drums")
            print("  - Right player: Choose below")
            print("\nWhich melodic instrument for the right player?")
            print("  1. Guitar (default)")
            print("  2. Piano")
            print("-" * 50)

            while True:
                try:
                    choice = input("\nSelect [1-2]: ").strip()
                    if choice == "" or choice == "1":
                        return ["drums", "guitar"]
                    if choice == "2":
                        return ["drums", "piano"]
                    print("Please enter 1 or 2")
                except ValueError:
                    print("Please enter a valid number")

        else:  # Single player
            # Use existing single instrument prompt
            instrument = WebcamRecorder.prompt_instrument()
            return [instrument]

    @staticmethod
    def prompt_guitar_handedness() -> str:
        """
        Prompt for guitar player's handedness.

        This affects role assignment for multi-player sessions:
        - Right-handed: Guitarist on the right, Pianist on the left
        - Left-handed: Guitarist on the left, Pianist on the right

        Returns:
            "right" or "left"
        """
        print("\n" + "=" * 50)
        print("GUITAR PLAYER HANDEDNESS")
        print("=" * 50)
        print("\nIs the guitar player right-handed or left-handed?")
        print("  1. Right-handed (default)")
        print("  2. Left-handed")
        print("\nThis affects position assignment:")
        print("  - Right-handed: Guitarist on RIGHT, Pianist on LEFT")
        print("  - Left-handed: Guitarist on LEFT, Pianist on RIGHT")
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
        - 'p': Recalibrate piano (piano mode only)
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
                key=self.key,
                model_complexity=1,
                on_strum_callback=self._on_strum
            )
        elif self.instrument == "piano":
            self.classifier = PianoClassifier(
                key=self.key,
                model_complexity=1,
                on_hit_callback=self._on_piano_hit
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
        if self.instrument in ["guitar", "piano"]:
            print(f"Key: {self.key}")

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
            print(f"  Zone:    {fret_hand.capitalize()} hand position (7 zones = 7 chord roots)")
            print("\nAuto-calibrates on first frame with both hands visible.")
            print("Strum intensity is tracked for volume control.")
            print("\nControls:")
            print("  'r' or 's' - Start/Stop recording")
            print("  'q' - Quit")
            print("  'c' - Clear strum log")
            print("  'g' - Recalibrate zone position")
        elif self.instrument == "piano":
            print("\nPiano Actions:")
            print("  Right Hand: Determines chord (7 zones = 7 chords)")
            print("  Left Hand:  Plays bass root note (zone = octave)")
            print("\nCalibration: 3-second countdown when you press 'r'")
            print("Position hands at LEFT and RIGHT edges of your virtual piano.")
            print("Hit upward (lift hands) to trigger notes.")
            print("\nControls:")
            print("  'r' or 's' - Start/Stop recording (with 3s calibration)")
            print("  'q' - Quit")
            print("  'c' - Clear hit log")
            print("  'p' - Recalibrate piano")

        print("=" * 50 + "\n")

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open webcam")
            return

        # Get actual FPS from camera, default to 30 if not available
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0:
            self.fps = 30.0

        print("Starting webcam feed...")
        print("Press 'r' for 5-second countdown, then recording starts\n")

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

            # Handle countdown for all instruments
            if self._check_calibration_countdown(frame):
                # During countdown, show frame and continue
                window_name = f'{self.instrument.capitalize()} Classifier'
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                continue

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
                elif self.instrument == "piano":
                    action_count = len(self.classifier.hit_log)
                    action_name = "hits"
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
                    "READY - Press 'r' for countdown",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            # Draw instructions at bottom
            h = frame.shape[0]
            if self.instrument == "guitar":
                instruction_text = "GUITAR | 'r'=record 's'=stop 'g'=recalibrate 'q'=quit"
            elif self.instrument == "piano":
                instruction_text = "PIANO | 'r'=record 's'=stop 'p'=recalibrate 'q'=quit"
            else:
                instruction_text = "DRUMS | 'r'=record 's'=stop 'q'=quit"

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
                if not self.is_recording and not self.calibration_countdown_active:
                    # All instruments use 5-second countdown
                    self._start_countdown()
            elif key == ord('s'):
                if self.is_recording:
                    self._stop_recording()
            elif key == ord('c'):
                # Clear the appropriate log
                if self.instrument == "drums":
                    self.classifier.clear_hit_log()
                elif self.instrument == "guitar":
                    self.classifier.clear_strum_log()
                elif self.instrument == "piano":
                    self.classifier.clear_hit_log()
            elif key == ord('g') and self.instrument == "guitar":
                # Recalibrate guitar
                self.classifier.reset_calibration()
            elif key == ord('p') and self.instrument == "piano":
                # Recalibrate piano with countdown (no recording)
                if not self.calibration_countdown_active and not self.is_recording:
                    self._start_countdown(start_recording_after=False)

        # Cleanup
        if self.is_recording:
            self._stop_recording()

        cap.release()
        cv2.destroyAllWindows()
        self.classifier.close()
        print("\nSession ended")


def main():
    """Main entry point with instrument, dexterity, and key selection."""
    # First, ask how many users
    num_users = WebcamRecorder.prompt_num_users()
    print(f"\nPlayers: {num_users}")

    if num_users == 1:
        # Single player mode - existing flow
        instruments = WebcamRecorder.prompt_instruments(num_users)
        instrument = instruments[0]
        print(f"\nSelected: {instrument.upper()}")

        # Prompt for dexterity
        dominant_hand = WebcamRecorder.prompt_dexterity()
        print(f"\nDominant hand: {dominant_hand.upper()}")

        # Prompt for key (only for guitar and piano)
        if instrument in ["guitar", "piano"]:
            key = WebcamRecorder.prompt_key()
            print(f"\nKey: {key}")
        else:
            key = DEFAULT_KEY

        recorder = WebcamRecorder(
            output_dir="output",
            instrument=instrument,
            dominant_hand=dominant_hand,
            key=key
        )
        recorder.run()

    else:
        # Multi-player mode
        run_multi_player_session(num_users)


def run_multi_player_session(num_users: int):
    """
    Run a multi-player session with the specified number of users.

    Args:
        num_users: Number of players (2 or 3)
    """
    from multi_person import get_session_manager, RoleAssigner
    from multi_person.yolo_detector import is_yolo_available
    MultiSessionManager = get_session_manager()

    # Check YOLO availability
    if not is_yolo_available():
        print("\n" + "=" * 50)
        print("WARNING: Multi-person detection requires YOLO")
        print("Install with: pip install ultralytics")
        print("Falling back to single-player mode...")
        print("=" * 50)
        main()  # Restart with single player
        return

    # Prompt for instruments
    instruments = WebcamRecorder.prompt_instruments(num_users)
    print(f"\nInstruments: {', '.join(i.upper() for i in instruments)}")

    # Prompt for guitar handedness if guitar is involved
    guitar_handedness = "right"
    if "guitar" in instruments and num_users > 1:
        guitar_handedness = WebcamRecorder.prompt_guitar_handedness()
        print(f"\nGuitar handedness: {guitar_handedness.upper()}")

    # Prompt for dexterity (for single dominant hand setting)
    dominant_hand = WebcamRecorder.prompt_dexterity()
    print(f"\nDefault dominant hand: {dominant_hand.upper()}")

    # Prompt for key if any melodic instrument
    if "guitar" in instruments or "piano" in instruments:
        key = WebcamRecorder.prompt_key()
        print(f"\nMusical key: {key}")
    else:
        key = DEFAULT_KEY

    # Create session config
    config = SessionConfig(
        num_players=num_users,
        instruments=instruments,
        guitar_handedness=guitar_handedness,
        key=key
    )

    # Show role assignment preview
    assigner = RoleAssigner(num_users, instruments, guitar_handedness)
    print("\n" + "=" * 50)
    print("ROLE ASSIGNMENT PREVIEW")
    print("=" * 50)
    print(assigner.describe_roles())
    print("=" * 50)

    # Instructions
    print("\n" + "=" * 50)
    print("MULTI-PLAYER SESSION")
    print("=" * 50)
    print(f"\nPlayers: {num_users}")
    print(f"Instruments: {', '.join(i.upper() for i in instruments)}")
    print(f"Key: {key}")
    print("\nInstructions:")
    print("  1. All players stand in position (sorted left to right)")
    print("  2. Press 'r' for 5-second countdown (auto-calibrates + starts recording)")
    print("  3. Roles will be locked based on x-position")
    print("  4. Optional: Press 'c' for manual calibration before recording")
    print("  5. Press 's' to stop recording")
    print("  6. Press 'q' to quit")
    print("=" * 50 + "\n")

    # Initialize session manager
    session_manager = MultiSessionManager(config)
    session_manager.initialize_classifiers()

    # Run multi-player loop
    _run_multi_player_loop(session_manager, config)


def _draw_countdown_overlay(frame, seconds_remaining: int):
    """Draw large centered countdown number on frame for multi-player mode."""
    h, w = frame.shape[:2]

    # Semi-transparent dark overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Large countdown number
    text = str(seconds_remaining)
    font_scale = 10.0
    thickness = 20
    (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    cv2.putText(frame, text, ((w - text_w) // 2, (h + text_h) // 2),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)

    # Instruction text below
    instruction = "GET IN POSITION!"
    inst_scale = 1.5
    (inst_w, _), _ = cv2.getTextSize(instruction, cv2.FONT_HERSHEY_SIMPLEX, inst_scale, 3)
    cv2.putText(frame, instruction, ((w - inst_w) // 2, h // 2 + 120),
                cv2.FONT_HERSHEY_SIMPLEX, inst_scale, (0, 255, 255), 3)


def _run_multi_player_loop(session_manager, config: SessionConfig):
    """
    Main loop for multi-player session.

    Args:
        session_manager: MultiSessionManager instance
        config: Session configuration
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    # Recording state
    is_recording = False
    session_start_time = None
    frame_count = 0
    video_writer = None
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Countdown state
    countdown_active = False
    countdown_start_time = 0.0
    COUNTDOWN_SECONDS = 5.0

    print("Starting webcam feed...")
    print("Press 'r' for 5-second countdown, then recording starts")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break

        current_time = time.time()

        # Process frame
        events = session_manager.process_frame(frame, current_time)

        # Draw overlay
        session_manager.draw_overlay(frame)

        # Handle countdown
        h, w = frame.shape[:2]
        if countdown_active:
            elapsed = time.time() - countdown_start_time
            remaining = COUNTDOWN_SECONDS - elapsed

            if remaining <= 0:
                # Countdown finished
                countdown_active = False

                # Auto-calibrate if needed
                if session_manager.awaiting_calibration:
                    persons = session_manager.tracker.last_persons
                    if len(persons) == config.num_players:
                        session_manager.calibrate_roles(persons)
                        session_manager.lock_roles()
                        print("Roles auto-calibrated!")

                # Start recording if calibration complete
                if session_manager.calibration_complete:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_path = os.path.join(output_dir, f"multi_session_{timestamp}.mp4")
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    video_writer = cv2.VideoWriter(video_path, fourcc, fps, (w, h))
                    is_recording = True
                    session_start_time = time.time()
                    frame_count = 0
                    session_manager.clear_events()
                    print(f"Recording started: {video_path}")
                else:
                    print("Calibration failed - not enough players detected")
            else:
                # Draw countdown overlay and continue
                _draw_countdown_overlay(frame, int(remaining) + 1)
                cv2.imshow('Multi-Player Session', frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                continue

        # Draw calibration/status indicator
        if session_manager.awaiting_calibration:
            cv2.putText(
                frame,
                "WAITING - Press 'r' to start (5s countdown + auto-calibrate)",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )

            # Show number of detected persons
            num_detected = len(session_manager.tracker.last_persons)
            status_color = (0, 255, 0) if num_detected == config.num_players else (0, 165, 255)
            cv2.putText(
                frame,
                f"Detected: {num_detected}/{config.num_players} players",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                status_color,
                2
            )
        elif is_recording:
            # Recording indicator
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

            elapsed = time.time() - session_start_time
            total_events = sum(len(e) for e in events.values())
            cv2.putText(
                frame,
                f"{elapsed:.1f}s | {frame_count} frames | {total_events} events",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1
            )

            video_writer.write(frame)
            frame_count += 1
        else:
            cv2.putText(
                frame,
                "READY - Press 'r' to record",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

        # Draw multi-player status at bottom
        status_text = f"MULTI-PLAYER | {config.num_players} users | 'r'=start 's'=stop 'q'=quit"
        cv2.putText(
            frame,
            status_text,
            (10, h - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1
        )

        cv2.imshow('Multi-Player Session', frame)

        # Handle key presses
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        elif key == ord('c'):
            # Calibrate roles
            if session_manager.awaiting_calibration:
                persons = session_manager.tracker.last_persons
                if len(persons) == config.num_players:
                    if session_manager.calibrate_roles(persons):
                        session_manager.lock_roles()
                        print("\nRoles calibrated and locked!")
                        print(session_manager.describe_session())
                    else:
                        print("Calibration failed - ensure all players are visible")
                else:
                    print(f"Need {config.num_players} players, detected {len(persons)}")

        elif key == ord('r'):
            if not is_recording and not countdown_active:
                # Start 5-second countdown (will auto-calibrate and record)
                countdown_active = True
                countdown_start_time = time.time()
                print("\n5-second countdown - get in position!")

        elif key == ord('s'):
            if is_recording:
                # Stop recording
                is_recording = False
                if video_writer:
                    video_writer.release()
                    video_writer = None

                # Save per-player events
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                _save_multi_player_session(session_manager, output_dir, timestamp, config)

                print("\nRecording stopped")

        elif key == ord('u'):
            # Unlock roles for reassignment
            if session_manager.role_locked:
                session_manager.unlock_roles()
                print("Roles unlocked - will reassign on next calibration")

    # Cleanup
    if is_recording and video_writer:
        video_writer.release()

    cap.release()
    cv2.destroyAllWindows()
    session_manager.close()
    print("\nMulti-player session ended")


def _save_multi_player_session(session_manager, output_dir: str, timestamp: str, config: SessionConfig):
    """
    Save per-player session data to JSON files.

    Args:
        session_manager: MultiSessionManager with recorded events
        output_dir: Directory to save files
        timestamp: Timestamp string for filename
        config: Session configuration
    """
    # Create session directory
    session_dir = os.path.join(output_dir, f"session_{timestamp}")
    os.makedirs(session_dir, exist_ok=True)

    # Save session config
    config_path = os.path.join(session_dir, "session_config.json")
    with open(config_path, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)
    print(f"Session config saved: {config_path}")

    # Save per-player events
    all_events = session_manager.get_all_events()
    for player_id, state in session_manager.players.items():
        events = state.events
        instrument = state.instrument

        # Convert events to serializable format
        event_data = []
        for event in events:
            if hasattr(event, '__dict__'):
                event_dict = {k: v for k, v in event.__dict__.items()
                             if not k.startswith('_')}
                event_data.append(event_dict)

        player_data = {
            "player_id": player_id,
            "instrument": instrument,
            "position_index": state.position_index,
            "total_events": len(event_data),
            "events": event_data
        }

        filename = f"player{player_id}_{instrument}.json"
        filepath = os.path.join(session_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(player_data, f, indent=2, default=str)
        print(f"Player {player_id} ({instrument}): {len(event_data)} events -> {filename}")


if __name__ == "__main__":
    main()
