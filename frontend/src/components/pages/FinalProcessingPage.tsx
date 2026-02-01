import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { theme } from '../../styles/theme';
import { DecorativeShapes } from '../common/DecorativeShapes';
import { Button } from '../common/Button';
import { useSession } from '../../context/SessionContext';

type ProcessingStage =
  | 'vocals'
  | 'mixing'
  | 'video'
  | 'completed'
  | 'error';

const stageMessages: Record<string, string[]> = {
  vocals: [
    'Transforming your voice...',
    'Applying AI voice conversion...',
    'Processing vocal characteristics...',
  ],
  mixing: [
    'Mixing vocal and instrumental tracks...',
    'Applying autotune corrections...',
    'Balancing audio levels...',
  ],
  video: [
    'Generating your music video...',
    'Creating anime-style avatars...',
    'Syncing visuals to music...',
    'Rendering final video...',
  ],
};

export const FinalProcessingPage = () => {
  const navigate = useNavigate();
  const {
    config,
    recordedBlob,
    vocalSettings,
    vocalBlob,
    instrumentalAudioUrl,
    hasVocals,
  } = useSession();

  const [stage, setStage] = useState<ProcessingStage>('vocals');
  const [messageIndex, setMessageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [finalAudioUrl, setFinalAudioUrl] = useState<string | null>(null);
  const [finalVideoUrl, setFinalVideoUrl] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const hasStarted = useRef(false);

  // Cycle through messages
  useEffect(() => {
    if (stage !== 'completed' && stage !== 'error') {
      const messages = stageMessages[stage] || [];
      if (messages.length > 0) {
        const interval = setInterval(() => {
          setMessageIndex((prev) => (prev + 1) % messages.length);
        }, 3000);
        return () => clearInterval(interval);
      }
    }
  }, [stage]);

  // Process the full pipeline
  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;

    const processFullPipeline = async () => {
      try {
        // If no vocals, skip to video generation
        if (!hasVocals || !vocalBlob || !vocalSettings) {
          setStage('video');
          await generateVideo();
          return;
        }

        // Stage 1: Process vocals
        setStage('vocals');
        setProgress(10);

        const vocalFormData = new FormData();
        vocalFormData.append('audio', vocalBlob, 'vocals.webm');
        vocalFormData.append(
          'config',
          JSON.stringify({
            voiceId: vocalSettings.voiceId,
            enableAutotune: vocalSettings.enableAutotune,
            retuneSpeed: vocalSettings.retuneSpeed,
            keyNote: config.keyNote,
            keyMode: config.keyMode,
          })
        );

        const vocalResponse = await fetch('http://localhost:3001/api/process-vocals', {
          method: 'POST',
          body: vocalFormData,
        });

        if (!vocalResponse.ok) {
          throw new Error('Vocal processing failed');
        }

        const vocalData = await vocalResponse.json();
        setProgress(40);

        // Stage 2: Mix vocals with instrumental
        setStage('mixing');

        const mixFormData = new FormData();
        mixFormData.append(
          'config',
          JSON.stringify({
            transformedVocalsUrl: vocalData.transformedVocalsUrl,
            instrumentalUrl: instrumentalAudioUrl,
            vocalVolume: vocalSettings.vocalVolume,
            instrumentalVolume: vocalSettings.instrumentalVolume,
          })
        );

        const mixResponse = await fetch('http://localhost:3001/api/mix-audio', {
          method: 'POST',
          body: mixFormData,
        });

        if (!mixResponse.ok) {
          throw new Error('Audio mixing failed');
        }

        const mixData = await mixResponse.json();
        setFinalAudioUrl(`http://localhost:3001${mixData.audioUrl}`);
        setProgress(60);

        // Stage 3: Generate video
        await generateVideo(mixData.audioUrl);
      } catch (err) {
        console.error('Processing error:', err);
        setError(err instanceof Error ? err.message : 'An unexpected error occurred');
        setStage('error');
      }
    };

    const generateVideo = async (audioPath?: string) => {
      try {
        setStage('video');
        setProgress(70);

        const videoFormData = new FormData();
        if (recordedBlob) {
          videoFormData.append('video', recordedBlob, 'recording.webm');
        }
        videoFormData.append(
          'config',
          JSON.stringify({
            audioUrl: audioPath || instrumentalAudioUrl,
            bpm: config.bpm,
            keyNote: config.keyNote,
            keyMode: config.keyMode,
            instruments: config.players.map((p) => p.instrument).filter(Boolean),
          })
        );

        const videoResponse = await fetch('http://localhost:3001/api/generate-video', {
          method: 'POST',
          body: videoFormData,
        });

        if (!videoResponse.ok) {
          // Video generation is optional - don't fail if it errors
          console.warn('Video generation failed, continuing without video');
        } else {
          const videoData = await videoResponse.json();
          setFinalVideoUrl(`http://localhost:3001${videoData.videoUrl}`);
        }

        setProgress(100);
        setStage('completed');

        // If we don't have a final audio URL yet, use the instrumental
        if (!finalAudioUrl && instrumentalAudioUrl) {
          setFinalAudioUrl(instrumentalAudioUrl);
        }
      } catch (err) {
        console.error('Video generation error:', err);
        // Don't fail entirely - just skip video
        setProgress(100);
        setStage('completed');
      }
    };

    processFullPipeline();
  }, [
    config,
    recordedBlob,
    vocalSettings,
    vocalBlob,
    instrumentalAudioUrl,
    hasVocals,
    finalAudioUrl,
  ]);

  const handleDownloadAudio = () => {
    if (finalAudioUrl) {
      const a = document.createElement('a');
      a.href = finalAudioUrl;
      a.download = 'digijam-track.wav';
      a.click();
    }
  };

  const handleDownloadVideo = () => {
    if (finalVideoUrl) {
      const a = document.createElement('a');
      a.href = finalVideoUrl;
      a.download = 'digijam-video.mp4';
      a.click();
    }
  };

  const currentMessages = stageMessages[stage] || [];
  const currentMessage = currentMessages[messageIndex] || '';

  const getStageLabel = () => {
    switch (stage) {
      case 'vocals':
        return 'Processing Vocals';
      case 'mixing':
        return 'Mixing Audio';
      case 'video':
        return 'Creating Video';
      case 'completed':
        return 'Complete!';
      case 'error':
        return 'Error';
      default:
        return 'Processing...';
    }
  };

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
          maxWidth: '600px',
          width: '100%',
        }}
      >
        {/* Processing State */}
        {stage !== 'completed' && stage !== 'error' && (
          <>
            {/* Spinner */}
            <div
              style={{
                width: 100,
                height: 100,
                border: `4px solid ${theme.colors.dark.surface}`,
                borderTopColor: theme.colors.accent.pink,
                borderRightColor: theme.colors.accent.yellow,
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
                marginBottom: '2rem',
              }}
            />

            {/* Stage Label */}
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
              {getStageLabel()}
            </h1>

            {/* Status Message */}
            <p
              style={{
                fontSize: '1.1rem',
                color: theme.colors.dark.textMuted,
                minHeight: '1.5em',
                marginBottom: '2rem',
              }}
            >
              {currentMessage}
            </p>

            {/* Progress Bar */}
            <div
              style={{
                width: '100%',
                height: 8,
                backgroundColor: theme.colors.dark.surface,
                borderRadius: 4,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${progress}%`,
                  height: '100%',
                  background: `linear-gradient(90deg, ${theme.colors.accent.pink}, ${theme.colors.accent.yellow})`,
                  borderRadius: 4,
                  transition: 'width 0.5s ease',
                }}
              />
            </div>
            <p
              style={{
                marginTop: '0.5rem',
                fontSize: '0.875rem',
                color: theme.colors.dark.textMuted,
              }}
            >
              {progress}% complete
            </p>

            {/* Stage Indicators */}
            <div
              style={{
                display: 'flex',
                gap: '2rem',
                marginTop: '2rem',
              }}
            >
              {['vocals', 'mixing', 'video'].map((s, i) => (
                <div
                  key={s}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    opacity: stage === s ? 1 : 0.4,
                  }}
                >
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: '50%',
                      backgroundColor:
                        stage === s
                          ? theme.colors.accent.pink
                          : theme.colors.dark.surface,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 600,
                      marginBottom: '0.5rem',
                    }}
                  >
                    {i + 1}
                  </div>
                  <span style={{ fontSize: '0.75rem', textTransform: 'capitalize' }}>{s}</span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Completed State */}
        {stage === 'completed' && (
          <>
            <div
              style={{
                width: 100,
                height: 100,
                borderRadius: '50%',
                background: `linear-gradient(135deg, ${theme.colors.accent.pink}, ${theme.colors.accent.yellow})`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '2rem',
                fontSize: '3rem',
              }}
            >
              ✓
            </div>

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
              Your Music is Ready!
            </h1>

            <p
              style={{
                color: theme.colors.dark.textMuted,
                marginBottom: '2rem',
              }}
            >
              Your AI-produced track{finalVideoUrl ? ' and music video are' : ' is'} complete
            </p>

            {/* Audio Player */}
            {finalAudioUrl && (
              <div
                style={{
                  width: '100%',
                  padding: '1.5rem',
                  backgroundColor: theme.colors.dark.surface,
                  borderRadius: theme.borderRadius.lg,
                  marginBottom: '1.5rem',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: '1rem' }}>Audio Track</div>
                <audio src={finalAudioUrl} controls style={{ width: '100%' }} />
              </div>
            )}

            {/* Video Player */}
            {finalVideoUrl && (
              <div
                style={{
                  width: '100%',
                  padding: '1.5rem',
                  backgroundColor: theme.colors.dark.surface,
                  borderRadius: theme.borderRadius.lg,
                  marginBottom: '1.5rem',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: '1rem' }}>Music Video</div>
                <video
                  src={finalVideoUrl}
                  controls
                  style={{ width: '100%', borderRadius: theme.borderRadius.md }}
                />
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
              {finalAudioUrl && (
                <Button onClick={handleDownloadAudio} variant="secondary">
                  Download Audio
                </Button>
              )}
              {finalVideoUrl && (
                <Button onClick={handleDownloadVideo} variant="secondary">
                  Download Video
                </Button>
              )}
              <Button onClick={() => navigate('/')}>New Session</Button>
            </div>
          </>
        )}

        {/* Error State */}
        {stage === 'error' && (
          <>
            <div
              style={{
                width: 100,
                height: 100,
                borderRadius: '50%',
                backgroundColor: '#ff4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '2rem',
                fontSize: '3rem',
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
                color: theme.colors.dark.textMuted,
                marginBottom: '2rem',
              }}
            >
              {error}
            </p>

            <div style={{ display: 'flex', gap: '1rem' }}>
              <Button onClick={() => navigate('/configure')} variant="secondary">
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
        `}
      </style>
    </div>
  );
};
