/**
 * Voice profiles for the vocals page.
 * Maps ElevenLabs voice IDs to display information.
 */

export interface VoiceProfile {
  id: string;
  elevenLabsId: string;
  name: string;
  type: string;
  description: string;
  avatarUrl: string;
  accentColor: string;
}

export const VOICE_PROFILES: VoiceProfile[] = [
  {
    id: "edouard",
    elevenLabsId: "xO2Q4ARMEd4BI2sGDH9c",
    name: "Edouard",
    type: "Professional Male",
    description: "Confident French professional with sophisticated charm",
    avatarUrl: "/avatars/edouard.png",
    accentColor: "#7bd2ff",
  },
  {
    id: "kuya",
    elevenLabsId: "JJQDkHrp6uKU5Vk0WKhY",
    name: "Kuya",
    type: "Energetic Male",
    description: "Upbeat Filipino announcer with infectious energy",
    avatarUrl: "/avatars/kuya.png",
    accentColor: "#eee13c",
  },
  {
    id: "candy",
    elevenLabsId: "Nggzl2QAXh3OijoXD116",
    name: "Candy",
    type: "Sweet Female",
    description: "Young kawaii voice with playful sweetness",
    avatarUrl: "/avatars/candy.png",
    accentColor: "#d51bdb",
  },
  {
    id: "rex-thunder",
    elevenLabsId: "mtrellq69YZsNwzUSyXh",
    name: "Rex Thunder",
    type: "Powerful Male",
    description: "Deep tough American voice with commanding presence",
    avatarUrl: "/avatars/rex-thunder.png",
    accentColor: "#ab42ee",
  },
  {
    id: "georg",
    elevenLabsId: "LRpNiUBlcqgIsKUzcrlN",
    name: "Georg",
    type: "Character Male",
    description: "Funny German grandfather with warm charm",
    avatarUrl: "/avatars/georg.png",
    accentColor: "#eee13c",
  },
  {
    id: "lison",
    elevenLabsId: "CKfuQaJKfvUG2Wtrda3Y",
    name: "Lison",
    type: "Elegant Female",
    description: "Seductive soft French voice with refined elegance",
    avatarUrl: "/avatars/lison.png",
    accentColor: "#d51bdb",
  },
  {
    id: "cherry",
    elevenLabsId: "SgG3x729SgH346SJc0ck",
    name: "Cherry",
    type: "Confident Female",
    description: "Eloquent Black female voice with elegant confidence",
    avatarUrl: "/avatars/cherry.png",
    accentColor: "#7bd2ff",
  },
  {
    id: "nata",
    elevenLabsId: "pZv6Kbgq62dtlvkJTupr",
    name: "Nata",
    type: "Artistic Female",
    description: "Tranquil Spanish singing teacher with warm artistry",
    avatarUrl: "/avatars/nata.png",
    accentColor: "#ab42ee",
  },
  {
    id: "american-bass",
    elevenLabsId: "lP1EpPqqTU5DCn2ga6OD",
    name: "American Bass",
    type: "Deep Male",
    description: "Rich deep bass voice with distinguished resonance",
    avatarUrl: "/avatars/american-bass.png",
    accentColor: "#7bd2ff",
  },
  {
    id: "sanna",
    elevenLabsId: "ui0NMIinCTg8KvB4ogeV",
    name: "Sanna Hartfield",
    type: "Soulful Female",
    description: "Funky soulful singer with artistic expression",
    avatarUrl: "/avatars/sanna.png",
    accentColor: "#d51bdb",
  },
];

export function getVoiceById(id: string): VoiceProfile | undefined {
  return VOICE_PROFILES.find((v) => v.id === id);
}

export function getVoiceByElevenLabsId(elevenLabsId: string): VoiceProfile | undefined {
  return VOICE_PROFILES.find((v) => v.elevenLabsId === elevenLabsId);
}
