"use client";

import { useRef, useCallback, useMemo } from "react";
import { Pose, POSE_LANDMARKS } from "@/lib/pose-constants";

export interface HitEvent {
  timestamp: number;
  playerId: number;
  hand: "left" | "right";
  action: string;
  velocity: number;
}

export interface HitFeedback {
  recentAction?: string;
  hitCount: number;
}

interface PositionHistory {
  y: number;
  timestamp: number;
}

interface PlayerState {
  leftHistory: PositionHistory[];
  rightHistory: PositionHistory[];
  leftLastHitTime: number;
  rightLastHitTime: number;
  leftPrevVelocity: number;
  rightPrevVelocity: number;
  recentAction?: string;
  recentActionExpiry: number;
  hitCount: number;
}

// Detection parameters (ported from drum_classifier.py)
const VELOCITY_THRESHOLD = 0.15; // Minimum downward velocity to consider (m/s equivalent in normalized coords)
const DEBOUNCE_TIME = 100; // Milliseconds between hits
const HISTORY_SIZE = 5; // Number of frames to track
const ACTION_DISPLAY_DURATION = 700; // How long to show action (ms)
const MIN_REVERSAL_VELOCITY = -0.03; // Minimum upward velocity to confirm hit

export function useHitDetector(
  poses: Pose[],
  instruments: string[],
  enabled: boolean
): HitFeedback[] {
  const playerStatesRef = useRef<Map<number, PlayerState>>(new Map());

  // Get or create player state
  const getPlayerState = useCallback((playerId: number): PlayerState => {
    if (!playerStatesRef.current.has(playerId)) {
      playerStatesRef.current.set(playerId, {
        leftHistory: [],
        rightHistory: [],
        leftLastHitTime: 0,
        rightLastHitTime: 0,
        leftPrevVelocity: 0,
        rightPrevVelocity: 0,
        recentAction: undefined,
        recentActionExpiry: 0,
        hitCount: 0,
      });
    }
    return playerStatesRef.current.get(playerId)!;
  }, []);

  // Calculate velocity from position history
  const calculateVelocity = useCallback((history: PositionHistory[]): number => {
    if (history.length < 2) return 0;

    const recent = history[history.length - 1];
    const older = history[0];
    const dt = (recent.timestamp - older.timestamp) / 1000; // Convert to seconds

    if (dt <= 0) return 0;

    // Positive velocity = moving down (y increases downward in normalized coords)
    return (recent.y - older.y) / dt;
  }, []);

  // Classify action based on hand position relative to body
  const classifyAction = useCallback(
    (
      hand: "left" | "right",
      landmarks: Pose["landmarks"],
      instrument: string
    ): string => {
      const wristIdx = hand === "left" ? POSE_LANDMARKS.LEFT_WRIST : POSE_LANDMARKS.RIGHT_WRIST;
      const shoulderIdx = hand === "left" ? POSE_LANDMARKS.LEFT_SHOULDER : POSE_LANDMARKS.RIGHT_SHOULDER;
      const hipIdx = hand === "left" ? POSE_LANDMARKS.LEFT_HIP : POSE_LANDMARKS.RIGHT_HIP;

      const wrist = landmarks[wristIdx];
      const shoulder = landmarks[shoulderIdx];
      const hip = landmarks[hipIdx];

      if (!wrist || !shoulder || !hip) return "hit";

      // For drums, classify based on position
      if (instrument === "drums") {
        // Above shoulders = hi-hat (dominant) or crash (non-dominant)
        if (wrist.y < shoulder.y) {
          return hand === "right" ? "hi-hat" : "crash";
        }
        // Between shoulder and hip, near center = snare
        if (wrist.y >= shoulder.y && wrist.y <= hip.y) {
          return "snare";
        }
        return "hit";
      }

      // For guitar
      if (instrument === "guitar") {
        return "strum";
      }

      // For piano
      if (instrument === "piano") {
        return hand === "right" ? "chord" : "bass";
      }

      return "hit";
    },
    []
  );

  // Detect hits using velocity reversal algorithm
  const detectHits = useCallback(
    (pose: Pose, playerId: number, instrument: string): HitEvent[] => {
      const state = getPlayerState(playerId);
      const now = performance.now();
      const hits: HitEvent[] = [];

      // Clear expired recent action
      if (state.recentActionExpiry > 0 && now > state.recentActionExpiry) {
        state.recentAction = undefined;
        state.recentActionExpiry = 0;
      }

      const landmarks = pose.landmarks;
      const leftWrist = landmarks[POSE_LANDMARKS.LEFT_WRIST];
      const rightWrist = landmarks[POSE_LANDMARKS.RIGHT_WRIST];

      // Process left hand
      if (leftWrist && leftWrist.visibility > 0.5) {
        state.leftHistory.push({ y: leftWrist.y, timestamp: now });
        if (state.leftHistory.length > HISTORY_SIZE) {
          state.leftHistory.shift();
        }

        const velocity = calculateVelocity(state.leftHistory);

        // Detect velocity reversal: was moving down fast, now moving up
        if (
          state.leftPrevVelocity > VELOCITY_THRESHOLD &&
          velocity < MIN_REVERSAL_VELOCITY &&
          now - state.leftLastHitTime > DEBOUNCE_TIME
        ) {
          const action = classifyAction("left", landmarks, instrument);
          hits.push({
            timestamp: now,
            playerId,
            hand: "left",
            action,
            velocity: state.leftPrevVelocity,
          });
          state.leftLastHitTime = now;
          state.recentAction = action.toUpperCase();
          state.recentActionExpiry = now + ACTION_DISPLAY_DURATION;
          state.hitCount++;
        }

        state.leftPrevVelocity = velocity;
      }

      // Process right hand
      if (rightWrist && rightWrist.visibility > 0.5) {
        state.rightHistory.push({ y: rightWrist.y, timestamp: now });
        if (state.rightHistory.length > HISTORY_SIZE) {
          state.rightHistory.shift();
        }

        const velocity = calculateVelocity(state.rightHistory);

        // Detect velocity reversal
        if (
          state.rightPrevVelocity > VELOCITY_THRESHOLD &&
          velocity < MIN_REVERSAL_VELOCITY &&
          now - state.rightLastHitTime > DEBOUNCE_TIME
        ) {
          const action = classifyAction("right", landmarks, instrument);
          hits.push({
            timestamp: now,
            playerId,
            hand: "right",
            action,
            velocity: state.rightPrevVelocity,
          });
          state.rightLastHitTime = now;
          state.recentAction = action.toUpperCase();
          state.recentActionExpiry = now + ACTION_DISPLAY_DURATION;
          state.hitCount++;
        }

        state.rightPrevVelocity = velocity;
      }

      return hits;
    },
    [getPlayerState, calculateVelocity, classifyAction]
  );

  // Process all poses and return feedback
  const feedback = useMemo((): HitFeedback[] => {
    if (!enabled || poses.length === 0) {
      return [];
    }

    const instrument = instruments[0] || "drums";
    const now = performance.now();

    return poses.map((pose, index) => {
      // Detect hits (side effect: updates state)
      detectHits(pose, index, instrument);

      const state = playerStatesRef.current.get(index);
      if (!state) {
        return { hitCount: 0 };
      }

      // Check if recent action has expired
      const recentAction =
        state.recentActionExpiry > now ? state.recentAction : undefined;

      return {
        recentAction,
        hitCount: state.hitCount,
      };
    });
  }, [poses, instruments, enabled, detectHits]);

  return feedback;
}
