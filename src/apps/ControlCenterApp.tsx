import {
  BatteryCharging,
  Bluetooth,
  Info,
  Keyboard,
  Maximize,
  Monitor,
  Palette,
  Volume2,
  Wifi,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { THEME_LIST } from '../themes/themes';
import { PowerProfile, SystemSettings, ThemeId } from '../types/os';

interface ControlCenterAppProps {
  settings: SystemSettings;
  updateSettings: (patch: Partial<SystemSettings>) => void;
  themeId: ThemeId;
  setThemeId: (id: ThemeId) => void;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
  initialTab?: string;
}

type TabKey = 'connections' | 'display' | 'themes' | 'input' | 'battery' | 'system';

const TABS: { id: TabKey; label: string }[] = [
  { id: 'connections', label: 'Rede & Bluetooth' },
  { id: 'display', label: 'Tela & Som' },
  { id: 'themes', label: 'Temas NURA' },
  { id: 'input', label: 'Toque & Teclado' },
  { id: 'battery', label: 'Bateria & Energia' },
  { id: 'system', label: 'Sistema' },
];

export function ControlCenterApp({
  settings,
  updateSettings,
  themeId,
  setThemeId,
  isFullscreen,
  onToggleFullscreen,
  initialTab,
}: ControlCenterAppProps) {
  const [activeTab, setActiveTab] = useState<TabKey>(
    initialTab === 'themes' ? 'themes' : 'connections'
  );

  useEffect(() => {
    if (initialTab === 'themes') {
      setActiveTab('themes');
    }
  }, [initialTab]);

  const playVolumeChime = () => {
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(528, ctx.currentTime);
      gain.gain.setValueAtTime((settings.volume / 100) * 0.16, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.26);
    } catch {
      // Audio playback skipped if blocked
    }
  };

  return (
    <div className="h-full flex flex-col sm:flex-row text-sm">
      {/* Navigation Sidebar */}
      <aside
        className="sm:w-[205px] p-2.5 border-b sm:border-b-0 sm:border-r flex sm:flex-col gap-1 overflow-x-auto nura-scroll shrink-0"
        style={{ borderColor: 'var(--nura-border)' }}
      >
        {TABS.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className="h-[40px] px-3 rounded-xl text-xs font-medium flex items-center gap-2 transition-colors whitespace-nowrap shrink-0 text-left"
              style={{
                backgroundColor: active ? 'var(--nura-surface-elevated)' : 'transparent',
                border: active
                  ? '1px solid var(--nura-border-strong)'
                  : '1px solid transparent',
                color: active ? 'var(--nura-accent)' : 'var(--nura-text)',
              }}
            >
              <span>{tab.label}</span>
            </button>
          );
        })}
      </aside>

      {/* Main Content */}
      <div
        className="flex-1 min-w-0 overflow-y-auto p-4 sm:p-5 space-y-5 nura-scroll"
        style={{ touchAction: 'pan-y' }}
      >
        <div
          className="px-3.5 py-2.5 rounded-xl text-xs leading-relaxed"
          style={{
            backgroundColor: 'var(--nura-surface-subtle)',
            border: '1px solid var(--nura-border)',
            color: 'var(--nura-text-muted)',
          }}
        >
          Aviso do protótipo: controles de hardware (Wi-Fi, Bluetooth, bateria e áudio do sistema)
          operam em <strong style={{ color: 'var(--nura-text)' }}>modo de demonstração</strong> e
          não alteram configurações reais do aparelho.
        </div>

        {activeTab === 'connections' && (
          <section className="space-y-4">
            <h3 className="font-display text-base font-semibold">Conectividade (Simulação)</h3>

            <div
              className="p-4 rounded-xl flex items-center justify-between gap-4"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Wifi size={20} style={{ color: 'var(--nura-accent)' }} className="shrink-0" />
                <div className="min-w-0">
                  <div className="font-medium text-sm">Wi-Fi · Demonstração</div>
                  <div className="text-xs truncate" style={{ color: 'var(--nura-text-muted)' }}>
                    {settings.wifiEnabled ? settings.wifiNetwork : 'Desconectado'}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => updateSettings({ wifiEnabled: !settings.wifiEnabled })}
                className="h-[38px] px-4 rounded-xl text-xs font-semibold transition-colors shrink-0"
                style={{
                  backgroundColor: settings.wifiEnabled
                    ? 'var(--nura-accent)'
                    : 'var(--nura-surface-elevated)',
                  color: settings.wifiEnabled
                    ? 'var(--nura-accent-contrast)'
                    : 'var(--nura-text)',
                  border: '1px solid var(--nura-border)',
                }}
              >
                {settings.wifiEnabled ? 'Ativado' : 'Desativado'}
              </button>
            </div>

            {settings.wifiEnabled && (
              <div className="space-y-1.5">
                <div className="text-xs font-medium" style={{ color: 'var(--nura-text-muted)' }}>
                  Redes simuladas disponíveis
                </div>
                {[
                  'NURA-Lab-5GHz (Simulado)',
                  'Alpine-Build-Net (Simulado)',
                  'Nubia-Hotspot (Simulado)',
                ].map((net) => (
                  <button
                    key={net}
                    type="button"
                    onClick={() => updateSettings({ wifiNetwork: net })}
                    className="w-full h-[42px] px-3.5 rounded-xl flex items-center justify-between text-xs hover:bg-white/5 transition-colors"
                    style={{
                      backgroundColor:
                        settings.wifiNetwork === net
                          ? 'var(--nura-surface-elevated)'
                          : 'transparent',
                      border: '1px solid var(--nura-border)',
                    }}
                  >
                    <span>{net}</span>
                    <span style={{ color: 'var(--nura-accent)' }}>
                      {settings.wifiNetwork === net ? 'Conectado' : 'Selecionar'}
                    </span>
                  </button>
                ))}
              </div>
            )}

            <div
              className="p-4 rounded-xl flex items-center justify-between gap-4"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Bluetooth size={20} style={{ color: 'var(--nura-accent)' }} className="shrink-0" />
                <div className="min-w-0">
                  <div className="font-medium text-sm">Bluetooth · Demonstração</div>
                  <div className="text-xs truncate" style={{ color: 'var(--nura-text-muted)' }}>
                    {settings.bluetoothEnabled ? settings.bluetoothDevice : 'Rádio desligado'}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => updateSettings({ bluetoothEnabled: !settings.bluetoothEnabled })}
                className="h-[38px] px-4 rounded-xl text-xs font-semibold transition-colors shrink-0"
                style={{
                  backgroundColor: settings.bluetoothEnabled
                    ? 'var(--nura-accent)'
                    : 'var(--nura-surface-elevated)',
                  color: settings.bluetoothEnabled
                    ? 'var(--nura-accent-contrast)'
                    : 'var(--nura-text)',
                  border: '1px solid var(--nura-border)',
                }}
              >
                {settings.bluetoothEnabled ? 'Ativado' : 'Desativado'}
              </button>
            </div>
          </section>
        )}

        {activeTab === 'display' && (
          <section className="space-y-4">
            <h3 className="font-display text-base font-semibold">Tela, Orientação & Áudio</h3>

            <div
              className="p-4 rounded-xl space-y-3"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-medium">
                  <Monitor size={17} style={{ color: 'var(--nura-accent)' }} />
                  Brilho da interface (Simulado)
                </span>
                <span className="text-xs font-mono tabular-nums">{settings.brightness}%</span>
              </div>
              <input
                type="range"
                min={35}
                max={100}
                value={settings.brightness}
                onChange={(e) => updateSettings({ brightness: Number(e.target.value) })}
                className="w-full accent-cyan-400 h-2 cursor-pointer"
              />
            </div>

            <div
              className="p-4 rounded-xl space-y-3"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-medium">
                  <Volume2 size={17} style={{ color: 'var(--nura-accent)' }} />
                  Volume demonstrativo
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono tabular-nums">{settings.volume}%</span>
                  <button
                    type="button"
                    onClick={playVolumeChime}
                    className="h-[32px] px-3 rounded-lg text-xs font-medium hover:bg-white/10"
                    style={{ border: '1px solid var(--nura-border)' }}
                  >
                    Testar som
                  </button>
                </div>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={settings.volume}
                onChange={(e) => updateSettings({ volume: Number(e.target.value) })}
                className="w-full accent-cyan-400 h-2 cursor-pointer"
              />
            </div>

            <div
              className="p-4 rounded-xl flex flex-wrap items-center justify-between gap-3"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div>
                <div className="text-sm font-medium">Modo de demonstração em tela cheia</div>
                <div className="text-xs" style={{ color: 'var(--nura-text-muted)' }}>
                  Expande o protótipo NURA OS para ocupar toda a tela do navegador
                </div>
              </div>
              <button
                type="button"
                onClick={onToggleFullscreen}
                className="h-[38px] px-4 rounded-xl text-xs font-semibold flex items-center gap-2 whitespace-nowrap shrink-0"
                style={{
                  backgroundColor: 'var(--nura-accent)',
                  color: 'var(--nura-accent-contrast)',
                }}
              >
                <Maximize size={14} />
                <span>{isFullscreen ? 'Sair da tela cheia' : 'Ativar tela cheia'}</span>
              </button>
            </div>

            <div
              className="p-4 rounded-xl flex flex-wrap items-center justify-between gap-3"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div>
                <div className="text-sm font-medium">Preferência de orientação</div>
                <div className="text-xs" style={{ color: 'var(--nura-text-muted)' }}>
                  Resolução de referência: 1920 × 1080 horizontal
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                {(['landscape-primary', 'auto'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => updateSettings({ orientationPreference: mode })}
                    className="h-[36px] px-3 rounded-lg text-xs font-medium whitespace-nowrap"
                    style={{
                      backgroundColor:
                        settings.orientationPreference === mode
                          ? 'var(--nura-accent)'
                          : 'var(--nura-surface-elevated)',
                      color:
                        settings.orientationPreference === mode
                          ? 'var(--nura-accent-contrast)'
                          : 'var(--nura-text)',
                      border: '1px solid var(--nura-border)',
                    }}
                  >
                    {mode === 'landscape-primary' ? 'Horizontal' : 'Automática'}
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

        {activeTab === 'themes' && (
          <section className="space-y-4">
            <div className="flex items-center gap-2">
              <Palette size={18} style={{ color: 'var(--nura-accent)' }} />
              <h3 className="font-display text-base font-semibold">Temas do NURA OS</h3>
            </div>
            <p className="text-xs" style={{ color: 'var(--nura-text-muted)' }}>
              Alterne entre os quatro temas visuais instantaneamente sem reiniciar o protótipo.
              Sua escolha é salva localmente.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {THEME_LIST.map((t) => {
                const selected = themeId === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setThemeId(t.id)}
                    className="p-4 rounded-xl text-left transition-all hover:bg-white/5"
                    style={{
                      backgroundColor: selected
                        ? 'var(--nura-surface-elevated)'
                        : 'var(--nura-surface-subtle)',
                      border: `1.5px solid ${
                        selected ? 'var(--nura-accent)' : 'var(--nura-border)'
                      }`,
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-display text-sm font-semibold">{t.name}</span>
                      <div className="flex items-center gap-1" aria-hidden="true">
                        {t.accentSwatch.map((hex, i) => (
                          <span
                            key={i}
                            className="w-3.5 h-3.5 rounded-full border border-white/20"
                            style={{ backgroundColor: hex }}
                          />
                        ))}
                      </div>
                    </div>
                    <p
                      className="text-xs mt-1.5 leading-relaxed"
                      style={{ color: 'var(--nura-text-muted)' }}
                    >
                      {t.subtitle}
                    </p>
                    <div
                      className="text-[11px] font-semibold mt-2.5"
                      style={{ color: selected ? 'var(--nura-accent)' : 'var(--nura-text-muted)' }}
                    >
                      {selected ? 'Tema ativo' : 'Aplicar tema'}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {activeTab === 'input' && (
          <section className="space-y-4">
            <h3 className="font-display text-base font-semibold">Entrada por Toque & Teclado</h3>

            <div
              className="p-4 rounded-xl flex items-center justify-between gap-4"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div className="flex items-center gap-3">
                <Keyboard size={20} style={{ color: 'var(--nura-accent)' }} />
                <div>
                  <div className="text-sm font-medium">Teclado virtual demonstrativo</div>
                  <div className="text-xs" style={{ color: 'var(--nura-text-muted)' }}>
                    Exibe o teclado tátil sobre a área de trabalho para entrada em tela sensível ao toque
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() =>
                  updateSettings({ virtualKeyboardOpen: !settings.virtualKeyboardOpen })
                }
                className="h-[38px] px-4 rounded-xl text-xs font-semibold shrink-0"
                style={{
                  backgroundColor: settings.virtualKeyboardOpen
                    ? 'var(--nura-accent)'
                    : 'var(--nura-surface-elevated)',
                  color: settings.virtualKeyboardOpen
                    ? 'var(--nura-accent-contrast)'
                    : 'var(--nura-text)',
                  border: '1px solid var(--nura-border)',
                }}
              >
                {settings.virtualKeyboardOpen ? 'Ocultar' : 'Abrir'}
              </button>
            </div>

            <div
              className="p-4 rounded-xl space-y-2 text-xs leading-relaxed"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
                color: 'var(--nura-text-muted)',
              }}
            >
              <div className="font-semibold text-sm" style={{ color: 'var(--nura-text)' }}>
                Gestos suportados neste protótipo
              </div>
              <p>· Arrastar barra de título com dedo ou mouse para mover janelas</p>
              <p>· Arrastar bordas ou canto inferior direito para redimensionar</p>
              <p>· Toque prolongado sobre ícones ou área de trabalho para menu de contexto</p>
              <p>· Rolagem independente dentro do corpo das janelas sem conflito de arraste</p>
            </div>
          </section>
        )}

        {activeTab === 'battery' && (
          <section className="space-y-4">
            <h3 className="font-display text-base font-semibold">Bateria & Energia (Simulação)</h3>

            <div
              className="p-4 rounded-xl flex items-center justify-between gap-4"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div className="flex items-center gap-3">
                <BatteryCharging size={22} className="text-emerald-400" />
                <div>
                  <div className="text-sm font-semibold tabular-nums">
                    {settings.batteryLevel}% · {settings.batteryCharging ? 'Carregamento simulado' : 'Em descarga simulada'}
                  </div>
                  <div className="text-xs" style={{ color: 'var(--nura-text-muted)' }}>
                    Referência Nubia Z17 Lite · 3200 mAh Li-Ion (dados demonstrativos)
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => updateSettings({ batteryCharging: !settings.batteryCharging })}
                className="h-[38px] px-3.5 rounded-xl text-xs font-medium shrink-0"
                style={{ border: '1px solid var(--nura-border)' }}
              >
                {settings.batteryCharging ? 'Simular bateria' : 'Simular carregador'}
              </button>
            </div>

            <div className="space-y-2">
              <div className="text-xs font-medium" style={{ color: 'var(--nura-text-muted)' }}>
                Perfil de desempenho (afeta o painel NURA Performance)
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {(
                  [
                    { id: 'powersave', label: 'Economia', desc: 'Menor frequência simulada' },
                    { id: 'balanced', label: 'Equilibrado', desc: 'Uso desktop padrão' },
                    { id: 'performance', label: 'Desempenho', desc: 'Carga máxima demonstrativa' },
                  ] as { id: PowerProfile; label: string; desc: string }[]
                ).map((p) => {
                  const active = settings.powerProfile === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => updateSettings({ powerProfile: p.id })}
                      className="p-3 rounded-xl text-left transition-colors"
                      style={{
                        backgroundColor: active
                          ? 'var(--nura-surface-elevated)'
                          : 'var(--nura-surface-subtle)',
                        border: `1px solid ${active ? 'var(--nura-accent)' : 'var(--nura-border)'}`,
                      }}
                    >
                      <div className="text-xs font-semibold">{p.label}</div>
                      <div className="text-[11px] mt-0.5" style={{ color: 'var(--nura-text-muted)' }}>
                        {p.desc}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>
        )}

        {activeTab === 'system' && (
          <section className="space-y-4">
            <div className="flex items-center gap-2">
              <Info size={18} style={{ color: 'var(--nura-accent)' }} />
              <h3 className="font-display text-base font-semibold">Informações do Sistema</h3>
            </div>

            <dl
              className="rounded-xl divide-y text-xs"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
                borderColor: 'var(--nura-border)',
              }}
            >
              {[
                ['Sistema Operacional', 'NURA OS Desktop · Protótipo Web 0.4'],
                ['Base Planejada', 'Alpine Linux / postmarketOS'],
                ['Dispositivo Alvo Inicial', 'ZTE Nubia Z17 Lite (nx591j) — referência'],
                ['Resolução de Referência', '1920 × 1080 (Horizontal Desktop)'],
                ['Execução Atual', 'Navegador Web (Sem acesso a kernel, bootloader ou partições)'],
              ].map(([label, value]) => (
                <div key={label} className="px-4 py-3 flex flex-wrap justify-between gap-2">
                  <dt style={{ color: 'var(--nura-text-muted)' }}>{label}</dt>
                  <dd className="font-medium text-right">{value}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}
      </div>
    </div>
  );
}
