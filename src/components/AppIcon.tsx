import {
  Activity,
  FolderOpen,
  Gamepad2,
  Info,
  SlidersHorizontal,
  Terminal,
} from 'lucide-react';
import { AppId } from '../types/os';

interface AppIconProps {
  appId: AppId;
  size?: number;
  containerSize?: number;
}

const ICON_COLORS: Record<AppId, { bg: string; fg: string; border: string; glow: string }> = {
  explorer: {
    bg: 'linear-gradient(135deg, rgba(37, 99, 235, 0.28), rgba(6, 182, 212, 0.14))',
    fg: '#38bdf8',
    border: 'rgba(56, 189, 248, 0.48)',
    glow: 'rgba(56, 189, 248, 0.22)',
  },
  terminal: {
    bg: 'linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(6, 182, 212, 0.18))',
    fg: '#22d3ee',
    border: 'rgba(34, 211, 238, 0.48)',
    glow: 'rgba(34, 211, 238, 0.24)',
  },
  'control-center': {
    bg: 'linear-gradient(135deg, rgba(37, 99, 235, 0.24), rgba(99, 102, 241, 0.18))',
    fg: '#60a5fa',
    border: 'rgba(96, 165, 250, 0.46)',
    glow: 'rgba(96, 165, 250, 0.2)',
  },
  'game-hub': {
    bg: 'linear-gradient(135deg, rgba(244, 63, 94, 0.24), rgba(34, 211, 238, 0.12))',
    fg: '#fb7185',
    border: 'rgba(244, 63, 94, 0.46)',
    glow: 'rgba(244, 63, 94, 0.22)',
  },
  performance: {
    bg: 'linear-gradient(135deg, rgba(16, 185, 129, 0.24), rgba(6, 182, 212, 0.14))',
    fg: '#34d399',
    border: 'rgba(52, 211, 153, 0.46)',
    glow: 'rgba(52, 211, 153, 0.2)',
  },
  about: {
    bg: 'linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(56, 189, 248, 0.14))',
    fg: '#818cf8',
    border: 'rgba(129, 140, 248, 0.46)',
    glow: 'rgba(129, 140, 248, 0.2)',
  },
};

export function AppIcon({ appId, size = 20, containerSize = 36 }: AppIconProps) {
  const palette = ICON_COLORS[appId];

  const renderGlyph = () => {
    switch (appId) {
      case 'explorer':
        return <FolderOpen size={size} strokeWidth={1.9} />;
      case 'terminal':
        return <Terminal size={size} strokeWidth={1.9} />;
      case 'control-center':
        return <SlidersHorizontal size={size} strokeWidth={1.9} />;
      case 'game-hub':
        return <Gamepad2 size={size} strokeWidth={1.9} />;
      case 'performance':
        return <Activity size={size} strokeWidth={1.9} />;
      case 'about':
        return <Info size={size} strokeWidth={1.9} />;
    }
  };

  return (
    <span
      className="relative inline-flex items-center justify-center rounded-xl shrink-0 overflow-hidden"
      style={{
        width: containerSize,
        height: containerSize,
        background: palette.bg,
        color: palette.fg,
        border: `1px solid ${palette.border}`,
        boxShadow: `0 6px 18px ${palette.glow}, inset 0 1px 0 rgba(255,255,255,0.18)`,
      }}
      aria-hidden="true"
    >
      {renderGlyph()}
    </span>
  );
}
