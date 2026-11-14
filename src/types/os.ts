export type AppId =
  | 'explorer'
  | 'terminal'
  | 'control-center'
  | 'game-hub'
  | 'performance'
  | 'about';

export type ThemeId = 'neon-blue' | 'dark' | 'minimal' | 'gamer';

export interface ThemeConfig {
  id: ThemeId;
  name: string;
  subtitle: string;
  isLight: boolean;
  vars: {
    bg: string;
    surface: string;
    surfaceElevated: string;
    surfaceSubtle: string;
    border: string;
    borderStrong: string;
    text: string;
    textMuted: string;
    accent: string;
    accentStrong: string;
    accentContrast: string;
    glow: string;
    taskbar: string;
    shadow: string;
  };
  wallpaperImage?: string;
  wallpaperGradient: string;
  accentSwatch: string[];
}

export interface AppDefinition {
  id: AppId;
  name: string;
  shortName: string;
  description: string;
  pinned: boolean;
  defaultSize: { width: number; height: number };
  minSize: { width: number; height: number };
  category: 'Sistema' | 'Utilitários' | 'Entretenimento';
}

export interface WindowState {
  id: string;
  appId: AppId;
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  minWidth: number;
  minHeight: number;
  zIndex: number;
  isMinimized: boolean;
  isMaximized: boolean;
  restoreBounds?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  metadata?: Record<string, string>;
}

export type VfsNodeType = 'folder' | 'file';

export interface VfsNode {
  id: string;
  name: string;
  type: VfsNodeType;
  parentId: string | null;
  sizeBytes: number;
  modifiedAt: string;
  mimeType?: string;
  content?: string;
  readonly?: boolean;
}

export interface OsNotification {
  id: string;
  title: string;
  message: string;
  appId?: AppId;
  timestamp: string;
  read: boolean;
  kind: 'info' | 'warning' | 'system';
}

export type OrientationPreference = 'landscape-primary' | 'auto';
export type PowerProfile = 'balanced' | 'performance' | 'powersave';

export interface SystemSettings {
  wifiEnabled: boolean;
  wifiNetwork: string;
  bluetoothEnabled: boolean;
  bluetoothDevice: string;
  brightness: number;
  volume: number;
  batteryLevel: number;
  batteryCharging: boolean;
  powerProfile: PowerProfile;
  orientationPreference: OrientationPreference;
  virtualKeyboardOpen: boolean;
  touchDragEnhanced: boolean;
}

export interface ContextMenuState {
  x: number;
  y: number;
  targetType: 'desktop' | 'icon';
  appId?: AppId;
}

export type GameCategory = 'Todos' | 'Corrida' | 'Estratégia' | 'Ação RPG' | 'Puzzle';

export interface GameItem {
  id: string;
  title: string;
  category: Exclude<GameCategory, 'Todos'>;
  developer: string;
  releaseYear: number;
  coverImage: string;
  description: string;
  engineTarget: string;
  storageRequired: string;
  controllerSupport: string;
  demoDisclaimer: string;
  favorite: boolean;
}

export interface GamepadMapping {
  a: string;
  b: string;
  x: string;
  y: string;
  l1: string;
  r1: string;
  start: string;
  select: string;
  deadzone: number;
}

export interface ProcessItem {
  pid: number;
  name: string;
  user: string;
  cpuPercent: number;
  memMb: number;
  state: 'running' | 'sleeping';
}

export interface TelemetrySnapshot {
  timestamp: number;
  cpuTotalPercent: number;
  cpuCores: number[];
  ramUsedGb: number;
  ramTotalGb: number;
  gpuPercent: number;
  gpuFreqMhz: number;
  storageUsedGb: number;
  storageTotalGb: number;
  storageReadMbS: number;
  storageWriteMbS: number;
  batteryPercent: number;
  batteryTempC: number;
  socTempC: number;
  processes: ProcessItem[];
  sourceMode: 'simulated-demo' | 'linux-sysfs';
}

export interface TelemetryProvider {
  readonly mode: 'simulated-demo' | 'linux-sysfs';
  getInitialSnapshot(): TelemetrySnapshot;
  nextSnapshot(prev: TelemetrySnapshot, powerProfile: PowerProfile): TelemetrySnapshot;
}
