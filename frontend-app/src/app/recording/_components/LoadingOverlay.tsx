"use client";

import { motion } from "motion/react";

interface LoadingOverlayProps {
  message?: string;
}

export function LoadingOverlay({
  message = "Processing your recording...",
}: LoadingOverlayProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-[#232323]/95"
    >
      {/* Spinner */}
      <div className="relative h-20 w-20">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
          className="absolute inset-0 rounded-full border-4 border-transparent border-t-[#d51bdb] border-r-[#7bd2ff]"
        />
        <motion.div
          animate={{ rotate: -360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
          className="absolute inset-2 rounded-full border-4 border-transparent border-b-[#eee13c] border-l-[#ab42ee]"
        />
      </div>

      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="mt-6 text-lg text-[#eeeeee]"
      >
        {message}
      </motion.p>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="mt-2 text-sm text-[#eeeeee]/60"
      >
        This may take a moment...
      </motion.p>
    </motion.div>
  );
}
