# Teclado USB no NX591J — por que não funciona hoje

**Conclusão curta:** não é problema do NURA Desktop, é do **kernel e da
árvore de dispositivos (DTB)**. A porta USB deste aparelho, no kernel
atual, é **somente dispositivo (peripheral)** e não fornece 5 V para
alimentar um teclado. Conectar um teclado USB hoje não pode funcionar —
nem com o NURA, nem com o X11, nem no console.

Este documento registra **o que foi verificado**, para não repetirmos a
investigação nem prometermos o que o hardware não entrega.

---

## 1. As duas barreiras independentes

### Barreira A — o controlador está em modo "peripheral"

Arquivo: `arch/arm64/boot/dts/qcom/msm8976.dtsi`

```
otg: usb@78db000 {
        compatible = "qcom,ci-hdrc";
        ...
        dr_mode = "peripheral";     <-- nunca será host
        phy_type = "ulpi";
        status = "disabled";
};
```

E no DTS do aparelho
(`arch/arm64/boot/dts/qcom/msm8976-nubia-nx591j.dts`):

```
&otg {
        phys = <&usb_hs_phy>;
        phy-names = "usb-phy";
        status = "okay";            <-- liga o controlador...
};                                  <-- ...mas mantém dr_mode = peripheral
```

`dr_mode = "peripheral"` quer dizer: o SoC só sabe **ser** um dispositivo
USB (como quando você pluga o celular no PC). Para ler um teclado ele
precisa ser **host** (`dr_mode = "host"`) ou **dual-role** (`"otg"`).

### Barreira B — não há alimentação VBUS (5 V) para o teclado

O nó `&otg` **não tem** `vbus-supply`, e o DTS do aparelho **não declara
nenhum regulador de 5 V/OTG**:

```bash
$ grep -nE 'vbus|otg.?boost|5v' msm8976-nubia-nx591j.dts
(nenhum resultado)
```

Um teclado USB consome energia pelo próprio cabo. Sem um boost de 5 V
(ou um hub alimentado), o teclado nem liga. Em outros aparelhos Qualcomm
isso é declarado como `vbus-supply = <&regulator_usb_vbus>`
(ver `hamoa-iot-evk.dts`, `lemons-evk.dts` no mesmo kernel).

### Barreira C (a que também quebra o adb) — o pull-up de D+

Mesmo em modo dispositivo, o aparelho **não enumera** no PC. Já foi
investigado e está em `STATUS.md` §"USB: o que já foi descartado":

* clocks, resets e reguladores do PHY: OK;
* ULPI acessível, `OTG Control`, `HS_PHY_SESS_VLD_CTRL`: sem efeito;
* switch Type-C (GPIOs 52/115/35/38): aplicado, sem efeito.

Hipótese principal: o DTB de fábrica tem `qcom,dp-manual-pullup` — neste
aparelho o **pull-up de D+ não é ligado pelo hardware**, é o software que
liga. O driver mainline `phy-qcom-usb-hs-28nm.c` não implementa isso, e
`/dev/mem` é bloqueado no arm64 (não dá para resolver no userspace).

---

## 2. O que foi verificado (evidências)

| Verificação | Resultado |
|---|---|
| `dr_mode` do controlador `usb@78db000` | `"peripheral"` |
| `&otg` no DTS do aparelho | `status = "okay"`, **sem** `vbus-supply` |
| Regulador VBUS/OTG de 5 V no DTS | **não existe** |
| `CONFIG_USB_CHIPIDEA_HOST=y` | **presente** (o driver de host existe) |
| `usbcore`, `ci_hdrc`, `ci_hdrc_msm`, `hid`, `usbhid` | **embutidos no kernel** (`modules.builtin`) |
| `hid-generic.ko`, `usb-storage.ko`, `xpad.ko` | **presentes** no rootfs |
| `dp_manual_pullup` no driver do kernel | **ausente** |
| Enumeração em modo dispositivo (adb) | **nunca** aconteceu |

Ou seja: **o software do NURA não é o obstáculo** — o kernel tem todos os
drivers de teclado USB compilados. O que falta é a configuração elétrica
e de modo do controlador.

---

## 3. O que seria necessário para ter teclado USB

Isto é uma mudança de **kernel + DTB**, não de aplicativo. Exige nova
imagem de boot e autorização própria (é além do passo 7):

1. **Pôr o controlador em host/otg**: `dr_mode = "host"` (ou `"otg"` com
   `usb-role-switch`) no nó `&otg`.
2. **Declarar um `vbus-supply`** de 5 V — só é possível se o PM8950/placa
   tiver o boost de OTG ligado a um GPIO. Ainda **não foi localizado** no
   DTS de fábrica que temos.
3. **Portar o `dp_manual_pullup`** do driver downstream (CAF
   `phy-msm-usm.c`) para o `phy-qcom-usb-hs-28nm.c` — o mesmo conserto
   que faria o **adb voltar a funcionar**.
4. Recompilar o kernel, gerar novo `boot.img`, gravar (com o mesmo
   procedimento e rollback do passo 7).

Risco: o item 2 depende de hardware que pode não existir (o switch
Type-C pode não rotear host mode). **Não há garantia de que funcione.**

---

## 4. Alternativas que funcionam hoje

| Alternativa | Situação |
|---|---|
| **Teclado virtual do NURA** | Funciona; agora com Shift de PC e acentos pt-BR |
| Console do sistema (`getty` em tty1) | Funciona com teclado virtual do console |
| Teclado Bluetooth | **Impossível**: o aparelho não tem Wi-Fi/BT neste port |
| Teclado USB | **Impossível** com o kernel atual (este documento) |

---

## 5. Se você quiser tentar

Diga **"autorizo a investigação do USB host"**. O que eu faço, em ordem,
**sem gravar nada** até você aprovar a imagem:

1. procurar no DTS de fábrica (stock) o regulador de VBUS/OTG e o GPIO
   que o habilita;
2. procurar o `dp_manual_pullup` no kernel downstream que já temos;
3. compilar um **kernel de teste** com `dr_mode = "host"` e o pull-up
   manual;
4. testar em bancada (o aparelho precisa de fastboot + recovery).

Se os passos 1–2 não acharem o hardware de VBUS, eu paro e explico — para
não gastar seu tempo com uma via que o hardware não suporta.

---

*Registrado em 13/11/2026, após a solicitação "por que não funciona
teclado USB?". Nenhuma alteração de kernel, DTB ou partição foi feita.*
