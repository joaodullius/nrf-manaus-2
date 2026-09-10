# Dia 5 — Segurança Embarcada — 4h

Módulo **teórico**: o que a plataforma Nordic oferece de segurança embarcada, chip a chip, e como
isso aparece no nRF Connect SDK v3.4.0. Sem labs e sem demo de bancada; os samples do SDK são
citados como referência de onde cada mecanismo está.

**Hardware de referência:** nRF54LM20-DK (CRACEN, KMU) e nRF9151-SMA-DK (CryptoCell 310, KMU,
modem com armazenamento próprio de credenciais). Os dois kits já estão na sala pelos outros
módulos; aqui servem como os dois exemplos concretos de cada tema.

## Decks

Os quatro decks ficam no repositório de documentação, em `doc/security/`, e são gerados por
`doc/_template/build_m3_0x.py`.

| Deck | Tema | O que cobre da súmula |
|------|------|-----------------------|
| **M3-01** Root of Trust, Secure Boot e Secure Update | raiz de confiança, NSIB e MCUboot por família, chaves e revogação, APPROTECT, transportes de atualização, sessão SMP autenticada, imagem cifrada, FOTA por BLE e por LTE, FOTA do modem | RoT e Secure Boot; a demo `secure_fota_ble` em teoria |
| **M3-02** Isolamento com Arm TrustZone | SPE e NSPE, SPU no nRF91 contra MPC e SAU no nRF54L, o mapa de memória como tabela de atribuição, a app celular sempre em `/ns`, custo da chamada segura | TrustZone; a demo `trustzone_partition` em teoria |
| **M3-03** Trusted Firmware-M | perfis e maturidade, serviços, chaves e HUK, ITS e PS, partição custom com periférico seguro, ciclo de vida PRoT e atestação, o modem do nRF91 como segundo domínio | TF-M; a demo `tfm_secure_service` em teoria |
| **M3-04** Criptografia, certificação e regulação | CryptoCell 310 contra CRACEN, pilha PSA Crypto e drivers, KMU, PSA Certified e SESIP, RED DA e EN 18031, SBOM e PSIRT, estado da PQC no NCS | Criptografia e certificação; diretrizes; roadmap PQC; a demo `pqc_demo` em teoria |

## Tópicos teóricos

- Root of Trust (RoT) e Secure Boot — princípios de inicialização segura
- Isolamento de hardware via Arm TrustZone
- Trusted Firmware-M (TF-M)
- Criptografia e certificação — diretrizes de segurança para dispositivos conectados; estado atual e roadmap para criptografia pós-quântica

## Fonte

[`LEVANTAMENTO_NCS.md`](LEVANTAMENTO_NCS.md) é o levantamento que sustenta os decks: para cada
item da súmula, o que existe na árvore do NCS v3.4.0 (samples que listam os dois kits, Kconfigs,
overlays) e o que a documentação da Nordic afirma (maturidade *Supported* ou *Experimental*,
limites, o que só existe em versões posteriores do SDK). Cada afirmação diz de qual das duas
fontes veio. Nada foi compilado nem gravado para este módulo.
