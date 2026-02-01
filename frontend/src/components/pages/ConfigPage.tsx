import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { theme } from '../../styles/theme';
import { DecorativeShapes } from '../common/DecorativeShapes';
import { Button } from '../common/Button';

type Instrument = 'drums' | 'guitar' | 'piano' | 'vocals';
type Hand = 'left' | 'right';

interface PlayerConfig {
  instrument: Instrument | null;
  hand: Hand;
}

const NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const MODES = ['Major', 'Minor'];

export const ConfigPage = () => {
  const navigate = useNavigate();
  const [userCount, setUserCount] = useState<1 | 2 | 3>(1);
  const [players, setPlayers] = useState<PlayerConfig[]>([{ instrument: null, hand: 'right' }]);
  const [bpm, setBpm] = useState(120);
  const [keyNote, setKeyNote] = useState('E');
  const [keyMode, setKeyMode] = useState('Minor');

  // Update players array when user count changes
  useEffect(() => {
    setPlayers((prev) => {
      const newPlayers: PlayerConfig[] = [];
      for (let i = 0; i < userCount; i++) {
        newPlayers.push(prev[i] || { instrument: null, hand: 'right' });
      }
      // If 2+ users, first player must be drums
      if (userCount >= 2 && newPlayers[0].instrument !== 'drums') {
        newPlayers[0] = { ...newPlayers[0], instrument: 'drums' };
      }
      return newPlayers;
    });
  }, [userCount]);

  const getAvailableInstruments = (playerIndex: number): Instrument[] => {
    const allInstruments: Instrument[] = ['drums', 'guitar', 'piano', 'vocals'];

    // First player with 2+ users must be drums
    if (userCount >= 2 && playerIndex === 0) {
      return ['drums'];
    }

    // Get already selected instruments (excluding vocals which can be duplicated and current player)
    const selectedNonVocals = players
      .filter((_, i) => i !== playerIndex)
      .map((p) => p.instrument)
      .filter((inst): inst is Instrument => inst !== null && inst !== 'vocals');

    // Filter out already selected non-vocal instruments
    return allInstruments.filter(
      (inst) => inst === 'vocals' || !selectedNonVocals.includes(inst)
    );
  };

  const handleInstrumentChange = (playerIndex: number, instrument: Instrument | null) => {
    setPlayers((prev) => {
      const newPlayers = [...prev];
      newPlayers[playerIndex] = { ...newPlayers[playerIndex], instrument };
      return newPlayers;
    });
  };

  const handleHandChange = (playerIndex: number, hand: Hand) => {
    setPlayers((prev) => {
      const newPlayers = [...prev];
      newPlayers[playerIndex] = { ...newPlayers[playerIndex], hand };
      return newPlayers;
    });
  };

  const needsHandConfig = (instrument: Instrument | null) => {
    return instrument && instrument !== 'vocals';
  };

  const isConfigValid = () => {
    return players.every((p) => p.instrument !== null);
  };

  const sectionStyle = {
    marginBottom: '2rem',
  };

  const labelStyle = {
    display: 'block',
    fontSize: '1rem',
    fontWeight: 600,
    color: theme.colors.light.text,
    marginBottom: '0.75rem',
  };

  const checkboxGroupStyle = {
    display: 'flex',
    gap: '1rem',
    flexWrap: 'wrap' as const,
  };

  const checkboxLabelStyle = (selected: boolean, disabled: boolean) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.75rem 1.25rem',
    borderRadius: theme.borderRadius.md,
    border: `2px solid ${selected ? theme.colors.accent.pink : '#ddd'}`,
    backgroundColor: selected ? `${theme.colors.accent.pink}15` : 'white',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'all 0.2s ease',
    fontWeight: 500,
    color: theme.colors.light.text,
  });

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: theme.colors.light.background,
        color: theme.colors.light.text,
        position: 'relative',
        padding: '2rem',
      }}
    >
      <DecorativeShapes subtle />

      <div
        style={{
          position: 'relative',
          zIndex: 1,
          maxWidth: '700px',
          margin: '0 auto',
        }}
      >
        {/* Header */}
        <h1
          style={{
            fontSize: '2.5rem',
            fontWeight: 700,
            marginBottom: '0.5rem',
            background: `linear-gradient(135deg, ${theme.colors.accent.pink} 0%, ${theme.colors.accent.yellow} 100%)`,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          Configure Session
        </h1>
        <p style={{ color: theme.colors.light.textMuted, marginBottom: '2rem' }}>
          Set up your band before the performance
        </p>

        {/* User Count */}
        <div style={sectionStyle}>
          <label style={labelStyle}>Number of Players</label>
          <div style={checkboxGroupStyle}>
            {([1, 2, 3] as const).map((count) => (
              <label
                key={count}
                style={checkboxLabelStyle(userCount === count, false)}
                onClick={() => setUserCount(count)}
              >
                <input
                  type="radio"
                  name="userCount"
                  checked={userCount === count}
                  onChange={() => setUserCount(count)}
                  style={{ display: 'none' }}
                />
                <span
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    border: `2px solid ${userCount === count ? theme.colors.accent.pink : '#ccc'}`,
                    backgroundColor: userCount === count ? theme.colors.accent.pink : 'transparent',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {userCount === count && (
                    <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'white' }} />
                  )}
                </span>
                {count} Player{count > 1 ? 's' : ''}
              </label>
            ))}
          </div>
        </div>

        {/* Players Configuration */}
        {players.map((player, index) => (
          <div
            key={index}
            style={{
              ...sectionStyle,
              padding: '1.5rem',
              backgroundColor: 'white',
              borderRadius: theme.borderRadius.lg,
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
            }}
          >
            <label style={{ ...labelStyle, color: theme.colors.accent.pink }}>
              Player {index + 1}
            </label>

            {/* Instrument Selection */}
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ ...labelStyle, fontSize: '0.875rem', fontWeight: 500 }}>
                Instrument
              </label>
              <div style={checkboxGroupStyle}>
                {(['drums', 'guitar', 'piano', 'vocals'] as Instrument[]).map((inst) => {
                  const available = getAvailableInstruments(index);
                  const isAvailable = available.includes(inst);
                  const isSelected = player.instrument === inst;

                  return (
                    <label
                      key={inst}
                      style={checkboxLabelStyle(isSelected, !isAvailable)}
                      onClick={() => isAvailable && handleInstrumentChange(index, inst)}
                    >
                      <input
                        type="radio"
                        name={`instrument-${index}`}
                        checked={isSelected}
                        disabled={!isAvailable}
                        onChange={() => handleInstrumentChange(index, inst)}
                        style={{ display: 'none' }}
                      />
                      <span
                        style={{
                          width: 18,
                          height: 18,
                          borderRadius: 4,
                          border: `2px solid ${isSelected ? theme.colors.accent.pink : '#ccc'}`,
                          backgroundColor: isSelected ? theme.colors.accent.pink : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '12px',
                          color: 'white',
                        }}
                      >
                        {isSelected && '✓'}
                      </span>
                      {inst.charAt(0).toUpperCase() + inst.slice(1)}
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Dominant Hand (only for non-vocal instruments) */}
            {needsHandConfig(player.instrument) && (
              <div>
                <label style={{ ...labelStyle, fontSize: '0.875rem', fontWeight: 500 }}>
                  Dominant Hand
                </label>
                <div style={checkboxGroupStyle}>
                  {(['left', 'right'] as Hand[]).map((hand) => (
                    <label
                      key={hand}
                      style={checkboxLabelStyle(player.hand === hand, false)}
                      onClick={() => handleHandChange(index, hand)}
                    >
                      <input
                        type="radio"
                        name={`hand-${index}`}
                        checked={player.hand === hand}
                        onChange={() => handleHandChange(index, hand)}
                        style={{ display: 'none' }}
                      />
                      <span
                        style={{
                          width: 18,
                          height: 18,
                          borderRadius: '50%',
                          border: `2px solid ${player.hand === hand ? theme.colors.accent.yellow : '#ccc'}`,
                          backgroundColor: player.hand === hand ? theme.colors.accent.yellow : 'transparent',
                        }}
                      />
                      {hand.charAt(0).toUpperCase() + hand.slice(1)}
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}

        {/* BPM */}
        <div style={sectionStyle}>
          <label style={labelStyle}>
            Tempo: {bpm} BPM
          </label>
          <input
            type="range"
            min={60}
            max={180}
            value={bpm}
            onChange={(e) => setBpm(Number(e.target.value))}
            style={{
              width: '100%',
              height: 8,
              borderRadius: 4,
              appearance: 'none',
              background: `linear-gradient(to right, ${theme.colors.accent.pink} 0%, ${theme.colors.accent.yellow} 100%)`,
              cursor: 'pointer',
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: theme.colors.light.textMuted, marginTop: '0.25rem' }}>
            <span>60</span>
            <span>180</span>
          </div>
        </div>

        {/* Key Selection */}
        <div style={sectionStyle}>
          <label style={labelStyle}>Key</label>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            {/* Note Selection */}
            <select
              value={keyNote}
              onChange={(e) => setKeyNote(e.target.value)}
              style={{
                padding: '0.75rem 1rem',
                borderRadius: theme.borderRadius.md,
                border: `2px solid ${theme.colors.accent.pink}`,
                backgroundColor: 'white',
                fontSize: '1rem',
                fontWeight: 500,
                cursor: 'pointer',
                minWidth: 80,
              }}
            >
              {NOTES.map((note) => (
                <option key={note} value={note}>
                  {note}
                </option>
              ))}
            </select>

            {/* Mode Selection */}
            <div style={checkboxGroupStyle}>
              {MODES.map((mode) => (
                <label
                  key={mode}
                  style={checkboxLabelStyle(keyMode === mode, false)}
                  onClick={() => setKeyMode(mode)}
                >
                  <input
                    type="radio"
                    name="keyMode"
                    checked={keyMode === mode}
                    onChange={() => setKeyMode(mode)}
                    style={{ display: 'none' }}
                  />
                  <span
                    style={{
                      width: 18,
                      height: 18,
                      borderRadius: '50%',
                      border: `2px solid ${keyMode === mode ? theme.colors.accent.yellow : '#ccc'}`,
                      backgroundColor: keyMode === mode ? theme.colors.accent.yellow : 'transparent',
                    }}
                  />
                  {mode}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Play Button */}
        <div style={{ marginTop: '3rem', textAlign: 'center' }}>
          <Button
            onClick={() => navigate('/instructions')}
            disabled={!isConfigValid()}
            style={{
              opacity: isConfigValid() ? 1 : 0.5,
              cursor: isConfigValid() ? 'pointer' : 'not-allowed',
            }}
          >
            Play
          </Button>
          {!isConfigValid() && (
            <p style={{ marginTop: '0.75rem', fontSize: '0.875rem', color: theme.colors.light.textMuted }}>
              Please select an instrument for each player
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
