import { createContext, useContext, useState, type ReactNode } from 'react';

export type Instrument = 'drums' | 'guitar' | 'piano' | 'vocals';
export type Hand = 'left' | 'right';

export interface PlayerConfig {
  instrument: Instrument | null;
  hand: Hand;
}

export interface VocalSettings {
  voiceId: string;
  voiceName: string;
  retuneSpeed: number;
  enableAutotune: boolean;
  vocalVolume: number;
  instrumentalVolume: number;
}

export interface SessionConfig {
  playerCount: 1 | 2 | 3;
  players: PlayerConfig[];
  bpm: number;
  keyNote: string;
  keyMode: string;
}

interface SessionContextType {
  config: SessionConfig;
  setConfig: (config: SessionConfig) => void;
  recordedBlob: Blob | null;
  setRecordedBlob: (blob: Blob | null) => void;
  vocalSettings: VocalSettings | null;
  setVocalSettings: (settings: VocalSettings | null) => void;
  vocalBlob: Blob | null;
  setVocalBlob: (blob: Blob | null) => void;
  instrumentalAudioUrl: string | null;
  setInstrumentalAudioUrl: (url: string | null) => void;
  hasVocals: boolean;
}

const defaultConfig: SessionConfig = {
  playerCount: 1,
  players: [{ instrument: null, hand: 'right' }],
  bpm: 120,
  keyNote: 'E',
  keyMode: 'Minor',
};

const SessionContext = createContext<SessionContextType | null>(null);

export const SessionProvider = ({ children }: { children: ReactNode }) => {
  const [config, setConfig] = useState<SessionConfig>(defaultConfig);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [vocalSettings, setVocalSettings] = useState<VocalSettings | null>(null);
  const [vocalBlob, setVocalBlob] = useState<Blob | null>(null);
  const [instrumentalAudioUrl, setInstrumentalAudioUrl] = useState<string | null>(null);

  // Check if any player has vocals
  const hasVocals = config.players.some((p) => p.instrument === 'vocals');

  return (
    <SessionContext.Provider
      value={{
        config,
        setConfig,
        recordedBlob,
        setRecordedBlob,
        vocalSettings,
        setVocalSettings,
        vocalBlob,
        setVocalBlob,
        instrumentalAudioUrl,
        setInstrumentalAudioUrl,
        hasVocals,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = () => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};

// Available ElevenLabs voices
export const AVAILABLE_VOICES = [
  { id: 'xO2Q4ARMEd4BI2sGDH9c', name: 'Deep Voice', description: 'Deep male voice' },
  { id: 'JJQDkHrp6uKU5Vk0WKhY', name: 'Smooth Voice', description: 'Smooth male voice' },
  { id: 'Nggzl2QAXh3OijoXD116', name: 'Energetic Voice', description: 'Energetic voice' },
  { id: 'mtrellq69YZsNwzUSyXh', name: 'Warm Voice', description: 'Warm voice' },
  { id: 'LRpNiUBlcqgIsKUzcrlN', name: 'Clear Voice', description: 'Clear voice' },
  { id: 'CKfuQaJKfvUG2Wtrda3Y', name: 'Rich Voice', description: 'Rich voice' },
  { id: 'SgG3x729SgH346SJc0ck', name: 'Soft Voice', description: 'Soft voice' },
  { id: 'pZv6Kbgq62dtlvkJTupr', name: 'Bright Voice', description: 'Bright voice' },
  { id: 'lP1EpPqqTU5DCn2ga6OD', name: 'Dynamic Voice', description: 'Dynamic voice' },
  { id: 'ui0NMIinCTg8KvB4ogeV', name: 'Expressive Voice', description: 'Expressive voice' },
];
