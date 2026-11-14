import React, { useEffect, useRef, useState } from 'react';
import { getNodePath, resolvePathToNodeId } from '../services/vfsService';
import { ThemeId, VfsNode } from '../types/os';

interface TerminalAppProps {
  vfsNodes: VfsNode[];
  setVfsNodes: React.Dispatch<React.SetStateAction<VfsNode[]>>;
  themeId: ThemeId;
  virtualInputSignal?: { key: string; seq: number } | null;
}

interface TerminalLine {
  id: string;
  type: 'input' | 'output' | 'accent';
  text: string;
}

const QUICK_COMMANDS = ['help', 'ls', 'pwd', 'neofetch', 'uname -a', 'date', 'clear'];

export function TerminalApp({
  vfsNodes,
  setVfsNodes,
  themeId,
  virtualInputSignal,
}: TerminalAppProps) {
  const [cwdId, setCwdId] = useState<string>('user-home');
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState<number>(-1);
  const [lines, setLines] = useState<TerminalLine[]>([
    {
      id: 'boot-1',
      type: 'accent',
      text: 'NURA Terminal · Shell demonstrativo (Alpine Linux / postmarketOS sandbox)',
    },
    {
      id: 'boot-2',
      type: 'output',
      text: 'Digite "help" para listar os comandos disponíveis. Nenhuma ação real é executada no sistema.',
    },
  ]);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [lines]);

  // Support virtual keyboard key injection when terminal is open
  useEffect(() => {
    if (!virtualInputSignal) return;
    const { key } = virtualInputSignal;
    if (key === 'ENTER') {
      runCommand(input);
      setInput('');
    } else if (key === 'BACKSPACE') {
      setInput((prev) => prev.slice(0, -1));
    } else if (key.length === 1) {
      setInput((prev) => prev + key);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [virtualInputSignal]);

  const cwdPath = getNodePath(vfsNodes, cwdId);
  const promptPrefix = `nura@nubia-z17-lite:${cwdPath === '/home/nura' ? '~' : cwdPath}$`;

  const appendLines = (entries: Omit<TerminalLine, 'id'>[]) => {
    setLines((prev) => [
      ...prev,
      ...entries.map((e, i) => ({ ...e, id: `ln-${Date.now()}-${i}-${Math.random()}` })),
    ]);
  };

  const runCommand = (rawCmd: string) => {
    const trimmed = rawCmd.trim();
    appendLines([{ type: 'input', text: `${promptPrefix} ${trimmed}` }]);

    if (!trimmed) return;
    setHistory((prev) => [trimmed, ...prev.slice(0, 30)]);
    setHistoryIdx(-1);

    const parts = trimmed.split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1);

    switch (cmd) {
      case 'help':
        appendLines([
          {
            type: 'output',
            text: [
              'Comandos disponíveis neste ambiente virtual:',
              '  help        Exibe esta lista de ajuda',
              '  clear       Limpa a tela do terminal',
              '  ls [dir]    Lista arquivos e pastas do VFS',
              '  pwd         Mostra o diretório virtual atual',
              '  cd [dir]    Navega entre diretórios (ex: cd Documentos, cd .., cd ~)',
              '  mkdir nome  Cria uma nova pasta no sistema de arquivos virtual',
              '  cat arq     Exibe o conteúdo de um arquivo texto do VFS',
              '  echo texto  Imprime texto na saída padrão',
              '  date        Mostra data e hora atual',
              '  uname [-a]  Informações simuladas do kernel Alpine/postmarketOS',
              '  neofetch    Resumo visual do protótipo NURA OS',
            ].join('\n'),
          },
        ]);
        break;

      case 'clear':
        setLines([]);
        break;

      case 'pwd':
        appendLines([{ type: 'output', text: cwdPath }]);
        break;

      case 'ls': {
        const targetId = args[0]
          ? resolvePathToNodeId(vfsNodes, cwdId, args[0])
          : cwdId;
        if (!targetId) {
          appendLines([{ type: 'output', text: `ls: '${args[0]}': Arquivo ou diretório inexistente` }]);
          break;
        }
        const children = vfsNodes
          .filter((n) => n.parentId === targetId)
          .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
        if (children.length === 0) {
          appendLines([{ type: 'output', text: '(diretório vazio)' }]);
        } else {
          const formatted = children
            .map((c) => (c.type === 'folder' ? `${c.name}/` : c.name))
            .join('   ');
          appendLines([{ type: 'output', text: formatted }]);
        }
        break;
      }

      case 'cd': {
        const target = args[0] || '~';
        const resolved = resolvePathToNodeId(vfsNodes, cwdId, target);
        if (!resolved) {
          appendLines([{ type: 'output', text: `cd: '${target}': Diretório não encontrado` }]);
          break;
        }
        const node = vfsNodes.find((n) => n.id === resolved);
        if (!node || node.type !== 'folder') {
          appendLines([{ type: 'output', text: `cd: '${target}': Não é um diretório` }]);
          break;
        }
        setCwdId(node.id);
        break;
      }

      case 'mkdir': {
        const folderName = args[0];
        if (!folderName) {
          appendLines([{ type: 'output', text: 'mkdir: informe o nome da pasta' }]);
          break;
        }
        const exists = vfsNodes.some(
          (n) => n.parentId === cwdId && n.name.toLowerCase() === folderName.toLowerCase()
        );
        if (exists) {
          appendLines([{ type: 'output', text: `mkdir: '${folderName}' já existe` }]);
          break;
        }
        const newNode: VfsNode = {
          id: `dir-${Date.now()}`,
          name: folderName,
          type: 'folder',
          parentId: cwdId,
          sizeBytes: 0,
          modifiedAt: new Date().toLocaleString('pt-BR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          }),
        };
        setVfsNodes((prev) => [...prev, newNode]);
        appendLines([{ type: 'output', text: `Pasta virtual '${folderName}' criada em ${cwdPath}` }]);
        break;
      }

      case 'cat': {
        const target = args[0];
        if (!target) {
          appendLines([{ type: 'output', text: 'cat: informe o nome do arquivo' }]);
          break;
        }
        const resolved = resolvePathToNodeId(vfsNodes, cwdId, target);
        const node = vfsNodes.find((n) => n.id === resolved);
        if (!node) {
          appendLines([{ type: 'output', text: `cat: '${target}': Arquivo não encontrado` }]);
        } else if (node.type === 'folder') {
          appendLines([{ type: 'output', text: `cat: '${target}': É um diretório` }]);
        } else {
          appendLines([{ type: 'output', text: node.content ?? '(arquivo binário ou vazio)' }]);
        }
        break;
      }

      case 'echo':
        appendLines([{ type: 'output', text: args.join(' ') }]);
        break;

      case 'date':
        appendLines([
          {
            type: 'output',
            text: new Date().toLocaleString('pt-BR', {
              dateStyle: 'full',
              timeStyle: 'medium',
            }),
          },
        ]);
        break;

      case 'uname':
        appendLines([
          {
            type: 'output',
            text: args.includes('-a')
              ? 'Linux nubia-z17-lite 6.6.0-postmarketos-qcom #1-Alpine SMP PREEMPT aarch64 GNU/Linux (Simulação)'
              : 'Linux (NURA OS Virtual)',
          },
        ]);
        break;

      case 'whoami':
        appendLines([{ type: 'output', text: 'nura' }]);
        break;

      case 'neofetch':
        appendLines([
          {
            type: 'accent',
            text: [
              '      /\\        nura@nubia-z17-lite (Protótipo Web)',
              '     /  \\       -----------------------------------',
              '    / /\\ \\      OS: NURA OS 0.4 Desktop (Alpine/postmarketOS)',
              '   / /  \\ \\     Host: ZTE Nubia Z17 Lite (Referência)',
              '  /_/    \\_\\    Kernel: 6.6-postmarketos (Simulado)',
              `                Theme: ${themeId}`,
              '                Shell: nura-sh (Sandbox Virtual)',
              '                CPU: Snapdragon 653 8-Core (Simulado)',
              '                Memory: 1.68 GiB / 4.00 GiB (Simulado)',
            ].join('\n'),
          },
        ]);
        break;

      default:
        appendLines([
          {
            type: 'output',
            text: `nura-sh: '${cmd}': comando não encontrado. Digite 'help' para ver os comandos.`,
          },
        ]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length > 0) {
        const nextIdx = Math.min(historyIdx + 1, history.length - 1);
        setHistoryIdx(nextIdx);
        setInput(history[nextIdx]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx > 0) {
        const nextIdx = historyIdx - 1;
        setHistoryIdx(nextIdx);
        setInput(history[nextIdx]);
      } else {
        setHistoryIdx(-1);
        setInput('');
      }
    }
  };

  return (
    <div
      className="h-full flex flex-col font-mono text-xs"
      style={{ backgroundColor: 'rgba(3, 6, 12, 0.92)', color: '#e2e8f0' }}
      onClick={() => inputRef.current?.focus()}
    >
      {/* Quick Touch Commands Strip */}
      <div
        className="px-3 py-2 border-b flex items-center gap-1.5 overflow-x-auto nura-scroll shrink-0"
        style={{
          borderColor: 'var(--nura-border)',
          backgroundColor: 'rgba(255, 255, 255, 0.03)',
        }}
      >
        <span className="text-[11px] text-slate-400 mr-1 shrink-0">Atalhos:</span>
        {QUICK_COMMANDS.map((cmd) => (
          <button
            key={cmd}
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              runCommand(cmd);
            }}
            className="h-[30px] px-2.5 rounded-lg text-[11px] font-medium hover:bg-white/10 transition-colors whitespace-nowrap shrink-0"
            style={{
              backgroundColor: 'rgba(56, 189, 248, 0.08)',
              border: '1px solid var(--nura-border)',
              color: '#7dd3fc',
            }}
          >
            {cmd}
          </button>
        ))}
      </div>

      {/* Terminal Output */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3.5 space-y-1.5 nura-scroll"
        style={{ touchAction: 'pan-y' }}
      >
        {lines.map((line) => (
          <pre
            key={line.id}
            className="whitespace-pre-wrap break-words leading-relaxed font-mono"
            style={{
              color:
                line.type === 'input'
                  ? '#38bdf8'
                  : line.type === 'accent'
                  ? '#22d3ee'
                  : '#cbd5e1',
            }}
          >
            {line.text}
          </pre>
        ))}

        {/* Prompt Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            runCommand(input);
            setInput('');
          }}
          className="flex items-center gap-2 pt-1"
        >
          <span className="text-cyan-400 font-semibold shrink-0">{promptPrefix}</span>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
            spellCheck={false}
            autoCapitalize="off"
            autoComplete="off"
            className="flex-1 bg-transparent outline-none text-slate-100 caret-cyan-400 min-w-[60px]"
            aria-label="Entrada de comando do Terminal"
          />
        </form>
      </div>
    </div>
  );
}
