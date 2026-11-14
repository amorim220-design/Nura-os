import { NuraLogo, NuraWordmark } from '../components/NuraLogo';

export function AboutApp() {
  return (
    <div
      className="h-full overflow-y-auto p-5 space-y-5 text-sm nura-scroll"
      style={{ touchAction: 'pan-y' }}
    >
      <div className="flex items-center gap-4">
        <NuraLogo size={48} />
        <div>
          <NuraWordmark height={22} />
          <p className="text-xs mt-1.5" style={{ color: 'var(--nura-text-muted)' }}>
            Protótipo Web Interativo · Referência de Interface Gráfica Desktop
          </p>
        </div>
      </div>

      <p className="text-xs leading-relaxed" style={{ color: 'var(--nura-text-muted)' }}>
        O NURA OS é um projeto de distribuição Linux em desenvolvimento baseada em{' '}
        <strong style={{ color: 'var(--nura-text)' }}>Alpine Linux / postmarketOS</strong>,
        inicialmente voltada para o smartphone{' '}
        <strong style={{ color: 'var(--nura-text)' }}>Nubia Z17 Lite</strong> com foco em uso
        horizontal desktop por toque e mouse.
      </p>

      <dl
        className="rounded-xl divide-y text-xs"
        style={{
          backgroundColor: 'var(--nura-surface-subtle)',
          border: '1px solid var(--nura-border)',
          borderColor: 'var(--nura-border)',
        }}
      >
        {[
          ['Arquitetura Alvo', 'ARM64 (aarch64) · Alpine musl + postmarketOS'],
          ['Resolução Base', '1920 × 1080 · Modo Horizontal Prioritário'],
          ['Módulos do Protótipo', 'Desktop, Window Manager, NURA Start, Explorer, Terminal, Control Center, Game Hub, Performance'],
          ['Escopo de Segurança', 'Execução exclusivamente no navegador; sem alterações em partições, bootloader ou sistema real'],
        ].map(([k, v]) => (
          <div key={k} className="px-4 py-3 flex flex-wrap justify-between gap-2">
            <dt style={{ color: 'var(--nura-text-muted)' }}>{k}</dt>
            <dd className="font-medium text-right">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
