import { useCallback, useEffect, useRef, useState } from 'react';
import { APPS_REGISTRY } from '../services/appsRegistry';
import { AppId, WindowState } from '../types/os';

const TASKBAR_HEIGHT = 54;

function getViewportBounds() {
  return {
    width: typeof window !== 'undefined' ? window.innerWidth : 1280,
    height: typeof window !== 'undefined' ? window.innerHeight : 720,
  };
}

function clampWindowToViewport(
  win: Pick<WindowState, 'x' | 'y' | 'width' | 'height' | 'minWidth' | 'minHeight'>
) {
  const vp = getViewportBounds();
  const maxAvailableW = Math.max(320, vp.width - 16);
  const maxAvailableH = Math.max(240, vp.height - TASKBAR_HEIGHT - 16);

  const width = Math.min(Math.max(win.width, Math.min(win.minWidth, maxAvailableW)), maxAvailableW);
  const height = Math.min(
    Math.max(win.height, Math.min(win.minHeight, maxAvailableH)),
    maxAvailableH
  );

  const x = Math.max(8, Math.min(win.x, vp.width - width - 8));
  const y = Math.max(8, Math.min(win.y, vp.height - TASKBAR_HEIGHT - height - 8));

  return { x, y, width, height };
}

export function useWindowManager() {
  const [windows, setWindows] = useState<WindowState[]>([]);
  const zCounterRef = useRef(20);

  const nextZ = useCallback(() => {
    zCounterRef.current += 1;
    return zCounterRef.current;
  }, []);

  const focusWindow = useCallback(
    (id: string) => {
      const z = nextZ();
      setWindows((prev) =>
        prev.map((w) => (w.id === id ? { ...w, zIndex: z, isMinimized: false } : w))
      );
    },
    [nextZ]
  );

  const openApp = useCallback(
    (appId: AppId, metadata?: Record<string, string>) => {
      const def = APPS_REGISTRY[appId];
      const z = nextZ();

      setWindows((prev) => {
        const existing = prev.find((w) => w.appId === appId);
        if (existing) {
          return prev.map((w) =>
            w.id === existing.id
              ? {
                  ...w,
                  isMinimized: false,
                  zIndex: z,
                  metadata: metadata ?? w.metadata,
                }
              : w
          );
        }

        const vp = getViewportBounds();
        const offset = (prev.length % 5) * 26;
        const targetW = Math.min(def.defaultSize.width, vp.width - 32);
        const targetH = Math.min(def.defaultSize.height, vp.height - TASKBAR_HEIGHT - 32);
        const centeredX = Math.max(12, Math.round((vp.width - targetW) / 2) + offset - 36);
        const centeredY = Math.max(
          12,
          Math.round((vp.height - TASKBAR_HEIGHT - targetH) / 2) + offset - 24
        );

        const clamped = clampWindowToViewport({
          x: centeredX,
          y: centeredY,
          width: targetW,
          height: targetH,
          minWidth: def.minSize.width,
          minHeight: def.minSize.height,
        });

        // Auto-maximize on very compact screens (< 720px wide) so touch UX stays clean
        const startMaximized = vp.width < 680;

        const created: WindowState = {
          id: `win-${appId}-${Date.now()}`,
          appId,
          title: def.name,
          ...clamped,
          minWidth: Math.min(def.minSize.width, vp.width - 24),
          minHeight: Math.min(def.minSize.height, vp.height - TASKBAR_HEIGHT - 24),
          zIndex: z,
          isMinimized: false,
          isMaximized: startMaximized,
          restoreBounds: startMaximized ? clamped : undefined,
          metadata,
        };

        return [...prev, created];
      });
    },
    [nextZ]
  );

  const closeWindow = useCallback((id: string) => {
    setWindows((prev) => prev.filter((w) => w.id !== id));
  }, []);

  const minimizeWindow = useCallback((id: string) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, isMinimized: true } : w))
    );
  }, []);

  const toggleMaximizeWindow = useCallback(
    (id: string) => {
      const z = nextZ();
      setWindows((prev) =>
        prev.map((w) => {
          if (w.id !== id) return w;
          if (!w.isMaximized) {
            return {
              ...w,
              isMaximized: true,
              isMinimized: false,
              zIndex: z,
              restoreBounds: { x: w.x, y: w.y, width: w.width, height: w.height },
            };
          }
          const restored = clampWindowToViewport({
            ...(w.restoreBounds ?? { x: 80, y: 40, width: 760, height: 480 }),
            minWidth: w.minWidth,
            minHeight: w.minHeight,
          });
          return {
            ...w,
            isMaximized: false,
            zIndex: z,
            ...restored,
          };
        })
      );
    },
    [nextZ]
  );

  const toggleTaskbarApp = useCallback(
    (appId: AppId) => {
      const existing = windows.find((w) => w.appId === appId);
      if (!existing) {
        openApp(appId);
        return;
      }

      const activeWin = windows
        .filter((w) => !w.isMinimized)
        .sort((a, b) => b.zIndex - a.zIndex)[0];

      if (existing.isMinimized || activeWin?.id !== existing.id) {
        focusWindow(existing.id);
      } else {
        minimizeWindow(existing.id);
      }
    },
    [windows, openApp, focusWindow, minimizeWindow]
  );

  const moveWindow = useCallback((id: string, x: number, y: number) => {
    const vp = getViewportBounds();
    setWindows((prev) =>
      prev.map((w) => {
        if (w.id !== id || w.isMaximized) return w;
        const clampedX = Math.max(-w.width + 120, Math.min(x, vp.width - 120));
        const clampedY = Math.max(0, Math.min(y, vp.height - TASKBAR_HEIGHT - 44));
        return { ...w, x: clampedX, y: clampedY };
      })
    );
  }, []);

  const resizeWindow = useCallback(
    (id: string, bounds: { x: number; y: number; width: number; height: number }) => {
      const vp = getViewportBounds();
      setWindows((prev) =>
        prev.map((w) => {
          if (w.id !== id || w.isMaximized) return w;
          const width = Math.max(w.minWidth, Math.min(bounds.width, vp.width - 12));
          const height = Math.max(
            w.minHeight,
            Math.min(bounds.height, vp.height - TASKBAR_HEIGHT - 12)
          );
          const x = Math.max(0, Math.min(bounds.x, vp.width - 100));
          const y = Math.max(0, Math.min(bounds.y, vp.height - TASKBAR_HEIGHT - 48));
          return { ...w, x, y, width, height };
        })
      );
    },
    []
  );

  // Re-clamp windows on viewport resize / orientation change
  useEffect(() => {
    const handleResize = () => {
      setWindows((prev) =>
        prev.map((w) => {
          if (w.isMaximized) return w;
          const clamped = clampWindowToViewport(w);
          return { ...w, ...clamped };
        })
      );
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const activeWindowId =
    windows
      .filter((w) => !w.isMinimized)
      .sort((a, b) => b.zIndex - a.zIndex)[0]?.id ?? null;

  return {
    windows,
    activeWindowId,
    openApp,
    closeWindow,
    minimizeWindow,
    toggleMaximizeWindow,
    focusWindow,
    toggleTaskbarApp,
    moveWindow,
    resizeWindow,
  };
}
