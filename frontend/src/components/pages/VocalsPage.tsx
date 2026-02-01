import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { theme } from '../../styles/theme';
import { DecorativeShapes } from '../common/DecorativeShapes';
import { Button } from '../common/Button';
import { useSession, AVAILABLE_VOICES } from '../../context/SessionContext';

type RecordingState = 'idle' | 'recording' | 'recorded';

export const VocalsPage = () => {
  const navigate = useNavigate();
  const { config, setVocalSettings, setVocalBlob, instrumentalAudioUrl } = useSession();

  // Voice selection
  const [selectedVoiceIndex, setSelectedVoiceIndex] = useState(0);

  // Autotune settings
  const [enableAutotune, setEnableAutotune] = useState(true);
  const [retuneSpeed, setRetuneSpeed] = useState(50);

  // Volume settings
  const [vocalVolume, setVocalVolume] = useState(100);
  const [instrumentalVolume, setInstrumentalVolume] = useState(80);

  // Recording state
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  // Refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const instrumentalRef = useRef<HTMLAudioElement>(null);

  const selectedVoice = AVAILABLE_VOICES[selectedVoiceIndex];

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        },
      });
      streamRef.current = stream;
      chunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setVocalBlob(blob);
        setRecordingState('recorded');
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(100);
      setRecordingState('recording');
      setRecordingDuration(0);

      // Play instrumental if available
      if (instrumentalRef.current && instrumentalAudioUrl) {
        instrumentalRef.current.currentTime = 0;
        instrumentalRef.current.play();
      }

      // Start duration timer
      timerRef.current = window.setInterval(() => {
        setRecordingDuration((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Microphone access error:', err);
      alert('Could not access microphone. Please check permissions.');
    }
  }, [setVocalBlob, instrumentalAudioUrl]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && recordingState === 'recording') {
      mediaRecorderRef.current.stop();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (instrumentalRef.current) {
        instrumentalRef.current.pause();
      }
    }
  }, [recordingState]);

  const resetRecording = () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    setAudioUrl(null);
    setVocalBlob(null);
    setRecordingState('idle');
    setRecordingDuration(0);
  };

  const handleContinue = () => {
    // Save vocal settings
    setVocalSettings({
      voiceId: selectedVoice.id,
      voiceName: selectedVoice.name,
      retuneSpeed,
      enableAutotune,
      vocalVolume: vocalVolume / 100,
      instrumentalVolume: instrumentalVolume / 100,
    });

    navigate('/final-processing');
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: theme.colors.dark.background,
        color: theme.colors.dark.text,
        position: 'relative',
        padding: '2rem',
      }}
    >
      <DecorativeShapes />

      {/* Hidden audio element for instrumental playback */}
      {instrumentalAudioUrl && (
        <audio ref={instrumentalRef} src={instrumentalAudioUrl} style={{ display: 'none' }} />
      )}

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
          Add Vocals
        </h1>
        <p style={{ color: theme.colors.dark.textMuted, marginBottom: '2rem' }}>
          Record your vocals and transform them with AI
        </p>

        {/* Voice Selection */}
        <div style={{ marginBottom: '2rem' }}>
          <label
            style={{
              display: 'block',
              fontSize: '1rem',
              fontWeight: 600,
              marginBottom: '0.75rem',
            }}
          >
            Select Voice Style
          </label>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
              gap: '0.75rem',
            }}
          >
            {AVAILABLE_VOICES.map((voice, index) => (
              <button
                key={voice.id}
                onClick={() => setSelectedVoiceIndex(index)}
                style={{
                  padding: '1rem',
                  borderRadius: theme.borderRadius.md,
                  border: `2px solid ${selectedVoiceIndex === index ? theme.colors.accent.pink : theme.colors.dark.surface}`,
                  backgroundColor:
                    selectedVoiceIndex === index
                      ? `${theme.colors.accent.pink}20`
                      : theme.colors.dark.surface,
                  color: theme.colors.dark.text,
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  textAlign: 'left',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{voice.name}</div>
                <div style={{ fontSize: '0.75rem', color: theme.colors.dark.textMuted }}>
                  {voice.description}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Autotune Settings */}
        <div
          style={{
            marginBottom: '2rem',
            padding: '1.5rem',
            backgroundColor: theme.colors.dark.surface,
            borderRadius: theme.borderRadius.lg,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={enableAutotune}
                onChange={(e) => setEnableAutotune(e.target.checked)}
                style={{ width: 18, height: 18, accentColor: theme.colors.accent.pink }}
              />
              <span style={{ fontWeight: 600 }}>Enable Autotune</span>
            </label>
            <span style={{ fontSize: '0.875rem', color: theme.colors.dark.textMuted }}>
              Key: {config.keyNote} {config.keyMode}
            </span>
          </div>

          {enableAutotune && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.875rem' }}>Retune Speed</span>
                <span style={{ fontSize: '0.875rem', color: theme.colors.accent.yellow }}>
                  {retuneSpeed}%
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={retuneSpeed}
                onChange={(e) => setRetuneSpeed(Number(e.target.value))}
                style={{
                  width: '100%',
                  height: 6,
                  borderRadius: 3,
                  appearance: 'none',
                  background: `linear-gradient(to right, ${theme.colors.accent.pink} 0%, ${theme.colors.accent.yellow} 100%)`,
                  cursor: 'pointer',
                }}
              />
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '0.75rem',
                  color: theme.colors.dark.textMuted,
                }}
              >
                <span>Natural</span>
                <span>Robotic</span>
              </div>
            </div>
          )}
        </div>

        {/* Volume Controls */}
        <div
          style={{
            marginBottom: '2rem',
            padding: '1.5rem',
            backgroundColor: theme.colors.dark.surface,
            borderRadius: theme.borderRadius.lg,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '1rem' }}>Mix Levels</div>

          <div style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.875rem' }}>Vocal Volume</span>
              <span style={{ fontSize: '0.875rem', color: theme.colors.accent.pink }}>
                {vocalVolume}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={150}
              value={vocalVolume}
              onChange={(e) => setVocalVolume(Number(e.target.value))}
              style={{
                width: '100%',
                height: 4,
                borderRadius: 2,
                appearance: 'none',
                background: theme.colors.dark.background,
                cursor: 'pointer',
              }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.875rem' }}>Instrumental Volume</span>
              <span style={{ fontSize: '0.875rem', color: theme.colors.accent.yellow }}>
                {instrumentalVolume}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={150}
              value={instrumentalVolume}
              onChange={(e) => setInstrumentalVolume(Number(e.target.value))}
              style={{
                width: '100%',
                height: 4,
                borderRadius: 2,
                appearance: 'none',
                background: theme.colors.dark.background,
                cursor: 'pointer',
              }}
            />
          </div>
        </div>

        {/* Recording Section */}
        <div
          style={{
            padding: '2rem',
            backgroundColor: theme.colors.dark.surface,
            borderRadius: theme.borderRadius.lg,
            textAlign: 'center',
          }}
        >
          {recordingState === 'idle' && (
            <>
              <div
                style={{
                  width: 100,
                  height: 100,
                  margin: '0 auto 1.5rem',
                  borderRadius: '50%',
                  backgroundColor: theme.colors.accent.pink,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'transform 0.2s ease',
                }}
                onClick={startRecording}
                onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.05)')}
                onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
              >
                <svg width="40" height="40" viewBox="0 0 24 24" fill="white">
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                </svg>
              </div>
              <p style={{ color: theme.colors.dark.textMuted }}>
                Click to start recording your vocals
              </p>
              {instrumentalAudioUrl && (
                <p style={{ fontSize: '0.875rem', color: theme.colors.accent.yellow, marginTop: '0.5rem' }}>
                  Instrumental will play during recording
                </p>
              )}
            </>
          )}

          {recordingState === 'recording' && (
            <>
              <div
                style={{
                  width: 100,
                  height: 100,
                  margin: '0 auto 1.5rem',
                  borderRadius: '50%',
                  backgroundColor: '#ff4444',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  animation: 'pulse 1s infinite',
                }}
                onClick={stopRecording}
              >
                <div
                  style={{
                    width: 30,
                    height: 30,
                    backgroundColor: 'white',
                    borderRadius: 4,
                  }}
                />
              </div>
              <p style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                {formatDuration(recordingDuration)}
              </p>
              <p style={{ color: theme.colors.dark.textMuted }}>Recording... Click to stop</p>
            </>
          )}

          {recordingState === 'recorded' && audioUrl && (
            <>
              <div
                style={{
                  width: 100,
                  height: 100,
                  margin: '0 auto 1.5rem',
                  borderRadius: '50%',
                  background: `linear-gradient(135deg, ${theme.colors.accent.pink}, ${theme.colors.accent.yellow})`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '2.5rem',
                }}
              >
                ✓
              </div>
              <p style={{ fontWeight: 600, marginBottom: '1rem' }}>
                Recording complete ({formatDuration(recordingDuration)})
              </p>
              <audio
                ref={audioRef}
                src={audioUrl}
                controls
                style={{ width: '100%', marginBottom: '1rem' }}
              />
              <button
                onClick={resetRecording}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: 'transparent',
                  border: `1px solid ${theme.colors.dark.textMuted}`,
                  borderRadius: theme.borderRadius.md,
                  color: theme.colors.dark.textMuted,
                  cursor: 'pointer',
                }}
              >
                Record Again
              </button>
            </>
          )}
        </div>

        {/* Continue Button */}
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <Button
            onClick={handleContinue}
            disabled={recordingState !== 'recorded'}
            style={{
              opacity: recordingState === 'recorded' ? 1 : 0.5,
              cursor: recordingState === 'recorded' ? 'pointer' : 'not-allowed',
            }}
          >
            Continue to Final Mix
          </Button>
        </div>
      </div>

      {/* Pulse animation */}
      <style>
        {`
          @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
          }
        `}
      </style>
    </div>
  );
};
