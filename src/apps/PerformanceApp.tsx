import { Cpu, HardDrive, MemoryStick, Thermometer } from 'lucide-react';
import { useEffect, useState } from 'react';
import { simulatedTelemetryProvider } from '../services/telemetryService';
import { PowerProfile, TelemetrySnapshot } from '../types/os';

interface PerformanceAppProps {
  powerProfile: PowerProfile;
}

function SparkAreaChart({
  values,
  color,
  max = 100,
}: {
  values: number[];
  color: string;
  max?: number;
}) {
  const width = 260;
  const height = 74;
  const pts = values.map((v, i) => {
    const x = (i / Math.max(1, values.length - 1)) * width;
    const y = height - (Math.min(max, Math.max(0, v)) / max) * (height - 8) - 4;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const linePath = `M ${pts.join(' L ')}`;
  const areaPath = `${linePath} L ${width},${height} L 0,${height} Z`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-[74px] overflow-visible"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={areaPath} fill={color} fillOpacity="0.14" />
      <path d={linePath} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

export function PerformanceApp({ powerProfile }: PerformanceAppProps) {
  const [snapshot, setSnapshot] = useState<TelemetrySnapshot>(() =>
    simulatedTelemetryProvider.getInitialSnapshot()
  );
  const [cpuSeries, setCpuSeries] = useState<number[]>(() =>
    Array.from({ length: 24 }, () => 22)
  );
  const [ramSeries, setRamSeries] = useState<number[]>(() =>
    Array.from({ length: 24 }, () => 42)
  );
  const [gpuSeries, setGpuSeries] = useState<number[]>(() =>
    Array.from({ length: 24 }, () => 18)
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSnapshot((prev) => {
        const next = simulatedTelemetryProvider.nextSnapshot(prev, powerProfile);
        setCpuSeries((s) => [...s.slice(1), next.cpuTotalPercent]);
        setRamSeries((s) => [
          ...s.slice(1),
          Math.round((next.ramUsedGb / next.ramTotalGb) * 100),
        ]);
        setGpuSeries((s) => [...s.slice(1), next.gpuPercent]);
        return next;
      });
    }, 1200);
    return () => window.clearInterval(timer);
  }, [powerProfile]);

  const ramPercent = Math.round((snapshot.ramUsedGb / snapshot.ramTotalGb) * 100);
  const storagePercent = Math.round((snapshot.storageUsedGb / snapshot.storageTotalGb) * 100);

  return (
    <div
      className="h-full overflow-y-auto p-4 sm:p-5 space-y-5 text-sm nura-scroll"
      style={{ touchAction: 'pan-y' }}
    >
      {/* Clear Demonstration Disclaimer */}
      <div
        className="px-3.5 py-2.5 rounded-xl flex flex-wrap items-center justify-between gap-2 text-xs"
        style={{
          backgroundColor: 'var(--nura-surface-subtle)',
          border: '1px solid var(--nura-border)',
          color: 'var(--nura-text-muted)',
        }}
      >
        <span>
          <strong style={{ color: 'var(--nura-text)' }}>Dados Demonstrativos (Simulação):</strong>{' '}
          telemetria gerada via interface <span className="font-mono">TelemetryProvider</span>{' '}
          preparada para futura leitura Linux (<span className="font-mono">/proc</span> e{' '}
          <span className="font-mono">/sys</span>).
        </span>
        <span className="font-mono tabular-nums" style={{ color: 'var(--nura-accent)' }}>
          Perfil: {powerProfile}
        </span>
      </div>

      {/* Primary Charts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        <div
          className="p-4 rounded-2xl flex flex-col justify-between gap-3"
          style={{
            backgroundColor: 'var(--nura-surface-subtle)',
            border: '1px solid var(--nura-border)',
          }}
        >
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-semibold">
              <Cpu size={15} style={{ color: '#38bdf8' }} />
              CPU (Snapdragon 653 sim.)
            </span>
            <span className="font-mono text-lg font-bold tabular-nums">
              {snapshot.cpuTotalPercent}%
            </span>
          </div>
          <SparkAreaChart values={cpuSeries} color="#38bdf8" />
          <div className="grid grid-cols-8 gap-1 pt-1">
            {snapshot.cpuCores.map((val, idx) => (
              <div key={idx} className="flex flex-col items-center gap-1">
                <div className="w-full h-8 rounded bg-white/5 flex items-end overflow-hidden">
                  <div
                    className="w-full rounded-t transition-all duration-300"
                    style={{ height: `${val}%`, backgroundColor: '#38bdf8' }}
                  />
                </div>
                <span className="text-[10px] font-mono tabular-nums" style={{ color: 'var(--nura-text-muted)' }}>
                  C{idx}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div
          className="p-4 rounded-2xl flex flex-col justify-between gap-3"
          style={{
            backgroundColor: 'var(--nura-surface-subtle)',
            border: '1px solid var(--nura-border)',
          }}
        >
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-semibold">
              <MemoryStick size={15} style={{ color: '#34d399' }} />
              Memória RAM (LPDDR4 sim.)
            </span>
            <span className="font-mono text-lg font-bold tabular-nums">{ramPercent}%</span>
          </div>
          <SparkAreaChart values={ramSeries} color="#34d399" />
          <div className="flex justify-between text-xs font-mono tabular-nums" style={{ color: 'var(--nura-text-muted)' }}>
            <span>Em uso: {snapshot.ramUsedGb.toFixed(2)} GB</span>
            <span>Total: {snapshot.ramTotalGb.toFixed(1)} GB</span>
          </div>
        </div>

        <div
          className="p-4 rounded-2xl flex flex-col justify-between gap-3"
          style={{
            backgroundColor: 'var(--nura-surface-subtle)',
            border: '1px solid var(--nura-border)',
          }}
        >
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-semibold">
              <Cpu size={15} style={{ color: '#a78bfa' }} />
              GPU (Adreno 510 sim.)
            </span>
            <span className="font-mono text-lg font-bold tabular-nums">
              {snapshot.gpuPercent}%
            </span>
          </div>
          <SparkAreaChart values={gpuSeries} color="#a78bfa" />
          <div className="flex justify-between text-xs font-mono tabular-nums" style={{ color: 'var(--nura-text-muted)' }}>
            <span>Clock: {snapshot.gpuFreqMhz} MHz</span>
            <span>Mesa Freedreno</span>
          </div>
        </div>
      </div>

      {/* Storage, Battery & Thermal Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        <div
          className="p-4 rounded-2xl space-y-2.5"
          style={{
            backgroundColor: 'var(--nura-surface-subtle)',
            border: '1px solid var(--nura-border)',
          }}
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="flex items-center gap-2">
              <HardDrive size={15} style={{ color: 'var(--nura-accent)' }} />
              Armazenamento eMMC (Simulado)
            </span>
            <span className="font-mono tabular-nums">
              {snapshot.storageUsedGb} / {snapshot.storageTotalGb} GB ({storagePercent}%)
            </span>
          </div>
          <div className="h-2 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{ width: `${storagePercent}%`, backgroundColor: 'var(--nura-accent)' }}
            />
          </div>
          <div className="flex justify-between text-xs font-mono tabular-nums" style={{ color: 'var(--nura-text-muted)' }}>
            <span>Leitura: {snapshot.storageReadMbS} MB/s</span>
            <span>Escrita: {snapshot.storageWriteMbS} MB/s</span>
          </div>
        </div>

        <div
          className="p-4 rounded-2xl space-y-2.5"
          style={{
            backgroundColor: 'var(--nura-surface-subtle)',
            border: '1px solid var(--nura-border)',
          }}
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="flex items-center gap-2">
              <Thermometer size={15} style={{ color: '#fbbf24' }} />
              Temperatura & Bateria (Simulado)
            </span>
            <span className="font-mono tabular-nums">SoC {snapshot.socTempC}°C</span>
          </div>
          <div className="grid grid-cols-3 gap-2 pt-1 text-xs font-mono tabular-nums">
            <div>
              <div style={{ color: 'var(--nura-text-muted)' }}>Carga</div>
              <div className="font-semibold mt-0.5">{snapshot.batteryPercent}%</div>
            </div>
            <div>
              <div style={{ color: 'var(--nura-text-muted)' }}>Bat. Temp</div>
              <div className="font-semibold mt-0.5">{snapshot.batteryTempC}°C</div>
            </div>
            <div>
              <div style={{ color: 'var(--nura-text-muted)' }}>SoC Temp</div>
              <div className="font-semibold mt-0.5">{snapshot.socTempC}°C</div>
            </div>
          </div>
        </div>
      </div>

      {/* Simulated Processes Table */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{
          backgroundColor: 'var(--nura-surface-subtle)',
          border: '1px solid var(--nura-border)',
        }}
      >
        <div
          className="px-4 py-2.5 border-b flex items-center justify-between"
          style={{ borderColor: 'var(--nura-border)' }}
        >
          <h3 className="font-display text-xs font-semibold">
            Processos do Sistema (Simulação)
          </h3>
          <span className="text-[11px] font-mono tabular-nums" style={{ color: 'var(--nura-text-muted)' }}>
            {snapshot.processes.length} processos ativos
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr
                className="border-b"
                style={{
                  borderColor: 'var(--nura-border)',
                  color: 'var(--nura-text-muted)',
                }}
              >
                <th className="px-4 py-2.5 font-medium">PID</th>
                <th className="px-4 py-2.5 font-medium">Processo</th>
                <th className="px-4 py-2.5 font-medium">Usuário</th>
                <th className="px-4 py-2.5 font-medium">Estado</th>
                <th className="px-4 py-2.5 font-medium text-right">CPU</th>
                <th className="px-4 py-2.5 font-medium text-right">Memória</th>
              </tr>
            </thead>
            <tbody className="divide-y font-mono tabular-nums" style={{ borderColor: 'var(--nura-border)' }}>
              {snapshot.processes.map((proc) => (
                <tr key={proc.pid} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-2.5" style={{ color: 'var(--nura-text-muted)' }}>
                    {proc.pid}
                  </td>
                  <td className="px-4 py-2.5 font-sans font-medium">{proc.name}</td>
                  <td className="px-4 py-2.5" style={{ color: 'var(--nura-text-muted)' }}>
                    {proc.user}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      style={{
                        color: proc.state === 'running' ? '#34d399' : 'var(--nura-text-muted)',
                      }}
                    >
                      {proc.state}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">{proc.cpuPercent.toFixed(1)}%</td>
                  <td className="px-4 py-2.5 text-right">{proc.memMb} MB</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
