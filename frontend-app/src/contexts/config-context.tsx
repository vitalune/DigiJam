"use client";

import React, { createContext, useContext, useCallback, useMemo } from "react";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { DEFAULT_KEY } from "@/lib/config-constants";

export type Instrument = "drums" | "guitar" | "piano";
export type Handedness = "right" | "left";
export type AiSupportLevel = "low" | "medium" | "high";

export interface HandednessConfig {
  drums?: Handedness;
  guitar?: Handedness;
}

export interface VocalsConfig {
  voiceId: string | null;
  lyricsPrompt: string | null;
  userVocalsBlob: Blob | null;
}

export interface SessionConfig {
  numUsers: 1 | 2 | 3;
  instruments: Instrument[];
  handedness: HandednessConfig;
  musicalKey: string;
  aiSupportLevel: AiSupportLevel;
  includeVocals: boolean;
  vocalsConfig: VocalsConfig;
}

export interface SessionResult {
  audioUrl: string;
  videoUrl: string;
  duration: number;
}

const DEFAULT_VOCALS_CONFIG: VocalsConfig = {
  voiceId: null,
  lyricsPrompt: null,
  userVocalsBlob: null,
};

const DEFAULT_CONFIG: SessionConfig = {
  numUsers: 1,
  instruments: ["drums"],
  handedness: { drums: "right", guitar: "right" },
  musicalKey: DEFAULT_KEY,
  aiSupportLevel: "low",
  includeVocals: false,
  vocalsConfig: DEFAULT_VOCALS_CONFIG,
};

interface ConfigContextType {
  config: SessionConfig;
  sessionResult: SessionResult | null;
  isHydrated: boolean;
  setNumUsers: (num: 1 | 2 | 3) => void;
  setInstruments: (instruments: Instrument[]) => void;
  setHandedness: (instrument: Instrument, hand: Handedness) => void;
  setMusicalKey: (key: string) => void;
  setAiSupportLevel: (level: AiSupportLevel) => void;
  setIncludeVocals: (include: boolean) => void;
  setVocalsConfig: (vocalsConfig: Partial<VocalsConfig>) => void;
  setSessionResult: (result: SessionResult | null) => void;
  resetConfig: () => void;
}

const ConfigContext = createContext<ConfigContextType | undefined>(undefined);

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig, isHydrated] = useLocalStorage<SessionConfig>(
    "digijam-config",
    DEFAULT_CONFIG
  );
  const [sessionResult, setSessionResult] = useLocalStorage<SessionResult | null>(
    "digijam-session-result",
    null
  );

  const setNumUsers = useCallback((num: 1 | 2 | 3) => {
    setConfig((prev) => {
      let instruments: Instrument[];
      if (num === 1) {
        // Keep first instrument or default to drums
        instruments = [prev.instruments[0] || "drums"];
      } else if (num === 2) {
        // Drums + choice of guitar or piano
        const melodic = prev.instruments.includes("piano") ? "piano" : "guitar";
        instruments = ["drums", melodic];
      } else {
        // All three instruments
        instruments = ["drums", "guitar", "piano"];
      }
      return { ...prev, numUsers: num, instruments };
    });
  }, [setConfig]);

  const setInstruments = useCallback((instruments: Instrument[]) => {
    setConfig((prev) => ({ ...prev, instruments }));
  }, [setConfig]);

  const setHandedness = useCallback((instrument: Instrument, hand: Handedness) => {
    setConfig((prev) => ({
      ...prev,
      handedness: { ...prev.handedness, [instrument]: hand },
    }));
  }, [setConfig]);

  const setMusicalKey = useCallback((key: string) => {
    setConfig((prev) => ({ ...prev, musicalKey: key }));
  }, [setConfig]);

  const setAiSupportLevel = useCallback((level: AiSupportLevel) => {
    setConfig((prev) => ({ ...prev, aiSupportLevel: level }));
  }, [setConfig]);

  const setIncludeVocals = useCallback((include: boolean) => {
    setConfig((prev) => ({ ...prev, includeVocals: include }));
  }, [setConfig]);

  const setVocalsConfig = useCallback((vocalsConfig: Partial<VocalsConfig>) => {
    setConfig((prev) => ({
      ...prev,
      vocalsConfig: { ...prev.vocalsConfig, ...vocalsConfig },
    }));
  }, [setConfig]);

  const resetConfig = useCallback(() => {
    setConfig(DEFAULT_CONFIG);
    setSessionResult(null);
  }, [setConfig]);

  const value = useMemo(
    () => ({
      config,
      sessionResult,
      isHydrated,
      setNumUsers,
      setInstruments,
      setHandedness,
      setMusicalKey,
      setAiSupportLevel,
      setIncludeVocals,
      setVocalsConfig,
      setSessionResult,
      resetConfig,
    }),
    [config, sessionResult, isHydrated, setNumUsers, setInstruments, setHandedness, setMusicalKey, setAiSupportLevel, setIncludeVocals, setVocalsConfig, resetConfig]
  );

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useConfig() {
  const context = useContext(ConfigContext);
  if (context === undefined) {
    throw new Error("useConfig must be used within a ConfigProvider");
  }
  return context;
}
