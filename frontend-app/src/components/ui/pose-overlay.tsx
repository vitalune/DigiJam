"use client";

import { useEffect, useRef, RefObject } from "react";
import {
  Pose,
  PoseLandmark,
  POSE_LANDMARKS,
  POSE_CONNECTIONS,
  POSE_COLORS,
  POSE_CONFIG,
} from "@/lib/pose-constants";

interface SessionConfig {
  instruments: string[];
  musicalKey: string;
}

interface HitFeedback {
  recentAction?: string;
  hitCount: number;
}

interface PoseOverlayProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  poses: Pose[];
  config?: SessionConfig;
  isRecording?: boolean;
  duration?: number;
  hitFeedback?: HitFeedback[];
}

interface DrawingDimensions {
  drawWidth: number;
  drawHeight: number;
  offsetX: number;
  offsetY: number;
  displayWidth: number;
  displayHeight: number;
}

/**
 * Calculate dimensions for mapping normalized pose coordinates to screen coordinates.
 * Handles object-cover scaling where video may be cropped to fill container.
 */
function getVideoDrawingDimensions(video: HTMLVideoElement): DrawingDimensions | null {
  // Get actual video stream dimensions (intrinsic)
  const videoWidth = video.videoWidth;
  const videoHeight = video.videoHeight;

  if (videoWidth === 0 || videoHeight === 0) {
    return null;
  }

  // Get CSS display dimensions
  const displayWidth = video.clientWidth;
  const displayHeight = video.clientHeight;

  if (displayWidth === 0 || displayHeight === 0) {
    return null;
  }

  // Calculate object-cover scaling (simulates CSS object-fit: cover)
  const videoAspect = videoWidth / videoHeight;
  const displayAspect = displayWidth / displayHeight;

  let drawWidth: number, drawHeight: number, offsetX: number, offsetY: number;

  if (displayAspect > videoAspect) {
    // Display is wider than video - scale to fit width, crop top/bottom
    drawWidth = displayWidth;
    drawHeight = displayWidth / videoAspect;
    offsetX = 0;
    offsetY = (displayHeight - drawHeight) / 2;
  } else {
    // Display is taller than video - scale to fit height, crop left/right
    drawHeight = displayHeight;
    drawWidth = displayHeight * videoAspect;
    offsetX = (displayWidth - drawWidth) / 2;
    offsetY = 0;
  }

  return { drawWidth, drawHeight, offsetX, offsetY, displayWidth, displayHeight };
}

/**
 * Transform normalized landmark coordinates (0-1) to screen coordinates.
 */
function toScreenCoords(
  landmark: PoseLandmark,
  dims: DrawingDimensions
): { x: number; y: number } {
  return {
    x: landmark.x * dims.drawWidth + dims.offsetX,
    y: landmark.y * dims.drawHeight + dims.offsetY,
  };
}

export function PoseOverlay({
  videoRef,
  poses,
  config,
  isRecording = false,
  duration = 0,
  hitFeedback = [],
}: PoseOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;

    if (!canvas || !video) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    function draw() {
      const canvas = canvasRef.current;
      const video = videoRef.current;

      if (!canvas || !video) return;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // Get video drawing dimensions with object-cover compensation
      const dims = getVideoDrawingDimensions(video);
      if (!dims) {
        animationFrameRef.current = requestAnimationFrame(draw);
        return;
      }

      // Set canvas size to match display (use clientWidth/Height for proper scaling)
      if (canvas.width !== dims.displayWidth || canvas.height !== dims.displayHeight) {
        canvas.width = dims.displayWidth;
        canvas.height = dims.displayHeight;
      }

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw poses with corrected coordinates
      poses.forEach((pose, poseIndex) => {
        drawSkeleton(ctx, pose.landmarks, dims);
        drawJoints(ctx, pose.landmarks, dims);
        drawPlayerLabel(ctx, pose.landmarks, poseIndex + 1, dims, hitFeedback[poseIndex]);
        drawWristZones(ctx, pose.landmarks, dims);
      });

      // Draw metrics panel
      if (config) {
        const totalHits = hitFeedback.reduce((sum, hf) => sum + (hf?.hitCount || 0), 0);
        drawMetrics(ctx, config, isRecording, duration, dims.displayWidth, totalHits);
      }

      animationFrameRef.current = requestAnimationFrame(draw);
    }

    animationFrameRef.current = requestAnimationFrame(draw);

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [videoRef, poses, config, isRecording, duration, hitFeedback]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ width: "100%", height: "100%" }}
    />
  );
}

function drawSkeleton(
  ctx: CanvasRenderingContext2D,
  landmarks: PoseLandmark[],
  dims: DrawingDimensions
) {
  ctx.strokeStyle = POSE_COLORS.skeleton;
  ctx.lineWidth = POSE_CONFIG.skeletonLineWidth;

  for (const [startIdx, endIdx] of POSE_CONNECTIONS) {
    const start = landmarks[startIdx];
    const end = landmarks[endIdx];

    if (!start || !end) continue;

    if (
      start.visibility > POSE_CONFIG.visibilityThreshold &&
      end.visibility > POSE_CONFIG.visibilityThreshold
    ) {
      const startCoords = toScreenCoords(start, dims);
      const endCoords = toScreenCoords(end, dims);

      ctx.beginPath();
      ctx.moveTo(startCoords.x, startCoords.y);
      ctx.lineTo(endCoords.x, endCoords.y);
      ctx.stroke();
    }
  }
}

function drawJoints(
  ctx: CanvasRenderingContext2D,
  landmarks: PoseLandmark[],
  dims: DrawingDimensions
) {
  ctx.fillStyle = POSE_COLORS.joints;

  for (const landmark of landmarks) {
    if (landmark.visibility > POSE_CONFIG.visibilityThreshold) {
      const coords = toScreenCoords(landmark, dims);
      ctx.globalAlpha = landmark.visibility;
      ctx.beginPath();
      ctx.arc(coords.x, coords.y, POSE_CONFIG.jointRadius, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
}

function drawPlayerLabel(
  ctx: CanvasRenderingContext2D,
  landmarks: PoseLandmark[],
  playerNum: number,
  dims: DrawingDimensions,
  feedback?: HitFeedback
) {
  const nose = landmarks[POSE_LANDMARKS.NOSE];
  if (!nose || nose.visibility < POSE_CONFIG.visibilityThreshold) return;

  const coords = toScreenCoords(nose, dims);
  const x = coords.x;
  const y = coords.y - POSE_CONFIG.labelOffsetY;

  // Show recent action if available, otherwise just player number
  const hasRecentAction = feedback?.recentAction;
  const label = hasRecentAction
    ? `Player ${playerNum}: ${feedback.recentAction}`
    : `Player ${playerNum}`;

  ctx.font = `bold ${POSE_CONFIG.labelFontSize}px sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  // Background rectangle
  const metrics = ctx.measureText(label);
  const padding = 5;
  const boxWidth = metrics.width + padding * 2;
  const boxHeight = POSE_CONFIG.labelFontSize + padding * 2;

  ctx.fillStyle = POSE_COLORS.labelBg;
  ctx.fillRect(x - boxWidth / 2, y - boxHeight / 2, boxWidth, boxHeight);

  // Text - green if recent action, white otherwise
  ctx.fillStyle = hasRecentAction ? "#00ff00" : POSE_COLORS.label;
  ctx.fillText(label, x, y);
}

function drawWristZones(
  ctx: CanvasRenderingContext2D,
  landmarks: PoseLandmark[],
  dims: DrawingDimensions
) {
  const leftWrist = landmarks[POSE_LANDMARKS.LEFT_WRIST];
  const rightWrist = landmarks[POSE_LANDMARKS.RIGHT_WRIST];

  ctx.strokeStyle = POSE_COLORS.zone;
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 5]);

  const zoneRadius = 20;

  if (leftWrist && leftWrist.visibility > POSE_CONFIG.visibilityThreshold) {
    const coords = toScreenCoords(leftWrist, dims);
    ctx.beginPath();
    ctx.arc(coords.x, coords.y, zoneRadius, 0, Math.PI * 2);
    ctx.stroke();
  }

  if (rightWrist && rightWrist.visibility > POSE_CONFIG.visibilityThreshold) {
    const coords = toScreenCoords(rightWrist, dims);
    ctx.beginPath();
    ctx.arc(coords.x, coords.y, zoneRadius, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.setLineDash([]);
}

function drawMetrics(
  ctx: CanvasRenderingContext2D,
  config: SessionConfig,
  isRecording: boolean,
  duration: number,
  width: number,
  hitCount: number
) {
  const panelX = width - POSE_CONFIG.metricsPanelWidth;
  const panelY = POSE_CONFIG.metricsPanelPadding;
  const contentX = panelX + 20;
  let contentY = panelY + 20;

  // Background panel (taller to fit hit count)
  ctx.fillStyle = POSE_COLORS.metricsBg;
  ctx.fillRect(
    panelX,
    panelY,
    POSE_CONFIG.metricsPanelWidth - POSE_CONFIG.metricsPanelPadding,
    POSE_CONFIG.metricsPanelHeight + (hitCount > 0 ? 20 : 0)
  );

  ctx.font = `${POSE_CONFIG.metricsFontSize}px sans-serif`;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillStyle = POSE_COLORS.metricsText;

  // Instruments
  const instruments = config.instruments
    .map((i) => i.charAt(0).toUpperCase() + i.slice(1))
    .join(", ");
  ctx.fillText(instruments || "No instruments", contentX, contentY);
  contentY += POSE_CONFIG.metricsLineHeight;

  // Musical key
  ctx.fillText(`Key: ${config.musicalKey || "Not set"}`, contentX, contentY);
  contentY += POSE_CONFIG.metricsLineHeight;

  // Recording status with hit count
  if (isRecording) {
    // Red dot
    ctx.fillStyle = POSE_COLORS.recording;
    ctx.beginPath();
    ctx.arc(contentX - 10, contentY, 5, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = POSE_COLORS.metricsText;
    ctx.fillText(`REC ${duration.toFixed(1)}s`, contentX, contentY);
    contentY += POSE_CONFIG.metricsLineHeight;

    // Hit count
    if (hitCount > 0) {
      ctx.fillStyle = "#00ff00";
      ctx.fillText(`${hitCount} hits`, contentX, contentY);
    }
  }
}
