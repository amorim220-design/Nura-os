import React, { useCallback, useRef, useState } from 'react';
import { AboutApp } from './apps/AboutApp';
import { ControlCenterApp } from './apps/ControlCenterApp';
import { ExplorerApp } from './apps/ExplorerApp';
import { GameHubApp } from './apps/GameHubApp';
import { PerformanceApp } from './apps/PerformanceApp';
import { TerminalApp } from './apps/TerminalApp';
import { OrientationBanner } from './components/OrientationBanner';
import { VirtualKeyboard } from './components/VirtualKeyboard';
import { BootScreen } from './desktop/BootScreen';
import { ContextMenu } from './desktop/ContextMenu';
import { DesktopIcons } from './desktop/DesktopIcons';
import { DesktopTelemetryWidget } from './desktop/DesktopTelemetryWidget';
import { DesktopWallpaper } from './desktop/DesktopWallpaper';
import { NotificationCenter } from './desktop/NotificationCenter';
import { PowerDialog } from './desktop/PowerDialog';
import { StartMenu } from './desktop/StartMenu';
import { Taskbar } from './desktop/Taskbar';
import { useOsState } from './hooks/useOsState';
import { useWindowManager } from './hooks/useWindowManager';
import { WindowState } from './types/os';
import { WindowFrame } from './window-manager/WindowFrame';

export default function App() {
  const os = useOsState();
  const wm = useWindowManager();
  const [isBooting, setIsBooting] = useState(true);
  const [bootKey, setBootKey] = useState(1);
  const [virtualInputSignal, setVirtualInputSignal] = useState<{
    key: string;
    seq: number;
  } | null>(null);
  const desktopLongPressRef = useRef<number | null>(null);

  const handleBootComplete = useCallback(() => {
    setIsBooting(false);
  }, []);

  const triggerBootSequence = useCallback(() => {
    setBootKey((k) => k + 1);
    setIsBooting(true);
  }, []);

  const unreadCount = os.notifications.filter((n) => !n.read).length;

  // Dispatch virtual keyboard input either to focused input/textarea or active Terminal
  const handleVirtualKeyPress = (key: string) => {
    const activeEl = document.activeElement;
    if (
      activeEl &&
      (activeEl instanceof HTMLInputElement || activeEl instanceof HTMLTextAreaElement) &&
      activeEl.getAttribute('aria-label') !== 'Entrada de comando do Terminal'
    ) {
      const start = activeEl.selectionStart ?? activeEl.value.length;
      const end = activeEl.selectionEnd ?? activeEl.value.length;

      let nextVal = activeEl.value;
      let nextCursor = start;

      if (key === 'BACKSPACE') {
        if (start > 0) {
          nextVal = activeEl.value.slice(0, start - 1) + activeEl.value.slice(end);
          nextCursor = start - 1;
        }
      } else if (key === 'ENTER') {
        activeEl.form?.requestSubmit();
        return;
      } else if (key.length === 1) {
        nextVal = activeEl.value.slice(0, start) + key + activeEl.value.slice(end);
        nextCursor = start + 1;
      }

      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
      )?.set;
      nativeSetter?.call(activeEl, nextVal);
      activeEl.dispatchEvent(new Event('input', { bubbles: true }));
      activeEl.setSelectionRange(nextCursor, nextCursor);
      return;
    }

    setVirtualInputSignal((prev) => ({ key, seq: (prev?.seq ?? 0) + 1 }));
  };

  const renderAppContent = (win: WindowState) => {
    switch (win.appId) {
      case 'explorer':
        return (
          <ExplorerApp
            vfsNodes={os.vfsNodes}
            setVfsNodes={os.setVfsNodes}
            onNotify={(title, message) =>
              os.pushNotification({ title, message, kind: 'info' })
            }
          />
        );
      case 'terminal':
        return (
          <TerminalApp
            vfsNodes={os.vfsNodes}
            setVfsNodes={os.setVfsNodes}
            themeId={os.themeId}
            virtualInputSignal={
              wm.activeWindowId === win.id ? virtualInputSignal : null
            }
          />
        );
      case 'control-center':
        return (
          <ControlCenterApp
            settings={os.settings}
            updateSettings={os.updateSettings}
            themeId={os.themeId}
            setThemeId={os.setThemeId}
            isFullscreen={os.isFullscreen}
            onToggleFullscreen={os.toggleFullscreen}
            initialTab={win.metadata?.tab}
          />
        );
      case 'game-hub':
        return <GameHubApp />;
      case 'performance':
        return <PerformanceApp powerProfile={os.settings.powerProfile} />;
      case 'about':
        return <AboutApp />;
    }
  };

  const handleDesktopPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    os.closeTransientOverlays();

    if (e.pointerType === 'touch' && e.target === e.currentTarget) {
      if (desktopLongPressRef.current !== null) {
        window.clearTimeout(desktopLongPressRef.current);
      }
      const x = e.clientX;
      const y = e.clientY;
      desktopLongPressRef.current = window.setTimeout(() => {
        os.setContextMenu({ x, y, targetType: 'desktop' });
      }, 550);
    }
  };

  const clearDesktopLongPress = () => {
    if (desktopLongPressRef.current !== null) {
      window.clearTimeout(desktopLongPressRef.current);
      desktopLongPressRef.current = null;
    }
  };

  // Simulated brightness dimming overlay opacity
  const dimOpacity = Math.max(0, (100 - os.settings.brightness) / 115);

  return (
    <main
      className="relative w-full h-full overflow-hidden select-none"
      style={{ backgroundColor: 'var(--nura-bg)', color: 'var(--nura-text)' }}
      onPointerDown={handleDesktopPointerDown}
      onPointerUp={clearDesktopLongPress}
      onPointerCancel={clearDesktopLongPress}
      onPointerMove={clearDesktopLongPress}
      onContextMenu={(e) => {
        e.preventDefault();
        os.setStartMenuOpen(false);
        os.setNotificationsOpen(false);
        os.setContextMenu({ x: e.clientX, y: e.clientY, targetType: 'desktop' });
      }}
    >
      <DesktopWallpaper theme={os.theme} />

      <OrientationBanner />

      <DesktopIcons
        onOpenApp={(appId) => {
          os.closeTransientOverlays();
          wm.openApp(appId);
        }}
        onContextMenuIcon={(x, y, appId) => {
          os.setStartMenuOpen(false);
          os.setNotificationsOpen(false);
          os.setContextMenu({ x, y, targetType: 'icon', appId });
        }}
      />

      <DesktopTelemetryWidget
        powerProfile={os.settings.powerProfile}
        batteryLevel={os.settings.batteryLevel}
        batteryCharging={os.settings.batteryCharging}
        onOpenPerformance={() => {
          os.closeTransientOverlays();
          wm.openApp('performance');
        }}
      />

      {/* Active Windows Layer */}
      {wm.windows.map((win) => (
        <WindowFrame
          key={win.id}
          win={win}
          isActive={wm.activeWindowId === win.id}
          onFocus={wm.focusWindow}
          onClose={wm.closeWindow}
          onMinimize={wm.minimizeWindow}
          onToggleMaximize={wm.toggleMaximizeWindow}
          onMove={wm.moveWindow}
          onResize={wm.resizeWindow}
        >
          {renderAppContent(win)}
        </WindowFrame>
      ))}

      <StartMenu
        isOpen={os.startMenuOpen}
        onClose={() => os.setStartMenuOpen(false)}
        onOpenApp={(appId) => wm.openApp(appId)}
        onTriggerPower={(action) => os.setPowerDialog(action)}
      />

      <NotificationCenter
        isOpen={os.notificationsOpen}
        notifications={os.notifications}
        toastQueue={os.toastQueue}
        onCloseDrawer={() => os.setNotificationsOpen(false)}
        onDismissToast={os.dismissToast}
        onMarkAllRead={os.markAllNotificationsRead}
        onClearAll={os.clearNotifications}
        onOpenApp={(appId) => wm.openApp(appId)}
      />

      <ContextMenu
        menu={os.contextMenu}
        onClose={() => os.setContextMenu(null)}
        onOpenApp={(appId, metadata) => wm.openApp(appId, metadata)}
        onToggleFullscreen={os.toggleFullscreen}
        onRefreshDesktop={() =>
          os.pushNotification({
            title: 'Área de trabalho atualizada',
            message: 'Grade de ícones e compositor gráfico NURA sincronizados.',
            kind: 'system',
          })
        }
      />

      <VirtualKeyboard
        isOpen={os.settings.virtualKeyboardOpen}
        onClose={() => os.updateSettings({ virtualKeyboardOpen: false })}
        onKeyPress={handleVirtualKeyPress}
      />

      <Taskbar
        windows={wm.windows}
        activeWindowId={wm.activeWindowId}
        startMenuOpen={os.startMenuOpen}
        notificationsOpen={os.notificationsOpen}
        unreadCount={unreadCount}
        settings={os.settings}
        isFullscreen={os.isFullscreen}
        onToggleStartMenu={() => {
          os.setNotificationsOpen(false);
          os.setContextMenu(null);
          os.setStartMenuOpen((prev) => !prev);
        }}
        onToggleNotifications={() => {
          os.setStartMenuOpen(false);
          os.setContextMenu(null);
          os.setNotificationsOpen((prev) => {
            const next = !prev;
            if (next) os.markAllNotificationsRead();
            return next;
          });
        }}
        onToggleTaskbarApp={(appId) => {
          os.closeTransientOverlays();
          wm.toggleTaskbarApp(appId);
        }}
        onToggleVirtualKeyboard={() =>
          os.updateSettings({
            virtualKeyboardOpen: !os.settings.virtualKeyboardOpen,
          })
        }
        onToggleFullscreen={os.toggleFullscreen}
        onOpenControlCenter={() => {
          os.closeTransientOverlays();
          wm.openApp('control-center');
        }}
      />

      <PowerDialog
        action={os.powerDialog}
        onClose={() => os.setPowerDialog(null)}
        onTriggerBoot={triggerBootSequence}
        onResetSession={() => {
          wm.windows.forEach((w) => wm.closeWindow(w.id));
          os.pushNotification({
            title: 'Sessão reiniciada (Simulação)',
            message: 'Janelas da área de trabalho foram redefinidas no protótipo web.',
            kind: 'system',
          });
        }}
      />

      {isBooting && (
        <BootScreen bootKey={bootKey} onComplete={handleBootComplete} />
      )}

      {/* Brightness Simulation Overlay */}
      {dimOpacity > 0 && (
        <div
          className="fixed inset-0 pointer-events-none z-[130]"
          style={{ backgroundColor: `rgba(0, 0, 0, ${dimOpacity.toFixed(2)})` }}
          aria-hidden="true"
        />
      )}
    </main>
  );
}
