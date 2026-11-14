import React, { useRef, useState } from 'react';
import { AppIcon } from '../components/AppIcon';
import { ALL_APPS } from '../services/appsRegistry';
import { AppId } from '../types/os';

interface DesktopIconsProps {
  onOpenApp: (appId: AppId) => void;
  onContextMenuIcon: (x: number, y: number, appId: AppId) => void;
}

export function DesktopIcons({ onOpenApp, onContextMenuIcon }: DesktopIconsProps) {
  const [selectedId, setSelectedId] = useState<AppId | null>(null);
  const longPressTimerRef = useRef<number | null>(null);

  const clearLongPress = () => {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };

  const handlePointerDown = (appId: AppId) => (e: React.PointerEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setSelectedId(appId);

    if (e.pointerType === 'touch') {
      clearLongPress();
      const clientX = e.clientX;
      const clientY = e.clientY;
      longPressTimerRef.current = window.setTimeout(() => {
        onContextMenuIcon(clientX, clientY, appId);
      }, 520);
    }
  };

  const handleClick = (appId: AppId) => (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setSelectedId(appId);
    // On touch pointers (coarse), open directly on tap; on mouse, allow double-click or click when already selected
    if (window.matchMedia('(pointer: coarse)').matches) {
      onOpenApp(appId);
    }
  };

  return (
    <div
      className="relative z-10 p-2.5 sm:p-5 grid grid-flow-row grid-cols-1 sm:grid-flow-col sm:grid-rows-5 gap-1.5 sm:gap-2.5 w-fit content-start"
      onClick={() => setSelectedId(null)}
    >
      {ALL_APPS.map((app) => {
        const isSelected = selectedId === app.id;
        return (
          <button
            key={app.id}
            type="button"
            onPointerDown={handlePointerDown(app.id)}
            onPointerUp={clearLongPress}
            onPointerCancel={clearLongPress}
            onPointerMove={clearLongPress}
            onClick={handleClick(app.id)}
            onDoubleClick={(e) => {
              e.stopPropagation();
              onOpenApp(app.id);
            }}
            onContextMenu={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setSelectedId(app.id);
              onContextMenuIcon(e.clientX, e.clientY, app.id);
            }}
            className="w-[74px] sm:w-[92px] min-h-[70px] sm:min-h-[88px] p-1.5 sm:p-2 rounded-xl flex flex-col items-center justify-start gap-1 sm:gap-1.5 text-center transition-all duration-150 focus-visible:outline-none focus-visible:ring-2"
            style={{
              backgroundColor: isSelected ? 'var(--nura-surface-elevated)' : 'transparent',
              border: isSelected
                ? '1px solid var(--nura-border-strong)'
                : '1px solid transparent',
              color: 'var(--nura-text)',
            }}
            title={`Abrir ${app.name}`}
          >
            <AppIcon appId={app.id} size={20} containerSize={40} />
            <span className="text-[11px] sm:text-xs font-medium leading-tight line-clamp-2 drop-shadow-sm">
              {app.shortName}
            </span>
          </button>
        );
      })}
    </div>
  );
}
