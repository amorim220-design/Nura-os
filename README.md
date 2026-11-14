# NURA OS

Este repositório reúne a demonstração web e o desktop Linux para o Nubia Z17 Lite (NX591J).

## Demonstração web

Na raiz, execute `npm install` e `npm run dev`. A interface React roda no navegador e usa telemetria simulada.

## Desktop Linux (NX591J)

O código em [device/nx591j](device/nx591j) usa Python 3, pycairo, framebuffer e evdev. O painel lê CPU, memória, armazenamento e sensores do Linux.

- [Teste manual no aparelho](device/nx591j/docs/TESTE-MANUAL.md)
- [API do shell](device/nx591j/docs/API-NURA.md)
- [Estado do USB e do teclado externo](device/nx591j/docs/USB-TECLADO.md)

Em Linux, com Python 3 e pycairo disponíveis, rode `bash device/nx591j/tests/run_tests.sh` para os testes em simulação. No aparelho já provisionado, `sudo nura-test` inicia uma sessão de 12 minutos e restaura a sessão anterior ao terminar.

Toque, digitação de underscore e fechamento de janelas foram confirmados no NX591J em imagens anteriores. A revisão importada ainda precisa ser testada no aparelho, em especial o ajuste de brilho, a pausa dos processos gráficos fora dos serviços e a validação de estabilidade. O armazenamento utilizável na última imagem gravada é de 2 GiB em uma partição de cerca de 52,55 GiB. A expansão do ext4 e a ativação automática continuam pendentes.
