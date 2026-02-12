"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "motion/react";
import { Download, Home, Music, Video, Share2 } from "lucide-react";
import { useConfig } from "@/contexts/config-context";
import { ShinyButton } from "@/components/ui/shiny-button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:3001";

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

export default function ResultsPage() {
  const router = useRouter();
  const { sessionResult, isHydrated, resetConfig } = useConfig();

  // Redirect if no session result
  useEffect(() => {
    if (isHydrated && !sessionResult) {
      router.replace("/");
    }
  }, [isHydrated, sessionResult, router]);

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

  const handleStartOver = () => {
    resetConfig();
    router.push("/");
  };

  return (
    <main className="min-h-screen bg-[#232323] flex flex-col items-center justify-center relative overflow-hidden py-12 px-4">
      <Background3D />

      <div className="relative z-10 max-w-3xl w-full">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-10"
        >
          <h1 className="text-4xl md:text-5xl font-bold text-[#eeeeee] mb-3">
            {sessionResult.videoUrl
              ? "Your Music Video is Ready!"
              : "Your Music is Ready!"}
          </h1>
          <p className="text-[#eeeeee]/70 text-lg">
            Duration: {sessionResult.duration.toFixed(1)} seconds
          </p>
        </motion.div>

        {/* Video Player (Primary) */}
        {sessionResult.videoUrl && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="mb-8"
          >
            <div className="flex items-center gap-2 mb-3">
              <Video className="w-5 h-5 text-[#d51bdb]" />
              <h2 className="text-lg font-semibold text-[#eeeeee]">
                Your Music Video
              </h2>
            </div>
            <div
              className="bg-[#1a1a1a] rounded-xl overflow-hidden"
              style={{ boxShadow: "0 0 40px rgba(213, 27, 219, 0.3)" }}
            >
              <video
                controls
                autoPlay
                muted
                className="w-full aspect-video"
              >
                <source
                  src={`${API_BASE}${sessionResult.videoUrl}`}
                  type="video/mp4"
                />
                Your browser does not support the video element.
              </video>
            </div>
          </motion.div>
        )}

        {/* Audio Player */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
          className="mb-10"
        >
          <div className="flex items-center gap-2 mb-3">
            <Music className="w-5 h-5 text-[#7bd2ff]" />
            <h2 className="text-lg font-semibold text-[#eeeeee]">
              Mixed Audio Track
            </h2>
          </div>
          <div className="bg-[#1a1a1a] rounded-xl p-6">
            <audio
              controls
              className="w-full"
              style={{
                filter: "invert(1) hue-rotate(180deg)",
              }}
            >
              <source
                src={`${API_BASE}${sessionResult.audioUrl}`}
                type="audio/wav"
              />
              Your browser does not support the audio element.
            </audio>
          </div>
        </motion.div>

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="flex flex-wrap justify-center gap-4"
        >
          {/* Video download first (primary) */}
          {sessionResult.videoUrl && (
            <a
              href={`${API_BASE}${sessionResult.videoUrl}`}
              download
              className="inline-flex items-center gap-2 px-6 py-3 bg-[#d51bdb] text-white font-semibold rounded-lg hover:bg-[#d51bdb]/80 transition-colors"
            >
              <Download className="w-5 h-5" />
              Download Video
            </a>
          )}

          <a
            href={`${API_BASE}${sessionResult.audioUrl}`}
            download
            className="inline-flex items-center gap-2 px-6 py-3 bg-[#7bd2ff] text-black font-semibold rounded-lg hover:bg-[#7bd2ff]/80 transition-colors"
          >
            <Download className="w-5 h-5" />
            Download Audio
          </a>

          <button
            onClick={() => {
              if (navigator.share) {
                navigator.share({
                  title: "My DigiJam Performance",
                  text: "Check out the music video I made with DigiJam!",
                  url: window.location.href,
                });
              }
            }}
            className="inline-flex items-center gap-2 px-6 py-3 bg-[#ab42ee] text-white font-semibold rounded-lg hover:bg-[#ab42ee]/80 transition-colors"
          >
            <Share2 className="w-5 h-5" />
            Share
          </button>
        </motion.div>

        {/* Start Over */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-center mt-10"
        >
          <Link href="/" onClick={handleStartOver}>
            <ShinyButton className="text-lg px-8 py-3">
              <Home className="w-5 h-5 mr-2" />
              Start Over
            </ShinyButton>
          </Link>
        </motion.div>
      </div>
    </main>
  );
}
