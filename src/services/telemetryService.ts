import { PowerProfile, ProcessItem, TelemetryProvider, TelemetrySnapshot } from '../types/os';

const BASE_PROCESSES: ProcessItem[] = [
  { pid: 102, name: 'nura-compositor', user: 'nura', cpuPercent: 6.4, memMb: 184, state: 'running' },
  { pid: 148, name: 'nura-desktop-shell', user: 'nura', cpuPercent: 4.1, memMb: 142, state: 'running' },
  { pid: 215, name: 'pipewire-pulse', user: 'nura', cpuPercent: 1.8, memMb: 46, state: 'sleeping' },
  { pid: 284, name: 'networkmanager', user: 'root', cpuPercent: 0.9, memMb: 38, state: 'sleeping' },
  { pid: 312, name: 'nura-explorer', user: 'nura', cpuPercent: 1.4, memMb: 68, state: 'sleeping' },
  { pid: 409, name: 'mesa-adreno-icd', user: 'nura', cpuPercent: 3.2, memMb: 112, state: 'running' },
  { pid: 518, name: 'bluez-daemon', user: 'root', cpuPercent: 0.4, memMb: 22, state: 'sleeping' },
  { pid: 604, name: 'nura-telemetryd', user: 'root', cpuPercent: 0.7, memMb: 19, state: 'sleeping' },
];

const clamp = (val: number, min: number, max: number) => Math.min(max, Math.max(min, val));

/**
 * Implementação demonstrativa do provedor de telemetria.
 * Projetada com a mesma interface TelemetryProvider para futura integração
 * com /proc/stat, /proc/meminfo e /sys/class/thermal no Alpine/postmarketOS real.
 */
export const simulatedTelemetryProvider: TelemetryProvider = {
  mode: 'simulated-demo',

  getInitialSnapshot(): TelemetrySnapshot {
    return {
      timestamp: Date.now(),
      cpuTotalPercent: 24,
      cpuCores: [32, 28, 22, 26, 18, 20, 24, 22],
      ramUsedGb: 1.68,
      ramTotalGb: 4.0,
      gpuPercent: 19,
      gpuFreqMhz: 320,
      storageUsedGb: 14.8,
      storageTotalGb: 64.0,
      storageReadMbS: 12.4,
      storageWriteMbS: 4.2,
      batteryPercent: 82,
      batteryTempC: 31.4,
      socTempC: 39.2,
      processes: BASE_PROCESSES,
      sourceMode: 'simulated-demo',
    };
  },

  nextSnapshot(prev: TelemetrySnapshot, powerProfile: PowerProfile): TelemetrySnapshot {
    const profileBias =
      powerProfile === 'performance' ? 12 : powerProfile === 'powersave' ? -8 : 0;

    const cpuCores = prev.cpuCores.map((core, idx) => {
      const wave = Math.sin(Date.now() / 1400 + idx * 0.9) * 8;
      const jitter = (Math.random() - 0.5) * 10;
      return Math.round(clamp(core * 0.55 + (24 + profileBias + wave + jitter) * 0.45, 6, 94));
    });

    const cpuTotalPercent = Math.round(
      cpuCores.reduce((acc, v) => acc + v, 0) / cpuCores.length
    );

    const gpuPercent = Math.round(
      clamp(prev.gpuPercent + (Math.random() - 0.48) * 9 + profileBias * 0.25, 8, 88)
    );

    const gpuFreqMhz =
      gpuPercent > 55 ? 550 : gpuPercent > 30 ? 400 : powerProfile === 'powersave' ? 216 : 320;

    const ramUsedGb = Number(
      clamp(prev.ramUsedGb + (Math.random() - 0.5) * 0.06, 1.35, 3.45).toFixed(2)
    );

    const socTempC = Number(
      clamp(34 + cpuTotalPercent * 0.24 + (Math.random() - 0.5) * 0.8, 32.0, 68.0).toFixed(1)
    );

    const batteryTempC = Number(clamp(29.5 + (socTempC - 34) * 0.22, 28.0, 42.0).toFixed(1));

    const processes = prev.processes.map((proc) => ({
      ...proc,
      cpuPercent: Number(
        clamp(proc.cpuPercent + (Math.random() - 0.5) * 1.4, 0.2, 24.0).toFixed(1)
      ),
      memMb: Math.round(clamp(proc.memMb + (Math.random() - 0.5) * 4, 16, 420)),
    }));

    return {
      timestamp: Date.now(),
      cpuTotalPercent,
      cpuCores,
      ramUsedGb,
      ramTotalGb: 4.0,
      gpuPercent,
      gpuFreqMhz,
      storageUsedGb: 14.8,
      storageTotalGb: 64.0,
      storageReadMbS: Number(clamp(4 + Math.random() * 28, 1.2, 85.0).toFixed(1)),
      storageWriteMbS: Number(clamp(1.5 + Math.random() * 14, 0.4, 42.0).toFixed(1)),
      batteryPercent: prev.batteryPercent,
      batteryTempC,
      socTempC,
      processes,
      sourceMode: 'simulated-demo',
    };
  },
};
