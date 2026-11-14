import { useEffect, useState } from 'react';
import { NuraCenterpiece } from '../components/NuraLogo';

interface BootScreenProps {
  bootKey: number;
  onComplete: () => void;
}

export function BootScreen({ bootKey, onComplete }: BootScreenProps) {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [fadingOut, setFadingOut] = useState(false);

  useEffect(() => {
    setElapsedMs(0);
    setFadingOut(false);

    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReduced) {
      setElapsedMs(4200);
      const t = window.setTimeout(() => {
        setFadingOut(true);
        window.setTimeout(onComplete, 180);
      }, 450);
      return () => window.clearTimeout(t);
    }

    const totalMs = 4200;
    const start = performance.now();
    let rafId = 0;
    let endTimer = 0;

    const tick = (now: number) => {
      const dt = Math.min(totalMs, now - start);
      setElapsedMs(dt);

      if (dt < totalMs) {
        rafId = window.requestAnimationFrame(tick);
      } else {
        setFadingOut(true);
        endTimer = window.setTimeout(onComplete, 340);
      }
    };

    rafId = window.requestAnimationFrame(tick);

    return () => {
      window.cancelAnimationFrame(rafId);
      window.clearTimeout(endTimer);
    };
  }, [bootKey, onComplete]);

  // Choreographed timeline matching the attached NURA OS boot video (0s -> 4.2s)
  // 0.00 - 0.55s: Void + laser line
  // 0.35 - 1.25s: Triangle + concentric orbital rings ignite + cyan flare sweep
  // 1.15 - 2.00s: Dark glass center band + Varino "NURA OS" left-to-right reveal + corner glass shards
  // 1.85 - 4.00s: Glowing cyan progress beam with flare head sweeps 0% -> 100%
  const ringReveal = Math.max(0, Math.min(1, (elapsedMs - 260) / 700));
  const wordmarkReveal = Math.max(0, Math.min(1, (elapsedMs - 1100) / 800));
  const shardReveal = Math.max(0, Math.min(1, (elapsedMs - 1250) / 650));
  const barVisible = elapsedMs >= 1800;
  const barProgress = Math.max(0, Math.min(100, ((elapsedMs - 1850) / 2150) * 100));

  const stageLabel =
    elapsedMs < 1100
      ? 'Inicializando núcleo gráfico NURA OS...'
      : elapsedMs < 2200
      ? 'Carregando ambiente Alpine / postmarketOS (simulado)...'
      : elapsedMs < 3300
      ? 'Montando sistema de arquivos virtual (VFS)...'
      : 'Preparando área de trabalho NURA Desktop...';

  const handleSkip = () => {
    setElapsedMs(4200);
    setFadingOut(true);
    window.setTimeout(onComplete, 180);
  };

  // Responsive scale so centerpiece fits comfortably even on smaller landscape phones
  const vpW = typeof window !== 'undefined' ? window.innerWidth : 1280;
  const vpH = typeof window !== 'undefined' ? window.innerHeight : 720;
  const scale = Math.max(0.62, Math.min(1.06, Math.min(vpW / 540, vpH / 540)));

  return (
    <div
      className={`fixed inset-0 z-[150] overflow-hidden flex flex-col items-center justify-center transition-opacity duration-300 ${
        fadingOut ? 'opacity-0 pointer-events-none' : 'opacity-100'
      }`}
      style={{
        backgroundColor: '#000000',
        backgroundImage:
          'radial-gradient(circle at 50% 48%, rgba(6, 182, 212, 0.1) 0%, rgba(15, 23, 42, 0.25) 45%, #000000 82%)',
        color: '#f1f5f9',
      }}
      role="status"
      aria-live="polite"
      aria-label="Inicializando NURA OS Desktop"
    >
      {/* Bottom-left & bottom-right angled futuristic prism shards (matching 00:02 - 00:07) */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none transition-opacity duration-700"
        style={{ opacity: shardReveal }}
        viewBox="0 0 1920 1080"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <polygon
          points="0,840 310,1080 0,1080"
          fill="rgba(14, 116, 144, 0.16)"
          stroke="rgba(56, 189, 248, 0.35)"
          strokeWidth="1.5"
        />
        <polygon
          points="0,920 200,1080 0,1080"
          fill="rgba(6, 182, 212, 0.08)"
          stroke="rgba(34, 211, 238, 0.22)"
          strokeWidth="1"
        />
        <polygon
          points="1920,840 1610,1080 1920,1080"
          fill="rgba(14, 116, 144, 0.16)"
          stroke="rgba(56, 189, 248, 0.35)"
          strokeWidth="1.5"
        />
        <polygon
          points="1920,920 1720,1080 1920,1080"
          fill="rgba(6, 182, 212, 0.08)"
          stroke="rgba(34, 211, 238, 0.22)"
          strokeWidth="1"
        />
      </svg>

      {/* Initial horizontal cyan laser line entering from left (00:00) */}
      <div
        className="absolute left-0 right-1/2 top-1/2 -translate-y-1/2 h-[2px] pointer-events-none nura-laser-in"
        style={{
          background:
            'linear-gradient(90deg, transparent, rgba(34, 211, 238, 0.9), #ffffff)',
          boxShadow: '0 0 16px rgba(34, 211, 238, 0.8)',
        }}
        aria-hidden="true"
      />

      {/* Right-side vertical/horizontal cyan optical flare sweep (00:01) */}
      <div
        className="absolute top-1/2 left-1/2 -translate-y-1/2 pointer-events-none nura-flare-sweep"
        aria-hidden="true"
      >
        <div
          className="w-3 h-48 rounded-full blur-[2px]"
          style={{
            background:
              'linear-gradient(180deg, transparent, rgba(56, 189, 248, 0.9), #ffffff, rgba(56, 189, 248, 0.9), transparent)',
          }}
        />
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-2 rounded-full blur-[1px]"
          style={{
            background:
              'linear-gradient(90deg, transparent, #67e8f9, #ffffff, #67e8f9, transparent)',
          }}
        />
      </div>

      {/* Center Triangle + Orbital Rings + Varino NURA OS */}
      <div className="relative flex flex-col items-center justify-center">
        <NuraCenterpiece
          scale={scale}
          showWordmark
          ringReveal={ringReveal}
          wordmarkReveal={wordmarkReveal}
        />

        {/* Sleek Glowing Cyan Progress Track below rings (00:04 - 00:06) */}
        <div
          className="mt-4 w-[min(340px,78vw)] transition-opacity duration-300"
          style={{ opacity: barVisible ? 1 : 0 }}
        >
          <div
            className="relative h-[4px] w-full rounded-full overflow-visible"
            style={{
              backgroundColor: 'rgba(56, 189, 248, 0.14)',
              border: '1px solid rgba(56, 189, 248, 0.22)',
            }}
          >
            <div
              className="relative h-full rounded-full"
              style={{
                width: `${barProgress}%`,
                background: 'linear-gradient(90deg, #0284c7, #22d3ee, #e0f2fe)',
                boxShadow: '0 0 14px rgba(34, 211, 238, 0.85)',
              }}
            >
              {/* Bright Cyan Optical Flare Head */}
              <span
                className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 w-3.5 h-3.5 rounded-full"
                style={{
                  background:
                    'radial-gradient(circle, #ffffff 0%, #67e8f9 45%, transparent 75%)',
                  boxShadow: '0 0 16px 4px rgba(34, 211, 238, 0.9)',
                }}
              />
            </div>
          </div>

          <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-slate-400">
            <span className="truncate">{stageLabel}</span>
            <span className="font-mono tabular-nums text-cyan-300 shrink-0">
              {Math.round(barProgress)}%
            </span>
          </div>
        </div>
      </div>

      {/* Skip control */}
      <button
        type="button"
        onClick={handleSkip}
        className="fixed bottom-5 right-5 h-[38px] px-4 rounded-xl text-xs font-medium text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
        style={{ border: '1px solid rgba(56, 189, 248, 0.26)' }}
      >
        Pular inicialização
      </button>
    </div>
  );
}
