"use client";

import { useEffect, useReducer, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "motion/react";
import { useWebcam } from "@/hooks/use-webcam";
import { useMediaRecorder } from "@/hooks/use-media-recorder";
import { useConfig } from "@/contexts/config-context";
import { WebcamView } from "./WebcamView";
import { PreRecordingOverlay } from "./PreRecordingOverlay";
import { CountdownOverlay } from "./CountdownOverlay";
import { RecordingOverlay } from "./RecordingOverlay";
import { LoadingOverlay } from "./LoadingOverlay";

type RecordingStatus =
  | "idle"
  | "pre-recording"
  | "countdown"
  | "recording"
  | "uploading"
  | "error";

interface RecordingState {
  status: RecordingStatus;
  countdownValue: number;
  error: Error | null;
}

type RecordingAction =
  | { type: "WEBCAM_READY" }
  | { type: "START_COUNTDOWN" }
  | { type: "COUNTDOWN_TICK" }
  | { type: "START_RECORDING" }
  | { type: "STOP_RECORDING" }
  | { type: "UPLOAD_STARTED" }
  | { type: "UPLOAD_COMPLETE" }
  | { type: "ERROR"; error: Error };

const initialState: RecordingState = {
  status: "idle",
  countdownValue: 5,
  error: null,
};

function recordingReducer(
  state: RecordingState,
  action: RecordingAction
): RecordingState {
  switch (action.type) {
    case "WEBCAM_READY":
      return { ...state, status: "pre-recording" };

    case "START_COUNTDOWN":
      return { ...state, status: "countdown", countdownValue: 5 };

    case "COUNTDOWN_TICK":
      const newValue = state.countdownValue - 1;
      if (newValue <= 0) {
        return { ...state, status: "recording", countdownValue: 0 };
      }
      return { ...state, countdownValue: newValue };

    case "START_RECORDING":
      return { ...state, status: "recording" };

    case "STOP_RECORDING":
      return { ...state, status: "uploading" };

    case "UPLOAD_STARTED":
      return { ...state, status: "uploading" };

    case "UPLOAD_COMPLETE":
      return { ...state, status: "idle" };

    case "ERROR":
      return { ...state, status: "error", error: action.error };

    default:
      return state;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:3001";

export function RecordingClient() {
  const router = useRouter();
  const { config, setSessionResult } = useConfig();
  const [state, dispatch] = useReducer(recordingReducer, initialState);

  const {
    stream,
    error: webcamError,
    isLoading: webcamLoading,
    hasPermission,
    requestPermission,
  } = useWebcam();

  const {
    isRecording,
    blob,
    duration,
    startRecording,
    stopRecording,
  } = useMediaRecorder(stream);

  // Request webcam permission on mount
  useEffect(() => {
    requestPermission();
  }, [requestPermission]);

  // Transition to pre-recording when webcam is ready
  useEffect(() => {
    if (hasPermission && state.status === "idle") {
      dispatch({ type: "WEBCAM_READY" });
    }
  }, [hasPermission, state.status]);

  // Handle countdown timer
  useEffect(() => {
    if (state.status !== "countdown") return;

    const timer = setInterval(() => {
      dispatch({ type: "COUNTDOWN_TICK" });
    }, 1000);

    return () => clearInterval(timer);
  }, [state.status]);

  // Start MediaRecorder when countdown finishes
  useEffect(() => {
    if (state.status === "recording" && !isRecording) {
      startRecording();
    }
  }, [state.status, isRecording, startRecording]);

  // Handle upload when recording stops
  useEffect(() => {
    if (state.status === "uploading" && blob) {
      uploadRecording(blob);
    }
  }, [state.status, blob]);

  const handleStartCountdown = useCallback(() => {
    dispatch({ type: "START_COUNTDOWN" });
  }, []);

  const handleStopRecording = useCallback(() => {
    stopRecording();
    dispatch({ type: "STOP_RECORDING" });
  }, [stopRecording]);

  const uploadRecording = async (videoBlob: Blob) => {
    try {
      // Health check: verify API server is running before upload
      try {
        const healthCheck = await fetch(`${API_BASE}/api/health`, {
          method: "GET",
          signal: AbortSignal.timeout(3000),
        });
        if (!healthCheck.ok) {
          throw new Error("API server is not responding");
        }
      } catch {
        throw new Error(
          "Cannot connect to API server. Please ensure the backend is running (python api/server.py)."
        );
      }

      const formData = new FormData();
      formData.append("video", videoBlob, "recording.webm");

      const [keyNote, keyMode] = config.musicalKey.split(" ");

      const sessionConfig = {
        playerCount: config.numUsers,
        players: config.instruments.map((inst) => ({
          instrument: inst,
          hand: config.handedness[inst as keyof typeof config.handedness] || "right",
        })),
        bpm: 120,
        keyNote: keyNote || "C",
        keyMode: keyMode || "Major",
      };

      formData.append("config", JSON.stringify(sessionConfig));

      const response = await fetch(`${API_BASE}/api/generate-music`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      // Parse response and store session result
      const result = await response.json();
      setSessionResult({
        audioUrl: result.audioUrl,
        videoUrl: result.videoUrl,
        duration: result.duration,
      });

      dispatch({ type: "UPLOAD_COMPLETE" });

      // Navigate to vocals page if enabled, otherwise loading page
      if (config.includeVocals) {
        router.push("/vocals");
      } else {
        router.push("/loading");
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Upload failed");
      dispatch({ type: "ERROR", error });
    }
  };

  // Handle webcam error
  if (webcamError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#232323] text-[#eeeeee]">
        <h2 className="mb-4 text-2xl font-bold text-red-500">
          Camera Access Required
        </h2>
        <p className="mb-6 max-w-md text-center text-[#eeeeee]/70">
          Please allow camera access to use the recording feature. Check your
          browser settings and try again.
        </p>
        <button
          onClick={requestPermission}
          className="rounded-lg bg-[#d51bdb] px-6 py-3 font-semibold text-white transition-colors hover:bg-[#d51bdb]/80"
        >
          Try Again
        </button>
      </div>
    );
  }

  // Handle state error
  if (state.error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#232323] text-[#eeeeee]">
        <h2 className="mb-4 text-2xl font-bold text-red-500">
          Something went wrong
        </h2>
        <p className="mb-6 max-w-md text-center text-[#eeeeee]/70">
          {state.error.message}
        </p>
        <button
          onClick={() => router.push("/config")}
          className="rounded-lg bg-[#7bd2ff] px-6 py-3 font-semibold text-black transition-colors hover:bg-[#7bd2ff]/80"
        >
          Back to Configuration
        </button>
      </div>
    );
  }

  // Loading state while waiting for webcam
  if (webcamLoading || state.status === "idle") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#232323] text-[#eeeeee]">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-[#d51bdb] border-t-transparent" />
        <p className="mt-4 text-[#eeeeee]/70">Initializing camera...</p>
      </div>
    );
  }

  const shouldBlur = state.status === "pre-recording";
  const shouldShowPose = state.status === "recording" || state.status === "countdown";

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#232323]">
      {/* Webcam feed (full screen background) */}
      <WebcamView
        stream={stream}
        blur={shouldBlur}
        showPose={shouldShowPose}
        config={{
          instruments: config.instruments,
          musicalKey: config.musicalKey,
        }}
        isRecording={state.status === "recording"}
        duration={duration}
        className="absolute inset-0"
      />

      {/* Pre-recording overlay with guidelines */}
      <AnimatePresence>
        {state.status === "pre-recording" && (
          <PreRecordingOverlay onStart={handleStartCountdown} />
        )}
      </AnimatePresence>

      {/* Countdown overlay */}
      <AnimatePresence>
        {state.status === "countdown" && (
          <CountdownOverlay value={state.countdownValue} />
        )}
      </AnimatePresence>

      {/* Recording overlay with controls */}
      <AnimatePresence>
        {state.status === "recording" && (
          <RecordingOverlay duration={duration} onStop={handleStopRecording} />
        )}
      </AnimatePresence>

      {/* Loading overlay during upload */}
      <AnimatePresence>
        {state.status === "uploading" && (
          <LoadingOverlay message="Uploading your performance..." />
        )}
      </AnimatePresence>
    </main>
  );
}
