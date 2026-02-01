"""
Real-time microphone recording for vocals.

Uses sounddevice for audio capture in a separate thread to avoid
blocking the main pose detection loop. Supports playing background
instrumental during recording.
"""

import threading
import queue
import numpy as np
import sounddevice as sd
import soundfile as sf
from typing import Optional, Union
from pathlib import Path

from .vocal_config import RecordingConfig


class VocalRecorder:
    """Records audio from microphone with optional background instrumental playback."""

    def __init__(self, config: Optional[RecordingConfig] = None):
        """
        Initialize the vocal recorder.

        Args:
            config: Recording configuration. Uses defaults if not provided.
        """
        self.config = config or RecordingConfig()
        self._audio_queue: queue.Queue = queue.Queue()
        self._recording_thread: Optional[threading.Thread] = None
        self._is_recording: bool = False
        self._recorded_audio: Optional[np.ndarray] = None
        self._stream: Optional[sd.InputStream] = None

        # Background playback
        self._instrumental_data: Optional[np.ndarray] = None
        self._instrumental_sr: int = 44100
        self._playback_stream: Optional[sd.OutputStream] = None
        self._playback_position: int = 0
        self._playback_lock: threading.Lock = threading.Lock()

    def load_instrumental(self, filepath: Union[str, Path]) -> float:
        """
        Load an instrumental file for background playback.

        Args:
            filepath: Path to the instrumental audio file

        Returns:
            Duration of the instrumental in seconds
        """
        self._instrumental_data, self._instrumental_sr = sf.read(filepath, dtype='float32')

        # Convert to mono if stereo
        if len(self._instrumental_data.shape) > 1:
            self._instrumental_data = self._instrumental_data.mean(axis=1)

        duration = len(self._instrumental_data) / self._instrumental_sr
        print(f"Loaded instrumental: {filepath} ({duration:.2f}s)")
        return duration

    def _playback_callback(self, outdata: np.ndarray, frames: int,
                           time_info, status) -> None:
        """Callback for instrumental playback."""
        if status:
            print(f"Playback status: {status}")

        with self._playback_lock:
            if self._instrumental_data is None:
                outdata.fill(0)
                return

            end_pos = self._playback_position + frames
            data_len = len(self._instrumental_data)

            if self._playback_position >= data_len:
                # Instrumental ended, fill with silence
                outdata.fill(0)
            elif end_pos > data_len:
                # Partial data at the end
                valid_frames = data_len - self._playback_position
                outdata[:valid_frames, 0] = self._instrumental_data[self._playback_position:data_len]
                outdata[valid_frames:, 0] = 0
                self._playback_position = data_len
            else:
                outdata[:, 0] = self._instrumental_data[self._playback_position:end_pos]
                self._playback_position = end_pos

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info, status) -> None:
        """Callback function called by sounddevice for each audio chunk."""
        if status:
            print(f"Recording status: {status}")
        self._audio_queue.put(indata.copy())

    def _recording_worker(self) -> None:
        """Background thread that collects audio from the queue."""
        chunks = []
        while self._is_recording or not self._audio_queue.empty():
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                chunks.append(chunk)
            except queue.Empty:
                continue

        if chunks:
            self._recorded_audio = np.concatenate(chunks, axis=0)
        else:
            self._recorded_audio = np.array([], dtype=self.config.dtype)

    def start_recording(self, play_instrumental: bool = True) -> None:
        """
        Start recording audio from the microphone.

        Args:
            play_instrumental: If True and instrumental is loaded, play it during recording
        """
        if self._is_recording:
            raise RuntimeError("Already recording")

        self._is_recording = True
        self._recorded_audio = None
        self._playback_position = 0

        # Clear the queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        # Start the collection thread
        self._recording_thread = threading.Thread(target=self._recording_worker)
        self._recording_thread.start()

        # Start instrumental playback if loaded and requested
        if play_instrumental and self._instrumental_data is not None:
            self._playback_stream = sd.OutputStream(
                samplerate=self._instrumental_sr,
                channels=1,
                dtype='float32',
                blocksize=self.config.chunk_size,
                callback=self._playback_callback
            )
            self._playback_stream.start()
            print("Playing instrumental...")

        # Start the recording stream
        self._stream = sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype=self.config.dtype,
            blocksize=self.config.chunk_size,
            callback=self._audio_callback
        )
        self._stream.start()
        print("Recording started. Press Enter to stop...")

    def stop_recording(self) -> np.ndarray:
        """
        Stop recording and return the recorded audio.

        Returns:
            numpy array of recorded audio samples
        """
        if not self._is_recording:
            raise RuntimeError("Not recording")

        self._is_recording = False

        # Stop the playback stream
        if self._playback_stream:
            self._playback_stream.stop()
            self._playback_stream.close()
            self._playback_stream = None
            print("Playback stopped.")

        # Stop the recording stream
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Wait for the collection thread to finish
        if self._recording_thread:
            self._recording_thread.join()
            self._recording_thread = None

        print(f"Recording stopped. Duration: {self.get_duration():.2f}s")
        return self._recorded_audio if self._recorded_audio is not None else np.array([])

    def save_recording(self, filepath: str) -> None:
        """
        Save the recorded audio to a file.

        Args:
            filepath: Path to save the audio file (WAV format)
        """
        if self._recorded_audio is None or len(self._recorded_audio) == 0:
            raise RuntimeError("No audio recorded")

        sf.write(filepath, self._recorded_audio, self.config.sample_rate)
        print(f"Saved recording to: {filepath}")

    def get_duration(self) -> float:
        """
        Get the duration of the recorded audio in seconds.

        Returns:
            Duration in seconds, or 0 if no audio recorded
        """
        if self._recorded_audio is None or len(self._recorded_audio) == 0:
            return 0.0
        return len(self._recorded_audio) / self.config.sample_rate

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    @property
    def audio_data(self) -> Optional[np.ndarray]:
        """Get the recorded audio data."""
        return self._recorded_audio

    @property
    def has_instrumental(self) -> bool:
        """Check if an instrumental is loaded."""
        return self._instrumental_data is not None
