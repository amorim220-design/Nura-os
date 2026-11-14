import { useCallback, useEffect, useState } from 'react';
import { THEMES } from '../themes/themes';
import {
  ContextMenuState,
  OsNotification,
  SystemSettings,
  ThemeId,
  VfsNode,
} from '../types/os';
import { loadVfs, saveVfs } from '../services/vfsService';

const THEME_KEY = 'nura_os_theme_v1';
const SETTINGS_KEY = 'nura_os_settings_v1';

const DEFAULT_SETTINGS: SystemSettings = {
  wifiEnabled: true,
  wifiNetwork: 'NURA-Lab-5GHz (Simulado)',
  bluetoothEnabled: true,
  bluetoothDevice: 'NURA Gamepad HID (Simulado)',
  brightness: 95,
  volume: 70,
  batteryLevel: 82,
  batteryCharging: false,
  powerProfile: 'balanced',
  orientationPreference: 'landscape-primary',
  virtualKeyboardOpen: false,
  touchDragEnhanced: true,
};

const INITIAL_NOTIFICATIONS: OsNotification[] = [
  {
    id: 'notif-welcome',
    title: 'NURA OS Desktop ativo',
    message:
      'Protótipo interativo em execução. Todos os indicadores de hardware e comandos operam em ambiente virtual.',
    appId: 'about',
    timestamp: 'Agora',
    read: false,
    kind: 'system',
  },
  {
    id: 'notif-touch',
    title: 'Modo Touch + Mouse habilitado',
    message:
      'Arraste janelas pela barra superior, use toque prolongado para menu de contexto ou ative o teclado virtual na barra de tarefas.',
    appId: 'control-center',
    timestamp: 'Agora',
    read: false,
    kind: 'info',
  },
];

export function useOsState() {
  const [themeId, setThemeIdState] = useState<ThemeId>(() => {
    try {
      const saved = localStorage.getItem(THEME_KEY) as ThemeId | null;
      if (saved && THEMES[saved]) return saved;
    } catch {
      // Ignore
    }
    return 'neon-blue';
  });

  const [settings, setSettings] = useState<SystemSettings>(() => {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      if (raw) {
        return { ...DEFAULT_SETTINGS, ...JSON.parse(raw), virtualKeyboardOpen: false };
      }
    } catch {
      // Ignore
    }
    return DEFAULT_SETTINGS;
  });

  const [vfsNodes, setVfsNodes] = useState<VfsNode[]>(() => loadVfs());
  const [notifications, setNotifications] = useState<OsNotification[]>(INITIAL_NOTIFICATIONS);
  const [toastQueue, setToastQueue] = useState<OsNotification[]>([]);
  const [startMenuOpen, setStartMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [powerDialog, setPowerDialog] = useState<'shutdown' | 'restart' | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const theme = THEMES[themeId];

  // Apply theme CSS custom properties to documentElement
  useEffect(() => {
    const root = document.documentElement;
    const v = theme.vars;
    root.style.setProperty('--nura-bg', v.bg);
    root.style.setProperty('--nura-surface', v.surface);
    root.style.setProperty('--nura-surface-elevated', v.surfaceElevated);
    root.style.setProperty('--nura-surface-subtle', v.surfaceSubtle);
    root.style.setProperty('--nura-border', v.border);
    root.style.setProperty('--nura-border-strong', v.borderStrong);
    root.style.setProperty('--nura-text', v.text);
    root.style.setProperty('--nura-text-muted', v.textMuted);
    root.style.setProperty('--nura-accent', v.accent);
    root.style.setProperty('--nura-accent-strong', v.accentStrong);
    root.style.setProperty('--nura-accent-contrast', v.accentContrast);
    root.style.setProperty('--nura-glow', v.glow);
    root.style.setProperty('--nura-taskbar', v.taskbar);
    root.style.setProperty('--nura-shadow', v.shadow);

    try {
      localStorage.setItem(THEME_KEY, themeId);
    } catch {
      // Ignore
    }
  }, [theme, themeId]);

  useEffect(() => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch {
      // Ignore
    }
  }, [settings]);

  useEffect(() => {
    saveVfs(vfsNodes);
  }, [vfsNodes]);

  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  const setThemeId = useCallback((id: ThemeId) => {
    setThemeIdState(id);
  }, []);

  const updateSettings = useCallback((patch: Partial<SystemSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
  }, []);

  const pushNotification = useCallback(
    (payload: Omit<OsNotification, 'id' | 'timestamp' | 'read'>) => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit',
      });
      const item: OsNotification = {
        ...payload,
        id: `notif-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        timestamp: timeStr,
        read: false,
      };
      setNotifications((prev) => [item, ...prev].slice(0, 20));
      setToastQueue((prev) => [...prev, item].slice(-3));
    },
    []
  );

  const dismissToast = useCallback((id: string) => {
    setToastQueue((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const markAllNotificationsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setToastQueue([]);
  }, []);

  const toggleFullscreen = useCallback(async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch {
      pushNotification({
        title: 'Tela cheia indisponível',
        message: 'O navegador ou iframe bloqueou a solicitação automática de tela cheia.',
        kind: 'warning',
      });
    }
  }, [pushNotification]);

  const closeTransientOverlays = useCallback(() => {
    setStartMenuOpen(false);
    setNotificationsOpen(false);
    setContextMenu(null);
  }, []);

  return {
    theme,
    themeId,
    setThemeId,
    settings,
    updateSettings,
    vfsNodes,
    setVfsNodes,
    notifications,
    toastQueue,
    pushNotification,
    dismissToast,
    markAllNotificationsRead,
    clearNotifications,
    startMenuOpen,
    setStartMenuOpen,
    notificationsOpen,
    setNotificationsOpen,
    contextMenu,
    setContextMenu,
    powerDialog,
    setPowerDialog,
    isFullscreen,
    toggleFullscreen,
    closeTransientOverlays,
  };
}
