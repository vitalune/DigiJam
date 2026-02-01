import { useNavigate } from 'react-router-dom';
import { theme } from '../../styles/theme';
import { DecorativeShapes } from '../common/DecorativeShapes';
import { Button } from '../common/Button';

export const HomePage = () => {
  const navigate = useNavigate();

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

      {/* Main content */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          maxWidth: '800px',
          gap: '2rem',
        }}
      >
        {/* Title */}
        <h1
          style={{
            fontSize: 'clamp(4rem, 12vw, 8rem)',
            fontWeight: 800,
            letterSpacing: '-0.02em',
            background: `linear-gradient(135deg, ${theme.colors.dark.text} 0%, ${theme.colors.accent.pink} 50%, ${theme.colors.accent.yellow} 100%)`,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            marginBottom: '0.5rem',
          }}
        >
          DigiJam
        </h1>

        {/* Caption */}
        <p
          style={{
            fontSize: 'clamp(1.25rem, 3vw, 1.75rem)',
            fontWeight: 600,
            color: theme.colors.accent.pink,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}
        >
          Your body is the instrument. AI is the producer.
        </p>

        {/* Description */}
        <p
          style={{
            fontSize: 'clamp(1rem, 2vw, 1.25rem)',
            lineHeight: 1.7,
            color: theme.colors.dark.textMuted,
            maxWidth: '600px',
            marginTop: '1rem',
          }}
        >
          Transform human movement into studio-quality music. Stand in front of your
          webcam, mime your instrument, and watch AI turn your performance into a
          professionally mixed track — no instruments required.
        </p>

        {/* Button */}
        <div style={{ marginTop: '2rem' }}>
          <Button onClick={() => navigate('/configure')}>Configure Environment</Button>
        </div>
      </div>
    </div>
  );
};
