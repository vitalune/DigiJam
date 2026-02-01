export const theme = {
  colors: {
    dark: {
      background: '#1a1a1a',
      surface: '#2d2d2d',
      text: '#ffffff',
      textMuted: '#a0a0a0',
    },
    light: {
      background: '#f5f5f5',
      surface: '#ffffff',
      text: '#1a1a1a',
      textMuted: '#6b6b6b',
    },
    accent: {
      pink: '#ff6b9d',
      pinkSubtle: '#ffb3c6',
      pinkGlow: 'rgba(255, 107, 157, 0.4)',
      yellow: '#ffd93d',
      yellowSubtle: '#fff0b3',
      yellowGlow: 'rgba(255, 217, 61, 0.4)',
    },
  },
  fonts: {
    display: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    body: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },
  spacing: {
    xs: '0.25rem',
    sm: '0.5rem',
    md: '1rem',
    lg: '1.5rem',
    xl: '2rem',
    xxl: '4rem',
  },
  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '16px',
    full: '9999px',
  },
};

export type Theme = typeof theme;
