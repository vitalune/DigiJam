"use client";

import { cn } from "@/lib/utils";
import { VoiceProfile } from "@/lib/voice-constants";
import { motion } from "motion/react";
import { User } from "lucide-react";

interface VoiceSelectorProps {
  voices: VoiceProfile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  className?: string;
}

export function VoiceSelector({
  voices,
  selectedId,
  onSelect,
  className,
}: VoiceSelectorProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 md:grid-cols-5 gap-4",
        className
      )}
    >
      {voices.map((voice, index) => (
        <VoiceCard
          key={voice.id}
          voice={voice}
          isSelected={selectedId === voice.id}
          onSelect={() => onSelect(voice.id)}
          index={index}
        />
      ))}
    </div>
  );
}

interface VoiceCardProps {
  voice: VoiceProfile;
  isSelected: boolean;
  onSelect: () => void;
  index: number;
}

function VoiceCard({ voice, isSelected, onSelect, index }: VoiceCardProps) {
  return (
    <motion.button
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      onClick={onSelect}
      className={cn(
        "group relative flex flex-col items-center p-4 rounded-xl transition-all duration-300",
        "bg-[#1a1a1a] hover:bg-[#252525]"
      )}
      style={{
        boxShadow: isSelected
          ? `0 0 0 2px #232323, 0 0 0 4px ${voice.accentColor}`
          : undefined,
      }}
    >
      {/* Avatar */}
      <div
        className={cn(
          "relative w-16 h-16 md:w-20 md:h-20 rounded-full overflow-hidden mb-3",
          "border-2 transition-all duration-300",
          isSelected ? "border-current scale-110" : "border-transparent group-hover:border-white/30"
        )}
        style={{
          borderColor: isSelected ? voice.accentColor : undefined,
        }}
      >
        {/* Placeholder avatar with icon */}
        <div
          className="w-full h-full flex items-center justify-center"
          style={{
            background: `linear-gradient(135deg, ${voice.accentColor}40, ${voice.accentColor}20)`,
          }}
        >
          <User
            className="w-8 h-8 md:w-10 md:h-10"
            style={{ color: voice.accentColor }}
          />
        </div>
      </div>

      {/* Name */}
      <h3
        className={cn(
          "font-semibold text-sm md:text-base transition-colors",
          isSelected ? "text-white" : "text-[#eeeeee]/80 group-hover:text-white"
        )}
      >
        {voice.name}
      </h3>

      {/* Type */}
      <p
        className="text-xs text-[#eeeeee]/50 mt-0.5"
        style={{
          color: isSelected ? voice.accentColor : undefined,
        }}
      >
        {voice.type}
      </p>

      {/* Description - shown on hover/select */}
      <motion.p
        initial={false}
        animate={{
          opacity: isSelected ? 1 : 0,
          height: isSelected ? "auto" : 0,
        }}
        className="text-xs text-[#eeeeee]/60 text-center mt-2 overflow-hidden"
      >
        {voice.description}
      </motion.p>

      {/* Selection indicator */}
      {isSelected && (
        <motion.div
          layoutId="voice-selection-indicator"
          className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full"
          style={{ backgroundColor: voice.accentColor }}
        />
      )}
    </motion.button>
  );
}
