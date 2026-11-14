# NURA OS — contrato da API interna (NURA Desktop)

Documento normativo para todos os componentes. Qualquer código novo
**deve** respeitar estas assinaturas.

Espaço de coordenadas: **sempre paisagem 1920x1080**. A conversão do
toque (retrato) para paisagem é feita pelo `nura_input`.

---

## 1. `nura_theme`

```python
from nura_theme import Theme, PALETTES, THEME_NAMES

theme = Theme("neon")          # 'neon' | 'dark' | 'minimal' | 'gamer'
theme.set_scale(1.0)          # escala da interface (0.8 .. 1.4)
```

Atributos de cor (RGB 0..1): `bg`, `bg2`, `panel`, `panel_hi`, `accent`,
`accent2`, `text`, `dim`, `dim2`, `ok`, `warn`, `err`, `light` (bool),
`glow` (bool).

Atributos de métrica (já multiplicados pela escala): `taskbar_h`,
`titlebar_h`, `icon`, `radius`, `gap`, `pad`, `font`, `font_small`,
`font_title`, `font_huge`.

Funções: `gradient_v(ctx,...)`, `rounded_rect(ctx,...)`, `panel(ctx,...)`,
`shadow(ctx,...)`, `text(ctx, s, x, y, size, color, weight, align)`,
`text_width(ctx, s, size, weight)`, `text_size(ctx, s, size, weight)`.

---

## 2. `nura_ui` — `Painter`

```python
from nura_ui import Painter, draw_wallpaper, draw_logo_text

p = Painter(ctx, theme)
```

| método | assinatura |
|---|---|
| `rect` | `(x, y, w, h, color=None, alpha=1.0)` |
| `round` | `(x, y, w, h, r=10, color=None, alpha=1.0, filled=True, width=1.0)` |
| `line` | `(x1, y1, x2, y2, color=None, width=1.0, alpha=1.0)` |
| `circle` | `(cx, cy, r, color=None, alpha=1.0, filled=True, width=2.0)` |
| `arc` | `(cx, cy, r, a0, a1, color=None, width=2.0, alpha=1.0)` |
| `poly` | `(points, color=None, alpha=1.0, filled=True, width=2.0)` |
| `gradient_v` / `gradient_diag` | `(x, y, w, h, c0, c1)` |
| `text` | `(s, x, y, size=None, color=None, weight="normal", align="left")` |
| `tw` | `(s, size=None, weight="normal") -> float` (largura) |
| `ts` | `(s, size=None, weight="normal") -> (w, h)` |
| `panel` | `(x, y, w, h, color=None, alpha=0.92, r=None, border=True)` |
| `button` | `(x, y, w, h, label, pressed=False, accent=None, size=None, icon=None) -> rect` |
| `progress` | `(x, y, w, h, frac, color=None, bg=None)` |
| `scrollbar` | `(x, y, w, h, frac, view=1.0)` |
| `icon` | `(name, cx, cy, size, color=None)` |
| `app_icon` | `(name, cx, cy, size)` — ícones coloridos: `monitor`, `folder`, `globe`, `terminal`, `store`, `gear`, `gamepad`, `power` |

Ícones de `icon()`: `search`, `bluetooth`, `wifi`, `battery`, `volume`,
`power`, `info`, `close`, `check`, `chevron_up`, `chevron_down`, `back`,
`forward`, `up`, `home`, `star`, `grid`, `refresh`, `cpu`, `ram`, `disk`,
`temp`.

---

## 3. `nura_input`

```python
from nura_input import TouchEvent, InputReader, GestureDetector, find_touch_device
```

`TouchEvent`: campos `type`, `x`, `y`, `button`, `dx`, `dy`, `amount`,
`scale`, `time`, `slots`.

`type` ∈ `"down" | "up" | "move" | "drag" | "tap" | "longpress" |
"scroll" | "cancel" | "pinch"`.

- `scroll`: `amount` = pixels de rolagem (positivo =滚 para cima).
- `drag`: `dx`/`dy` = deslocamento desde o último evento.

---

## 4. `nura_window` — `App` e `Window`

```python
from nura_window import App

class MeuApp(App):
    title = "Meu App"
    icon = "terminal"          # nome de icone do Painter.icon
    width, height = 900, 620
    min_width, min_height = 480, 320
    resizable = True

    def on_open(self): pass          # 1x ao abrir
    def on_close(self): pass         # 1x ao fechar
    def on_focus(self, focused): pass
    def draw(self, p): pass          # CONTEUDO (a moldura ja foi desenhada)
    def on_touch(self, ev): return False   # True = consumido
    def on_key(self, ev): return False
    def on_tick(self, dt): pass      # dt em segundos
```

O `draw` do app recebe o `Painter` e desenha **apenas o conteúdo**, ou
seja, a área útil é `(window.x, window.y + titlebar_h, window.w,
window.h - titlebar_h)`. Use `self.window.content_rect()` para saber
onde está a área útil.

`self.shell` está disponível dentro do app e oferece:

| método | efeito |
|---|---|
| `shell.open_app(app, **kw)` | abre uma janela nova |
| `shell.close_window(win)` | fecha |
| `shell.focus_window(win)` | traz para frente |
| `shell.notify(msg, kind="info")` | mostra um aviso na barra |
| `shell.confirm(title, message, on_ok)` | diálogo de confirmação |
| `shell.sysinfo` | instância de `nura_sysinfo.SysInfo` |
| `shell.filemgr` | instância de `nura_filemgr.FileManager` |
| `shell.theme` | tema ativo |
| `shell.launch(cmd)` | executa um comando (use só para apps reais) |

---

## 5. `nura_sysinfo` (criado por outro componente)

`SysInfo(root="/sys", proc="/proc")` com os métodos:
`cpu_times()`, `cpu_usage(prev)`, `cpu_freq()`, `ram_info()`,
`loadavg()`, `uptime()`, `storage_info(path='/')`, `battery()`,
`power_supplies()`, `thermal_zones()`, `processes(limit=50)`,
`cpu_governor()`, `drm_info()`, `wlan_info()`, `bluetooth_info()`,
`kernel_info()`, `os_info()`, `summary()`.

**Regra:** devolve `None`/lista vazia quando o dado não existe. Nunca
inventar valores.

---

## 6. `nura_filemgr` (criado por outro componente)

`FileManager(root=...)` com `listdir()`, `stat_info()`, `copy()`,
`move()`, `rename()`, `mkdir()`, `delete(path, recursive, confirm)`,
`du()`, `storage()`, `mounts()`, `removable_devices()`, `search()`,
`open_with()`, `recent_files()`, `operation_log()`.

**Regra:** nada de operação privilegiada; `delete` exige `confirm=True`.

---

## 7. Regras de escrita de tela (touch-first)

- Alvo mínimo de toque: **44x44 px lógicos** (escala 1.0).
- Espaçamento entre botões: >= 8 px.
- Nada de texto menor que `theme.font_small` (14 px).
- Evite hover/estados de mouse; o alvo é o dedo.
- Feedback visual de toque: alterar `pressed` no mesmo quadro do `down`.

---

## 8. `nura_keyboard` — `Keyboard`

Teclado virtual desenhado em cairo, usado por qualquer app que receba
texto. Não depende de X11, GTK nem matchbox-keyboard.

### 8.1 Construção e ciclo de vida

```python
kb = Keyboard(shell=sh)      # usa sh.theme para as métricas
kb.show() / kb.hide() / kb.toggle()
kb.draw(painter)             # chamado pelo shell por último
kb.on_touch(ev)              # True se consumiu o evento
```

`on_touch` devolve `True` também para eventos dentro da faixa do
teclado, para que nada abaixo dele receba o toque.

### 8.2 Contrato do Shift (corrigido em 13/11/2026)

**O Shift vale para todas as teclas, como num teclado de PC.**

| sem Shift | 1 | - | = | ; | ' | , | . | / | \ | [ | ] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **com Shift** | ! | _ | + | : | " | < | > | ? | \| | { | } |

O Shift é **de um toque só**: depois de produzir uma tecla, volta a
desligar (comportamento de teclado móvel). Letras viram maiúsculas.

### 8.3 Camadas

* **base**: `1234567890-=` / `qwertyuiop[]` / `asdfghjkl;'` / `zxcvbnm,./\`
* **`123`**: símbolos restantes + **acentos pt-BR**
  (`á à â ã é ê í ó ô õ ú ü ç` e maiúsculas) + `~`

### 8.4 Entrega das teclas

`Keyboard._send(valor)` chama `shell.on_key(valor)`. Valores especiais:
`" "` (espaço), `"BackSpace"`, `"Return"`. Qualquer outro valor é o
caractere literal — o Terminal, por exemplo, insere o texto.

### 8.5 Geometria

* alvo mínimo de 52 px de altura (`52 * ui_scale`);
* sem sobreposição de teclas (verificado nos 4 temas);
* a linha de ações ocupa **exatamente** a mesma largura das linhas de
  letras (`total_w`), sem folga à direita.
