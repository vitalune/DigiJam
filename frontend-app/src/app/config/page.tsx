"use client";

import { useRouter } from "next/navigation";
import { useConfig, Instrument, Handedness, AiSupportLevel } from "@/contexts/config-context";
import { ShineBorder } from "@/components/ui/shine-border";
import { ShinyButton } from "@/components/ui/shiny-button";
import { AnimatedThemeToggler } from "@/components/ui/animated-theme-toggler";
import { AVAILABLE_KEYS, AI_SUPPORT_LEVELS, INSTRUMENT_INFO } from "@/lib/config-constants";
import { cn } from "@/lib/utils";

function ConfigSection({
  title,
  children
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative rounded-xl bg-white/90 backdrop-blur-sm p-6 shadow-lg">
      <ShineBorder
        shineColor={["#d51bdb", "#7bd2ff", "#ab42ee"]}
        borderWidth={2}
        duration={10}
      />
      <h3 className="text-xl font-bold mb-4">{title}</h3>
      {children}
    </div>
  );
}

function SelectionButton({
  selected,
  onClick,
  children,
  className = "",
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-4 py-3 rounded-lg border-2 transition-all duration-200 text-left",
        selected
          ? "border-[#d51bdb] bg-[#d51bdb]/10"
          : "border-gray-300 hover:border-[#7bd2ff] bg-white",
        className
      )}
    >
      {children}
    </button>
  );
}

export default function ConfigPage() {
  const router = useRouter();
  const {
    config,
    isHydrated,
    setNumUsers,
    setInstruments,
    setHandedness,
    setMusicalKey,
    setAiSupportLevel,
    setIncludeVocals,
  } = useConfig();

  const handlePlay = () => {
    router.push("/recording");
  };

  // Derived state for conditional rendering
  const showKeySelection = config.instruments.includes("guitar") || config.instruments.includes("piano");
  const showGuitarHandedness = config.instruments.includes("guitar");
  const showDrumsHandedness = config.instruments.includes("drums");

  // Prevent hydration mismatch
  if (!isHydrated) {
    return (
      <main className="config-page min-h-screen flex items-center justify-center">
        <div>Loading configuration...</div>
      </main>
    );
  }

  return (
    <main className="config-page min-h-screen flex flex-col items-center px-4 py-12 gap-8 relative">
      {/* Theme Toggler */}
      <div className="absolute top-4 right-4">
        <AnimatedThemeToggler />
      </div>

      {/* Header */}
      <header className="text-center">
        <h1 className="text-4xl md:text-5xl font-bold mb-2">
          Configure Your Session
        </h1>
        <p className="text-lg text-muted">
          Set up your instruments and preferences
        </p>
      </header>

      {/* Form sections */}
      <div className="w-full max-w-3xl flex flex-col gap-6">

        {/* 1. Number of Users */}
        <ConfigSection title="Number of Players">
          <div className="flex gap-4 flex-wrap">
            {([1, 2, 3] as const).map((num) => (
              <SelectionButton
                key={num}
                selected={config.numUsers === num}
                onClick={() => setNumUsers(num)}
                className="flex-1 min-w-[100px] text-center"
              >
                <span className="text-2xl font-bold block">{num}</span>
                <span className="block text-sm mt-1 text-muted">
                  {num === 1 ? "Solo" : num === 2 ? "Duo" : "Trio"}
                </span>
              </SelectionButton>
            ))}
          </div>
        </ConfigSection>

        {/* 2. Instrument Selection */}
        <ConfigSection title="Instruments">
          {config.numUsers === 1 ? (
            <div className="flex gap-4 flex-wrap">
              {(["drums", "guitar", "piano"] as const).map((inst) => (
                <SelectionButton
                  key={inst}
                  selected={config.instruments[0] === inst}
                  onClick={() => setInstruments([inst])}
                  className="flex-1 min-w-[120px] text-center"
                >
                  <span className="text-3xl block">{INSTRUMENT_INFO[inst].icon}</span>
                  <span className="block font-semibold mt-2">{INSTRUMENT_INFO[inst].name}</span>
                  <span className="block text-xs text-muted mt-1">
                    {INSTRUMENT_INFO[inst].description}
                  </span>
                </SelectionButton>
              ))}
            </div>
          ) : config.numUsers === 2 ? (
            <div>
              <p className="text-sm text-muted mb-3">
                Drums is always included. Choose a second instrument:
              </p>
              <div className="flex gap-4 flex-wrap">
                {(["guitar", "piano"] as const).map((inst) => (
                  <SelectionButton
                    key={inst}
                    selected={config.instruments.includes(inst)}
                    onClick={() => setInstruments(["drums", inst])}
                    className="flex-1 min-w-[150px] text-center"
                  >
                    <span className="text-3xl block">{INSTRUMENT_INFO[inst].icon}</span>
                    <span className="block font-semibold mt-2">{INSTRUMENT_INFO[inst].name}</span>
                  </SelectionButton>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <p className="text-sm text-muted mb-3">
                All instruments will be used for a trio session:
              </p>
              <div className="flex gap-4 flex-wrap">
                {(["drums", "guitar", "piano"] as const).map((inst) => (
                  <div
                    key={inst}
                    className="flex-1 min-w-[120px] px-4 py-3 rounded-lg border-2 border-[#d51bdb] bg-[#d51bdb]/10 text-center"
                  >
                    <span className="text-3xl block">{INSTRUMENT_INFO[inst].icon}</span>
                    <span className="block font-semibold mt-2">
                      {INSTRUMENT_INFO[inst].name}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </ConfigSection>

        {/* 3. Handedness Settings */}
        {(showDrumsHandedness || showGuitarHandedness) && (
          <ConfigSection title="Handedness">
            <div className="flex flex-col gap-4">
              {showDrumsHandedness && (
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Drums - Dominant Hand
                  </label>
                  <div className="flex gap-3">
                    {(["right", "left"] as const).map((hand) => (
                      <SelectionButton
                        key={hand}
                        selected={config.handedness.drums === hand}
                        onClick={() => setHandedness("drums", hand)}
                      >
                        {hand === "right" ? "Right-handed" : "Left-handed"}
                      </SelectionButton>
                    ))}
                  </div>
                </div>
              )}

              {showGuitarHandedness && (
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Guitar - Player Handedness
                  </label>
                  <p className="text-xs text-muted mb-2">
                    Affects player positions: Right-handed = Guitarist on RIGHT
                  </p>
                  <div className="flex gap-3">
                    {(["right", "left"] as const).map((hand) => (
                      <SelectionButton
                        key={hand}
                        selected={config.handedness.guitar === hand}
                        onClick={() => setHandedness("guitar", hand)}
                      >
                        {hand === "right" ? "Right-handed" : "Left-handed"}
                      </SelectionButton>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </ConfigSection>
        )}

        {/* 4. Musical Key Selection */}
        {showKeySelection && (
          <ConfigSection title="Musical Key">
            <p className="text-sm text-muted mb-3">
              Select the key for guitar and piano chords
            </p>
            <div className="grid grid-cols-4 md:grid-cols-6 gap-2">
              {AVAILABLE_KEYS.map((key) => (
                <SelectionButton
                  key={key}
                  selected={config.musicalKey === key}
                  onClick={() => setMusicalKey(key)}
                  className="text-sm py-2 text-center"
                >
                  {key}
                </SelectionButton>
              ))}
            </div>
          </ConfigSection>
        )}

        {/* 5. AI Support Level */}
        <ConfigSection title="AI Support Level">
          <div className="flex gap-4 flex-wrap">
            {AI_SUPPORT_LEVELS.map((level) => (
              <SelectionButton
                key={level.value}
                selected={config.aiSupportLevel === level.value}
                onClick={() => setAiSupportLevel(level.value as AiSupportLevel)}
                className="flex-1 min-w-[200px]"
              >
                <span className="font-bold text-lg block">{level.label}</span>
                <span className="block text-sm text-muted mt-1">
                  {level.description}
                </span>
              </SelectionButton>
            ))}
          </div>
        </ConfigSection>

        {/* 6. Vocals */}
        <ConfigSection title="Vocals">
          <p className="text-sm text-muted mb-3">
            Add vocals to your performance after recording
          </p>
          <div className="flex gap-4">
            <SelectionButton
              selected={!config.includeVocals}
              onClick={() => setIncludeVocals(false)}
              className="flex-1 text-center"
            >
              <span className="text-2xl block">🎵</span>
              <span className="font-bold block mt-2">Instrumental Only</span>
              <span className="block text-xs text-muted mt-1">
                Skip vocals recording
              </span>
            </SelectionButton>
            <SelectionButton
              selected={config.includeVocals}
              onClick={() => setIncludeVocals(true)}
              className="flex-1 text-center"
            >
              <span className="text-2xl block">🎤</span>
              <span className="font-bold block mt-2">Include Vocals</span>
              <span className="block text-xs text-muted mt-1">
                Record vocals after performance
              </span>
            </SelectionButton>
          </div>
        </ConfigSection>
      </div>

      {/* Play Button */}
      <div className="mt-8">
        <ShinyButton
          onClick={handlePlay}
          className="cta-glow text-lg md:text-xl px-12 py-5 font-bold [&_span]:text-black dark:[&_span]:text-white"
        >
          Start Recording
        </ShinyButton>
      </div>
    </main>
  );
}
