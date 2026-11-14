import {
  Battery,
  BatteryCharging,
  Bell,
  Bluetooth,
  Keyboard,
  Maximize,
  Minimize,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { AppIcon } from '../components/AppIcon';
import { NuraLogo } from '../components/NuraLogo';
import { ALL_APPS } from '../services/appsRegistry';
import { AppId, SystemSettings, WindowState } from '../types/os';

interface TaskbarProps {
  windows: WindowState[];
  activeWindowId: string | null;
  startMenuOpen: boolean;
  notificationsOpen: boolean;
  unreadCount: number;
  settings: SystemSettings;
  isFullscreen: boolean;
  onToggleStartMenu: () => void;
  onToggleNotifications: () => void;
  onToggleTaskbarApp: (appId: AppId) => void;
  onToggleVirtualKeyboard: () => void;
  onToggleFullscreen: () => void;
  onOpenControlCenter: () => void;
}

export function Taskbar({
  windows,
  activeWindowId,
  startMenuOpen,
  notificationsOpen,
  unreadCount,
  settings,
  isFullscreen,
  onToggleStartMenu,
  onToggleNotifications,
  onToggleTaskbarApp,
  onToggleVirtualKeyboard,
  onToggleFullscreen,
  onOpenControlCenter,
}: TaskbarProps) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 15000);
    return () => window.clearInterval(id);
  }, []);

  const timeFormatted = now.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const dateFormatted = now.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });

  const taskbarApps = ALL_APPS.filter(
    (app) => app.pinned || windows.some((w) => w.appId === app.id)
  );

  return (
    <footer
      className="fixed bottom-0 left-0 right-0 h-[54px] z-[80] px-2.5 sm:px-4 flex items-center justify-between gap-2 backdrop-blur-2xl"
      style={{
        backgroundColor: 'var(--nura-taskbar)',
        borderTop: '1px solid var(--nura-border)',
        boxShadow: '0 -12px 36px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.06)',
        color: 'var(--nura-text)',
      }}
      aria-label="Barra de tarefas do NURA OS"
    >
      {/* Left: NURA Start & App Dock */}
      <div className="flex items-center gap-1.5 min-w-0 overflow-x-auto nura-scroll">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onToggleStartMenu();
          }}
          className="h-[42px] px-3 rounded-xl flex items-center gap-2 shrink-0 transition-all active:scale-95"
          style={{
            backgroundColor: startMenuOpen
              ? 'var(--nura-surface-elevated)'
              : 'var(--nura-surface-subtle)',
            border: startMenuOpen
              ? '1px solid var(--nura-border-strong)'
              : '1px solid var(--nura-border)',
            boxShadow: startMenuOpen ? '0 0 18px var(--nura-glow)' : 'none',
          }}
          aria-expanded={startMenuOpen}
          aria-label="Abrir Menu Iniciar NURA Start"
        >
          <NuraLogo size={20} />
          <span className="font-display text-xs font-semibold tracking-wide hidden sm:inline whitespace-nowrap">
            NURA Start
          </span>
        </button>

        <div className="h-6 w-px mx-1 shrink-0 bg-white/10" aria-hidden="true" />

        <nav className="flex items-center gap-1" aria-label="Aplicativos na barra de tarefas">
          {taskbarApps.map((app) => {
            const win = windows.find((w) => w.appId === app.id);
            const isOpen = Boolean(win);
            const isFocused = Boolean(win && win.id === activeWindowId && !win.isMinimized);

            return (
              <button
                key={app.id}
                type="button"
                onClick={() => onToggleTaskbarApp(app.id)}
                className="relative h-[42px] min-w-[44px] px-2 rounded-xl flex items-center gap-2 transition-all shrink-0 hover:bg-white/10 active:scale-95"
                style={{
                  backgroundColor: isFocused
                    ? 'var(--nura-surface-elevated)'
                    : isOpen
                    ? 'var(--nura-surface-subtle)'
                    : 'transparent',
                  border: isFocused
                    ? '1px solid var(--nura-border-strong)'
                    : '1px solid transparent',
                  boxShadow: isFocused ? '0 0 14px var(--nura-glow)' : 'none',
                }}
                title={app.name}
                aria-label={app.name}
              >
                <AppIcon appId={app.id} size={17} containerSize={30} />
                <span className="text-xs font-medium hidden md:inline whitespace-nowrap">
                  {app.shortName}
                </span>
                {isOpen && (
                  <span
                    className="absolute bottom-1 left-1/2 -translate-x-1/2 h-[3px] rounded-full transition-all"
                    style={{
                      width: isFocused ? '20px' : '8px',
                      backgroundColor: isFocused
                        ? 'var(--nura-accent)'
                        : 'var(--nura-text-muted)',
                      boxShadow: isFocused ? '0 0 8px var(--nura-accent)' : 'none',
                    }}
                    aria-hidden="true"
                  />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Right: Virtual Keyboard, Fullscreen, System Tray, Clock */}
      <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
        <button
          type="button"
          onClick={onToggleVirtualKeyboard}
          className="min-w-[40px] h-[40px] px-2 rounded-xl flex items-center justify-center hover:bg-white/10 transition-colors"
          style={{
            backgroundColor: settings.virtualKeyboardOpen
              ? 'var(--nura-surface-elevated)'
              : 'transparent',
            color: settings.virtualKeyboardOpen
              ? 'var(--nura-accent)'
              : 'var(--nura-text-muted)',
          }}
          title="Alternar Teclado Virtual"
          aria-label="Alternar Teclado Virtual"
        >
          <Keyboard size={17} />
        </button>

        <button
          type="button"
          onClick={onToggleFullscreen}
          className="min-w-[40px] h-[40px] px-2 rounded-xl flex items-center justify-center hover:bg-white/10 transition-colors"
          style={{ color: 'var(--nura-text-muted)' }}
          title={isFullscreen ? 'Sair da tela cheia' : 'Modo demonstração em tela cheia'}
          aria-label={isFullscreen ? 'Sair da tela cheia' : 'Modo demonstração em tela cheia'}
        >
          {isFullscreen ? <Minimize size={17} /> : <Maximize size={17} />}
        </button>

        <button
          type="button"
          onClick={onOpenControlCenter}
          className="h-[40px] px-2.5 rounded-xl flex items-center gap-2 hover:bg-white/10 transition-colors"
          style={{ color: 'var(--nura-text)' }}
          title="Abrir NURA Control Center (Indicadores simulados)"
          aria-label="Indicadores simulados de Wi-Fi, Bluetooth e Bateria"
        >
          {settings.wifiEnabled ? (
            <Wifi size={15} style={{ color: 'var(--nura-accent)' }} />
          ) : (
            <WifiOff size={15} style={{ color: 'var(--nura-text-muted)' }} />
          )}
          <Bluetooth
            size={15}
            className="hidden sm:inline"
            style={{
              color: settings.bluetoothEnabled ? 'var(--nura-accent)' : 'var(--nura-text-muted)',
            }}
          />
          <span className="flex items-center gap-1 text-xs tabular-nums">
            {settings.batteryCharging ? (
              <BatteryCharging size={16} className="text-emerald-400" />
            ) : (
              <Battery size={16} />
            )}
            <span className="hidden sm:inline">{settings.batteryLevel}%</span>
          </span>
        </button>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onToggleNotifications();
          }}
          className="relative min-w-[40px] h-[40px] rounded-xl flex items-center justify-center hover:bg-white/10 transition-colors"
          style={{
            backgroundColor: notificationsOpen
              ? 'var(--nura-surface-elevated)'
              : 'transparent',
            color: 'var(--nura-text)',
          }}
          title="Notificações"
          aria-label="Abrir centro de notificações"
        >
          <Bell size={16} />
          {unreadCount > 0 && (
            <span
              className="absolute top-1.5 right-1.5 min-w-[16px] h-[16px] px-1 rounded-full text-[10px] font-semibold flex items-center justify-center tabular-nums"
              style={{
                backgroundColor: 'var(--nura-accent)',
                color: 'var(--nura-accent-contrast)',
              }}
            >
              {unreadCount}
            </span>
          )}
        </button>

        <div
          className="h-[40px] px-2.5 rounded-xl flex flex-col items-end justify-center leading-tight tabular-nums"
          style={{ color: 'var(--nura-text)' }}
        >
          <span className="text-xs font-semibold">{timeFormatted}</span>
          <span className="text-[11px]" style={{ color: 'var(--nura-text-muted)' }}>
            {dateFormatted}
          </span>
        </div>
      </div>
    </footer>
  );
}
