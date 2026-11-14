import { Power, RotateCcw, X } from 'lucide-react';
import { useState } from 'react';
import { NuraLogo } from '../components/NuraLogo';

interface PowerDialogProps {
  action: 'shutdown' | 'restart' | null;
  onClose: () => void;
  onResetSession: () => void;
  onTriggerBoot: () => void;
}

export function PowerDialog({
  action,
  onClose,
  onResetSession,
  onTriggerBoot,
}: PowerDialogProps) {
  const [simulatedState, setSimulatedState] = useState<'idle' | 'halted'>('idle');

  if (!action) return null;

  const isShutdown = action === 'shutdown';

  const handleConfirm = () => {
    if (isShutdown) {
      setSimulatedState('halted');
    } else {
      onResetSession();
      onClose();
      onTriggerBoot();
    }
  };

  if (simulatedState === 'halted') {
    return (
      <div
        className="fixed inset-0 z-[120] flex flex-col items-center justify-center p-6 text-center"
        style={{ backgroundColor: '#020408', color: '#f1f5f9' }}
      >
        <NuraLogo size={54} />
        <h2 className="font-display text-xl font-semibold mt-4">
          Desligamento Simulado Concluído
        </h2>
        <p className="text-sm text-slate-400 max-w-md mt-2 leading-relaxed">
          Esta é apenas uma simulação da interface web NURA OS Desktop. Nenhum sistema operacional
          real ou hardware do dispositivo foi desligado.
        </p>
        <button
          type="button"
          onClick={() => {
            setSimulatedState('idle');
            onResetSession();
            onClose();
            onTriggerBoot();
          }}
          className="mt-6 h-[44px] px-6 rounded-xl text-sm font-semibold transition-transform active:scale-95"
          style={{
            backgroundColor: 'var(--nura-accent)',
            color: 'var(--nura-accent-contrast)',
          }}
        >
          Ligar NURA OS (Simulação)
        </button>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 z-[110] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl p-5 backdrop-blur-2xl"
        style={{
          backgroundColor: 'var(--nura-surface-elevated)',
          border: '1px solid var(--nura-border-strong)',
          boxShadow: 'var(--nura-shadow)',
          color: 'var(--nura-text)',
        }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="power-dialog-title"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{
                backgroundColor: isShutdown
                  ? 'rgba(244, 63, 94, 0.16)'
                  : 'rgba(6, 182, 212, 0.16)',
                color: isShutdown ? '#fb7185' : 'var(--nura-accent)',
              }}
            >
              {isShutdown ? <Power size={20} /> : <RotateCcw size={20} />}
            </span>
            <div>
              <h3 id="power-dialog-title" className="font-display text-base font-semibold">
                {isShutdown ? 'Simular Desligamento' : 'Simular Reinicialização'}
              </h3>
              <p className="text-xs" style={{ color: 'var(--nura-text-muted)' }}>
                Ação demonstrativa do protótipo NURA OS
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="min-w-[36px] min-h-[36px] rounded-lg flex items-center justify-center hover:bg-white/10"
            aria-label="Cancelar"
          >
            <X size={16} />
          </button>
        </div>

        <p className="text-sm mt-4 leading-relaxed" style={{ color: 'var(--nura-text-muted)' }}>
          {isShutdown
            ? 'Este botão demonstra o fluxo de desligamento do NURA OS Desktop no navegador. Ele não desliga seu aparelho nem executa comandos reais de energia.'
            : 'Este botão demonstra a reinicialização da sessão gráfica do NURA OS no navegador (fechando janelas abertas). Nenhum dispositivo físico será reiniciado.'}
        </p>

        <div className="mt-5 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="h-[40px] px-4 rounded-xl text-xs font-medium hover:bg-white/10 transition-colors"
            style={{
              border: '1px solid var(--nura-border)',
              color: 'var(--nura-text)',
            }}
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            className="h-[40px] px-4 rounded-xl text-xs font-semibold transition-transform active:scale-95"
            style={{
              backgroundColor: isShutdown ? '#e11d48' : 'var(--nura-accent)',
              color: '#ffffff',
            }}
          >
            {isShutdown ? 'Confirmar Simulação' : 'Reiniciar Sessão'}
          </button>
        </div>
      </div>
    </div>
  );
}
