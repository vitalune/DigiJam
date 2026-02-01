import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { theme } from '../../styles/theme';
import { DecorativeShapes } from '../common/DecorativeShapes';
import { Button } from '../common/Button';

const guidelines = [
  {
    title: 'Position Yourself',
    description: 'Stand 4-6 feet from your webcam. Make sure your full upper body is visible.',
  },
  {
    title: 'Good Lighting',
    description: 'Face a light source. Avoid backlighting or harsh shadows.',
  },
  {
    title: 'Clear Background',
    description: 'A plain background helps the AI track your movements more accurately.',
  },
  {
    title: 'Move Naturally',
    description: 'Play your air instrument as you normally would. Exaggerate slightly for better detection.',
  },
  {
    title: 'Stay in Frame',
    description: 'Keep your hands and arms visible throughout the performance.',
  },
];

export const InstructionsPage = () => {
  const navigate = useNavigate();
  const [showButton, setShowButton] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowButton(true);
    }, 5000);

    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: theme.colors.light.background,
        color: theme.colors.light.text,
        position: 'relative',
        padding: '2rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <DecorativeShapes subtle />

      <div
        style={{
          position: 'relative',
          zIndex: 1,
          maxWidth: '600px',
          width: '100%',
          textAlign: 'center',
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
          Before You Start
        </h1>
        <p style={{ color: theme.colors.light.textMuted, marginBottom: '2.5rem' }}>
          Follow these tips for the best performance capture
        </p>

        {/* Guidelines */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', textAlign: 'left' }}>
          {guidelines.map((guide, index) => (
            <div
              key={index}
              style={{
                padding: '1.25rem',
                backgroundColor: 'white',
                borderRadius: theme.borderRadius.lg,
                boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                borderLeft: `4px solid ${index % 2 === 0 ? theme.colors.accent.pink : theme.colors.accent.yellow}`,
              }}
            >
              <h3
                style={{
                  fontSize: '1.1rem',
                  fontWeight: 600,
                  marginBottom: '0.25rem',
                  color: theme.colors.light.text,
                }}
              >
                {guide.title}
              </h3>
              <p
                style={{
                  fontSize: '0.95rem',
                  color: theme.colors.light.textMuted,
                  lineHeight: 1.5,
                }}
              >
                {guide.description}
              </p>
            </div>
          ))}
        </div>

        {/* Begin Button with fade-in */}
        <div
          style={{
            marginTop: '3rem',
            opacity: showButton ? 1 : 0,
            transform: showButton ? 'translateY(0)' : 'translateY(10px)',
            transition: 'opacity 0.6s ease, transform 0.6s ease',
          }}
        >
          <Button onClick={() => navigate('/recording')}>Begin</Button>
        </div>

        {/* Loading indicator while waiting */}
        {!showButton && (
          <p
            style={{
              marginTop: '2rem',
              fontSize: '0.875rem',
              color: theme.colors.light.textMuted,
            }}
          >
            Read the guidelines above...
          </p>
        )}
      </div>
    </div>
  );
};
