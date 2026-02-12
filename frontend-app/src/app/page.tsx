import Link from "next/link";
import { VideoText } from "@/components/ui/video-text";
import { Highlighter } from "@/components/ui/highlighter";
import { ShinyButton } from "@/components/ui/shiny-button";

function Background3D() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none">
      {/* Large glowing orbs */}
      <div
        className="absolute w-[400px] h-[400px] rounded-full pulse-glow"
        style={{
          background: "radial-gradient(circle, var(--accent-magenta) 0%, transparent 70%)",
          top: "10%",
          left: "-10%",
        }}
      />
      <div
        className="absolute w-[300px] h-[300px] rounded-full pulse-glow"
        style={{
          background: "radial-gradient(circle, var(--accent-cyan) 0%, transparent 70%)",
          top: "60%",
          right: "-5%",
          animationDelay: "2s",
        }}
      />
      <div
        className="absolute w-[250px] h-[250px] rounded-full pulse-glow"
        style={{
          background: "radial-gradient(circle, var(--accent-purple) 0%, transparent 70%)",
          bottom: "5%",
          left: "20%",
          animationDelay: "1s",
        }}
      />
      <div
        className="absolute w-[200px] h-[200px] rounded-full pulse-glow"
        style={{
          background: "radial-gradient(circle, var(--accent-yellow) 0%, transparent 70%)",
          top: "20%",
          right: "15%",
          animationDelay: "3s",
        }}
      />

      {/* Floating 3D spheres */}
      <div
        className="absolute w-20 h-20 sphere float-element"
        style={{
          background: "radial-gradient(circle at 30% 30%, var(--accent-magenta), transparent 70%)",
          border: "1px solid rgba(213, 27, 219, 0.5)",
          top: "15%",
          left: "10%",
          animationDelay: "0s",
        }}
      />
      <div
        className="absolute w-16 h-16 sphere float-element-reverse"
        style={{
          background: "radial-gradient(circle at 30% 30%, var(--accent-cyan), transparent 70%)",
          border: "1px solid rgba(123, 210, 255, 0.5)",
          top: "70%",
          left: "8%",
          animationDelay: "1s",
        }}
      />
      <div
        className="absolute w-12 h-12 sphere float-element"
        style={{
          background: "radial-gradient(circle at 30% 30%, var(--accent-yellow), transparent 70%)",
          border: "1px solid rgba(238, 225, 60, 0.5)",
          top: "40%",
          right: "12%",
          animationDelay: "2s",
        }}
      />
      <div
        className="absolute w-24 h-24 sphere float-element-reverse"
        style={{
          background: "radial-gradient(circle at 30% 30%, var(--accent-purple), transparent 70%)",
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
        <div className="w-14 h-14 border-2 border-accent-cyan/50 rotate-45 transform-gpu"
          style={{
            background: "linear-gradient(135deg, rgba(123, 210, 255, 0.1) 0%, transparent 50%)",
            boxShadow: "0 0 20px rgba(123, 210, 255, 0.3)"
          }}
        />
      </div>
      <div
        className="absolute float-element-reverse"
        style={{ bottom: "30%", left: "15%", animationDelay: "2.5s" }}
      >
        <div className="w-10 h-10 border-2 border-accent-yellow/50 rotate-12 transform-gpu"
          style={{
            background: "linear-gradient(135deg, rgba(238, 225, 60, 0.1) 0%, transparent 50%)",
            boxShadow: "0 0 15px rgba(238, 225, 60, 0.3)"
          }}
        />
      </div>
      <div
        className="absolute float-element"
        style={{ top: "55%", left: "5%", animationDelay: "3.5s" }}
      >
        <div className="w-8 h-8 border-2 border-accent-magenta/50 -rotate-12 transform-gpu"
          style={{
            background: "linear-gradient(135deg, rgba(213, 27, 219, 0.1) 0%, transparent 50%)",
            boxShadow: "0 0 15px rgba(213, 27, 219, 0.3)"
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

export default function Home() {
  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12 gap-12 relative overflow-hidden">
      <Background3D />

      {/* Content container */}
      <div className="relative z-10 flex flex-col items-center gap-10">
        {/* Header - VideoText Title */}
        <div className="relative h-[180px] md:h-[280px] lg:h-[380px] w-screen">
          <VideoText
            src="/videos/concertvideo1.mp4"
            fontSize={18}
            fontWeight="900"
            fontFamily="system-ui, sans-serif"
          >
            DIGIJAM
          </VideoText>
        </div>

        {/* Caption */}
        <h2 className="text-3xl md:text-4xl lg:text-5xl text-foreground text-center font-bold">
          Your body is the instrument.{" "}
          <br className="md:hidden" />
          AI is the producer.
        </h2>

        {/* Description - With highlighted keywords */}
        <p className="text-xl md:text-2xl text-foreground/90 text-center max-w-4xl leading-relaxed">
          DigiJam uses{" "}
          <Highlighter action="highlight" color="#7bd2ff" strokeWidth={2}>
            machine vision
          </Highlighter>{" "}
          to track your gestures as you play{" "}
          <Highlighter action="highlight" color="#eee13c" strokeWidth={2}>
            air drums
          </Highlighter>
          , strum an{" "}
          <Highlighter action="highlight" color="#eee13c" strokeWidth={2}>
            invisible guitar
          </Highlighter>
          , or tap on a{" "}
          <Highlighter action="highlight" color="#eee13c" strokeWidth={2}>
            phantom piano
          </Highlighter>{" "}
          . The system captures every movement with{" "}
          <Highlighter action="highlight" color="#d51bdb" strokeWidth={2}>
            millisecond precision
          </Highlighter>
          , converts it to audio, and mixes it into a{" "}
          <Highlighter action="highlight" color="#ab42ee" strokeWidth={2}>
            polished track
          </Highlighter>
          . When you&apos;re done, you get a{" "}
          <Highlighter action="highlight" color="#7bd2ff" strokeWidth={2}>
            shareable music video
          </Highlighter>{" "}
          featuring{" "}
          <Highlighter action="highlight" color="#d51bdb" strokeWidth={2}>
            AI-generated avatars
          </Highlighter>{" "}
          of you and your bandmates.
        </p>

        {/* CTA Button */}
        <Link href="/config" className="mt-6">
          <ShinyButton className="cta-glow text-lg md:text-xl px-10 py-4 font-semibold border-2">
            Configure Environment
          </ShinyButton>
        </Link>
      </div>
    </main>
  );
}
