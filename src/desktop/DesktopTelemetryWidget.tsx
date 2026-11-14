import { useEffect, useState } from 'react';
import { simulatedTelemetryProvider } from '../services/telemetryService';
import { PowerProfile, TelemetrySnapshot } from '../types/os';

interface DesktopTelemetryWidgetProps {
  powerProfile: PowerProfile;
  batteryLevel?: number;
  batteryCharging?: boolean;
  onOpenPerformance: () => void;
}

function formatPtDecimal(value: number, digits = 1): string {
  return value.toFixed(digits).replace('.', ',');
}

function WeatherPartlyCloudyIcon() {
  return (
    <svg
      width="34"
      height="26"
      viewBox="0 0 36 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle cx="22" cy="9.5" r="5.5" fill="#FBBF24" />
      <path
        d="M11 23.5H24.5C27.2614 23.5 29.5 21.2614 29.5 18.5C29.5 15.9255 27.5542 13.8058 25.0522 13.5305C24.212 10.6305 21.539 8.5 18.375 8.5C14.578 8.5 11.5 11.578 11.5 15.375C11.5 15.6122 11.512 15.8466 11.5355 16.0777C9.2471 16.4184 7.5 18.391 7.5 20.7778C7.5 22.2812 8.71878 23.5 10.2222 23.5H11Z"
        fill="#F8FAFC"
      />
    </svg>
  );
}

export function DesktopTelemetryWidget({
  powerProfile,
  onOpenPerformance,
}: DesktopTelemetryWidgetProps) {
  const [snapshot, setSnapshot] = useState<TelemetrySnapshot>(() =>
    simulatedTelemetryProvider.getInitialSnapshot()
  );
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const telemetryTimer = window.setInterval(() => {
      setSnapshot((prev) => simulatedTelemetryProvider.nextSnapshot(prev, powerProfile));
    }, 1500);
    const clockTimer = window.setInterval(() => setNow(new Date()), 15000);
    return () => {
      window.clearInterval(telemetryTimer);
      window.clearInterval(clockTimer);
    };
  }, [powerProfile]);

  const timeFormatted = now.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const weekday = now
    .toLocaleDateString('pt-BR', { weekday: 'short' })
    .replace('.', '');
  const day = now.toLocaleDateString('pt-BR', { day: '2-digit' });
  const month = now
    .toLocaleDateString('pt-BR', { month: 'short' })
    .replace('.', '');
  const dateLabel = `${weekday.charAt(0).toUpperCase() + weekday.slice(1)}, ${day} de ${
    month.charAt(0).toUpperCase() + month.slice(1)
  }`;

  const ramPercent = Math.round((snapshot.ramUsedGb / snapshot.ramTotalGb) * 100);
  const storagePercent = Math.round((snapshot.storageUsedGb / snapshot.storageTotalGb) * 100);

  return (
    <aside
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      className="flex flex-col gap-2 sm:gap-2.5 fixed top-3 right-3 sm:top-4 sm:right-4 z-10 w-[216px] sm:w-[262px] md:w-[292px] select-none"
      aria-label="Widgets da área de trabalho NURA OS"
    >
      {/* Top Card: Clock, Date & Simulated Weather */}
      <div
        className="relative rounded-2xl px-3 py-2.5 sm:px-4 sm:py-3.5 backdrop-blur-xl grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-3 overflow-hidden"
        style={{
          backgroundColor: 'var(--nura-surface)',
          border: '1px solid var(--nura-border)',
          boxShadow: '0 14px 36px rgba(0, 0, 0, 0.44), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
          color: 'var(--nura-text)',
        }}
      >
        <div
          className="absolute top-0 left-5 right-5 h-[1px] pointer-events-none"
          style={{
            background:
              'linear-gradient(90deg, transparent, var(--nura-border-strong), transparent)',
          }}
          aria-hidden="true"
        />

        {/* Clock + Date */}
        <div className="flex flex-col items-center text-center min-w-0">
          <div className="font-display text-[24px] sm:text-[32px] md:text-[34px] font-bold leading-none tracking-tight tabular-nums">
            {timeFormatted}
          </div>
          <div
            className="text-[10px] sm:text-[11px] mt-1 sm:mt-1.5 whitespace-nowrap truncate max-w-full"
            style={{ color: 'var(--nura-text-muted)' }}
          >
            {dateLabel}
          </div>
        </div>

        {/* Center Hairline Divider */}
        <div
          className="w-px h-12"
          style={{ backgroundColor: 'var(--nura-border)' }}
          aria-hidden="true"
        />

        {/* Weather (Simulated) */}
        <div className="flex flex-col items-center text-center min-w-0">
          <WeatherPartlyCloudyIcon />
          <div className="font-display text-lg font-bold leading-tight mt-0.5 tabular-nums">
            28°C
          </div>
          <div
            className="text-[10px] leading-tight truncate max-w-full"
            style={{ color: 'var(--nura-text-muted)' }}
            title="Clima demonstrativo (Simulação)"
          >
            Parc. nublado · Sim.
          </div>
        </div>
      </div>

      {/* Bottom Card: CPU, RAM & Storage Widget */}
      <button
        type="button"
        onClick={onOpenPerformance}
        className="relative w-full rounded-2xl px-4 py-3.5 backdrop-blur-xl text-left space-y-3 transition-transform active:scale-[0.99] hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 overflow-hidden"
        style={{
          backgroundColor: 'var(--nura-surface)',
          border: '1px solid var(--nura-border)',
          boxShadow: '0 14px 36px rgba(0, 0, 0, 0.44), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
          color: 'var(--nura-text)',
        }}
        title="Dados demonstrativos · Clique para abrir NURA Performance"
        aria-label="Widget de CPU, RAM e Armazenamento simulados. Clique para abrir NURA Performance."
      >
        <div
          className="absolute top-0 left-5 right-5 h-[1px] pointer-events-none"
          style={{
            background:
              'linear-gradient(90deg, transparent, var(--nura-border-strong), transparent)',
          }}
          aria-hidden="true"
        />

        {/* CPU */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: 'var(--nura-text-muted)' }}>CPU</span>
            <span className="font-mono font-semibold tabular-nums">
              {snapshot.cpuTotalPercent}%
            </span>
          </div>
          <div
            className="h-[7px] w-full rounded-full overflow-hidden"
            style={{ backgroundColor: 'rgba(56, 189, 248, 0.14)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${snapshot.cpuTotalPercent}%`,
                backgroundColor: 'var(--nura-accent)',
              }}
            />
          </div>
        </div>

        {/* RAM */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: 'var(--nura-text-muted)' }}>RAM</span>
            <span className="font-mono font-semibold tabular-nums">
              {formatPtDecimal(snapshot.ramUsedGb)} / {formatPtDecimal(snapshot.ramTotalGb)} GB
            </span>
          </div>
          <div
            className="h-[7px] w-full rounded-full overflow-hidden"
            style={{ backgroundColor: 'rgba(56, 189, 248, 0.14)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${ramPercent}%`,
                backgroundColor: 'var(--nura-accent)',
              }}
            />
          </div>
        </div>

        {/* Armazenamento */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: 'var(--nura-text-muted)' }}>Armazenamento</span>
            <span className="font-mono font-semibold tabular-nums">
              {formatPtDecimal(snapshot.storageUsedGb)} / {formatPtDecimal(snapshot.storageTotalGb)} GB
            </span>
          </div>
          <div
            className="h-[7px] w-full rounded-full overflow-hidden"
            style={{ backgroundColor: 'rgba(56, 189, 248, 0.14)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${storagePercent}%`,
                backgroundColor: 'var(--nura-accent)',
              }}
            />
          </div>
        </div>
      </button>
    </aside>
  );
}
