import { createContext, useContext, useState, type ReactNode } from 'react';

export type Instrument = 'drums' | 'guitar' | 'piano' | 'vocals';
export type Hand = 'left' | 'right';

export interface PlayerConfig {
  instrument: Instrument | null;
  hand: Hand;
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

  return (
    <SessionContext.Provider value={{ config, setConfig, recordedBlob, setRecordedBlob }}>
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
