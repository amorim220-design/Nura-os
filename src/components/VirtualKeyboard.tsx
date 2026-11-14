import { CornerDownLeft, Delete, Space, X } from 'lucide-react';
import { useState } from 'react';

interface VirtualKeyboardProps {
  isOpen: boolean;
  onClose: () => void;
  onKeyPress: (key: string) => void;
}

const ROWS_LOWER = [
  ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '/'],
  ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
  ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', '~'],
  ['z', 'x', 'c', 'v', 'b', 'n', 'm', '.', '_'],
];

const ROWS_UPPER = [
  ['!', '@', '#', '$', '%', '&', '*', '(', ')', '_', '+', '|'],
  ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
  ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':'],
  ['Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '?'],
];

export function VirtualKeyboard({ isOpen, onClose, onKeyPress }: VirtualKeyboardProps) {
  const [shift, setShift] = useState(false);

  if (!isOpen) return null;

  const rows = shift ? ROWS_UPPER : ROWS_LOWER;

  const handleTap = (key: string) => {
    onKeyPress(key);
    if (shift && key.length === 1) {
      setShift(false);
    }
  };

  return (
    <div
      className="fixed left-1/2 -translate-x-1/2 bottom-[62px] z-[90] w-[min(760px,calc(100vw-16px))] rounded-2xl p-3 backdrop-blur-2xl transition-transform duration-150"
      style={{
        backgroundColor: 'var(--nura-surface-elevated)',
        border: '1px solid var(--nura-border-strong)',
        boxShadow: 'var(--nura-shadow)',
      }}
      onPointerDown={(e) => e.preventDefault()}
      aria-label="Teclado Virtual Demonstrativo NURA OS"
    >
      <div className="flex items-center justify-between px-1 pb-2 mb-2 border-b border-white/10">
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--nura-text-muted)' }}>
          <span className="font-display font-semibold" style={{ color: 'var(--nura-text)' }}>
            Teclado Virtual NURA
          </span>
          <span aria-hidden="true">·</span>
          <span>Toque para digitar no campo ou terminal ativo</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg hover:bg-white/10 transition-colors"
          style={{ color: 'var(--nura-text-muted)' }}
          aria-label="Fechar teclado virtual"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex flex-col gap-1.5">
        {rows.map((row, rIdx) => (
          <div key={rIdx} className="flex items-center justify-center gap-1.5">
            {row.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => handleTap(key)}
                className="flex-1 min-w-[26px] max-w-[54px] h-[42px] rounded-lg text-sm font-medium flex items-center justify-center active:scale-95 transition-transform"
                style={{
                  backgroundColor: 'var(--nura-surface-subtle)',
                  border: '1px solid var(--nura-border)',
                  color: 'var(--nura-text)',
                }}
              >
                {key}
              </button>
            ))}
            {rIdx === 3 && (
              <button
                type="button"
                onClick={() => handleTap('BACKSPACE')}
                className="px-3 h-[42px] rounded-lg text-xs font-medium flex items-center justify-center active:scale-95 transition-transform"
                style={{
                  backgroundColor: 'rgba(244, 63, 94, 0.16)',
                  border: '1px solid rgba(244, 63, 94, 0.35)',
                  color: 'var(--nura-text)',
                }}
                aria-label="Apagar caractere"
              >
                <Delete size={16} />
              </button>
            )}
          </div>
        ))}

        <div className="flex items-center justify-center gap-2 pt-0.5">
          <button
            type="button"
            onClick={() => setShift((s) => !s)}
            className="px-4 h-[42px] rounded-lg text-xs font-semibold whitespace-nowrap shrink-0 active:scale-95 transition-transform"
            style={{
              backgroundColor: shift ? 'var(--nura-accent)' : 'var(--nura-surface-subtle)',
              color: shift ? 'var(--nura-accent-contrast)' : 'var(--nura-text)',
              border: '1px solid var(--nura-border)',
            }}
          >
            Shift
          </button>
          <button
            type="button"
            onClick={() => handleTap(' ')}
            className="flex-1 max-w-[320px] h-[42px] rounded-lg text-xs font-medium flex items-center justify-center gap-2 active:scale-95 transition-transform"
            style={{
              backgroundColor: 'var(--nura-surface-subtle)',
              border: '1px solid var(--nura-border)',
              color: 'var(--nura-text-muted)',
            }}
          >
            <Space size={15} />
            <span>Espaço</span>
          </button>
          <button
            type="button"
            onClick={() => handleTap('ENTER')}
            className="px-4 h-[42px] rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 whitespace-nowrap shrink-0 active:scale-95 transition-transform"
            style={{
              backgroundColor: 'var(--nura-accent)',
              color: 'var(--nura-accent-contrast)',
            }}
          >
            <CornerDownLeft size={15} />
            <span>Enter</span>
          </button>
        </div>
      </div>
    </div>
  );
}
