import type { CSSProperties } from 'react';
import { theme } from '../../styles/theme';

interface ShapeProps {
  style?: CSSProperties;
  color: 'pink' | 'yellow';
  size?: number;
  blur?: number;
  opacity?: number;
}

interface DecorativeShapesProps {
  subtle?: boolean;
}

const GlowOrb = ({ style, color, size = 300, blur = 80, opacity = 0.25 }: ShapeProps) => {
  const baseColor = color === 'pink' ? theme.colors.accent.pinkSubtle : theme.colors.accent.yellowSubtle;

  return (
    <div
      style={{
        position: 'absolute',
        width: size,
        height: size,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${baseColor} 0%, transparent 70%)`,
        filter: `blur(${blur}px)`,
        opacity,
        pointerEvents: 'none',
        ...style,
      }}
    />
  );
};

const GeometricShape = ({ style, color, size = 200, opacity = 0.15 }: ShapeProps) => {
  const baseColor = color === 'pink' ? theme.colors.accent.pinkSubtle : theme.colors.accent.yellowSubtle;

  return (
    <div
      style={{
        position: 'absolute',
        width: size,
        height: size,
        border: `2px solid ${baseColor}`,
        borderRadius: '20%',
        transform: 'rotate(45deg)',
        opacity,
        pointerEvents: 'none',
        ...style,
      }}
    />
  );
};

export const DecorativeShapes = ({ subtle = false }: DecorativeShapesProps) => {
  const orbOpacity = subtle ? 0.4 : 1;
  const shapeOpacity = subtle ? 0.15 : 0.3;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        overflow: 'hidden',
        pointerEvents: 'none',
        zIndex: 0,
      }}
    >
      {/* Top left pink glow */}
      <GlowOrb
        color="pink"
        size={400}
        blur={100}
        opacity={orbOpacity}
        style={{ top: -150, left: -150 }}
      />

      {/* Top right yellow glow */}
      <GlowOrb
        color="yellow"
        size={350}
        blur={90}
        opacity={orbOpacity}
        style={{ top: -100, right: -100 }}
      />

      {/* Bottom left yellow glow */}
      <GlowOrb
        color="yellow"
        size={300}
        blur={80}
        opacity={orbOpacity}
        style={{ bottom: -100, left: -50 }}
      />

      {/* Bottom right pink glow */}
      <GlowOrb
        color="pink"
        size={450}
        blur={110}
        opacity={orbOpacity}
        style={{ bottom: -200, right: -150 }}
      />

      {/* Geometric accents */}
      <GeometricShape
        color="pink"
        size={150}
        opacity={shapeOpacity}
        style={{ top: 100, left: 50 }}
      />
      <GeometricShape
        color="yellow"
        size={100}
        opacity={shapeOpacity * 0.8}
        style={{ top: 200, right: 80 }}
      />
      <GeometricShape
        color="yellow"
        size={180}
        opacity={shapeOpacity * 0.7}
        style={{ bottom: 150, left: 100 }}
      />
      <GeometricShape
        color="pink"
        size={120}
        opacity={shapeOpacity}
        style={{ bottom: 80, right: 120 }}
      />
    </div>
  );
};
