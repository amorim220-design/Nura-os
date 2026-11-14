import { Maximize2, Minimize2, Minus, X } from 'lucide-react';
import React, { useRef } from 'react';
import { AppIcon } from '../components/AppIcon';
import { WindowState } from '../types/os';

interface WindowFrameProps {
  win: WindowState;
  isActive: boolean;
  onFocus: (id: string) => void;
  onClose: (id: string) => void;
  onMinimize: (id: string) => void;
  onToggleMaximize: (id: string) => void;
  onMove: (id: string, x: number, y: number) => void;
  onResize: (
    id: string,
    bounds: { x: number; y: number; width: number; height: number }
  ) => void;
  children: React.ReactNode;
}

type ResizeDirection = 'e' | 's' | 'se' | 'w';

export function WindowFrame({
  win,
  isActive,
  onFocus,
  onClose,
  onMinimize,
  onToggleMaximize,
  onMove,
  onResize,
  children,
}: WindowFrameProps) {
  const dragStateRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);

  const resizeStateRef = useRef<{
    pointerId: number;
    dir: ResizeDirection;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    originW: number;
    originH: number;
  } | null>(null);

  if (win.isMinimized) return null;

  const handleTitlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('button')) return;
    onFocus(win.id);
    if (win.isMaximized) return;

    e.currentTarget.setPointerCapture(e.pointerId);
    dragStateRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      originX: win.x,
      originY: win.y,
    };
  };

  const handleTitlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = dragStateRef.current;
    if (!d || d.pointerId !== e.pointerId) return;
    const dx = e.clientX - d.startX;
    const dy = e.clientY - d.startY;
    onMove(win.id, d.originX + dx, d.originY + dy);
  };

  const handleTitlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (dragStateRef.current?.pointerId === e.pointerId) {
      dragStateRef.current = null;
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    }
  };

  const startResize = (dir: ResizeDirection) => (e: React.PointerEvent<HTMLDivElement>) => {
    if (win.isMaximized) return;
    e.stopPropagation();
    onFocus(win.id);
    e.currentTarget.setPointerCapture(e.pointerId);
    resizeStateRef.current = {
      pointerId: e.pointerId,
      dir,
      startX: e.clientX,
      startY: e.clientY,
      originX: win.x,
      originY: win.y,
      originW: win.width,
      originH: win.height,
    };
  };

  const moveResize = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = resizeStateRef.current;
    if (!r || r.pointerId !== e.pointerId) return;
    const dx = e.clientX - r.startX;
    const dy = e.clientY - r.startY;

    let nextX = r.originX;
    let nextY = r.originY;
    let nextW = r.originW;
    let nextH = r.originH;

    if (r.dir === 'e' || r.dir === 'se') {
      nextW = Math.max(win.minWidth, r.originW + dx);
    }
    if (r.dir === 's' || r.dir === 'se') {
      nextH = Math.max(win.minHeight, r.originH + dy);
    }
    if (r.dir === 'w') {
      const candidateW = Math.max(win.minWidth, r.originW - dx);
      nextX = r.originX + (r.originW - candidateW);
      nextW = candidateW;
    }

    onResize(win.id, { x: nextX, y: nextY, width: nextW, height: nextH });
  };

  const endResize = (e: React.PointerEvent<HTMLDivElement>) => {
    if (resizeStateRef.current?.pointerId === e.pointerId) {
      resizeStateRef.current = null;
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    }
  };

  const frameStyle: React.CSSProperties = win.isMaximized
    ? {
        left: 0,
        top: 0,
        width: '100%',
        height: 'calc(100% - 54px)',
        zIndex: win.zIndex,
        borderRadius: 0,
      }
    : {
        transform: `translate3d(${win.x}px, ${win.y}px, 0)`,
        width: win.width,
        height: win.height,
        zIndex: win.zIndex,
        borderRadius: '14px',
      };

  return (
    <section
      aria-label={win.title}
      onPointerDown={() => onFocus(win.id)}
      style={{
        ...frameStyle,
        backgroundColor: 'var(--nura-surface)',
        border: `1px solid ${isActive ? 'var(--nura-border-strong)' : 'var(--nura-border)'}`,
        boxShadow: isActive
          ? `var(--nura-shadow), 0 0 28px var(--nura-glow), inset 0 1px 0 rgba(255,255,255,0.12)`
          : '0 14px 36px rgba(0, 0, 0, 0.45)',
        color: 'var(--nura-text)',
      }}
      className="fixed top-0 left-0 flex flex-col overflow-hidden backdrop-blur-2xl transition-opacity duration-150"
    >
      {/* Top specular energy beam on active window */}
      {isActive && (
        <div
          className="absolute top-0 left-6 right-6 h-[1.5px] pointer-events-none z-20"
          style={{
            background:
              'linear-gradient(90deg, transparent, var(--nura-accent), var(--nura-accent-strong), transparent)',
          }}
          aria-hidden="true"
        />
      )}

      {/* Title Bar - touch-action: none so finger drag never scrolls underlying page */}
      <header
        onPointerDown={handleTitlePointerDown}
        onPointerMove={handleTitlePointerMove}
        onPointerUp={handleTitlePointerUp}
        onPointerCancel={handleTitlePointerUp}
        onDoubleClick={() => onToggleMaximize(win.id)}
        style={{
          touchAction: 'none',
          backgroundColor: isActive ? 'var(--nura-surface-elevated)' : 'var(--nura-surface)',
          borderBottom: '1px solid var(--nura-border)',
        }}
        className="h-[46px] px-3 flex items-center justify-between gap-3 shrink-0 cursor-grab active:cursor-grabbing select-none"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <AppIcon appId={win.appId} size={16} containerSize={28} />
          <h2 className="font-display text-sm font-semibold truncate">{win.title}</h2>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onMinimize(win.id);
            }}
            className="min-w-[40px] min-h-[38px] rounded-lg flex items-center justify-center hover:bg-white/10 transition-colors"
            style={{ color: 'var(--nura-text-muted)' }}
            aria-label={`Minimizar ${win.title}`}
            title="Minimizar"
          >
            <Minus size={16} />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleMaximize(win.id);
            }}
            className="min-w-[40px] min-h-[38px] rounded-lg flex items-center justify-center hover:bg-white/10 transition-colors"
            style={{ color: 'var(--nura-text-muted)' }}
            aria-label={win.isMaximized ? `Restaurar ${win.title}` : `Maximizar ${win.title}`}
            title={win.isMaximized ? 'Restaurar' : 'Maximizar'}
          >
            {win.isMaximized ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onClose(win.id);
            }}
            className="min-w-[40px] min-h-[38px] rounded-lg flex items-center justify-center hover:bg-rose-500/80 hover:text-white transition-colors"
            style={{ color: 'var(--nura-text-muted)' }}
            aria-label={`Fechar ${win.title}`}
            title="Fechar"
          >
            <X size={16} />
          </button>
        </div>
      </header>

      {/* Application Body */}
      <div className="flex-1 min-h-0 overflow-hidden relative">{children}</div>

      {/* Resize Handles (when not maximized) */}
      {!win.isMaximized && (
        <>
          <div
            onPointerDown={startResize('e')}
            onPointerMove={moveResize}
            onPointerUp={endResize}
            style={{ touchAction: 'none' }}
            className="absolute top-12 right-0 bottom-4 w-2.5 cursor-ew-resize"
            aria-hidden="true"
          />
          <div
            onPointerDown={startResize('w')}
            onPointerMove={moveResize}
            onPointerUp={endResize}
            style={{ touchAction: 'none' }}
            className="absolute top-12 left-0 bottom-4 w-2.5 cursor-ew-resize"
            aria-hidden="true"
          />
          <div
            onPointerDown={startResize('s')}
            onPointerMove={moveResize}
            onPointerUp={endResize}
            style={{ touchAction: 'none' }}
            className="absolute left-4 right-4 bottom-0 h-2.5 cursor-ns-resize"
            aria-hidden="true"
          />
          <div
            onPointerDown={startResize('se')}
            onPointerMove={moveResize}
            onPointerUp={endResize}
            style={{ touchAction: 'none' }}
            className="absolute right-0 bottom-0 w-5 h-5 cursor-nwse-resize flex items-end justify-end p-1"
            aria-hidden="true"
          >
            <span
              className="w-2 h-2 rounded-br-sm border-r-2 border-b-2 opacity-40"
              style={{ borderColor: 'var(--nura-accent)' }}
            />
          </div>
        </>
      )}
    </section>
  );
}
