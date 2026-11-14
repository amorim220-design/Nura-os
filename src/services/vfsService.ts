import { VfsNode } from '../types/os';

const STORAGE_KEY = 'nura_os_vfs_v1';

export const INITIAL_VFS_NODES: VfsNode[] = [
  {
    id: 'root',
    name: '/',
    type: 'folder',
    parentId: null,
    sizeBytes: 0,
    modifiedAt: '2026-11-14 08:00',
    readonly: true,
  },
  {
    id: 'home',
    name: 'home',
    type: 'folder',
    parentId: 'root',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 08:00',
    readonly: true,
  },
  {
    id: 'etc',
    name: 'etc',
    type: 'folder',
    parentId: 'root',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 08:00',
    readonly: true,
  },
  {
    id: 'etc-nura',
    name: 'nura',
    type: 'folder',
    parentId: 'etc',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 08:00',
    readonly: true,
  },
  {
    id: 'etc-os-release',
    name: 'os-release',
    type: 'file',
    parentId: 'etc',
    sizeBytes: 312,
    modifiedAt: '2026-11-14 08:00',
    mimeType: 'text/plain',
    readonly: true,
    content: `NAME="NURA OS Desktop (Protótipo Web)"
ID=nura
ID_LIKE="postmarketos alpine"
VERSION_ID="0.4-proto"
PRETTY_NAME="NURA OS 0.4 Desktop Prototype"
TARGET_DEVICE="ZTE Nubia Z17 Lite (nx591j)"
NOTE="Ambiente virtual demonstrativo no navegador"`,
  },
  {
    id: 'etc-nura-conf',
    name: 'desktop.conf',
    type: 'file',
    parentId: 'etc-nura',
    sizeBytes: 428,
    modifiedAt: '2026-11-14 08:12',
    mimeType: 'text/plain',
    content: `[compositor]
shell = nura-desktop-shell
orientation = landscape-primary
touch_gestures = enabled
virtual_keyboard = on-demand

[theme]
default = neon-blue
radius = 12px`,
  },
  {
    id: 'user-home',
    name: 'nura',
    type: 'folder',
    parentId: 'home',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 08:30',
  },
  {
    id: 'docs',
    name: 'Documentos',
    type: 'folder',
    parentId: 'user-home',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 09:10',
  },
  {
    id: 'downloads',
    name: 'Downloads',
    type: 'folder',
    parentId: 'user-home',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 09:15',
  },
  {
    id: 'images',
    name: 'Imagens',
    type: 'folder',
    parentId: 'user-home',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 09:20',
  },
  {
    id: 'games-dir',
    name: 'Jogos',
    type: 'folder',
    parentId: 'user-home',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 09:25',
  },
  {
    id: 'sys-dir',
    name: 'Sistema',
    type: 'folder',
    parentId: 'user-home',
    sizeBytes: 0,
    modifiedAt: '2026-11-14 09:30',
  },
  {
    id: 'readme-txt',
    name: 'bem-vindo-nura.txt',
    type: 'file',
    parentId: 'docs',
    sizeBytes: 640,
    modifiedAt: '2026-11-14 09:11',
    mimeType: 'text/plain',
    content: `NURA OS Desktop — Notas de Protótipo

Este é um sistema de arquivos virtual armazenado apenas na memória local do navegador.
Nenhum arquivo real do seu dispositivo é acessado ou modificado.

Base de referência planejada:
- Distribuição: Alpine Linux / postmarketOS
- Dispositivo alvo inicial: Nubia Z17 Lite (Snapdragon 653 / 4GB RAM)
- Experiência: Desktop horizontal com suporte completo a toque e mouse.`,
  },
  {
    id: 'roadmap-md',
    name: 'arquitetura-linux.md',
    type: 'file',
    parentId: 'docs',
    sizeBytes: 910,
    modifiedAt: '2026-11-14 09:14',
    mimeType: 'text/markdown',
    content: `# Arquitetura NURA OS (Referência de Desenvolvimento)

1. Camada Base: Kernel mainline / postmarketOS + Alpine musl
2. Sessão Gráfica: Compositor Wayland adaptado para toque horizontal
3. Telemetria: Leitura futura via /proc/stat, /proc/meminfo e /sys/class/thermal
4. Aplicações Nativas: Explorer, Terminal, Game Hub, Control Center`,
  },
  {
    id: 'apk-list',
    name: 'pacotes-postmarketos.txt',
    type: 'file',
    parentId: 'downloads',
    sizeBytes: 384,
    modifiedAt: '2026-11-14 09:18',
    mimeType: 'text/plain',
    content: `alpine-base
postmarketos-base
mesa-dri-gallium
pipewire
bluez
networkmanager
wayland-protocols`,
  },
  {
    id: 'wallpaper-ref',
    name: 'nura-neon-blue-4k.jpg',
    type: 'file',
    parentId: 'images',
    sizeBytes: 2480000,
    modifiedAt: '2026-11-14 09:22',
    mimeType: 'image/jpeg',
    content: 'Papel de parede oficial NURA Neon Blue (ativo na área de trabalho).',
  },
  {
    id: 'gamepad-profile',
    name: 'controle-nubia-hid.json',
    type: 'file',
    parentId: 'games-dir',
    sizeBytes: 512,
    modifiedAt: '2026-11-14 09:26',
    mimeType: 'application/json',
    content: `{
  "profile": "NURA Pad Standard",
  "deadzone": 0.12,
  "mapping": "xinput-compatible-demo"
}`,
  },
  {
    id: 'sys-hw',
    name: 'hw-nubia-z17-lite.info',
    type: 'file',
    parentId: 'sys-dir',
    sizeBytes: 495,
    modifiedAt: '2026-11-14 09:32',
    mimeType: 'text/plain',
    content: `Dispositivo de Referência: ZTE Nubia Z17 Lite (NX591J)
SoC: Qualcomm Snapdragon 653 (MSM8976 Pro)
CPU: 4x Cortex-A72 + 4x Cortex-A53
GPU: Adreno 510
Memória: 4 GB LPDDR4 (simulado neste protótipo)
Tela: 5.5" 1920x1080 IPS (modo desktop horizontal)`,
  },
];

export function loadVfs(): VfsNode[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return INITIAL_VFS_NODES;
    const parsed = JSON.parse(raw) as VfsNode[];
    if (Array.isArray(parsed) && parsed.some((n) => n.id === 'user-home')) {
      return parsed;
    }
  } catch {
    // Fallback to initial tree
  }
  return INITIAL_VFS_NODES;
}

export function saveVfs(nodes: VfsNode[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nodes));
  } catch {
    // Ignore storage quota errors
  }
}

export function getNodePath(nodes: VfsNode[], folderId: string): string {
  const map = new Map(nodes.map((n) => [n.id, n]));
  const parts: string[] = [];
  let current = map.get(folderId);
  while (current && current.parentId !== null) {
    parts.unshift(current.name);
    current = map.get(current.parentId);
  }
  return '/' + parts.join('/');
}

export function getBreadcrumbs(nodes: VfsNode[], folderId: string): VfsNode[] {
  const map = new Map(nodes.map((n) => [n.id, n]));
  const chain: VfsNode[] = [];
  let current = map.get(folderId);
  while (current) {
    chain.unshift(current);
    current = current.parentId ? map.get(current.parentId) : undefined;
  }
  return chain;
}

export function resolvePathToNodeId(
  nodes: VfsNode[],
  currentFolderId: string,
  targetPath: string
): string | null {
  const trimmed = targetPath.trim();
  if (!trimmed || trimmed === '.') return currentFolderId;
  if (trimmed === '~') return 'user-home';

  let pointerId = trimmed.startsWith('/') ? 'root' : currentFolderId;
  const segments = trimmed.split('/').filter(Boolean);

  for (const seg of segments) {
    if (seg === '.') continue;
    if (seg === '..') {
      const curr = nodes.find((n) => n.id === pointerId);
      if (curr && curr.parentId) {
        pointerId = curr.parentId;
      }
      continue;
    }
    if (seg === '~' && pointerId === currentFolderId) {
      pointerId = 'user-home';
      continue;
    }
    const child = nodes.find((n) => n.parentId === pointerId && n.name === seg);
    if (!child) return null;
    pointerId = child.id;
  }

  return pointerId;
}

export function collectSubtreeIds(nodes: VfsNode[], rootId: string): string[] {
  const result = [rootId];
  const children = nodes.filter((n) => n.parentId === rootId);
  for (const child of children) {
    result.push(...collectSubtreeIds(nodes, child.id));
  }
  return result;
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
