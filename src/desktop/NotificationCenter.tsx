import { Bell, CheckCheck, Trash2, X } from 'lucide-react';
import { AppId, OsNotification } from '../types/os';

interface NotificationCenterProps {
  isOpen: boolean;
  notifications: OsNotification[];
  toastQueue: OsNotification[];
  onCloseDrawer: () => void;
  onDismissToast: (id: string) => void;
  onMarkAllRead: () => void;
  onClearAll: () => void;
  onOpenApp: (appId: AppId) => void;
}

export function NotificationCenter({
  isOpen,
  notifications,
  toastQueue,
  onCloseDrawer,
  onDismissToast,
  onMarkAllRead,
  onClearAll,
  onOpenApp,
}: NotificationCenterProps) {
  return (
    <>
      {/* Floating Toasts */}
      {toastQueue.length > 0 && !isOpen && (
        <div className="fixed bottom-[66px] right-3 sm:right-4 z-[82] w-[min(340px,calc(100vw-24px))] flex flex-col gap-2 pointer-events-none">
          {toastQueue.map((toast) => (
            <div
              key={toast.id}
              className="pointer-events-auto rounded-xl p-3.5 backdrop-blur-2xl flex items-start justify-between gap-3 transition-transform"
              style={{
                backgroundColor: 'var(--nura-surface-elevated)',
                border: '1px solid var(--nura-border-strong)',
                boxShadow: 'var(--nura-shadow)',
                color: 'var(--nura-text)',
              }}
              role="status"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-xs font-semibold">
                  <Bell size={13} style={{ color: 'var(--nura-accent)' }} />
                  <span className="truncate">{toast.title}</span>
                </div>
                <p
                  className="text-xs mt-1 leading-relaxed"
                  style={{ color: 'var(--nura-text-muted)' }}
                >
                  {toast.message}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onDismissToast(toast.id)}
                className="min-w-[32px] min-h-[32px] rounded-lg flex items-center justify-center hover:bg-white/10 shrink-0"
                style={{ color: 'var(--nura-text-muted)' }}
                aria-label="Dispensar notificação"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Drawer */}
      {isOpen && (
        <aside
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
          className="fixed bottom-[64px] right-3 sm:right-4 z-[85] w-[min(380px,calc(100vw-24px))] max-h-[min(520px,calc(100vh-84px))] rounded-2xl flex flex-col overflow-hidden backdrop-blur-2xl"
          style={{
            backgroundColor: 'var(--nura-surface-elevated)',
            border: '1px solid var(--nura-border-strong)',
            boxShadow: 'var(--nura-shadow)',
            color: 'var(--nura-text)',
          }}
          aria-label="Central de Notificações"
        >
          <div
            className="px-4 py-3 border-b flex items-center justify-between gap-2"
            style={{ borderColor: 'var(--nura-border)' }}
          >
            <div className="flex items-center gap-2">
              <Bell size={16} style={{ color: 'var(--nura-accent)' }} />
              <h3 className="font-display text-sm font-semibold">Notificações</h3>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={onMarkAllRead}
                className="min-w-[36px] min-h-[36px] px-2 rounded-lg flex items-center gap-1 text-xs hover:bg-white/10 transition-colors"
                style={{ color: 'var(--nura-text-muted)' }}
                title="Marcar todas como lidas"
              >
                <CheckCheck size={14} />
              </button>
              <button
                type="button"
                onClick={onClearAll}
                className="min-w-[36px] min-h-[36px] px-2 rounded-lg flex items-center gap-1 text-xs hover:bg-white/10 transition-colors"
                style={{ color: 'var(--nura-text-muted)' }}
                title="Limpar notificações"
              >
                <Trash2 size={14} />
              </button>
              <button
                type="button"
                onClick={onCloseDrawer}
                className="min-w-[36px] min-h-[36px] rounded-lg flex items-center justify-center hover:bg-white/10 transition-colors"
                style={{ color: 'var(--nura-text-muted)' }}
                aria-label="Fechar central de notificações"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2 nura-scroll">
            {notifications.length === 0 ? (
              <div className="py-10 text-center text-xs" style={{ color: 'var(--nura-text-muted)' }}>
                Nenhuma notificação no momento.
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => {
                    if (n.appId) {
                      onOpenApp(n.appId);
                      onCloseDrawer();
                    }
                  }}
                  className={`p-3 rounded-xl transition-colors ${
                    n.appId ? 'cursor-pointer hover:bg-white/10' : ''
                  }`}
                  style={{
                    backgroundColor: 'var(--nura-surface-subtle)',
                    border: '1px solid var(--nura-border)',
                  }}
                >
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-semibold truncate">{n.title}</span>
                    <span className="tabular-nums shrink-0" style={{ color: 'var(--nura-text-muted)' }}>
                      {n.timestamp}
                    </span>
                  </div>
                  <p
                    className="text-xs mt-1 leading-relaxed"
                    style={{ color: 'var(--nura-text-muted)' }}
                  >
                    {n.message}
                  </p>
                </div>
              ))
            )}
          </div>
        </aside>
      )}
    </>
  );
}
