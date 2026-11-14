import { Gamepad2, Heart, Search, Sliders, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { GameCategory, GameItem, GamepadMapping } from '../types/os';

const INITIAL_GAMES: GameItem[] = [
  {
    id: 'alpine-velocity',
    title: 'Alpine Velocity',
    category: 'Corrida',
    developer: 'NURA Interactive Showcase',
    releaseYear: 2026,
    coverImage: '/src/assets/images/game_cover_velocity_1794651525012.jpg',
    description:
      'Corrida futurista em circuitos de basalto pensada para demonstrar perfis de desempenho GPU e resposta de gatilhos analógicos no catálogo NURA Game Hub.',
    engineTarget: 'OpenGL ES 3.2 / Vulkan (Referência Linux ARM64)',
    storageRequired: '1.4 GB',
    controllerSupport: 'Gamepad HID completo + Toque',
    demoDisclaimer:
      'Entrada visual demonstrativa. Este protótipo web não executa jogos Windows, Android ou de consoles.',
    favorite: true,
  },
  {
    id: 'orbital-vector',
    title: 'Orbital Vector',
    category: 'Estratégia',
    developer: 'Kestrel Horizon Lab',
    releaseYear: 2025,
    coverImage: '/src/assets/images/game_cover_orbital_1794651525939.jpg',
    description:
      'Estratégia tática em órbita planetária com planejamento de trajetórias e interface otimizada para telas horizontais de alta densidade.',
    engineTarget: 'Godot 4 Forward+ (Alvo Linux nativo)',
    storageRequired: '860 MB',
    controllerSupport: 'Mouse, Toque ou Gamepad',
    demoDisclaimer:
      'Entrada visual demonstrativa. Este protótipo web não executa jogos Windows, Android ou de consoles.',
    favorite: false,
  },
  {
    id: 'chrono-fracture',
    title: 'Chrono Fracture',
    category: 'Ação RPG',
    developer: 'Obsidian Spire Studio',
    releaseYear: 2026,
    coverImage: '/src/assets/images/game_cover_fracture_1794651526324.jpg',
    description:
      'Aventura isométrica em ruínas monolíticas com iluminação em cobalto, explorando mapeamento de botões ABXY e pré-visualização de controles.',
    engineTarget: 'SDL2 / Mesa Freedreno (Referência Adreno)',
    storageRequired: '2.1 GB',
    controllerSupport: 'Gamepad HID padrão',
    demoDisclaimer:
      'Entrada visual demonstrativa. Este protótipo web não executa jogos Windows, Android ou de consoles.',
    favorite: true,
  },
  {
    id: 'prism-relay',
    title: 'Prism Relay',
    category: 'Puzzle',
    developer: 'Monolith Works',
    releaseYear: 2025,
    coverImage: '/src/assets/images/game_cover_prism_1794651525844.jpg',
    description:
      'Quebra-cabeça arquitetônico com refração de feixes ciano em câmaras geométricas minimalistas, ideal para sessões rápidas por toque.',
    engineTarget: 'WebGL / Wayland Native Shell',
    storageRequired: '420 MB',
    controllerSupport: 'Toque direto e direcional',
    demoDisclaimer:
      'Entrada visual demonstrativa. Este protótipo web não executa jogos Windows, Android ou de consoles.',
    favorite: false,
  },
];

const CATEGORIES: (GameCategory | 'Favoritos')[] = [
  'Todos',
  'Favoritos',
  'Corrida',
  'Estratégia',
  'Ação RPG',
  'Puzzle',
];

const DEFAULT_MAPPING: GamepadMapping = {
  a: 'Confirmar / Acelerar',
  b: 'Voltar / Frear',
  x: 'Ação Secundária',
  y: 'Menu Rápido',
  l1: 'Câmera / Marcha -',
  r1: 'Boost / Marcha +',
  start: 'Pausa',
  select: 'Mapa / Visão',
  deadzone: 12,
};

export function GameHubApp() {
  const [games, setGames] = useState<GameItem[]>(INITIAL_GAMES);
  const [activeView, setActiveView] = useState<'library' | 'controller'>('library');
  const [category, setCategory] = useState<GameCategory | 'Favoritos'>('Todos');
  const [search, setSearch] = useState('');
  const [selectedGame, setSelectedGame] = useState<GameItem | null>(null);
  const [mapping, setMapping] = useState<GamepadMapping>(DEFAULT_MAPPING);
  const [pressedControl, setPressedControl] = useState<string | null>(null);
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});

  const filteredGames = useMemo(() => {
    const q = search.trim().toLowerCase();
    return games.filter((g) => {
      if (category === 'Favoritos' && !g.favorite) return false;
      if (category !== 'Todos' && category !== 'Favoritos' && g.category !== category) {
        return false;
      }
      if (!q) return true;
      return (
        g.title.toLowerCase().includes(q) ||
        g.category.toLowerCase().includes(q) ||
        g.developer.toLowerCase().includes(q)
      );
    });
  }, [games, category, search]);

  const toggleFavorite = (id: string) => {
    setGames((prev) =>
      prev.map((g) => (g.id === id ? { ...g, favorite: !g.favorite } : g))
    );
    setSelectedGame((prev) =>
      prev && prev.id === id ? { ...prev, favorite: !prev.favorite } : prev
    );
  };

  return (
    <div className="h-full flex flex-col text-sm relative">
      {/* Top Bar */}
      <div
        className="px-4 py-2.5 border-b flex flex-wrap items-center justify-between gap-3 shrink-0"
        style={{ borderColor: 'var(--nura-border)' }}
      >
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setActiveView('library')}
            className="h-[36px] px-3.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors whitespace-nowrap shrink-0"
            style={{
              backgroundColor:
                activeView === 'library'
                  ? 'var(--nura-accent)'
                  : 'var(--nura-surface-subtle)',
              color:
                activeView === 'library'
                  ? 'var(--nura-accent-contrast)'
                  : 'var(--nura-text)',
              border: '1px solid var(--nura-border)',
            }}
          >
            <Gamepad2 size={15} />
            <span>Biblioteca</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveView('controller')}
            className="h-[36px] px-3.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors whitespace-nowrap shrink-0"
            style={{
              backgroundColor:
                activeView === 'controller'
                  ? 'var(--nura-accent)'
                  : 'var(--nura-surface-subtle)',
              color:
                activeView === 'controller'
                  ? 'var(--nura-accent-contrast)'
                  : 'var(--nura-text)',
              border: '1px solid var(--nura-border)',
            }}
          >
            <Sliders size={15} />
            <span>Configuração de Controle</span>
          </button>
        </div>

        {activeView === 'library' && (
          <label className="relative flex items-center w-full sm:w-[230px]">
            <Search
              size={14}
              className="absolute left-3 pointer-events-none"
              style={{ color: 'var(--nura-text-muted)' }}
            />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar no catálogo..."
              className="w-full h-[36px] pl-8 pr-3 rounded-xl text-xs outline-none"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
                color: 'var(--nura-text)',
              }}
            />
          </label>
        )}
      </div>

      {/* Main Content */}
      <div
        className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 nura-scroll"
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
          Catálogo demonstrativo do NURA Game Hub. Este protótipo web exibe capas, ficha técnica e
          configuração visual de controle — não executa jogos Windows, Android ou de consoles.
        </div>

        {activeView === 'library' ? (
          <>
            {/* Category Filter Bar */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 nura-scroll">
              {CATEGORIES.map((cat) => {
                const active = category === cat;
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setCategory(cat)}
                    className="h-[34px] px-3 rounded-lg text-xs font-medium transition-colors whitespace-nowrap shrink-0"
                    style={{
                      backgroundColor: active
                        ? 'var(--nura-surface-elevated)'
                        : 'transparent',
                      border: active
                        ? '1px solid var(--nura-border-strong)'
                        : '1px solid var(--nura-border)',
                      color: active ? 'var(--nura-accent)' : 'var(--nura-text-muted)',
                    }}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>

            {/* Game Cards Grid */}
            {filteredGames.length === 0 ? (
              <div className="py-12 text-center text-xs" style={{ color: 'var(--nura-text-muted)' }}>
                Nenhum título encontrado para os filtros atuais.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
                {filteredGames.map((game) => (
                  <article
                    key={game.id}
                    className="rounded-2xl overflow-hidden flex flex-col transition-transform hover:translate-y-[-2px]"
                    style={{
                      backgroundColor: 'var(--nura-surface-subtle)',
                      border: '1px solid var(--nura-border)',
                    }}
                  >
                    <div className="relative aspect-[4/3] w-full overflow-hidden bg-slate-950">
                      {!failedImages[game.id] ? (
                        <img
                          src={game.coverImage}
                          alt={`Capa ilustrativa de ${game.title}`}
                          referrerPolicy="no-referrer"
                          onError={() =>
                            setFailedImages((prev) => ({ ...prev, [game.id]: true }))
                          }
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-slate-900 to-slate-950">
                          <Gamepad2 size={32} style={{ color: 'var(--nura-accent)' }} />
                          <span className="text-xs font-medium">{game.title}</span>
                        </div>
                      )}
                      <button
                        type="button"
                        onClick={() => toggleFavorite(game.id)}
                        className="absolute top-2.5 right-2.5 min-w-[38px] min-h-[38px] rounded-xl flex items-center justify-center backdrop-blur-md transition-colors"
                        style={{
                          backgroundColor: 'rgba(3, 6, 12, 0.72)',
                          border: '1px solid rgba(255,255,255,0.16)',
                        }}
                        aria-label={
                          game.favorite
                            ? `Remover ${game.title} dos favoritos`
                            : `Adicionar ${game.title} aos favoritos`
                        }
                      >
                        <Heart
                          size={16}
                          className={game.favorite ? 'fill-rose-500 text-rose-500' : 'text-slate-200'}
                        />
                      </button>
                    </div>

                    <div className="p-4 flex-1 flex flex-col justify-between gap-3">
                      <div>
                        <h3 className="font-display text-base font-semibold">{game.title}</h3>
                        <div
                          className="text-xs mt-1 flex flex-wrap items-center gap-1.5"
                          style={{ color: 'var(--nura-text-muted)' }}
                        >
                          <span>{game.category}</span>
                          <span aria-hidden="true">·</span>
                          <span className="tabular-nums">{game.releaseYear}</span>
                          <span aria-hidden="true">·</span>
                          <span className="tabular-nums">{game.storageRequired}</span>
                        </div>
                        <p
                          className="text-xs mt-2 leading-relaxed line-clamp-2"
                          style={{ color: 'var(--nura-text-muted)' }}
                        >
                          {game.description}
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={() => setSelectedGame(game)}
                        className="h-[38px] px-4 rounded-xl text-xs font-semibold transition-colors w-full"
                        style={{
                          backgroundColor: 'var(--nura-surface-elevated)',
                          border: '1px solid var(--nura-border-strong)',
                          color: 'var(--nura-text)',
                        }}
                      >
                        Ver detalhes do título
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        ) : (
          /* Visual Controller Configuration */
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="font-display text-base font-semibold">
                  Configuração Visual de Controle
                </h3>
                <p className="text-xs mt-0.5" style={{ color: 'var(--nura-text-muted)' }}>
                  Toque ou clique nos botões virtuais abaixo para testar o mapeamento visual (simulação).
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMapping(DEFAULT_MAPPING)}
                className="h-[36px] px-3 rounded-xl text-xs font-medium hover:bg-white/10"
                style={{ border: '1px solid var(--nura-border)' }}
              >
                Restaurar padrão
              </button>
            </div>

            {/* Interactive SVG / Button Gamepad Schematic */}
            <div
              className="p-5 rounded-2xl flex flex-col items-center gap-5"
              style={{
                backgroundColor: 'var(--nura-surface-subtle)',
                border: '1px solid var(--nura-border)',
              }}
            >
              <div className="w-full max-w-[520px] flex items-center justify-between gap-4">
                <button
                  type="button"
                  onClick={() => setPressedControl(`L1 — ${mapping.l1}`)}
                  className="h-[36px] px-5 rounded-xl text-xs font-mono font-semibold active:scale-95 transition-transform"
                  style={{
                    backgroundColor: 'var(--nura-surface-elevated)',
                    border: '1px solid var(--nura-border-strong)',
                  }}
                >
                  L1
                </button>
                <span className="text-xs font-mono" style={{ color: 'var(--nura-accent)' }}>
                  {pressedControl ?? 'Aguardando toque no controle...'}
                </span>
                <button
                  type="button"
                  onClick={() => setPressedControl(`R1 — ${mapping.r1}`)}
                  className="h-[36px] px-5 rounded-xl text-xs font-mono font-semibold active:scale-95 transition-transform"
                  style={{
                    backgroundColor: 'var(--nura-surface-elevated)',
                    border: '1px solid var(--nura-border-strong)',
                  }}
                >
                  R1
                </button>
              </div>

              <div className="w-full max-w-[520px] grid grid-cols-3 items-center gap-4">
                {/* D-Pad */}
                <div className="grid grid-cols-3 gap-1 w-[114px] mx-auto">
                  <span />
                  <button
                    type="button"
                    onClick={() => setPressedControl('D-Pad Cima')}
                    className="h-[36px] rounded-lg text-xs font-semibold active:scale-95"
                    style={{
                      backgroundColor: 'var(--nura-surface-elevated)',
                      border: '1px solid var(--nura-border)',
                    }}
                  >
                    ▲
                  </button>
                  <span />
                  <button
                    type="button"
                    onClick={() => setPressedControl('D-Pad Esquerda')}
                    className="h-[36px] rounded-lg text-xs font-semibold active:scale-95"
                    style={{
                      backgroundColor: 'var(--nura-surface-elevated)',
                      border: '1px solid var(--nura-border)',
                    }}
                  >
                    ◀
                  </button>
                  <span
                    className="h-[36px] rounded-lg"
                    style={{ backgroundColor: 'var(--nura-surface)' }}
                  />
                  <button
                    type="button"
                    onClick={() => setPressedControl('D-Pad Direita')}
                    className="h-[36px] rounded-lg text-xs font-semibold active:scale-95"
                    style={{
                      backgroundColor: 'var(--nura-surface-elevated)',
                      border: '1px solid var(--nura-border)',
                    }}
                  >
                    ▶
                  </button>
                  <span />
                  <button
                    type="button"
                    onClick={() => setPressedControl('D-Pad Baixo')}
                    className="h-[36px] rounded-lg text-xs font-semibold active:scale-95"
                    style={{
                      backgroundColor: 'var(--nura-surface-elevated)',
                      border: '1px solid var(--nura-border)',
                    }}
                  >
                    ▼
                  </button>
                  <span />
                </div>

                {/* Center Select / Start */}
                <div className="flex items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPressedControl(`Select — ${mapping.select}`)}
                    className="h-[32px] px-2.5 rounded-lg text-[11px] font-medium"
                    style={{ border: '1px solid var(--nura-border)' }}
                  >
                    Select
                  </button>
                  <button
                    type="button"
                    onClick={() => setPressedControl(`Start — ${mapping.start}`)}
                    className="h-[32px] px-2.5 rounded-lg text-[11px] font-medium"
                    style={{ border: '1px solid var(--nura-border)' }}
                  >
                    Start
                  </button>
                </div>

                {/* ABXY */}
                <div className="grid grid-cols-3 gap-1 w-[114px] mx-auto">
                  <span />
                  <button
                    type="button"
                    onClick={() => setPressedControl(`Y — ${mapping.y}`)}
                    className="h-[36px] rounded-full text-xs font-bold active:scale-95"
                    style={{
                      backgroundColor: 'rgba(234, 179, 8, 0.16)',
                      border: '1px solid rgba(234, 179, 8, 0.45)',
                      color: '#facc15',
                    }}
                  >
                    Y
                  </button>
                  <span />
                  <button
                    type="button"
                    onClick={() => setPressedControl(`X — ${mapping.x}`)}
                    className="h-[36px] rounded-full text-xs font-bold active:scale-95"
                    style={{
                      backgroundColor: 'rgba(59, 130, 246, 0.16)',
                      border: '1px solid rgba(59, 130, 246, 0.45)',
                      color: '#60a5fa',
                    }}
                  >
                    X
                  </button>
                  <span />
                  <button
                    type="button"
                    onClick={() => setPressedControl(`B — ${mapping.b}`)}
                    className="h-[36px] rounded-full text-xs font-bold active:scale-95"
                    style={{
                      backgroundColor: 'rgba(244, 63, 94, 0.16)',
                      border: '1px solid rgba(244, 63, 94, 0.45)',
                      color: '#fb7185',
                    }}
                  >
                    B
                  </button>
                  <span />
                  <button
                    type="button"
                    onClick={() => setPressedControl(`A — ${mapping.a}`)}
                    className="h-[36px] rounded-full text-xs font-bold active:scale-95"
                    style={{
                      backgroundColor: 'rgba(16, 185, 129, 0.16)',
                      border: '1px solid rgba(16, 185, 129, 0.45)',
                      color: '#34d399',
                    }}
                  >
                    A
                  </button>
                  <span />
                </div>
              </div>

              {/* Deadzone control */}
              <div className="w-full max-w-[520px] pt-2 border-t flex items-center justify-between gap-4" style={{ borderColor: 'var(--nura-border)' }}>
                <span className="text-xs">Zona morta dos analógicos (simulada)</span>
                <div className="flex items-center gap-3 w-48">
                  <input
                    type="range"
                    min={4}
                    max={30}
                    value={mapping.deadzone}
                    onChange={(e) =>
                      setMapping((prev) => ({ ...prev, deadzone: Number(e.target.value) }))
                    }
                    className="flex-1 accent-cyan-400"
                  />
                  <span className="text-xs font-mono tabular-nums w-8 text-right">
                    {mapping.deadzone}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Game Details Window / Modal */}
      {selectedGame && (
        <div
          className="absolute inset-0 z-20 bg-black/65 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setSelectedGame(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-xl rounded-2xl overflow-hidden flex flex-col max-h-[92%]"
            style={{
              backgroundColor: 'var(--nura-surface-elevated)',
              border: '1px solid var(--nura-border-strong)',
              boxShadow: 'var(--nura-shadow)',
            }}
          >
            <div className="relative h-44 w-full bg-slate-950 shrink-0">
              <img
                src={selectedGame.coverImage}
                alt={`Capa de ${selectedGame.title}`}
                referrerPolicy="no-referrer"
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />
              <button
                type="button"
                onClick={() => setSelectedGame(null)}
                className="absolute top-3 right-3 min-w-[36px] min-h-[36px] rounded-xl flex items-center justify-center bg-black/60 text-white hover:bg-black/80"
                aria-label="Fechar detalhes"
              >
                <X size={16} />
              </button>
              <div className="absolute bottom-3 left-4 right-4">
                <h3 className="font-display text-xl font-bold text-white">
                  {selectedGame.title}
                </h3>
                <div className="text-xs text-slate-300 mt-0.5">
                  {selectedGame.developer} · {selectedGame.category} · {selectedGame.releaseYear}
                </div>
              </div>
            </div>

            <div className="p-4 overflow-y-auto space-y-3 nura-scroll text-xs">
              <p className="leading-relaxed text-sm">{selectedGame.description}</p>
              <dl
                className="rounded-xl divide-y"
                style={{
                  backgroundColor: 'var(--nura-surface-subtle)',
                  border: '1px solid var(--nura-border)',
                  borderColor: 'var(--nura-border)',
                }}
              >
                <div className="px-3 py-2 flex justify-between gap-2">
                  <dt style={{ color: 'var(--nura-text-muted)' }}>Alvo técnico planejado</dt>
                  <dd className="font-medium text-right">{selectedGame.engineTarget}</dd>
                </div>
                <div className="px-3 py-2 flex justify-between gap-2">
                  <dt style={{ color: 'var(--nura-text-muted)' }}>Espaço estimado</dt>
                  <dd className="font-medium tabular-nums">{selectedGame.storageRequired}</dd>
                </div>
                <div className="px-3 py-2 flex justify-between gap-2">
                  <dt style={{ color: 'var(--nura-text-muted)' }}>Controles</dt>
                  <dd className="font-medium text-right">{selectedGame.controllerSupport}</dd>
                </div>
              </dl>

              <p
                className="p-3 rounded-xl leading-relaxed"
                style={{
                  backgroundColor: 'var(--nura-surface-subtle)',
                  border: '1px solid var(--nura-border)',
                  color: 'var(--nura-text-muted)',
                }}
              >
                {selectedGame.demoDisclaimer}
              </p>

              <div className="flex items-center justify-between gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => toggleFavorite(selectedGame.id)}
                  className="h-[38px] px-4 rounded-xl text-xs font-medium flex items-center gap-2"
                  style={{ border: '1px solid var(--nura-border)' }}
                >
                  <Heart
                    size={14}
                    className={selectedGame.favorite ? 'fill-rose-500 text-rose-500' : ''}
                  />
                  <span>
                    {selectedGame.favorite ? 'Remover favorito' : 'Adicionar aos favoritos'}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedGame(null)}
                  className="h-[38px] px-4 rounded-xl text-xs font-semibold"
                  style={{
                    backgroundColor: 'var(--nura-accent)',
                    color: 'var(--nura-accent-contrast)',
                  }}
                >
                  Fechar ficha
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
