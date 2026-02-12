"use client";

import { useEffect } from "react";
import { motion } from "motion/react";
import { Play, Square } from "lucide-react";
import { useConfig } from "@/contexts/config-context";

interface RecordingOverlayProps {
  duration: number;
  onStop: () => void;
}

export function RecordingOverlay({ duration, onStop }: RecordingOverlayProps) {
  const { config } = useConfig();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.code === "Space") {
        e.preventDefault();
        onStop();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onStop]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="absolute inset-0 z-40 pointer-events-none">
      {/* Top-left: PLAY symbol with recording indicator */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        className="absolute top-4 left-4 flex items-center gap-3"
      >
        <div className="flex items-center gap-2 rounded-lg bg-black/60 px-4 py-2">
          <Play className="h-6 w-6 text-[#d51bdb] fill-[#d51bdb]" />
          <span className="text-lg font-bold text-white">PLAY</span>
        </div>

        {/* Recording indicator */}
        <div className="flex items-center gap-2 rounded-lg bg-black/60 px-3 py-2">
          <motion.div
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
            className="h-3 w-3 rounded-full bg-red-500"
          />
          <span className="text-sm font-medium text-white">REC</span>
        </div>
      </motion.div>

      {/* Top-right: Metrics display */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        className="absolute top-4 right-4 rounded-lg bg-black/60 px-4 py-3"
      >
        <div className="space-y-1 text-right">
          <div className="text-2xl font-mono font-bold text-white">
            {formatDuration(duration)}
          </div>
          <div className="text-sm text-[#eeeeee]/70">
            {config.numUsers} player{config.numUsers > 1 ? "s" : ""} &bull; {config.musicalKey}
          </div>
        </div>
      </motion.div>

      {/* Bottom-right: Stop button */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute bottom-6 right-6 pointer-events-auto"
      >
        <button
          onClick={onStop}
          className="flex items-center gap-3 rounded-lg bg-red-600 px-6 py-3 text-white transition-all hover:bg-red-700 hover:scale-105 active:scale-95"
        >
          <Square className="h-5 w-5 fill-white" />
          <span className="font-semibold">Stop Recording</span>
        </button>
        <p className="mt-2 text-center text-sm text-[#eeeeee]/60">
          or press SPACE
        </p>
      </motion.div>
    </div>
  );
}
