"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ShinyButton } from "@/components/ui/shiny-button";
import { useConfig } from "@/contexts/config-context";
import { INSTRUMENT_INFO } from "@/lib/config-constants";

interface PreRecordingOverlayProps {
  onStart: () => void;
}

export function PreRecordingOverlay({ onStart }: PreRecordingOverlayProps) {
  const { config } = useConfig();
  const [showButton, setShowButton] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowButton(true);
    }, 5000);

    return () => clearTimeout(timer);
  }, []);

  const instrumentNames = config.instruments
    .map((inst) => INSTRUMENT_INFO[inst]?.name || inst)
    .join(", ");

  return (
    <div className="absolute inset-0 z-40 flex flex-col items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="max-w-xl px-6 text-center">
        <motion.h1
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 text-4xl font-bold text-[#eeeeee] md:text-5xl"
        >
          Get Ready to Record
        </motion.h1>

        <motion.ul
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mb-8 space-y-3 text-left text-lg text-[#eeeeee]/90"
        >
          <li className="flex items-start gap-3">
            <span className="text-[#d51bdb]">&#9679;</span>
            <span>
              <strong>{config.numUsers}</strong> player{config.numUsers > 1 ? "s" : ""} playing{" "}
              <strong>{instrumentNames}</strong>
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="text-[#7bd2ff]">&#9679;</span>
            <span>
              Musical key: <strong>{config.musicalKey}</strong>
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="text-[#eee13c]">&#9679;</span>
            <span>Position yourself so your full body is visible</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="text-[#ab42ee]">&#9679;</span>
            <span>Press <strong>SPACE</strong> to stop recording when finished</span>
          </li>
        </motion.ul>

        <AnimatePresence>
          {showButton && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.5 }}
            >
              <ShinyButton
                onClick={onStart}
                className="cta-glow px-10 py-4 text-lg font-bold [&_span]:text-black"
              >
                Start Recording
              </ShinyButton>
            </motion.div>
          )}
        </AnimatePresence>

        {!showButton && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-[#eeeeee]/60"
          >
            Button appears in a moment...
          </motion.p>
        )}
      </div>
    </div>
  );
}
