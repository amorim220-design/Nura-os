import {
  FolderOpen,
  Power,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Terminal,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { AppIcon } from '../components/AppIcon';
import { NuraLogo } from '../components/NuraLogo';
import { ALL_APPS } from '../services/appsRegistry';
import { AppId } from '../types/os';

interface StartMenuProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenApp: (appId: AppId) => void;
  onTriggerPower: (action: 'shutdown' | 'restart') => void;
}

export function StartMenu({
  isOpen,
  onClose,
  onOpenApp,
  onTriggerPower,
}: StartMenuProps) {
  const [query, setQuery] = useState('');

  const filteredApps = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ALL_APPS;
    return ALL_APPS.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.category.toLowerCase().includes(q)
    );
  }, [query]);

  const pinnedApps = useMemo(() => ALL_APPS.filter((a) => a.pinned), []);

  if (!isOpen) return null;

  const launch = (appId: AppId) => {
    onOpenApp(appId);
    onClose();
    setQuery('');
  };

  return (
    <aside
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      className="fixed bottom-[64px] left-3 sm:left-4 z-[85] w-[min(540px,calc(100vw-24px))] max-h-[min(620px,calc(100vh-84px))] rounded-2xl flex flex-col overflow-hidden backdrop-blur-2xl"
      style={{
        backgroundColor: 'var(--nura-surface-elevated)',
        border: '1px solid var(--nura-border-strong)',
        boxShadow: 'var(--nura-shadow), 0 0 32px var(--nura-glow), inset 0 1px 0 rgba(255,255,255,0.1)',
        color: 'var(--nura-text)',
      }}
      aria-label="Menu Iniciar NURA Start"
    >
      <div
        className="h-[1.5px] w-full shrink-0"
        style={{
          background:
            'linear-gradient(90deg, transparent, var(--nura-accent), var(--nura-accent-strong), transparent)',
        }}
        aria-hidden="true"
      />
      {/* Header + Search */}
      <div className="p-4 pb-3 border-b" style={{ borderColor: 'var(--nura-border)' }}>
        <div className="flex items-center justify-between gap-3 mb-3">
          <NuraLogo size={28} withWordmark />
          <span className="text-xs" style={{ color: 'var(--nura-text-muted)' }}>
            Sessão Desktop · Protótipo
          </span>
        </div>

        <label className="relative flex items-center">
          <Search
            size={16}
            className="absolute left-3.5 pointer-events-none"
            style={{ color: 'var(--nura-text-muted)' }}
          />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Pesquisar aplicativos do NURA OS..."
            className="w-full h-[42px] pl-10 pr-4 rounded-xl text-sm outline-none transition-colors"
            style={{
              backgroundColor: 'var(--nura-surface-subtle)',
              border: '1px solid var(--nura-border)',
              color: 'var(--nura-text)',
            }}
          />
        </label>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 nura-scroll">
        {!query.trim() && (
          <section>
            <div className="flex items-center justify-between mb-2.5">
              <h3
                className="text-xs font-semibold tracking-wide"
                style={{ color: 'var(--nura-text-muted)' }}
              >
                Aplicativos fixados
              </h3>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
              {pinnedApps.map((app) => (
                <button
                  key={app.id}
                  type="button"
                  onClick={() => launch(app.id)}
                  className="p-2.5 rounded-xl flex flex-col items-center gap-2 text-center hover:bg-white/10 transition-colors active:scale-95"
                  style={{
                    backgroundColor: 'var(--nura-surface-subtle)',
                    border: '1px solid var(--nura-border)',
                  }}
                >
                  <AppIcon appId={app.id} size={20} containerSize={38} />
                  <span className="text-xs font-medium leading-tight line-clamp-1">
                    {app.shortName}
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        <section>
          <h3
            className="text-xs font-semibold tracking-wide mb-2.5"
            style={{ color: 'var(--nura-text-muted)' }}
          >
            {query.trim() ? 'Resultados da pesquisa' : 'Todos os aplicativos'}
          </h3>

          {filteredApps.length === 0 ? (
            <p className="text-sm py-6 text-center" style={{ color: 'var(--nura-text-muted)' }}>
              Nenhum aplicativo encontrado para "{query}".
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {filteredApps.map((app) => (
                <button
                  key={app.id}
                  type="button"
                  onClick={() => launch(app.id)}
                  className="w-full min-h-[52px] px-3 py-2 rounded-xl flex items-center gap-3 text-left hover:bg-white/10 transition-colors"
                >
                  <AppIcon appId={app.id} size={18} containerSize={36} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">{app.name}</div>
                    <div
                      className="text-xs truncate"
                      style={{ color: 'var(--nura-text-muted)' }}
                    >
                      {app.category} · {app.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Footer: Quick shortcuts + Simulated Power Actions */}
      <div
        className="px-4 py-3 border-t flex flex-wrap items-center justify-between gap-2"
        style={{
          borderColor: 'var(--nura-border)',
          backgroundColor: 'var(--nura-surface)',
        }}
      >
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => launch('explorer')}
            className="h-[38px] px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-white/10 transition-colors whitespace-nowrap shrink-0"
            title="Abrir Arquivos"
          >
            <FolderOpen size={15} style={{ color: 'var(--nura-accent)' }} />
            <span>Arquivos</span>
          </button>
          <button
            type="button"
            onClick={() => launch('terminal')}
            className="h-[38px] px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-white/10 transition-colors whitespace-nowrap shrink-0"
            title="Abrir Terminal"
          >
            <Terminal size={15} style={{ color: 'var(--nura-accent)' }} />
            <span>Terminal</span>
          </button>
          <button
            type="button"
            onClick={() => launch('control-center')}
            className="h-[38px] px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-white/10 transition-colors whitespace-nowrap shrink-0"
            title="Abrir Configurações"
          >
            <SlidersHorizontal size={15} style={{ color: 'var(--nura-accent)' }} />
            <span>Configurações</span>
          </button>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => {
              onClose();
              onTriggerPower('restart');
            }}
            className="h-[38px] px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-white/10 transition-colors whitespace-nowrap shrink-0"
            style={{ color: 'var(--nura-text-muted)' }}
            title="Reiniciar (Simulação)"
          >
            <RotateCcw size={15} />
            <span className="hidden sm:inline">Reiniciar</span>
          </button>
          <button
            type="button"
            onClick={() => {
              onClose();
              onTriggerPower('shutdown');
            }}
            className="h-[38px] px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-rose-500/20 hover:text-rose-300 transition-colors whitespace-nowrap shrink-0"
            style={{ color: 'var(--nura-text)' }}
            title="Desligar (Simulação)"
          >
            <Power size={15} className="text-rose-400" />
            <span>Desligar</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
