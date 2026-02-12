"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { Check, Loader2, AlertCircle } from "lucide-react";
import { useConfig } from "@/contexts/config-context";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:3001";

// Processing steps vary by AI mode
const HIGH_AI_STEPS = [
  { threshold: 0, label: "Extracting audio features" },
  { threshold: 15, label: "Generating melody" },
  { threshold: 30, label: "Mixing instrumental" },
  { threshold: 45, label: "Generating lyrics" },
  { threshold: 60, label: "Selecting voices" },
  { threshold: 70, label: "Synthesizing vocals" },
  { threshold: 85, label: "Creating music video" },
  { threshold: 95, label: "Finalizing" },
];

const MEDIUM_AI_STEPS = [
  { threshold: 0, label: "Extracting audio features" },
  { threshold: 15, label: "Generating melody" },
  { threshold: 30, label: "Generating partial lyrics" },
  { threshold: 45, label: "Synthesizing AI vocals" },
  { threshold: 60, label: "Transforming your vocals" },
  { threshold: 75, label: "Mixing all tracks" },
  { threshold: 85, label: "Creating music video" },
  { threshold: 95, label: "Finalizing" },
];

const LOW_AI_STEPS = [
  { threshold: 0, label: "Extracting audio features" },
  { threshold: 20, label: "Generating background melody" },
  { threshold: 40, label: "Transforming your vocals" },
  { threshold: 60, label: "Mixing all tracks" },
  { threshold: 80, label: "Creating music video" },
  { threshold: 95, label: "Finalizing" },
];

function Background3D() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none">
      {/* Large glowing orbs */}
      <div
        className="absolute w-[400px] h-[400px] rounded-full pulse-glow"
        style={{
          background:
            "radial-gradient(circle, var(--accent-magenta) 0%, transparent 70%)",
          top: "10%",
          left: "-10%",
        }}
      />
      <div
        className="absolute w-[300px] h-[300px] rounded-full pulse-glow"
        style={{
          background:
            "radial-gradient(circle, var(--accent-cyan) 0%, transparent 70%)",
          top: "60%",
          right: "-5%",
          animationDelay: "2s",
        }}
      />
      <div
        className="absolute w-[250px] h-[250px] rounded-full pulse-glow"
        style={{
          background:
            "radial-gradient(circle, var(--accent-purple) 0%, transparent 70%)",
          bottom: "5%",
          left: "20%",
          animationDelay: "1s",
        }}
      />
      <div
        className="absolute w-[200px] h-[200px] rounded-full pulse-glow"
        style={{
          background:
            "radial-gradient(circle, var(--accent-yellow) 0%, transparent 70%)",
          top: "20%",
          right: "15%",
          animationDelay: "3s",
        }}
      />

      {/* Floating 3D spheres */}
      <div
        className="absolute w-20 h-20 sphere float-element"
        style={{
          background:
            "radial-gradient(circle at 30% 30%, var(--accent-magenta), transparent 70%)",
          border: "1px solid rgba(213, 27, 219, 0.5)",
          top: "15%",
          left: "10%",
          animationDelay: "0s",
        }}
      />
      <div
        className="absolute w-16 h-16 sphere float-element-reverse"
        style={{
          background:
            "radial-gradient(circle at 30% 30%, var(--accent-cyan), transparent 70%)",
          border: "1px solid rgba(123, 210, 255, 0.5)",
          top: "70%",
          left: "8%",
          animationDelay: "1s",
        }}
      />
      <div
        className="absolute w-12 h-12 sphere float-element"
        style={{
          background:
            "radial-gradient(circle at 30% 30%, var(--accent-yellow), transparent 70%)",
          border: "1px solid rgba(238, 225, 60, 0.5)",
          top: "40%",
          right: "12%",
          animationDelay: "2s",
        }}
      />
      <div
        className="absolute w-24 h-24 sphere float-element-reverse"
        style={{
          background:
            "radial-gradient(circle at 30% 30%, var(--accent-purple), transparent 70%)",
          border: "1px solid rgba(171, 66, 238, 0.5)",
          bottom: "20%",
          right: "20%",
          animationDelay: "0.5s",
        }}
      />

      {/* Floating cubes */}
      <div
        className="absolute float-element"
        style={{ top: "25%", right: "8%", animationDelay: "1.5s" }}
      >
        <div
          className="w-14 h-14 border-2 border-accent-cyan/50 rotate-45 transform-gpu"
          style={{
            background:
              "linear-gradient(135deg, rgba(123, 210, 255, 0.1) 0%, transparent 50%)",
            boxShadow: "0 0 20px rgba(123, 210, 255, 0.3)",
          }}
        />
      </div>
      <div
        className="absolute float-element-reverse"
        style={{ bottom: "30%", left: "15%", animationDelay: "2.5s" }}
      >
        <div
          className="w-10 h-10 border-2 border-accent-yellow/50 rotate-12 transform-gpu"
          style={{
            background:
              "linear-gradient(135deg, rgba(238, 225, 60, 0.1) 0%, transparent 50%)",
            boxShadow: "0 0 15px rgba(238, 225, 60, 0.3)",
          }}
        />
      </div>
      <div
        className="absolute float-element"
        style={{ top: "55%", left: "5%", animationDelay: "3.5s" }}
      >
        <div
          className="w-8 h-8 border-2 border-accent-magenta/50 -rotate-12 transform-gpu"
          style={{
            background:
              "linear-gradient(135deg, rgba(213, 27, 219, 0.1) 0%, transparent 50%)",
            boxShadow: "0 0 15px rgba(213, 27, 219, 0.3)",
          }}
        />
      </div>

      {/* Ring elements */}
      <div
        className="absolute w-32 h-32 rounded-full border-2 border-accent-purple/30 float-element"
        style={{ top: "10%", right: "25%", animationDelay: "4s" }}
      />
      <div
        className="absolute w-20 h-20 rounded-full border border-accent-cyan/20 float-element-reverse"
        style={{ bottom: "15%", left: "30%", animationDelay: "2s" }}
      />
    </div>
  );
}

export default function LoadingPage() {
  const router = useRouter();
  const { config, sessionResult, setSessionResult, isHydrated } = useConfig();
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const hasStarted = useRef(false);

  // Get steps based on AI mode
  const PROCESSING_STEPS =
    config.aiSupportLevel === "high"
      ? HIGH_AI_STEPS
      : config.aiSupportLevel === "medium"
        ? MEDIUM_AI_STEPS
        : LOW_AI_STEPS;

  // Extract session ID from audio URL
  const extractSessionId = useCallback((audioUrl: string) => {
    // URL format: /api/files/audio/mixed_abc12345.wav
    const match = audioUrl.match(/mixed_([a-z0-9]+)\.wav/);
    return match ? match[1] : `session_${Date.now()}`;
  }, []);

  // Run the pipeline
  const runPipeline = useCallback(async () => {
    if (!sessionResult?.audioUrl || isProcessing) return;

    setIsProcessing(true);
    setError(null);

    try {
      const sessionId = extractSessionId(sessionResult.audioUrl);
      const [keyNote, keyMode] = config.musicalKey.split(" ");

      // Determine endpoint and build form data
      let endpoint: string;
      const formData = new FormData();

      formData.append("session_id", sessionId);
      formData.append("instrumental_url", sessionResult.audioUrl);
      formData.append("bpm", "120"); // TODO: Get from config
      formData.append("key", config.musicalKey);

      if (config.aiSupportLevel === "high") {
        endpoint = "/api/pipeline/high";
        formData.append("genre", "pop");
        if (config.vocalsConfig?.lyricsPrompt) {
          formData.append("lyrics_prompt", config.vocalsConfig.lyricsPrompt);
        }
        if (config.vocalsConfig?.voiceId) {
          formData.append("voice_id", config.vocalsConfig.voiceId);
        }
      } else if (config.aiSupportLevel === "medium") {
        endpoint = "/api/pipeline/medium";
        formData.append("genre", "pop");
        formData.append("voice_id", config.vocalsConfig?.voiceId || "");
        formData.append(
          "lyrics_prompt",
          config.vocalsConfig?.lyricsPrompt || ""
        );

        // Add user vocals
        if (config.vocalsConfig?.userVocalsBlob) {
          formData.append("user_vocals", config.vocalsConfig.userVocalsBlob);
        } else {
          throw new Error("User vocals required for medium AI mode");
        }
      } else {
        // Low AI mode
        endpoint = "/api/pipeline/low";
        formData.append("voice_id", config.vocalsConfig?.voiceId || "");

        // Add user vocals
        if (config.vocalsConfig?.userVocalsBlob) {
          formData.append("user_vocals", config.vocalsConfig.userVocalsBlob);
        } else {
          throw new Error("User vocals required for low AI mode");
        }
      }

      // Simulate progress while waiting for response
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) return prev;
          return prev + Math.random() * 5 + 1;
        });
      }, 800);

      // Call pipeline endpoint
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        body: formData,
      });

      clearInterval(progressInterval);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Pipeline failed: ${response.statusText}`);
      }

      const result = await response.json();

      // Update session result with new video and audio URLs
      setSessionResult({
        audioUrl: result.audioUrl,
        videoUrl: result.videoUrl,
        duration: result.duration,
      });

      setProgress(100);
    } catch (err) {
      console.error("Pipeline error:", err);
      setError(err instanceof Error ? err.message : "An error occurred");
      setProgress(0);
    } finally {
      setIsProcessing(false);
    }
  }, [
    sessionResult?.audioUrl,
    config,
    isProcessing,
    extractSessionId,
    setSessionResult,
  ]);

  // Start pipeline when component mounts and sessionResult is available
  useEffect(() => {
    if (isHydrated && sessionResult?.audioUrl && !hasStarted.current) {
      hasStarted.current = true;
      runPipeline();
    }
  }, [isHydrated, sessionResult?.audioUrl, runPipeline]);

  // Redirect if no session result
  useEffect(() => {
    if (isHydrated && !sessionResult) {
      router.replace("/");
    }
  }, [isHydrated, sessionResult, router]);

  // Auto-redirect when complete
  useEffect(() => {
    if (progress >= 100) {
      const timer = setTimeout(() => {
        router.push("/results");
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [progress, router]);

  const currentStepIndex = PROCESSING_STEPS.findLastIndex(
    (step) => progress >= step.threshold
  );

  // Loading state
  if (!isHydrated || !sessionResult) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#232323]">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
          className="w-8 h-8 border-2 border-[#d51bdb] border-t-transparent rounded-full"
        />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#232323] flex flex-col items-center justify-center relative overflow-hidden">
      <Background3D />

      <div className="relative z-10 max-w-lg w-full px-6">
        {/* Header */}
        <motion.h1
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-3xl md:text-4xl font-bold text-[#eeeeee] text-center mb-8"
        >
          {error
            ? "Processing Failed"
            : progress >= 100
              ? "Your music video is ready!"
              : "Creating your music video..."}
        </motion.h1>

        {/* Error state */}
        {error ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-center"
          >
            <div className="mb-6">
              <AlertCircle className="w-16 h-16 text-red-500 mx-auto" />
            </div>
            <p className="text-red-400 mb-6">{error}</p>
            <button
              onClick={() => {
                setError(null);
                hasStarted.current = false;
                runPipeline();
              }}
              className="px-6 py-3 bg-[#d51bdb] text-white rounded-lg hover:bg-[#d51bdb]/80 transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={() => router.push("/")}
              className="ml-4 px-6 py-3 bg-[#333] text-white rounded-lg hover:bg-[#444] transition-colors"
            >
              Start Over
            </button>
          </motion.div>
        ) : (
          <>
            {/* Progress bar with glow */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 }}
              className="mb-8"
            >
              <div className="h-3 w-full overflow-hidden rounded-full bg-[#eeeeee]/10 backdrop-blur-sm">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(progress, 100)}%` }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  className="h-full rounded-full bg-gradient-to-r from-[#d51bdb] via-[#7bd2ff] to-[#ab42ee]"
                  style={{ boxShadow: "0 0 20px rgba(213, 27, 219, 0.5)" }}
                />
              </div>
              <p className="text-center text-[#eeeeee]/50 mt-2 text-sm">
                {Math.min(Math.round(progress), 100)}%
              </p>
            </motion.div>

            {/* Step indicators */}
            <div className="space-y-3">
              {PROCESSING_STEPS.map((step, index) => {
                const isComplete =
                  progress >= (PROCESSING_STEPS[index + 1]?.threshold ?? 100);
                const isCurrent = index === currentStepIndex;

                return (
                  <motion.div
                    key={step.label}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 + index * 0.1 }}
                    className={`flex items-center gap-3 transition-colors duration-300 ${
                      isComplete
                        ? "text-[#7bd2ff]"
                        : isCurrent
                          ? "text-[#eeeeee]"
                          : "text-[#eeeeee]/30"
                    }`}
                  >
                    {isComplete ? (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{
                          type: "spring",
                          stiffness: 500,
                          damping: 30,
                        }}
                      >
                        <Check className="w-5 h-5" />
                      </motion.div>
                    ) : isCurrent ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border border-current" />
                    )}
                    <span className={isCurrent ? "font-medium" : ""}>
                      {step.label}
                    </span>
                  </motion.div>
                );
              })}
            </div>

            {/* Completion message */}
            {progress >= 100 && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center text-[#7bd2ff] mt-8 font-medium"
              >
                Complete! Redirecting...
              </motion.p>
            )}
          </>
        )}
      </div>
    </main>
  );
}
