"use client";

import { useState, useCallback, useRef, useEffect } from "react";

interface UseMediaRecorderReturn {
  isRecording: boolean;
  blob: Blob | null;
  duration: number;
  startRecording: () => void;
  stopRecording: () => void;
  resetRecording: () => void;
}

export function useMediaRecorder(
  stream: MediaStream | null
): UseMediaRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [duration, setDuration] = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRecording = useCallback(() => {
    if (!stream || isRecording) return;

    chunksRef.current = [];
    setBlob(null);
    setDuration(0);

    const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
      ? "video/webm;codecs=vp9"
      : "video/webm";

    const recorder = new MediaRecorder(stream, { mimeType });

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data);
      }
    };

    recorder.onstop = () => {
      const recordedBlob = new Blob(chunksRef.current, { type: mimeType });
      setBlob(recordedBlob);
      setIsRecording(false);

      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }
    };

    recorder.start(1000);
    recorderRef.current = recorder;
    startTimeRef.current = Date.now();
    setIsRecording(true);

    durationIntervalRef.current = setInterval(() => {
      setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
  }, [stream, isRecording]);

  const stopRecording = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  }, []);

  const resetRecording = useCallback(() => {
    setBlob(null);
    setDuration(0);
    chunksRef.current = [];
  }, []);

  useEffect(() => {
    return () => {
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
      }
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
    };
  }, []);

  return {
    isRecording,
    blob,
    duration,
    startRecording,
    stopRecording,
    resetRecording,
  };
}
