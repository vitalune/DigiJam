"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface UseWebcamReturn {
  stream: MediaStream | null;
  error: Error | null;
  isLoading: boolean;
  hasPermission: boolean;
  requestPermission: () => Promise<void>;
  stopStream: () => void;
}

export function useWebcam(): UseWebcamReturn {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasPermission, setHasPermission] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setStream(null);
      setHasPermission(false);
    }
  }, []);

  const requestPermission = useCallback(async () => {
    if (streamRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: "user",
        },
        audio: true,
      });

      streamRef.current = mediaStream;
      setStream(mediaStream);
      setHasPermission(true);
    } catch (err) {
      const error =
        err instanceof Error ? err : new Error("Failed to access webcam");
      setError(error);
      setHasPermission(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  return {
    stream,
    error,
    isLoading,
    hasPermission,
    requestPermission,
    stopStream,
  };
}
