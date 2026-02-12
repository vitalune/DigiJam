// Available keys from audio/music_theory.py
export const AVAILABLE_KEYS = [
  "C Major", "C Minor",
  "Db Major", "Db Minor",
  "D Major", "D Minor",
  "Eb Major", "Eb Minor",
  "E Major", "E Minor",
  "F Major", "F Minor",
  "Gb Major", "Gb Minor",
  "G Major", "G Minor",
  "Ab Major", "Ab Minor",
  "A Major", "A Minor",
  "Bb Major", "Bb Minor",
  "B Major", "B Minor",
] as const;

export const DEFAULT_KEY = "C Major";

export const INSTRUMENTS = ["drums", "guitar", "piano"] as const;

export const NUM_USERS_OPTIONS = [1, 2, 3] as const;

export const AI_SUPPORT_LEVELS = [
  { value: "low", label: "Low", description: "Minimal AI - you sing everything, AI adds subtle melody" },
  { value: "medium", label: "Medium", description: "Collaborative - AI sings parts, you fill in the gaps" },
  { value: "high", label: "High", description: "Full AI - complete vocals generated automatically" },
] as const;

export const INSTRUMENT_INFO = {
  drums: {
    name: "Drums",
    icon: "🥁",
    description: "Air drums tracked via body movement",
  },
  guitar: {
    name: "Guitar",
    icon: "🎸",
    description: "Virtual guitar with strum detection",
  },
  piano: {
    name: "Piano",
    icon: "🎹",
    description: "Phantom piano with chord zones",
  },
} as const;
