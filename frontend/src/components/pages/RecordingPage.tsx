import { useRef, useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { theme } from '../../styles/theme';
import { useSession, type Instrument } from '../../context/SessionContext';

export const RecordingPage = () => {
  const navigate = useNavigate();
  const { config, setRecordedBlob } = useSession();
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Start webcam
  useEffect(() => {
    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1920 },
            height: { ideal: 1080 },
            facingMode: 'user',
          },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        setError('Could not access webcam. Please ensure camera permissions are granted.');
        console.error('Camera error:', err);
      }
    };

    startCamera();

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  // Start recording after countdown
  const startRecording = useCallback(() => {
    if (!streamRef.current) return;

    chunksRef.current = [];
    const mediaRecorder = new MediaRecorder(streamRef.current, {
      mimeType: 'video/webm;codecs=vp9',
    });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data);
      }
    };

    mediaRecorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'video/webm' });
      setRecordedBlob(blob);
      navigate('/processing');
    };

    mediaRecorderRef.current = mediaRecorder;
    mediaRecorder.start();
    setIsRecording(true);
  }, [navigate, setRecordedBlob]);

  // Countdown and start recording
  useEffect(() => {
    // Start countdown immediately when page loads
    setCountdown(3);
  }, []);

  useEffect(() => {
    if (countdown === null) return;

    if (countdown > 0) {
      const timer = setTimeout(() => {
        setCountdown(countdown - 1);
      }, 1000);
      return () => clearTimeout(timer);
    } else if (countdown === 0) {
      setCountdown(null);
      startRecording();
    }
  }, [countdown, startRecording]);

  // Stop recording
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  // Handle spacebar to stop
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && isRecording) {
        e.preventDefault();
        stopRecording();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isRecording, stopRecording]);

  // Get instruments being recorded
  const instruments = config.players
    .map((p) => p.instrument)
    .filter((i): i is Instrument => i !== null)
    .map((i) => i.charAt(0).toUpperCase() + i.slice(1))
    .join(' + ');

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: '#000',
        overflow: 'hidden',
      }}
    >
      {/* Webcam Feed */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: 'scaleX(-1)', // Mirror the video
        }}
      />

      {/* Error Message */}
      {error && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0,0,0,0.8)',
            color: 'white',
            padding: '2rem',
            textAlign: 'center',
          }}
        >
          <p style={{ fontSize: '1.25rem' }}>{error}</p>
        </div>
      )}

      {/* Countdown Overlay */}
      {countdown !== null && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0,0,0,0.6)',
          }}
        >
          <span
            style={{
              fontSize: '12rem',
              fontWeight: 800,
              color: 'white',
              textShadow: `0 0 60px ${theme.colors.accent.pink}`,
            }}
          >
            {countdown}
          </span>
        </div>
      )}

      {/* Recording Indicator */}
      {isRecording && (
        <div
          style={{
            position: 'absolute',
            top: '2rem',
            left: '2rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.75rem 1.25rem',
            backgroundColor: 'rgba(0,0,0,0.6)',
            borderRadius: theme.borderRadius.lg,
          }}
        >
          <span
            style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              backgroundColor: '#ff4444',
              animation: 'pulse 1s infinite',
            }}
          />
          <span style={{ color: 'white', fontWeight: 600 }}>Recording</span>
        </div>
      )}

      {/* Session Info */}
      <div
        style={{
          position: 'absolute',
          top: '2rem',
          right: '2rem',
          padding: '0.75rem 1.25rem',
          backgroundColor: 'rgba(0,0,0,0.6)',
          borderRadius: theme.borderRadius.lg,
          color: 'white',
          fontSize: '0.875rem',
        }}
      >
        <div style={{ fontWeight: 600 }}>{instruments}</div>
        <div style={{ opacity: 0.8 }}>
          {config.bpm} BPM • {config.keyNote} {config.keyMode}
        </div>
      </div>

      {/* Stop Recording Button */}
      {isRecording && (
        <button
          onClick={stopRecording}
          style={{
            position: 'absolute',
            bottom: '2rem',
            right: '2rem',
            padding: '1rem 1.5rem',
            backgroundColor: 'rgba(0,0,0,0.7)',
            border: `2px solid ${theme.colors.accent.pink}`,
            borderRadius: theme.borderRadius.lg,
            color: 'white',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = theme.colors.accent.pink;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(0,0,0,0.7)';
          }}
        >
          <span
            style={{
              padding: '0.25rem 0.5rem',
              backgroundColor: 'rgba(255,255,255,0.2)',
              borderRadius: 4,
              fontSize: '0.75rem',
            }}
          >
            SPACE
          </span>
          Stop Recording
        </button>
      )}

      {/* Pulse animation */}
      <style>
        {`
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
          }
        `}
      </style>
    </div>
  );
};
