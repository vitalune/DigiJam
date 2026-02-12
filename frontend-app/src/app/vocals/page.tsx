"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { Mic, Music, Square, Play, Pause } from "lucide-react";

import { useConfig } from "@/contexts/config-context";
import { VOICE_PROFILES, getVoiceById } from "@/lib/voice-constants";
import { AnimatedGridPattern } from "@/components/ui/animated-grid-pattern";
import { AnimatedGradientText } from "@/components/ui/animated-gradient-text";
import { MagicCard } from "@/components/ui/magic-card";
import { VoiceSelector } from "@/components/ui/voice-selector";
import { ShinyButton } from "@/components/ui/shiny-button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:3001";

export default function VocalsPage() {
  const router = useRouter();
  const { config, sessionResult, isHydrated, setVocalsConfig } = useConfig();
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [lyricsPrompt, setLyricsPrompt] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  // Recording refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Access control: redirect if vocals not included or high AI mode
  useEffect(() => {
    if (isHydrated) {
      if (!config.includeVocals || config.aiSupportLevel === "high") {
        router.replace("/loading");
      }
    }
  }, [isHydrated, config.includeVocals, config.aiSupportLevel, router]);

  // Don't render until hydrated and access is confirmed
  if (!isHydrated || !config.includeVocals || config.aiSupportLevel === "high") {
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

  const selectedVoiceData = selectedVoice ? getVoiceById(selectedVoice) : null;

  // Start recording vocals
  const handleStartRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });

      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        setRecordedBlob(blob);

        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop());

        // Stop timer
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(100); // Collect data every 100ms

      // Start timer
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);

      setIsRecording(true);
    } catch (error) {
      console.error("Failed to start recording:", error);
      alert("Failed to access microphone. Please grant permission.");
    }
  }, []);

  // Stop recording
  const handleStopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  // Play recorded audio
  const handlePlayRecording = useCallback(() => {
    if (recordedBlob && !isPlaying) {
      const url = URL.createObjectURL(recordedBlob);
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(url);
      };

      audio.play();
      setIsPlaying(true);
    } else if (audioRef.current && isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  }, [recordedBlob, isPlaying]);

  // Format recording time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Save config and navigate
  const handleNext = () => {
    // Save vocals config to context
    setVocalsConfig({
      voiceId: selectedVoice,
      lyricsPrompt: config.aiSupportLevel === "medium" ? lyricsPrompt : null,
      userVocalsBlob: recordedBlob,
    });

    router.push("/loading");
  };

  // Check if can proceed
  const canProceed =
    selectedVoice &&
    (config.aiSupportLevel === "medium" || recordedBlob !== null);

  return (
    <main className="min-h-screen bg-[#232323] relative overflow-hidden">
      {/* Animated Grid Background */}
      <AnimatedGridPattern
        className="fill-[#d51bdb]/10 stroke-[#d51bdb]/10"
        numSquares={30}
        maxOpacity={0.3}
        duration={3}
      />

      <div className="relative z-10 container mx-auto px-4 py-8 max-w-5xl">
        {/* Header */}
        <header className="text-center mb-10">
          <motion.h1
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-4xl md:text-5xl font-bold text-[#eeeeee] mb-3"
          >
            Add Vocals
          </motion.h1>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <AnimatedGradientText
              colorFrom="#d51bdb"
              colorTo="#7bd2ff"
              className="text-lg md:text-xl"
            >
              {config.aiSupportLevel === "low"
                ? "Choose a voice style for AI transformation"
                : "Choose a voice and describe your lyrics"}
            </AnimatedGradientText>
          </motion.div>
        </header>

        {/* Instrumental Preview */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mb-10"
        >
          <div className="flex items-center justify-center gap-2 mb-4">
            <Music className="w-5 h-5 text-[#7bd2ff]" />
            <h2 className="text-lg font-semibold text-[#eeeeee]">
              Your Instrumental Track
            </h2>
          </div>
          <div className="bg-[#1a1a1a] rounded-xl p-6 max-w-2xl mx-auto">
            {sessionResult?.audioUrl ? (
              <div className="space-y-4">
                {/* Audio Player */}
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
                <p className="text-center text-[#eeeeee]/50 text-sm">
                  Duration: {sessionResult.duration.toFixed(1)}s
                </p>
              </div>
            ) : (
              <div className="py-8 flex items-center justify-center">
                <p className="text-[#eeeeee]/50">No instrumental available</p>
              </div>
            )}
          </div>
        </motion.section>

        {/* Voice Selection */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mb-10"
        >
          <h2 className="text-xl font-semibold text-[#eeeeee] mb-4 text-center">
            Choose Your Voice
          </h2>
          <VoiceSelector
            voices={VOICE_PROFILES}
            selectedId={selectedVoice}
            onSelect={setSelectedVoice}
          />
          {selectedVoiceData && (
            <motion.p
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="text-center mt-4 text-[#eeeeee]/70"
            >
              Selected:{" "}
              <span style={{ color: selectedVoiceData.accentColor }}>
                {selectedVoiceData.name}
              </span>{" "}
              - {selectedVoiceData.description}
            </motion.p>
          )}
        </motion.section>

        {/* LOW AI Mode: Recording Section */}
        {config.aiSupportLevel === "low" && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="mb-10"
          >
            <h2 className="text-xl font-semibold text-[#eeeeee] mb-4 text-center">
              Record Your Vocals
            </h2>
            <div className="text-center">
              <div className="mb-6">
                <div
                  className={`inline-flex items-center justify-center w-24 h-24 rounded-full transition-all duration-300 ${
                    isRecording
                      ? "bg-red-500/20 animate-pulse"
                      : recordedBlob
                        ? "bg-[#7bd2ff]/20"
                        : "bg-[#d51bdb]/20"
                  }`}
                >
                  {isRecording ? (
                    <Square className="w-12 h-12 text-red-500" />
                  ) : recordedBlob ? (
                    isPlaying ? (
                      <Pause className="w-12 h-12 text-[#7bd2ff]" />
                    ) : (
                      <Play className="w-12 h-12 text-[#7bd2ff]" />
                    )
                  ) : (
                    <Mic className="w-12 h-12 text-[#d51bdb]" />
                  )}
                </div>
                {isRecording && (
                  <p className="text-red-500 font-mono mt-2 text-lg">
                    {formatTime(recordingTime)}
                  </p>
                )}
              </div>

              <p className="text-[#eeeeee]/70 mb-6 max-w-md mx-auto">
                {recordedBlob
                  ? "Recording complete! You can re-record or continue."
                  : "Record your vocals and AI will transform your voice to match the selected style"}
              </p>

              <div className="flex justify-center gap-4">
                {recordedBlob && !isRecording && (
                  <ShinyButton
                    onClick={handlePlayRecording}
                    className="!border-[#7bd2ff]"
                  >
                    {isPlaying ? "Pause" : "Play Recording"}
                  </ShinyButton>
                )}
                <ShinyButton
                  onClick={
                    isRecording ? handleStopRecording : handleStartRecording
                  }
                  className={isRecording ? "!border-red-500" : ""}
                >
                  {isRecording
                    ? "Stop Recording"
                    : recordedBlob
                      ? "Re-record"
                      : "Start Recording"}
                </ShinyButton>
              </div>
            </div>
          </motion.section>
        )}

        {/* MEDIUM AI Mode: Lyrics Prompt + Recording */}
        {config.aiSupportLevel === "medium" && (
          <>
            <motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="mb-10"
            >
              <h2 className="text-xl font-semibold text-[#eeeeee] mb-4 text-center">
                Describe Your Lyrics Theme
              </h2>
              <MagicCard
                gradientFrom="#d51bdb"
                gradientTo="#ab42ee"
                className="max-w-2xl mx-auto"
              >
                <div className="p-6">
                  <textarea
                    placeholder="Describe the lyrics you want AI to generate...

Examples:
- A love song about summer nights
- An upbeat track about following your dreams
- A melancholic ballad about lost friendship"
                    value={lyricsPrompt}
                    onChange={(e) => setLyricsPrompt(e.target.value)}
                    className="w-full h-40 bg-transparent text-[#eeeeee] placeholder:text-[#eeeeee]/40 resize-none focus:outline-none"
                  />
                </div>
              </MagicCard>
              <p className="text-center mt-4 text-[#eeeeee]/50 text-sm">
                AI will generate partial lyrics with gaps for you to fill in
              </p>
            </motion.section>

            {/* Recording for Medium Mode */}
            <motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="mb-10"
            >
              <h2 className="text-xl font-semibold text-[#eeeeee] mb-4 text-center">
                Record Your Parts
              </h2>
              <div className="text-center">
                <div className="mb-6">
                  <div
                    className={`inline-flex items-center justify-center w-24 h-24 rounded-full transition-all duration-300 ${
                      isRecording
                        ? "bg-red-500/20 animate-pulse"
                        : recordedBlob
                          ? "bg-[#7bd2ff]/20"
                          : "bg-[#ab42ee]/20"
                    }`}
                  >
                    {isRecording ? (
                      <Square className="w-12 h-12 text-red-500" />
                    ) : recordedBlob ? (
                      isPlaying ? (
                        <Pause className="w-12 h-12 text-[#7bd2ff]" />
                      ) : (
                        <Play className="w-12 h-12 text-[#7bd2ff]" />
                      )
                    ) : (
                      <Mic className="w-12 h-12 text-[#ab42ee]" />
                    )}
                  </div>
                  {isRecording && (
                    <p className="text-red-500 font-mono mt-2 text-lg">
                      {formatTime(recordingTime)}
                    </p>
                  )}
                </div>

                <p className="text-[#eeeeee]/70 mb-6 max-w-md mx-auto">
                  {recordedBlob
                    ? "Recording saved! AI will blend your vocals with generated sections."
                    : "Record vocals to fill in the chorus/gaps. AI will handle the verses."}
                </p>

                <div className="flex justify-center gap-4">
                  {recordedBlob && !isRecording && (
                    <ShinyButton
                      onClick={handlePlayRecording}
                      className="!border-[#7bd2ff]"
                    >
                      {isPlaying ? "Pause" : "Play"}
                    </ShinyButton>
                  )}
                  <ShinyButton
                    onClick={
                      isRecording ? handleStopRecording : handleStartRecording
                    }
                    className={isRecording ? "!border-red-500" : ""}
                  >
                    {isRecording
                      ? "Stop"
                      : recordedBlob
                        ? "Re-record"
                        : "Record"}
                  </ShinyButton>
                </div>
              </div>
            </motion.section>
          </>
        )}

        {/* Next Button */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="text-center"
        >
          <ShinyButton
            onClick={handleNext}
            disabled={!canProceed}
            className={!canProceed ? "opacity-50 cursor-not-allowed" : ""}
          >
            Continue to Processing
          </ShinyButton>
          {!canProceed && (
            <p className="text-[#eeeeee]/50 text-sm mt-2">
              {!selectedVoice
                ? "Please select a voice to continue"
                : config.aiSupportLevel === "low"
                  ? "Please record your vocals"
                  : "Please record your vocals for the chorus sections"}
            </p>
          )}
        </motion.div>
      </div>
    </main>
  );
}
