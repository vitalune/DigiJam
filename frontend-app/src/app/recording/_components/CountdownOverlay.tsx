"use client";

import { motion, AnimatePresence } from "motion/react";

interface CountdownOverlayProps {
  value: number;
  instruction?: string;
}

export function CountdownOverlay({
  value,
  instruction = "GET READY!",
}: CountdownOverlayProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-black/60"
    >
      <AnimatePresence mode="wait">
        <motion.span
          key={value}
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 1.5, opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="text-[20vw] font-bold text-white leading-none"
        >
          {value}
        </motion.span>
      </AnimatePresence>

      <motion.span
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="mt-8 text-2xl font-semibold text-[#eee13c] md:text-3xl"
      >
        {instruction}
      </motion.span>
    </motion.div>
  );
}
