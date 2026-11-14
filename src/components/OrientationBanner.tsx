import { RotateCw, X } from 'lucide-react';
import { useEffect, useState } from 'react';

export function OrientationBanner() {
  const [isPortrait, setIsPortrait] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const check = () => {
      const portrait = window.innerHeight > window.innerWidth && window.innerWidth < 820;
      setIsPortrait(portrait);
      if (!portrait) setDismissed(false);
    };
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  if (!isPortrait || dismissed) return null;

  return (
    <div
      className="fixed bottom-[64px] left-3 right-3 z-50 flex items-center justify-between gap-3 rounded-xl px-4 py-2.5 backdrop-blur-xl shadow-lg"
      style={{
        backgroundColor: 'var(--nura-surface-elevated)',
        border: '1px solid var(--nura-border-strong)',
        color: 'var(--nura-text)',
      }}
      role="status"
    >
      <div className="flex items-center gap-3 min-w-0">
        <RotateCw
          size={18}
          className="shrink-0"
          style={{ color: 'var(--nura-accent)' }}
        />
        <p className="text-xs leading-snug">
          <span className="font-semibold">Modo horizontal recomendado:</span> gire o smartphone
          para aproveitar a área de trabalho NURA OS em tela ampla.
        </p>
      </div>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg hover:bg-white/10 transition-colors shrink-0"
        aria-label="Dispensar aviso de orientação"
      >
        <X size={16} />
      </button>
    </div>
  );
}
