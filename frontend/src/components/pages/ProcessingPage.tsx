import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { theme } from '../../styles/theme';
import { DecorativeShapes } from '../common/DecorativeShapes';
import { Button } from '../common/Button';
import { useSession } from '../../context/SessionContext';

type ProcessingStatus = 'uploading' | 'processing' | 'completed' | 'error';

const statusMessages: Record<string, string[]> = {
  uploading: ['Uploading your performance...'],
  processing: [
    'Analyzing your movements...',
    'Detecting instrument gestures...',
    'Extracting musical events...',
    'Rendering audio tracks...',
    'Mixing your masterpiece...',
  ],
};

export const ProcessingPage = () => {
  const navigate = useNavigate();
  const { config, recordedBlob, setInstrumentalAudioUrl, hasVocals } = useSession();
  const [status, setStatus] = useState<ProcessingStatus>('uploading');
  const [messageIndex, setMessageIndex] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const hasStarted = useRef(false);

  // Cycle through status messages
  useEffect(() => {
    if (status === 'processing') {
      const interval = setInterval(() => {
        setMessageIndex((prev) => (prev + 1) % statusMessages.processing.length);
      }, 2500);
      return () => clearInterval(interval);
    }
  }, [status]);

  // Process the recording
  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;

    const processRecording = async () => {
      if (!recordedBlob) {
        setError('No recording found. Please go back and record again.');
        setStatus('error');
        return;
      }

      try {
        setStatus('uploading');

        // Prepare form data
        const formData = new FormData();
        formData.append('video', recordedBlob, 'recording.webm');
        formData.append(
          'config',
          JSON.stringify({
            playerCount: config.playerCount,
            players: config.players,
            bpm: config.bpm,
            keyNote: config.keyNote,
            keyMode: config.keyMode,
          })
        );

        setStatus('processing');

        // Send to backend
        const response = await fetch('http://localhost:3001/api/generate-music', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Processing failed');
        }

        const data = await response.json();
        const fullAudioUrl = `http://localhost:3001${data.audioUrl}`;
        setAudioUrl(fullAudioUrl);
        setInstrumentalAudioUrl(fullAudioUrl);
        setStatus('completed');

        // Auto-navigate based on whether vocals are needed
        if (hasVocals) {
          // Wait a moment to show completion, then navigate to vocals
          setTimeout(() => {
            navigate('/vocals');
          }, 1500);
        }
      } catch (err) {
        console.error('Processing error:', err);
        setError(err instanceof Error ? err.message : 'An unexpected error occurred');
        setStatus('error');
      }
    };

    processRecording();
  }, [recordedBlob, config, setInstrumentalAudioUrl, hasVocals, navigate]);

  const handleRetry = () => {
    navigate('/recording');
  };

  const handleDownload = () => {
    if (audioUrl) {
      const a = document.createElement('a');
      a.href = audioUrl;
      a.download = 'digijam-track.wav';
      a.click();
    }
  };

  const handleContinueToVocals = () => {
    navigate('/vocals');
  };

  const handleFinish = () => {
    navigate('/final-processing');
  };

  const currentMessage =
    status === 'uploading'
      ? statusMessages.uploading[0]
      : status === 'processing'
        ? statusMessages.processing[messageIndex]
        : '';

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: theme.colors.dark.background,
        color: theme.colors.dark.text,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        padding: '2rem',
      }}
    >
      <DecorativeShapes />

      <div
        style={{
          position: 'relative',
          zIndex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          maxWidth: '500px',
        }}
      >
        {/* Processing State */}
        {(status === 'uploading' || status === 'processing') && (
          <>
            {/* Spinner */}
            <div
              style={{
                width: 80,
                height: 80,
                border: `4px solid ${theme.colors.dark.surface}`,
                borderTopColor: theme.colors.accent.pink,
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
                marginBottom: '2rem',
              }}
            />

            {/* Title */}
            <h1
              style={{
                fontSize: '2rem',
                fontWeight: 700,
                marginBottom: '1rem',
                background: `linear-gradient(135deg, ${theme.colors.accent.pink} 0%, ${theme.colors.accent.yellow} 100%)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              Creating your instrumental...
            </h1>

            {/* Status Message */}
            <p
              style={{
                fontSize: '1.1rem',
                color: theme.colors.dark.textMuted,
                minHeight: '1.5em',
                transition: 'opacity 0.3s ease',
              }}
            >
              {currentMessage}
            </p>

            {/* Progress Bar */}
            <div
              style={{
                width: '100%',
                height: 4,
                backgroundColor: theme.colors.dark.surface,
                borderRadius: 2,
                marginTop: '2rem',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: '30%',
                  height: '100%',
                  background: `linear-gradient(90deg, ${theme.colors.accent.pink}, ${theme.colors.accent.yellow})`,
                  borderRadius: 2,
                  animation: 'progress 2s ease-in-out infinite',
                }}
              />
            </div>
          </>
        )}

        {/* Completed State */}
        {status === 'completed' && audioUrl && (
          <>
            <div
              style={{
                width: 80,
                height: 80,
                borderRadius: '50%',
                background: `linear-gradient(135deg, ${theme.colors.accent.pink}, ${theme.colors.accent.yellow})`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '2rem',
                fontSize: '2.5rem',
              }}
            >
              ✓
            </div>

            <h1
              style={{
                fontSize: '2rem',
                fontWeight: 700,
                marginBottom: '0.5rem',
                background: `linear-gradient(135deg, ${theme.colors.accent.pink} 0%, ${theme.colors.accent.yellow} 100%)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              {hasVocals ? 'Instrumental Ready!' : 'Your track is ready!'}
            </h1>

            <p
              style={{
                fontSize: '1rem',
                color: theme.colors.dark.textMuted,
                marginBottom: '2rem',
              }}
            >
              {hasVocals
                ? 'Preview your instrumental before adding vocals'
                : 'Listen to your AI-produced masterpiece'}
            </p>

            {/* Audio Player */}
            <div
              style={{
                width: '100%',
                padding: '1.5rem',
                backgroundColor: theme.colors.dark.surface,
                borderRadius: theme.borderRadius.lg,
                marginBottom: '1.5rem',
              }}
            >
              <audio
                ref={audioRef}
                src={audioUrl}
                controls
                style={{
                  width: '100%',
                  height: 50,
                }}
              />
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
              <Button onClick={handleDownload} variant="secondary">
                Download
              </Button>
              {hasVocals ? (
                <Button onClick={handleContinueToVocals}>Continue to Vocals</Button>
              ) : (
                <Button onClick={handleFinish}>Generate Video</Button>
              )}
            </div>
          </>
        )}

        {/* Error State */}
        {status === 'error' && (
          <>
            <div
              style={{
                width: 80,
                height: 80,
                borderRadius: '50%',
                backgroundColor: '#ff4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '2rem',
                fontSize: '2.5rem',
              }}
            >
              ✕
            </div>

            <h1
              style={{
                fontSize: '2rem',
                fontWeight: 700,
                marginBottom: '0.5rem',
                color: '#ff4444',
              }}
            >
              Something went wrong
            </h1>

            <p
              style={{
                fontSize: '1rem',
                color: theme.colors.dark.textMuted,
                marginBottom: '2rem',
              }}
            >
              {error}
            </p>

            <div style={{ display: 'flex', gap: '1rem' }}>
              <Button onClick={handleRetry} variant="secondary">
                Try Again
              </Button>
              <Button onClick={() => navigate('/')}>Start Over</Button>
            </div>
          </>
        )}
      </div>

      {/* Animations */}
      <style>
        {`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
          @keyframes progress {
            0% { transform: translateX(-100%); }
            50% { transform: translateX(200%); }
            100% { transform: translateX(-100%); }
          }
        `}
      </style>
    </div>
  );
};
