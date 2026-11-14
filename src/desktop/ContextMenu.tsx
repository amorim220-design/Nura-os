import {
  FolderOpen,
  Maximize,
  Palette,
  RefreshCw,
  SlidersHorizontal,
  Terminal,
} from 'lucide-react';
import { APPS_REGISTRY } from '../services/appsRegistry';
import { AppId, ContextMenuState } from '../types/os';

interface ContextMenuProps {
  menu: ContextMenuState | null;
  onClose: () => void;
  onOpenApp: (appId: AppId, metadata?: Record<string, string>) => void;
  onToggleFullscreen: () => void;
  onRefreshDesktop: () => void;
}

export function ContextMenu({
  menu,
  onClose,
  onOpenApp,
  onToggleFullscreen,
  onRefreshDesktop,
}: ContextMenuProps) {
  if (!menu) return null;

  const vpW = typeof window !== 'undefined' ? window.innerWidth : 1280;
  const vpH = typeof window !== 'undefined' ? window.innerHeight : 720;
  const left = Math.min(menu.x, vpW - 240);
  const top = Math.min(menu.y, vpH - 260);

  const appDef = menu.appId ? APPS_REGISTRY[menu.appId] : null;

  return (
    <div
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      style={{
        left,
        top,
        backgroundColor: 'var(--nura-surface-elevated)',
        border: '1px solid var(--nura-border-strong)',
        boxShadow: 'var(--nura-shadow)',
        color: 'var(--nura-text)',
      }}
      className="fixed z-[95] w-[228px] rounded-xl p-1.5 backdrop-blur-2xl"
      role="menu"
    >
      {menu.targetType === 'icon' && appDef && (
        <>
          <button
            type="button"
            onClick={() => {
              onOpenApp(appDef.id);
              onClose();
            }}
            className="w-full min-h-[40px] px-3 rounded-lg flex items-center gap-2.5 text-xs font-medium hover:bg-white/10 transition-colors text-left"
            role="menuitem"
          >
            <FolderOpen size={15} style={{ color: 'var(--nura-accent)' }} />
            <span>Abrir {appDef.shortName}</span>
          </button>
          <div className="my-1 border-t" style={{ borderColor: 'var(--nura-border)' }} />
        </>
      )}

      <button
        type="button"
        onClick={() => {
          onOpenApp('explorer');
          onClose();
        }}
        className="w-full min-h-[40px] px-3 rounded-lg flex items-center gap-2.5 text-xs font-medium hover:bg-white/10 transition-colors text-left"
        role="menuitem"
      >
        <FolderOpen size={15} style={{ color: 'var(--nura-accent)' }} />
        <span>Abrir NURA Explorer</span>
      </button>

      <button
        type="button"
        onClick={() => {
          onOpenApp('terminal');
          onClose();
        }}
        className="w-full min-h-[40px] px-3 rounded-lg flex items-center gap-2.5 text-xs font-medium hover:bg-white/10 transition-colors text-left"
        role="menuitem"
      >
        <Terminal size={15} style={{ color: 'var(--nura-accent)' }} />
        <span>Abrir NURA Terminal</span>
      </button>

      <button
        type="button"
        onClick={() => {
          onOpenApp('control-center', { tab: 'themes' });
          onClose();
        }}
        className="w-full min-h-[40px] px-3 rounded-lg flex items-center gap-2.5 text-xs font-medium hover:bg-white/10 transition-colors text-left"
        role="menuitem"
      >
        <Palette size={15} style={{ color: 'var(--nura-accent)' }} />
        <span>Personalizar temas</span>
      </button>

      <button
        type="button"
        onClick={() => {
          onOpenApp('control-center');
          onClose();
        }}
        className="w-full min-h-[40px] px-3 rounded-lg flex items-center gap-2.5 text-xs font-medium hover:bg-white/10 transition-colors text-left"
        role="menuitem"
      >
        <SlidersHorizontal size={15} style={{ color: 'var(--nura-accent)' }} />
        <span>Configurações do sistema</span>
      </button>

      <div className="my-1 border-t" style={{ borderColor: 'var(--nura-border)' }} />

      <button
        type="button"
        onClick={() => {
          onToggleFullscreen();
          onClose();
        }}
        className="w-full min-h-[40px] px-3 rounded-lg flex items-center gap-2.5 text-xs font-medium hover:bg-white/10 transition-colors text-left"
        role="menuitem"
      >
        <Maximize size={15} style={{ color: 'var(--nura-text-muted)' }} />
        <span>Alternar tela cheia</span>
      </button>

      <button
        type="button"
        onClick={() => {
          onRefreshDesktop();
          onClose();
        }}
        className="w-full min-h-[40px] px-3 rounded-lg flex items-center gap-2.5 text-xs font-medium hover:bg-white/10 transition-colors text-left"
        role="menuitem"
      >
        <RefreshCw size={15} style={{ color: 'var(--nura-text-muted)' }} />
        <span>Atualizar área de trabalho</span>
      </button>
    </div>
  );
}
