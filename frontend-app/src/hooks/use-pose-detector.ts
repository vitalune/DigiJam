"use client";

import { useEffect, useRef, useState, useCallback, RefObject } from "react";
import { PoseLandmarker, FilesetResolver, PoseLandmarkerResult } from "@mediapipe/tasks-vision";
import { Pose, PoseLandmark } from "@/lib/pose-constants";

interface UsePoseDetectorResult {
  poses: Pose[];
  isLoading: boolean;
  error: Error | null;
}

const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
const WASM_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm";

export function usePoseDetector(
  videoRef: RefObject<HTMLVideoElement | null>,
  enabled: boolean = true
): UsePoseDetectorResult {
  const [poses, setPoses] = useState<Pose[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const poseLandmarkerRef = useRef<PoseLandmarker | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastVideoTimeRef = useRef<number>(-1);

  // Initialize MediaPipe PoseLandmarker
  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }

    let isMounted = true;

    async function initializePoseLandmarker() {
      try {
        setIsLoading(true);
        setError(null);

        const vision = await FilesetResolver.forVisionTasks(WASM_URL);

        const poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: MODEL_URL,
            delegate: "GPU",
          },
          runningMode: "VIDEO",
          numPoses: 3, // Support up to 3 players
        });

        if (isMounted) {
          poseLandmarkerRef.current = poseLandmarker;
          setIsLoading(false);
        } else {
          poseLandmarker.close();
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err : new Error("Failed to initialize pose detector"));
          setIsLoading(false);
        }
      }
    }

    initializePoseLandmarker();

    return () => {
      isMounted = false;
      if (poseLandmarkerRef.current) {
        poseLandmarkerRef.current.close();
        poseLandmarkerRef.current = null;
      }
    };
  }, [enabled]);

  // Convert MediaPipe result to our Pose format
  const convertResult = useCallback((result: PoseLandmarkerResult): Pose[] => {
    return result.landmarks.map((landmarks, index) => ({
      landmarks: landmarks.map((lm) => ({
        x: lm.x,
        y: lm.y,
        z: lm.z,
        visibility: lm.visibility ?? 1,
      })) as PoseLandmark[],
      worldLandmarks: result.worldLandmarks[index]?.map((lm) => ({
        x: lm.x,
        y: lm.y,
        z: lm.z,
        visibility: lm.visibility ?? 1,
      })) as PoseLandmark[],
    }));
  }, []);

  // Run pose detection on each animation frame
  useEffect(() => {
    if (!enabled || isLoading || error) {
      return;
    }

    const video = videoRef.current;
    const poseLandmarker = poseLandmarkerRef.current;

    if (!video || !poseLandmarker) {
      return;
    }

    function detectPose() {
      const video = videoRef.current;
      const poseLandmarker = poseLandmarkerRef.current;

      if (!video || !poseLandmarker) {
        return;
      }

      // Only run detection when video has new data
      if (video.readyState >= 2 && video.currentTime !== lastVideoTimeRef.current) {
        lastVideoTimeRef.current = video.currentTime;

        const startTimeMs = performance.now();
        const result = poseLandmarker.detectForVideo(video, startTimeMs);

        if (result.landmarks.length > 0) {
          setPoses(convertResult(result));
        } else {
          setPoses([]);
        }
      }

      animationFrameRef.current = requestAnimationFrame(detectPose);
    }

    animationFrameRef.current = requestAnimationFrame(detectPose);

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [enabled, isLoading, error, videoRef, convertResult]);

  // Clear poses when disabled
  useEffect(() => {
    if (!enabled) {
      setPoses([]);
    }
  }, [enabled]);

  return { poses, isLoading, error };
}
