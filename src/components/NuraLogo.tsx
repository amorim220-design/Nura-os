import { useId } from 'react';

interface NuraLogoProps {
  size?: number;
  withWordmark?: boolean;
  className?: string;
}

interface NuraWordmarkProps {
  height?: number;
  showOs?: boolean;
  className?: string;
}

interface NuraCenterpieceProps {
  scale?: number;
  showWordmark?: boolean;
  wordmarkReveal?: number; // 0 to 1 for progressive left-to-right boot reveal
  ringReveal?: number; // 0 to 1 for triangle + orbital ring ignition
  isLight?: boolean;
}

/**
 * Wordmark vetorial fiel à tipografia geométrica arredondada Varino (Arterfak Project):
 * "NURA" em branco nítido com "A" sem travessa + ponto central, e "OS" em ciano brilhante.
 */
export function NuraWordmark({
  height = 24,
  showOs = true,
  className = '',
}: NuraWordmarkProps) {
  const uid = useId().replace(/:/g, '');
  const viewBoxWidth = showOs ? 520 : 334;
  const computedWidth = Math.round((height * viewBoxWidth) / 64);

  return (
    <svg
      width={computedWidth}
      height={height}
      viewBox={`0 0 ${viewBoxWidth} 64`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={showOs ? 'NURA OS' : 'NURA'}
      className={`shrink-0 select-none ${className}`}
      style={{ filter: 'drop-shadow(0 0 12px var(--nura-glow))' }}
    >
      <defs>
        <linearGradient
          id={`osGrad-${uid}`}
          x1="350"
          y1="10"
          x2="510"
          y2="54"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="var(--nura-accent)" />
          <stop offset="100%" stopColor="#38bdf8" />
        </linearGradient>
      </defs>

      {/* NURA */}
      <g
        stroke="var(--nura-text)"
        strokeWidth="8.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M 12 53 L 12 16 C 12 10 17 9 21 13 L 55 51 C 59 55 64 54 64 48 L 64 11" />
        <path d="M 88 11 L 88 34 C 88 47 98 53 117 53 C 136 53 146 47 146 34 L 146 11" />
        <path d="M 170 53 L 170 19 C 170 13 174 11 181 11 L 205 11 C 219 11 227 16 227 23 C 227 30 219 35 205 35 L 186 35" />
        <path d="M 204 35 L 220 50 C 223 53 226 53 230 53" />
        <path d="M 250 53 L 274 16 C 279 9 291 9 296 16 L 320 53" />
      </g>

      {/* Signature center dot inside Varino "A" */}
      <circle cx="285" cy="42" r="6.3" fill="var(--nura-text)" />

      {/* OS */}
      {showOs && (
        <g
          stroke={`url(#osGrad-${uid})`}
          strokeWidth="8.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M 380 11 L 400 11 C 416 11 426 19 426 32 C 426 45 416 53 400 53 L 380 53 C 364 53 354 45 354 32 C 354 19 364 11 380 11 Z" />
          <path d="M 502 14 C 497 11 490 11 480 11 L 468 11 C 455 11 448 15 448 21 C 448 28 455 31 468 32 L 486 33 C 499 34 506 38 506 44 C 506 50 498 53 484 53 L 466 53 C 456 53 450 51 446 48" />
        </g>
      )}
    </svg>
  );
}

/**
 * Emblema compacto NURA OS (triângulo luminoso dentro de anel orbital) para Barra de Tarefas e NURA Start.
 */
export function NuraLogo({ size = 28, withWordmark = false, className = '' }: NuraLogoProps) {
  const uid = useId().replace(/:/g, '');

  return (
    <div className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0"
        style={{ filter: 'drop-shadow(0 0 8px var(--nura-glow))' }}
      >
        <defs>
          <linearGradient id={`tri-${uid}`} x1="10" y1="8" x2="54" y2="56" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="var(--nura-accent)" />
            <stop offset="100%" stopColor="var(--nura-accent-strong)" />
          </linearGradient>
        </defs>
        <circle
          cx="32"
          cy="32"
          r="27"
          stroke={`url(#tri-${uid})`}
          strokeWidth="2.4"
          strokeDasharray="62 10 24 10"
          fill="var(--nura-surface-elevated)"
        />
        <circle
          cx="32"
          cy="32"
          r="22"
          stroke="var(--nura-accent)"
          strokeOpacity="0.35"
          strokeWidth="1.2"
        />
        <path
          d="M32 16L47 43H17L32 16Z"
          stroke="var(--nura-accent)"
          strokeWidth="3.2"
          strokeLinejoin="round"
        />
        <circle cx="5.5" cy="32" r="2.2" fill="var(--nura-accent)" />
        <circle cx="58.5" cy="32" r="2.2" fill="var(--nura-accent)" />
      </svg>
      {withWordmark && <NuraWordmark height={Math.max(16, Math.round(size * 0.66))} />}
    </div>
  );
}

const PARTICLE_MOTES = [
  { x: 110, y: 120, r: 1.5, o: 0.55 },
  { x: 165, y: 88, r: 1.1, o: 0.45 },
  { x: 240, y: 112, r: 1.8, o: 0.6 },
  { x: 295, y: 150, r: 1.2, o: 0.4 },
  { x: 145, y: 245, r: 1.6, o: 0.5 },
  { x: 255, y: 265, r: 1.3, o: 0.55 },
  { x: 192, y: 185, r: 1.4, o: 0.45 },
  { x: 222, y: 210, r: 1.9, o: 0.65 },
  { x: 170, y: 295, r: 1.2, o: 0.45 },
  { x: 268, y: 92, r: 1.5, o: 0.5 },
];

/**
 * Emblema central oficial no estilo do vídeo de inicialização:
 * Triângulo ciano brilhante + dois anéis orbitais concêntricos segmentados com nós de luz +
 * faixa horizontal de vidro escuro com wordmark Varino "NURA OS".
 */
export function NuraCenterpiece({
  scale = 1,
  showWordmark = true,
  wordmarkReveal = 1,
  ringReveal = 1,
  isLight = false,
}: NuraCenterpieceProps) {
  const uid = useId().replace(/:/g, '');
  const sizePx = Math.round(380 * scale);
  const clipRightPct = Math.max(0, Math.min(100, (1 - wordmarkReveal) * 100));

  return (
    <div
      className="relative flex items-center justify-center select-none"
      style={{ width: sizePx, height: sizePx }}
    >
      {/* Ambient Radial Aura */}
      <div
        className="absolute inset-4 rounded-full pointer-events-none transition-opacity duration-500"
        style={{
          opacity: ringReveal,
          background: isLight
            ? 'radial-gradient(circle, rgba(2, 132, 199, 0.16) 0%, transparent 66%)'
            : 'radial-gradient(circle, rgba(6, 182, 212, 0.22) 0%, rgba(37, 99, 235, 0.09) 42%, transparent 72%)',
        }}
      />

      {/* Concentric Segmented Rings + Luminous Cyan Triangle */}
      <svg
        viewBox="0 0 380 380"
        className="w-full h-full overflow-visible transition-all duration-500"
        style={{
          opacity: ringReveal,
          transform: `scale(${0.86 + ringReveal * 0.14})`,
        }}
        fill="none"
      >
        <defs>
          <filter id={`cyanGlow-${uid}`} x="-35%" y="-35%" width="170%" height="170%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id={`ringGrad-${uid}`} x1="30" y1="30" x2="350" y2="350" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="var(--nura-accent)" />
            <stop offset="50%" stopColor="#38bdf8" />
            <stop offset="100%" stopColor="var(--nura-accent-strong)" />
          </linearGradient>
        </defs>

        {/* Subtle Particle Motes inside ring */}
        <g>
          {PARTICLE_MOTES.map((m, i) => (
            <circle
              key={i}
              cx={m.x}
              cy={m.y}
              r={m.r}
              fill="#38bdf8"
              fillOpacity={m.o * ringReveal}
            />
          ))}
        </g>

        {/* Outer Segmented Orbital Ring */}
        <g className="nura-orbit-slow">
          <circle
            cx="190"
            cy="190"
            r="168"
            stroke={`url(#ringGrad-${uid})`}
            strokeWidth="2.2"
            strokeDasharray="195 36 110 28 85 30"
            strokeLinecap="round"
            filter={`url(#cyanGlow-${uid})`}
          />
          {/* Left & Right Glowing Cyan Orbital Nodes */}
          <circle
            cx="22"
            cy="190"
            r="4.5"
            fill="#67e8f9"
            filter={`url(#cyanGlow-${uid})`}
          />
          <circle
            cx="358"
            cy="190"
            r="4.5"
            fill="#67e8f9"
            filter={`url(#cyanGlow-${uid})`}
          />
        </g>

        {/* Inner Segmented Orbital Ring */}
        <g className="nura-orbit-reverse">
          <circle
            cx="190"
            cy="190"
            r="138"
            stroke="var(--nura-accent)"
            strokeOpacity="0.65"
            strokeWidth="1.5"
            strokeDasharray="160 44 92 38"
            strokeLinecap="round"
          />
        </g>

        {/* Center Glowing Cyan Equilateral Triangle */}
        <path
          d="M 190 92 L 279 246 L 101 246 Z"
          stroke="var(--nura-accent)"
          strokeWidth="3.4"
          strokeLinejoin="round"
          fill={isLight ? 'rgba(255,255,255,0.22)' : 'rgba(6, 182, 212, 0.04)'}
          filter={`url(#cyanGlow-${uid})`}
        />
      </svg>

      {/* Dark Glass Horizontal Band + Varino "NURA OS" Wordmark */}
      {showWordmark && (
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center px-6 py-3 rounded-xl backdrop-blur-md transition-opacity duration-300"
          style={{
            width: Math.round(338 * scale),
            background: isLight
              ? 'linear-gradient(90deg, rgba(255,255,255,0.2), rgba(255,255,255,0.82) 20%, rgba(255,255,255,0.82) 80%, rgba(255,255,255,0.2))'
              : 'linear-gradient(90deg, rgba(2,5,11,0.18), rgba(4,10,22,0.82) 18%, rgba(4,10,22,0.82) 82%, rgba(2,5,11,0.18))',
            borderTop: '1px solid rgba(56, 189, 248, 0.24)',
            borderBottom: '1px solid rgba(56, 189, 248, 0.24)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45)',
            opacity: wordmarkReveal > 0.02 ? 1 : 0,
          }}
        >
          <div
            className="flex items-center justify-center"
            style={{
              clipPath: `inset(0 ${clipRightPct}% 0 0)`,
            }}
          >
            <NuraWordmark height={Math.round(36 * scale)} />
          </div>
        </div>
      )}
    </div>
  );
}
