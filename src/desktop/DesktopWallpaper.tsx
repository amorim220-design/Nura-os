import { useEffect, useState } from 'react';
import { NuraCenterpiece } from '../components/NuraLogo';
import { ThemeConfig } from '../types/os';

interface DesktopWallpaperProps {
  theme: ThemeConfig;
}

function calcCenterScale() {
  if (typeof window === 'undefined') return 1;
  return Math.max(
    0.58,
    Math.min(1.06, Math.min(window.innerWidth / 560, window.innerHeight / 560))
  );
}

export function DesktopWallpaper({ theme }: DesktopWallpaperProps) {
  const [centerScale, setCenterScale] = useState<number>(calcCenterScale);

  useEffect(() => {
    const onResize = () => setCenterScale(calcCenterScale());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return (
    <div
      className="absolute inset-0 overflow-hidden pointer-events-none select-none"
      style={{ background: theme.wallpaperGradient }}
      aria-hidden="true"
    >
      {theme.wallpaperImage && (
        <img
          src={theme.wallpaperImage}
          alt=""
          referrerPolicy="no-referrer"
          className="absolute inset-0 w-full h-full object-cover opacity-55"
        />
      )}

      {/* Deep ambient radial glow behind centerpiece */}
      <div
        className="absolute inset-0"
        style={{
          background: theme.isLight
            ? 'radial-gradient(circle at 50% 48%, rgba(2, 132, 199, 0.14) 0%, transparent 62%)'
            : 'radial-gradient(circle at 50% 48%, rgba(6, 182, 212, 0.16) 0%, rgba(2, 5, 11, 0.65) 58%, rgba(0, 0, 0, 0.85) 100%)',
        }}
      />

      {/* Angled futuristic glass prism shards at bottom corners (matching boot frame 00:07) */}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 1920 1080"
        preserveAspectRatio="none"
      >
        <polygon
          points="0,840 310,1080 0,1080"
          fill={theme.isLight ? 'rgba(2, 132, 199, 0.08)' : 'rgba(14, 116, 144, 0.18)'}
          stroke="var(--nura-border-strong)"
          strokeOpacity="0.45"
          strokeWidth="1.5"
        />
        <polygon
          points="0,925 195,1080 0,1080"
          fill={theme.isLight ? 'rgba(29, 78, 216, 0.06)' : 'rgba(6, 182, 212, 0.09)'}
          stroke="var(--nura-accent)"
          strokeOpacity="0.28"
          strokeWidth="1"
        />
        <polygon
          points="1920,840 1610,1080 1920,1080"
          fill={theme.isLight ? 'rgba(2, 132, 199, 0.08)' : 'rgba(14, 116, 144, 0.18)'}
          stroke="var(--nura-border-strong)"
          strokeOpacity="0.45"
          strokeWidth="1.5"
        />
        <polygon
          points="1920,925 1725,1080 1920,1080"
          fill={theme.isLight ? 'rgba(29, 78, 216, 0.06)' : 'rgba(6, 182, 212, 0.09)'}
          stroke="var(--nura-accent)"
          strokeOpacity="0.28"
          strokeWidth="1"
        />
      </svg>

      {/* Centerpiece Triangle + Concentric Orbital Rings + Varino NURA OS */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pb-12">
        <NuraCenterpiece scale={centerScale} showWordmark isLight={theme.isLight} />
      </div>
    </div>
  );
}
