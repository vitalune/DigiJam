"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { usePoseDetector } from "@/hooks/use-pose-detector";
import { useHitDetector } from "@/hooks/use-hit-detector";
import { PoseOverlay } from "@/components/ui/pose-overlay";

interface SessionConfig {
  instruments: string[];
  musicalKey: string;
}

interface WebcamViewProps {
  stream: MediaStream | null;
  blur?: boolean;
  showPose?: boolean;
  config?: SessionConfig;
  isRecording?: boolean;
  duration?: number;
  className?: string;
}

export function WebcamView({
  stream,
  blur = false,
  showPose = false,
  config,
  isRecording = false,
  duration = 0,
  className,
}: WebcamViewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [mounted, setMounted] = useState(false);

  const { poses, isLoading: poseLoading } = usePoseDetector(videoRef, showPose);
  const hitFeedback = useHitDetector(
    poses,
    config?.instruments || [],
    showPose && isRecording
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  if (!mounted) {
    return (
      <div className={cn("w-full h-full bg-[#232323]", className)} />
    );
  }

  return (
    <div className={cn("relative w-full h-full", className)}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={cn(
          "w-full h-full object-cover",
          blur && "blur-lg scale-105"
        )}
      />
      {showPose && !poseLoading && (
        <PoseOverlay
          videoRef={videoRef}
          poses={poses}
          config={config}
          isRecording={isRecording}
          duration={duration}
          hitFeedback={hitFeedback}
        />
      )}
    </div>
  );
}
