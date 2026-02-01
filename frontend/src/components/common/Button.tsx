import type { ButtonHTMLAttributes, CSSProperties } from 'react';
import { theme } from '../../styles/theme';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary';
  size?: 'md' | 'lg';
}

export const Button = ({
  children,
  variant = 'primary',
  size = 'lg',
  style,
  ...props
}: ButtonProps) => {
  const baseStyles: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 600,
    borderRadius: theme.borderRadius.lg,
    transition: 'all 0.2s ease',
    position: 'relative',
    overflow: 'hidden',
  };

  const sizeStyles: Record<string, CSSProperties> = {
    md: {
      padding: '0.75rem 1.5rem',
      fontSize: '1rem',
    },
    lg: {
      padding: '1rem 2.5rem',
      fontSize: '1.125rem',
    },
  };

  const variantStyles: Record<string, CSSProperties> = {
    primary: {
      background: `linear-gradient(135deg, ${theme.colors.accent.pink} 0%, ${theme.colors.accent.yellow} 100%)`,
      color: '#1a1a1a',
      boxShadow: `0 4px 20px ${theme.colors.accent.pinkGlow}`,
    },
    secondary: {
      background: 'transparent',
      color: theme.colors.dark.text,
      border: `2px solid ${theme.colors.accent.pink}`,
    },
  };

  return (
    <button
      style={{
        ...baseStyles,
        ...sizeStyles[size],
        ...variantStyles[variant],
        ...style,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = `0 6px 30px ${theme.colors.accent.pinkGlow}`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow =
          variant === 'primary' ? `0 4px 20px ${theme.colors.accent.pinkGlow}` : 'none';
      }}
      {...props}
    >
      {children}
    </button>
  );
};
