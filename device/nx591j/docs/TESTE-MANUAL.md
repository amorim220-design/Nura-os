# NURA OS — teste manual no aparelho (passo 8)

Guia curto para quem estiver com o NX591J na mão. Nada aqui é
destrutivo: nenhuma partição é tocada, nenhum serviço é habilitado
permanentemente.

> O **NURA Desktop não é o padrão** após a instalação do passo 7.
> O aparelho continua booteando no X11 (`nxgui.service`), como antes.
> Este guia é para **experimentar** a sessão nova.

---

## 0. Onde entrar

No console do aparelho (o login automático já entra como `dev`):

```
NX591J login: dev
```

Alternativa: se o X11 estiver na tela, o `xterm` dá acesso ao mesmo
sistema.

---

## 1. Parar o X11 (o X e o shell disputam o mesmo framebuffer)

```sh
sudo systemctl stop nxgui
```
A tela fica preta por um instante — **é normal**: o console assume.

---

## 2. Teste 1 — o desktop aparece?

```sh
python3 /usr/share/nura/src/nura_shell.py
```

**Esperado:** a tela fica preta e depois aparece a **área de trabalho
em paisagem** (1920×1080): triângulo neon, "NURA OS" no centro, os 7
ícones à esquerda, o relógio e o monitor de sistema à direita, e a
barra de tarefas embaixo.

Para sair: `Ctrl+C` (ou desligar e religar).

---

## 3. Teste 2 — o toque está alinhado?

```sh
python3 /usr/share/nura/src/nura_shell.py --touch-test
```

**Esperado:** ao tocar, aparece um retículo **exatamente sob o dedo**,
com as coordenadas "paisagem" e "painel" ao lado.

Faça o teste nos **4 cantos** e no **centro**. Se o retículo estiver
deslocado, o problema é de escala do digitizador (e não de rotação) —
nesse caso me passe os números que aparecem na tela e eu ajusto a
normalização em `nura_input.py`.

---

## 4. Teste 3 — desempenho real

```sh
python3 /usr/share/nura/src/nura_shell.py --bench=30
```

**Esperado:** algo como

```
[bench] 450 quadros em 30.0 s -> 15.0 fps
[bench] RAM maxima: 78.4 MB
[bench] por quadro: 66.7 ms
```

**Critérios de aceite:** ≥ 15 fps e RAM ≤ 120 MB.
(Anote o número: o A53 é bem mais lento que o PC onde os testes
rodaram a 30 fps.)

---

## 5. Teste 4 — os aplicativos

```sh
python3 /usr/share/nura/src/nura_shell.py
```

| Ação | Como | Esperado |
|---|---|---|
| Abrir o menu Iniciar | toque no botão do canto inferior esquerdo | menu com busca e 6 apps |
| Filtrar a busca | toque no campo "Buscar aplicativos" | a lista filtra |
| Abrir o Terminal | toque no ícone "Terminal" (coluna esquerda) | janela com abas de sessão e prompt do busybox |
| Comandar | digite `echo ola` e toque em **Executar** | aparece `ola` |
| Comando perigoso | digite `sudo ls` | aparece o diálogo de confirmação; **não executa** sem aceitar |
| Abrir os Arquivos | ícone "Arquivos" | gerenciador com lista, barra lateral e armazenamento |
| Renomear/excluir | toque longo num item | barra de ações; excluir pede confirmação |
| Performance | ícone "Configurações" → ou app fixado | CPU/RAM/disco com **valores reais** (compare com `top`/`free`/`df`) |
| Teclado virtual | toque em um campo de texto | teclado aparece embaixo e digita |
| **Shift de PC** | toque em **Shift** e depois em **`-`** | aparece **`_`** (o Shift fica aceso em ciano) |
| **Acentos** | toque em **123** | aparecem `á à â ã é ê í ó ô õ ú ü ç` e as maiúsculas |
| Mover uma janela | arraste a barra de título | a janela segue o dedo |
| Redimensionar | arraste a borda inferior direita | a janela muda de tamanho |

Ao terminar cada teste, **reinicie o X11**:

```sh
sudo systemctl start nxgui
```

---

## 6. Se algo der errado

```sh
nura-recovery status      # estado do NURA (falhas, auto-start, backups)
nura-recovery doctor      # diagnóstico completo
```

**Perdeu a tela?** O console continua disponível: o `getty@tty1` tem
autologin e não depende do NURA. Se a tela estiver presa, use
`Ctrl+Alt+F1` (ou o botão de volume, como o aparelho já faz) para
voltar ao console.

**Quer desligar o NURA do boot?** (ele nem está habilitado, mas
caso você tenha feito isso)

```sh
nura-recovery disable
```

---

## 7. O que NÃO fazer agora

* Não rodar `systemctl enable nura-shell.service` ainda — isso é o
  **passo 10**, que precisa de **autorização separada**.
* Não formatar partições, não mexer no `boot`, não mexer no initramfs.
* Não mexer nos drivers (`msm`, `msm_fbdev`): o display depende deles.

---

## 7.1 Teclado USB — não tente, não vai funcionar

Se você plugar um teclado USB (ou um adaptador OTG), **nada acontece** —
e isso não é defeito do NURA. A porta deste aparelho, no kernel atual:

* está em **`dr_mode = "peripheral"`** (só modo dispositivo);
* **não fornece 5 V** (VBUS) para alimentar o teclado;
* nem o modo dispositivo enumera (é o mesmo motivo de o `adb` não
  funcionar).

O laudo completo, com as evidências, está em
`mainline/nura/docs/USB-TECLADO.md`. Fazer teclado USB funcionar exige
**outro kernel e outro DTB**, o que é uma etapa futura com autorização
própria — e sem garantia de que o hardware suporte.

**Use o teclado virtual** (Shift de PC + acentos pt-BR).

---

## 8. Depois dos testes

Me passe:

1. O resultado do `--bench` (fps e RAM).
2. O resultado do `--touch-test` (se o retículo caiu sob o dedo).
3. Qualquer comportamento estranho (app que não abre, janela que não
   move, etc.).

Com isso eu ajusto o que for preciso e apresento o **passo 9**
(validação de touchscreen e estabilidade) e o **passo 10**
(ativação do auto-start) para sua autorização.
