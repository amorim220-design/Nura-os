import {
  ArrowLeft,
  ChevronRight,
  ClipboardPaste,
  Copy,
  FileText,
  Folder,
  FolderPlus,
  HardDrive,
  LayoutGrid,
  List,
  Pencil,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import React, { useMemo, useState } from 'react';
import {
  collectSubtreeIds,
  formatBytes,
  getBreadcrumbs,
  getNodePath,
} from '../services/vfsService';
import { VfsNode } from '../types/os';

interface ExplorerAppProps {
  vfsNodes: VfsNode[];
  setVfsNodes: React.Dispatch<React.SetStateAction<VfsNode[]>>;
  onNotify: (title: string, message: string) => void;
}

const QUICK_PLACES = [
  { id: 'user-home', label: 'Pasta Pessoal' },
  { id: 'docs', label: 'Documentos' },
  { id: 'downloads', label: 'Downloads' },
  { id: 'images', label: 'Imagens' },
  { id: 'games-dir', label: 'Jogos' },
  { id: 'sys-dir', label: 'Sistema' },
  { id: 'etc-nura', label: '/etc/nura' },
];

export function ExplorerApp({ vfsNodes, setVfsNodes, onNotify }: ExplorerAppProps) {
  const [currentFolderId, setCurrentFolderId] = useState<string>('user-home');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [clipboard, setClipboard] = useState<{ nodeId: string } | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [previewNode, setPreviewNode] = useState<VfsNode | null>(null);
  const [inlinePrompt, setInlinePrompt] = useState<{
    mode: 'new-folder' | 'rename';
    value: string;
    targetId?: string;
  } | null>(null);

  const breadcrumbs = useMemo(
    () => getBreadcrumbs(vfsNodes, currentFolderId),
    [vfsNodes, currentFolderId]
  );

  const currentPath = useMemo(
    () => getNodePath(vfsNodes, currentFolderId),
    [vfsNodes, currentFolderId]
  );

  const visibleItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const base = q
      ? vfsNodes.filter((n) => n.parentId !== null && n.name.toLowerCase().includes(q))
      : vfsNodes.filter((n) => n.parentId === currentFolderId);

    return [...base].sort((a, b) => {
      if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
      return a.name.localeCompare(b.name, 'pt-BR');
    });
  }, [vfsNodes, currentFolderId, searchQuery]);

  const selectedNode = useMemo(
    () => vfsNodes.find((n) => n.id === selectedId) ?? null,
    [vfsNodes, selectedId]
  );

  const totalVfsBytes = useMemo(
    () => vfsNodes.reduce((acc, n) => acc + n.sizeBytes, 0),
    [vfsNodes]
  );

  const goUp = () => {
    const current = vfsNodes.find((n) => n.id === currentFolderId);
    if (current && current.parentId) {
      setCurrentFolderId(current.parentId);
      setSelectedId(null);
    }
  };

  const openNode = (node: VfsNode) => {
    if (node.type === 'folder') {
      setCurrentFolderId(node.id);
      setSelectedId(null);
      setSearchQuery('');
    } else {
      setPreviewNode(node);
    }
  };

  const handleSubmitPrompt = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inlinePrompt) return;
    const trimmed = inlinePrompt.value.trim();
    if (!trimmed) return;

    const nowStr = new Date().toLocaleString('pt-BR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });

    if (inlinePrompt.mode === 'new-folder') {
      const duplicate = vfsNodes.some(
        (n) => n.parentId === currentFolderId && n.name.toLowerCase() === trimmed.toLowerCase()
      );
      if (duplicate) {
        onNotify('Nome já existente', `Já existe um item chamado "${trimmed}" nesta pasta.`);
        return;
      }
      const created: VfsNode = {
        id: `dir-${Date.now()}`,
        name: trimmed,
        type: 'folder',
        parentId: currentFolderId,
        sizeBytes: 0,
        modifiedAt: nowStr,
      };
      setVfsNodes((prev) => [...prev, created]);
      setSelectedId(created.id);
    } else if (inlinePrompt.mode === 'rename' && inlinePrompt.targetId) {
      setVfsNodes((prev) =>
        prev.map((n) =>
          n.id === inlinePrompt.targetId ? { ...n, name: trimmed, modifiedAt: nowStr } : n
        )
      );
    }
    setInlinePrompt(null);
  };

  const handleCopy = () => {
    if (!selectedNode) return;
    setClipboard({ nodeId: selectedNode.id });
    onNotify('Copiado (VFS)', `"${selectedNode.name}" pronto para colar.`);
  };

  const handlePaste = () => {
    if (!clipboard) return;
    const source = vfsNodes.find((n) => n.id === clipboard.nodeId);
    if (!source) return;

    const nowStr = new Date().toLocaleString('pt-BR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });

    const cloneSubtree = (srcId: string, newParentId: string, isTop: boolean): VfsNode[] => {
      const orig = vfsNodes.find((n) => n.id === srcId);
      if (!orig) return [];
      const copyId = `copy-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      let finalName = orig.name;
      if (isTop) {
        const exists = vfsNodes.some(
          (n) => n.parentId === newParentId && n.name === finalName
        );
        if (exists) finalName = `${orig.name} (cópia)`;
      }
      const cloned: VfsNode = {
        ...orig,
        id: copyId,
        parentId: newParentId,
        name: finalName,
        modifiedAt: nowStr,
        readonly: false,
      };
      const children = vfsNodes.filter((n) => n.parentId === srcId);
      return [cloned, ...children.flatMap((c) => cloneSubtree(c.id, copyId, false))];
    };

    const newNodes = cloneSubtree(source.id, currentFolderId, true);
    setVfsNodes((prev) => [...prev, ...newNodes]);
    if (newNodes[0]) setSelectedId(newNodes[0].id);
  };

  const handleDelete = () => {
    if (!selectedNode) return;
    if (selectedNode.readonly) {
      onNotify('Item protegido', 'Diretórios base do sistema virtual não podem ser removidos.');
      return;
    }
    const idsToRemove = new Set(collectSubtreeIds(vfsNodes, selectedNode.id));
    setVfsNodes((prev) => prev.filter((n) => !idsToRemove.has(n.id)));
    setSelectedId(null);
  };

  return (
    <div className="h-full flex flex-col text-sm">
      {/* Top Toolbar */}
      <div
        className="px-3 py-2 border-b flex flex-wrap items-center justify-between gap-2 shrink-0"
        style={{ borderColor: 'var(--nura-border)' }}
      >
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          <button
            type="button"
            onClick={goUp}
            disabled={currentFolderId === 'root'}
            className="min-w-[38px] h-[38px] rounded-lg flex items-center justify-center hover:bg-white/10 disabled:opacity-35 transition-colors shrink-0"
            title="Pasta anterior"
            aria-label="Subir diretório"
          >
            <ArrowLeft size={16} />
          </button>

          {/* Breadcrumb Bar */}
          <div
            className="h-[38px] px-3 rounded-xl flex items-center gap-1 overflow-x-auto nura-scroll flex-1 min-w-[140px]"
            style={{
              backgroundColor: 'var(--nura-surface-subtle)',
              border: '1px solid var(--nura-border)',
            }}
          >
            {breadcrumbs.map((crumb, idx) => (
              <React.Fragment key={crumb.id}>
                {idx > 0 && (
                  <ChevronRight
                    size={13}
                    className="shrink-0"
                    style={{ color: 'var(--nura-text-muted)' }}
                  />
                )}
                <button
                  type="button"
                  onClick={() => {
                    setCurrentFolderId(crumb.id);
                    setSelectedId(null);
                    setSearchQuery('');
                  }}
                  className="text-xs font-medium hover:underline whitespace-nowrap shrink-0 px-1 py-0.5 rounded"
                >
                  {crumb.name === '/' ? 'nura-vfs' : crumb.name}
                </button>
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Search */}
        <label className="relative flex items-center w-full sm:w-[210px] shrink-0">
          <Search
            size={14}
            className="absolute left-3 pointer-events-none"
            style={{ color: 'var(--nura-text-muted)' }}
          />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Buscar arquivos..."
            className="w-full h-[38px] pl-8 pr-3 rounded-xl text-xs outline-none"
            style={{
              backgroundColor: 'var(--nura-surface-subtle)',
              border: '1px solid var(--nura-border)',
              color: 'var(--nura-text)',
            }}
          />
        </label>
      </div>

      {/* Action Ribbon */}
      <div
        className="px-3 py-1.5 border-b flex flex-wrap items-center justify-between gap-2 shrink-0"
        style={{
          borderColor: 'var(--nura-border)',
          backgroundColor: 'var(--nura-surface-subtle)',
        }}
      >
        <div className="flex flex-wrap items-center gap-1">
          <button
            type="button"
            onClick={() =>
              setInlinePrompt({ mode: 'new-folder', value: 'Nova Pasta' })
            }
            className="h-[34px] px-2.5 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-white/10 transition-colors whitespace-nowrap shrink-0"
          >
            <FolderPlus size={14} style={{ color: 'var(--nura-accent)' }} />
            <span>Nova pasta</span>
          </button>

          <button
            type="button"
            disabled={!selectedNode}
            onClick={handleCopy}
            className="h-[34px] px-2.5 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-white/10 disabled:opacity-35 transition-colors whitespace-nowrap shrink-0"
          >
            <Copy size={14} />
            <span>Copiar</span>
          </button>

          <button
            type="button"
            disabled={!clipboard}
            onClick={handlePaste}
            className="h-[34px] px-2.5 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-white/10 disabled:opacity-35 transition-colors whitespace-nowrap shrink-0"
          >
            <ClipboardPaste size={14} />
            <span>Colar</span>
          </button>

          <button
            type="button"
            disabled={!selectedNode || selectedNode.readonly}
            onClick={() =>
              selectedNode &&
              setInlinePrompt({
                mode: 'rename',
                value: selectedNode.name,
                targetId: selectedNode.id,
              })
            }
            className="h-[34px] px-2.5 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-white/10 disabled:opacity-35 transition-colors whitespace-nowrap shrink-0"
          >
            <Pencil size={14} />
            <span>Renomear</span>
          </button>

          <button
            type="button"
            disabled={!selectedNode || selectedNode.readonly}
            onClick={handleDelete}
            className="h-[34px] px-2.5 rounded-lg flex items-center gap-1.5 text-xs font-medium hover:bg-rose-500/20 disabled:opacity-35 transition-colors whitespace-nowrap shrink-0"
          >
            <Trash2 size={14} className="text-rose-400" />
            <span>Excluir</span>
          </button>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => setViewMode('grid')}
            className="min-w-[34px] h-[34px] rounded-lg flex items-center justify-center transition-colors"
            style={{
              backgroundColor:
                viewMode === 'grid' ? 'var(--nura-surface-elevated)' : 'transparent',
              color: viewMode === 'grid' ? 'var(--nura-accent)' : 'var(--nura-text-muted)',
            }}
            aria-label="Visualização em grade"
          >
            <LayoutGrid size={15} />
          </button>
          <button
            type="button"
            onClick={() => setViewMode('list')}
            className="min-w-[34px] h-[34px] rounded-lg flex items-center justify-center transition-colors"
            style={{
              backgroundColor:
                viewMode === 'list' ? 'var(--nura-surface-elevated)' : 'transparent',
              color: viewMode === 'list' ? 'var(--nura-accent)' : 'var(--nura-text-muted)',
            }}
            aria-label="Visualização em lista"
          >
            <List size={15} />
          </button>
        </div>
      </div>

      {/* Inline Create/Rename Bar */}
      {inlinePrompt && (
        <form
          onSubmit={handleSubmitPrompt}
          className="px-3 py-2 border-b flex items-center gap-2 shrink-0"
          style={{
            borderColor: 'var(--nura-border)',
            backgroundColor: 'var(--nura-surface-elevated)',
          }}
        >
          <span className="text-xs font-medium shrink-0">
            {inlinePrompt.mode === 'new-folder' ? 'Nome da nova pasta:' : 'Novo nome:'}
          </span>
          <input
            autoFocus
            type="text"
            value={inlinePrompt.value}
            onChange={(e) =>
              setInlinePrompt({ ...inlinePrompt, value: e.target.value })
            }
            className="flex-1 h-[34px] px-3 rounded-lg text-xs outline-none"
            style={{
              backgroundColor: 'var(--nura-surface-subtle)',
              border: '1px solid var(--nura-border-strong)',
              color: 'var(--nura-text)',
            }}
          />
          <button
            type="submit"
            className="h-[34px] px-3 rounded-lg text-xs font-semibold shrink-0"
            style={{
              backgroundColor: 'var(--nura-accent)',
              color: 'var(--nura-accent-contrast)',
            }}
          >
            Confirmar
          </button>
          <button
            type="button"
            onClick={() => setInlinePrompt(null)}
            className="h-[34px] px-2.5 rounded-lg text-xs hover:bg-white/10 shrink-0"
          >
            Cancelar
          </button>
        </form>
      )}

      {/* Main Split Workspace */}
      <div className="flex-1 min-h-0 flex">
        {/* Left Sidebar */}
        <aside
          className="w-[185px] hidden md:flex flex-col justify-between p-2.5 border-r shrink-0"
          style={{ borderColor: 'var(--nura-border)' }}
        >
          <div className="space-y-0.5">
            <div
              className="px-2.5 py-1.5 text-[11px] font-semibold"
              style={{ color: 'var(--nura-text-muted)' }}
            >
              Acesso rápido
            </div>
            {QUICK_PLACES.map((place) => {
              const active = currentFolderId === place.id && !searchQuery;
              return (
                <button
                  key={place.id}
                  type="button"
                  onClick={() => {
                    setCurrentFolderId(place.id);
                    setSelectedId(null);
                    setSearchQuery('');
                  }}
                  className="w-full h-[36px] px-2.5 rounded-lg flex items-center gap-2 text-xs font-medium transition-colors text-left"
                  style={{
                    backgroundColor: active ? 'var(--nura-surface-elevated)' : 'transparent',
                    color: active ? 'var(--nura-accent)' : 'var(--nura-text)',
                  }}
                >
                  <Folder size={14} className="shrink-0" />
                  <span className="truncate">{place.label}</span>
                </button>
              );
            })}
          </div>

          {/* Storage Indicator */}
          <div
            className="p-2.5 rounded-xl"
            style={{
              backgroundColor: 'var(--nura-surface-subtle)',
              border: '1px solid var(--nura-border)',
            }}
          >
            <div className="flex items-center gap-1.5 text-xs font-medium">
              <HardDrive size={14} style={{ color: 'var(--nura-accent)' }} />
              <span>Armazenamento</span>
            </div>
            <div className="mt-2 h-1.5 rounded-full overflow-hidden bg-white/10">
              <div
                className="h-full rounded-full"
                style={{ width: '24%', backgroundColor: 'var(--nura-accent)' }}
              />
            </div>
            <div
              className="mt-1.5 text-[11px] tabular-nums"
              style={{ color: 'var(--nura-text-muted)' }}
            >
              14,8 GB de 64 GB (Simulado) · VFS {formatBytes(totalVfsBytes)}
            </div>
          </div>
        </aside>

        {/* Center File Area */}
        <div
          className="flex-1 min-w-0 overflow-y-auto p-3 nura-scroll"
          style={{ touchAction: 'pan-y' }}
          onClick={() => setSelectedId(null)}
        >
          {visibleItems.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center py-10">
              <Folder size={34} style={{ color: 'var(--nura-text-muted)' }} />
              <p className="text-sm font-medium mt-2">
                {searchQuery ? 'Nenhum arquivo encontrado' : 'Esta pasta está vazia'}
              </p>
              <p className="text-xs mt-1" style={{ color: 'var(--nura-text-muted)' }}>
                {searchQuery
                  ? 'Tente outro termo de pesquisa.'
                  : 'Use "Nova pasta" para criar um diretório virtual.'}
              </p>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
              {visibleItems.map((item) => {
                const isSelected = selectedId === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedId(item.id);
                    }}
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      openNode(item);
                    }}
                    className="p-3 rounded-xl flex flex-col items-center text-center gap-2 transition-colors hover:bg-white/5"
                    style={{
                      backgroundColor: isSelected
                        ? 'var(--nura-surface-elevated)'
                        : 'var(--nura-surface-subtle)',
                      border: `1px solid ${
                        isSelected ? 'var(--nura-border-strong)' : 'var(--nura-border)'
                      }`,
                    }}
                  >
                    {item.type === 'folder' ? (
                      <Folder size={30} style={{ color: 'var(--nura-accent)' }} />
                    ) : (
                      <FileText size={30} style={{ color: '#94a3b8' }} />
                    )}
                    <div className="w-full min-w-0">
                      <div className="text-xs font-medium truncate">{item.name}</div>
                      <div
                        className="text-[11px] mt-0.5 tabular-nums"
                        style={{ color: 'var(--nura-text-muted)' }}
                      >
                        {item.type === 'folder' ? 'Pasta' : formatBytes(item.sizeBytes)}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--nura-border)' }}>
              {visibleItems.map((item) => {
                const isSelected = selectedId === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedId(item.id);
                    }}
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      openNode(item);
                    }}
                    className="w-full min-h-[44px] px-3 py-2 flex items-center justify-between gap-3 text-left rounded-lg transition-colors hover:bg-white/5"
                    style={{
                      backgroundColor: isSelected ? 'var(--nura-surface-elevated)' : 'transparent',
                    }}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      {item.type === 'folder' ? (
                        <Folder size={17} style={{ color: 'var(--nura-accent)' }} className="shrink-0" />
                      ) : (
                        <FileText size={17} style={{ color: '#94a3b8' }} className="shrink-0" />
                      )}
                      <span className="text-xs font-medium truncate">{item.name}</span>
                    </div>
                    <div
                      className="flex items-center gap-4 text-xs tabular-nums shrink-0"
                      style={{ color: 'var(--nura-text-muted)' }}
                    >
                      <span className="hidden sm:inline">{item.modifiedAt}</span>
                      <span className="w-16 text-right">
                        {item.type === 'folder' ? 'Pasta' : formatBytes(item.sizeBytes)}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Details Inspector */}
        {selectedNode && (
          <aside
            className="w-[210px] hidden lg:flex flex-col p-3 border-l shrink-0"
            style={{ borderColor: 'var(--nura-border)' }}
          >
            <div className="text-xs font-semibold mb-3">Detalhes do item</div>
            <div className="flex flex-col items-center text-center py-3 border-b" style={{ borderColor: 'var(--nura-border)' }}>
              {selectedNode.type === 'folder' ? (
                <Folder size={36} style={{ color: 'var(--nura-accent)' }} />
              ) : (
                <FileText size={36} style={{ color: '#94a3b8' }} />
              )}
              <div className="text-xs font-semibold mt-2 break-all">{selectedNode.name}</div>
            </div>
            <dl className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between gap-2">
                <dt style={{ color: 'var(--nura-text-muted)' }}>Tipo</dt>
                <dd>{selectedNode.type === 'folder' ? 'Diretório' : 'Arquivo'}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt style={{ color: 'var(--nura-text-muted)' }}>Tamanho</dt>
                <dd className="tabular-nums">
                  {selectedNode.type === 'folder' ? '—' : formatBytes(selectedNode.sizeBytes)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt style={{ color: 'var(--nura-text-muted)' }}>Modificado</dt>
                <dd className="tabular-nums text-right">{selectedNode.modifiedAt}</dd>
              </div>
            </dl>
            <button
              type="button"
              onClick={() => openNode(selectedNode)}
              className="mt-4 h-[36px] rounded-lg text-xs font-semibold transition-transform active:scale-95"
              style={{
                backgroundColor: 'var(--nura-accent)',
                color: 'var(--nura-accent-contrast)',
              }}
            >
              {selectedNode.type === 'folder' ? 'Abrir pasta' : 'Visualizar conteúdo'}
            </button>
          </aside>
        )}
      </div>

      {/* Bottom Status Bar */}
      <div
        className="px-3 py-1.5 border-t flex items-center justify-between text-[11px] tabular-nums shrink-0"
        style={{
          borderColor: 'var(--nura-border)',
          color: 'var(--nura-text-muted)',
        }}
      >
        <span className="truncate">
          {currentPath} · {visibleItems.length} {visibleItems.length === 1 ? 'item' : 'itens'}
        </span>
        <span className="shrink-0">Sistema de arquivos virtual no navegador</span>
      </div>

      {/* File Content Preview Overlay */}
      {previewNode && (
        <div
          className="absolute inset-0 z-20 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setPreviewNode(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg rounded-xl overflow-hidden flex flex-col max-h-[85%]"
            style={{
              backgroundColor: 'var(--nura-surface-elevated)',
              border: '1px solid var(--nura-border-strong)',
            }}
          >
            <div
              className="px-4 py-2.5 border-b flex items-center justify-between"
              style={{ borderColor: 'var(--nura-border)' }}
            >
              <span className="text-xs font-semibold truncate">{previewNode.name}</span>
              <button
                type="button"
                onClick={() => setPreviewNode(null)}
                className="min-w-[32px] min-h-[32px] rounded-lg flex items-center justify-center hover:bg-white/10"
              >
                <X size={15} />
              </button>
            </div>
            <pre className="p-4 text-xs font-mono whitespace-pre-wrap overflow-y-auto nura-scroll leading-relaxed">
              {previewNode.content ?? 'Arquivo demonstrativo sem conteúdo textual.'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
