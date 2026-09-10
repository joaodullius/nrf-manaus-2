# Segurança Embarcada — o que o NCS v3.4.0 e a documentação Nordic oferecem

Levantamento feito em 2026-09-10 sobre os itens da súmula do dia 5 (`security/README.md`),
para os dois kits do curso que têm plataforma de segurança:

- **nRF54LM20-DK, variante B** — `nrf54lm20dk/nrf54lm20b/cpuapp` e `.../cpuapp/ns`
  (CRACEN, KMU, sem modem);
- **nRF9151-SMA-DK** — `nrf9151dk/nrf9151/ns` (CryptoCell 310, KMU, modem LTE com o
  próprio armazenamento de credenciais).

O SDK é o **nRF Connect SDK v3.4.0** instalado em `C:\ncs\v3.4.0`.

Cada afirmação vem de uma de duas fontes, e o texto diz qual: **[tree]** é o que está no
SDK instalado (`sample.yaml`, `Kconfig`, overlays, devicetree); **[doc]** é a documentação
da Nordic consultada pelo MCP (release notes, guias do NCS, datasheets, AT Commands
Reference, whitepaper *Nordic platform security* nwp_057, nRF Cloud docs, Academy). Onde
a doc "latest" descreve algo que **não** está no v3.4.0, está marcado.

Níveis de maturidade citados são os da Nordic: *Supported* ou *Experimental*.

## 1. As duas plataformas, lado a lado

| Recurso | nRF54LM20B | nRF9151 | Fonte |
|---|---|---|---|
| Acelerador criptográfico | CRACEN (mascarado contra DPA) | Arm CryptoCell 310: AES-128, SHA-1/256, RSA ≤2048, ECC ≤521 bits, Ed/Curve25519, ChaCha20 | datasheets [doc] |
| TRNG | NIST SP 800-90B | NIST SP 800-90B, FIPS 140-2, AIS-31 | [doc] |
| TrustZone | IDAU preset + SAU + **MPC** (memória) + SPU (periféricos) | **SPU** controla o IDAU; a SAU fica desligada; blocos de 32 KB de flash e 8 KB de RAM | datasheets [doc] |
| Armazenamento de chaves | KMU + IKG do CRACEN | KMU (empurra chave direto para o AES/ChaCha) + KDR/KPRTL do CryptoCell | [doc] |
| HUK (chave única de hardware) | MKEK, MEXT, IKG — *Supported* | KDR, MKEK, MEXT — *Supported* | tabela de maturidade [doc] |
| Boot imutável | `UICR.BOOTCONF` aplicado por hardware antes do CPU; NSIB **não** com MCUboot no LM20A | NSIB (B0) *Supported*, com dados em **OTP do UICR**; NSIB + MCUboot em dois estágios | [doc] |
| Chave do MCUboot | ED25519 no CRACEN, chave pública no **KMU**, revogação em runtime | ECDSA P-256 verificada pelo `nrf_cc310_bl`, chave pública embutida na imagem do MCUboot | `Kconfig.mcuboot` [tree], [doc] |
| TF-M perfil mínimo / configurável | Experimental / Experimental | **Supported** / Experimental | [doc] |
| TF-M Crypto Service | Experimental | Experimental | [doc] |
| Atestação PSA (IAK no KMU) | sem sample para o LM20 | `tfm_psa_template` + `provisioning_image` — *Supported* | [tree] |
| APPROTECT | HW + SW (Kconfig) | HW + SW no nRF91x1 (no nRF9160 só HW); SECUREAPPROTECT separado; `ERASEPROTECT` | [doc] |
| Debug autenticado (ADAC) | mailbox no silício, sem suporte no NCS | não existe | nwp_057 [doc] |
| Segurança física (tamper, glitch, shield) | sim | não | nwp_057 [doc] |
| PQC (ML-DSA / ML-KEM) | Oberon em software no 3.4.0; verify no CRACEN só no 3.4.99 | Oberon em software; CC310 não acelera | tabelas [doc] |
| PSA Certified (alvo) | Level 3 para L15/L10/L05; o LM20 não consta na tabela | **Level 2** (nRF9160 e nRF9151) | nwp_057 [doc] |
| Rádio para FOTA | BLE (SMP) | LTE-M/NB-IoT (HTTP, nRF Cloud MQTT/CoAP, LwM2M); sem BLE | [tree] |
| Só no modem | — | credential store `%CMNG`, TLS/DTLS 1.2 dentro do modem, `%KEYGEN`, `%ATTESTTOKEN`, `%JWT`, firmware do modem assinado e cifrado pela Nordic | AT Commands [doc] |

O que a tabela diz para o desenho do módulo: o **LM20 é a plataforma nova** (CRACEN, chave
do bootloader no KMU, revogação, tamper), mas com quase tudo *Experimental* no NCS 3.4.0;
o **nRF9151 é a plataforma madura** (TF-M *Supported*, NSIB *Supported*, atestação com
sample) e ainda traz um segundo domínio de segurança que o LM20 não tem: o modem. As
quatro demos da súmula cabem no LM20; **atestação, boot em dois estágios e credenciais
que nunca saem do chip** só dá para mostrar no nRF9151.

## 2. Item a item da súmula — nRF54LM20-DK

### 2.1 `secure_fota_ble/` — FOTA assinada por BLE, com autenticação obrigatória

**Tem tudo no SDK instalado.**

| Peça | Onde | Estado |
|---|---|---|
| Sample de SMP server com MCUboot, BLE, alvo LM20 A e B | `nrf/samples/dfu/smp_svr` + `overlay-bt.conf`, overlays de placa `nrf54lm20dk_nrf54lm20b_cpuapp*.overlay` [tree] | pronto para compilar |
| Assinatura ED25519 verificada pelo **CRACEN** no MCUboot | `SB_CONFIG_BOOT_SIGNATURE_TYPE_ED25519` (padrão no nRF54); opcional `..._PURE` (assinatura sobre a imagem, não sobre o hash) [doc] | Supported |
| Chave pública no **KMU** em vez de embutida no bootloader | `SB_CONFIG_MCUBOOT_SIGNATURE_USING_KMU`; provisionamento automático com `west flash --erase`/`--recover` via `SB_CONFIG_MCUBOOT_GENERATE_DEFAULT_KEY_FILE` [doc]; KMU disponível no LM20 [doc] | Supported |
| **Autenticação obrigatória** da sessão SMP | `CONFIG_MCUMGR_TRANSPORT_BT_PERM_RW_AUTHEN=y` força pareamento antes de acessar as características SMP [doc]. **O `overlay-bt.conf` do sample vem sem isso** ("unauthenticated") [tree]: é a linha que a demo liga | a demo mostra o antes e o depois |
| Cliente | app **nRF Device Manager** (Android/iOS) ou `nrfutil mcu-manager ble` com `--pair --bond --secure-connection --mitm` [doc] | pronto |
| Proteção contra downgrade em hardware | MCUboot no nRF54L, desde o NCS 3.1 [doc] | Supported |
| Revogação de chave em runtime | `CONFIG_BOOT_KEYS_REVOCATION` + `CONFIG_BOOT_SIGNATURE_KMU_SLOTS`; tem de ser ligado no primeiro build, a última chave não se revoga [doc] | Experimental |
| **Imagem cifrada** (AES + ECIES-X25519) | `nrf/samples/dfu/mcuboot_with_encryption`, alvo LM20 A e B [tree]; limitações: só com ED25519, não em direct-xip, chave privada ECIES não vai ao KMU [doc] | Experimental |
| Atualização comprimida | `nrf/samples/dfu/compressed_update`, alvo LM20 [tree] | — |
| FOTA em cima de um app do curso | `CONFIG_NCS_SAMPLE_MCUMGR_BT_OTA_DFU=y` + `SB_CONFIG_BOOTLOADER_MCUBOOT=y` em qualquer sample periférico (a doc usa `peripheral_lbs`, que lista o LM20) [doc, tree] | reaproveita um lab do módulo 2 |

**NSIB (bootloader imutável da Nordic) + MCUboot:** a página *Configuring DFU and MCUboot*
diz que **o nRF54LM20A não suporta essa combinação** e que NSIB sozinho não é suportado
[doc]; `nrf/samples/bootloader/sample.yaml` não lista o LM20 [tree]. Porém o `smp_svr`
traz `nrf54lm20dk_nrf54lm20b_cpuapp_nsib.overlay` [tree]. **Conferir na bancada.** O caminho
seguro para a demo é **MCUboot como bootloader imutável de primeiro estágio**, que é o que a
Nordic descreve para o nRF54L (com `fprotect` travando a região) [doc].

Demo possível em 4 passos: build com MCUboot + KMU; FOTA pelo app sem pareamento
(funciona); religar com `PERM_RW_AUTHEN` (o app pede pareamento antes de listar imagens);
tentar uma imagem assinada com outra chave (MCUboot recusa e mantém a anterior).

### 2.2 `trustzone_partition/` — secure / non-secure com Arm TrustZone

**Tem no SDK instalado**, com uma ressalva de maturidade.

- Alvo `nrf54lm20dk/nrf54lm20b/cpuapp/ns` existe e inclui o TF-M automaticamente [tree,
  doc]. A app é compilada como imagem não segura; o TF-M é a imagem segura; o build funde
  as duas num hex só [doc].
- `nrf/samples/tfm/tfm_hello_world` lista o LM20 A e B [tree]: chama PSA (SHA-256, RNG) e
  o serviço de plataforma do TF-M para ler FICR — e imprime a **latência da chamada
  segura** ("Approximate IPC overhead us") [tree]. É o número a medir no LM20.
- Como a partição é definida [doc]: os nós de devicetree `slot0_s_partition`/`sram0_s` são
  seguros e `slot0_ns_partition`/`sram0_ns`/`storage_partition` não seguros; no nRF54L quem
  impõe é **MPC + SAU** (no nRF53/91 era o SPU), com fronteiras em múltiplos de
  `CONFIG_NRF_TRUSTZONE_FLASH_REGION_SIZE`/`RAM_REGION_SIZE`. Periféricos seguros ficam no
  alias `0x5...` e não seguros em `0x4...`; o SPU controla a associação de periféricos,
  GPIO por pino e canais de PPI [doc, datasheet].
- Demo natural: a app NS lê memória que o TF-M marcou como segura e recebe **bus fault**
  do MPC; depois pede a mesma leitura pelo serviço de plataforma (é o que o hello world
  faz com o FICR).
- `CONFIG_TFM_LOG_NS_MEMORY_LAYOUT`, que imprime a configuração de SAU e MPC no boot, **só
  existe no 3.4.99** [doc]; no 3.4.0 o mapa sai do `.dts` e do log do TF-M.
- Maturidade: TF-M no LM20 é **Experimental** nos dois perfis [doc]. O material precisa
  dizer isso.

### 2.3 `tfm_secure_service/` — serviço seguro via TF-M

**Tem no SDK instalado**, e é o item mais rico.

- `nrf/samples/tfm/tfm_secure_peripheral` lista o LM20 A e B [tree]: partição customizada
  (`secure_peripheral_partition/`, com manifesto YAML, `CMakeLists.txt` e o código da
  partição), um **periférico configurado como seguro** (`CONFIG_NRF_TIMER1_SECURE=y`, pinos
  de GPIO por bitmask `CONFIG_NRF_GPIO0_PIN_MASK_SECURE`), interrupção segura e um serviço
  chamado da app NS pela API de cliente PSA (`psa_call`) [tree, doc]. Opcionalmente com
  analisador lógico para ver o periférico seguro pulsando [doc].
- Serviços de TF-M disponíveis no NCS [doc]: Platform, **Crypto** (PSA Crypto API 1.4),
  **ITS** e **PS** (PSA Storage 1.0), **Initial Attestation** (PSA Attestation 1.0).
  Firmware Update **não** (o NCS usa MCUboot/NSIB no lugar).
- Chaves: com TF-M no nRF54L, o **KMU** substitui o ITS como armazenamento de chave; o
  TF-M pode filtrar chaves do KMU e do IKG do CRACEN para só o mundo seguro ver [doc].
  `nrf/samples/crypto/kmu_cracen_usage` e `persistent_key_usage` listam o LM20 [tree] e
  mostram chave persistente no KMU, provisionada pelo `nrfutil` a partir de um `keys.json`.
- `tfm_psa_template` (atestação + provisionamento) **não** lista o LM20: só nRF5340 e
  nRF91 [tree]. `keys/hw_unique_key` idem [tree]. Atestação no LM20 fica como teoria —
  **no nRF9151 tem sample** (§3.3).
- Maturidade: TF-M Crypto Service no LM20 é **Experimental** [doc].

Demo natural: a app NS pede uma assinatura com uma chave que só existe no KMU e nunca vê a
chave; tenta ler o TIMER1 seguro e leva bus fault; o serviço custom da partição responde.

### 2.4 `pqc_demo/` — criptografia pós-quântica

**Parcialmente no SDK instalado; a doc "latest" está adiante do 3.4.0.**

| O que | v3.4.0 instalado | doc latest (3.4.99 / 3.5) |
|---|---|---|
| ML-DSA (FIPS 204) 44/65/87 pela PSA API | `PSA_WANT_ALG_ML_DSA`, `PSA_WANT_ML_DSA_KEY_SIZE_65`, key pair import/export e public key existem no `Kconfig.psa.nordic`; o driver **nrf_oberon** implementa verify e sign de mensagem (`PSA_NEED_OBERON_ML_DSA_VERIFY`, `..._MESSAGE_ML_DSA`) [tree] — **software**, Experimental [doc] | verificação ML-DSA **acelerada pelo CRACEN** ("only supports signature verification") [doc]; sample `nrf/samples/crypto/ml_dsa` (verifica ML-DSA-65; alvos só nRF54L: LM20, L15, L10, L05, LV10) [doc] — **não está no 3.4.0** [tree] |
| ML-KEM (FIPS 203) 512/768/1024 | `PSA_WANT_ALG_ML_KEM`, `PSA_WANT_ML_KEM_KEY_SIZE_768` no Kconfig [tree]; Oberon, Experimental [doc] | idem |
| Hash-based (LMS/HSS, XMSS/XMSS-MT) | Oberon, Experimental, em todas as famílias [doc]; sem aceleração | — |
| Assinatura PQC no MCUboot | não há no NCS [doc]; o BL1 do TF-M upstream usa LMS, mas a Nordic não usa BL1 [doc] | — |
| Roadmap declarado pela Nordic | nenhuma afirmação além de "Experimental" e "PSA Crypto API 1.4 PQC Extension" [doc] | — |

Caminho para a demo no 3.4.0: uma app freestanding no molde de `nrf/samples/crypto/eddsa`
(mesma estrutura, mesmas chamadas PSA) que importa uma chave pública ML-DSA-65 e verifica
uma assinatura gerada no PC (`liboqs` ou `pqcrypto` em Python), comparando com ED25519 no
mesmo firmware: tamanho de chave (1952 B contra 32 B), de assinatura (3309 B contra 64 B),
tempo de verificação e FLASH. O sample `ml_dsa` do `main` serve de referência de código
(licença Nordic 5-Clause, mesma do SDK), mas o firmware do curso compila no 3.4.0 com o
Oberon, não com o CRACEN — e o material diz isso. A mesma app compila para o nRF9151, e
os dois números lado a lado (Cortex-M33 a 128 MHz contra 64 MHz, ambos em software) são
um slide.

### 2.5 Tópicos teóricos

| Tópico da súmula | Fonte primária para o deck | O que dá para mostrar no LM20 |
|---|---|---|
| Root of Trust e Secure Boot | nwp_057 (*Nordic platform security*): PRoT/IRoT/URoT, cadeia de confiança, etapas do boot seguro; Academy *nRF54L Series express course*, lição 4; datasheet: `BOOTCONF`, `USER.ROT.PUBKEY[n].REVOKE` | MCUboot imutável com `fprotect`, chave no KMU, downgrade protection, revogação, `nrfutil device protection-set All` (APPROTECT) e o custo: só `nrfutil device recover` (ERASEALL) reabre |
| Arm TrustZone | datasheet cap. *Security*: IDAU preset (0x4 NS / 0x5 S), SAU, MPC, SPU, split peripherals; tabela de atributos S/NS/NSC | o `.dts` do `/ns`, o bus fault do MPC, o alias 0x5 |
| TF-M | *TF-M support and limitations*: TF-M 2.3.0, Mbed TLS 4.1.0, perfis minimal/configurable, serviços; *TF-M memory partitioning* | `tfm_hello_world` (latência da chamada), `tfm_secure_peripheral` |
| Criptografia e certificação; PQC | *PSA Certified Security Framework overview* (APIs suportadas e versões); *Supported cryptographic operations* (tabelas por SoC); nwp_057 cap. *Device certification* (níveis PSA 1/2/3); tabelas ML-DSA/ML-KEM | `kmu_cracen_usage`; a app de ML-DSA da §2.4 |

## 3. Item a item da súmula — nRF9151 (família nRF9x)

O kit do curso é o **nRF9151-SMA-DK** (mesmo alvo `nrf9151dk/nrf9151/ns`). Duas regras da
plataforma que valem para todo o módulo:

1. **Toda app celular roda em NSPE, com TF-M.** A biblioteca do modem exige rodar no
   ambiente não seguro, com IPC e POWER não seguros e a memória compartilhada com o modem
   nos primeiros 128 KB de RAM, como bloco não seguro (`sram0_ns_modem`) [doc]. Por isso
   todos os samples celulares só listam `/ns` [tree]. No nRF91 o TrustZone não é opcional:
   ele já está em cada lab de GNSS e de NTN do curso, sem que o aluno tenha percebido.
2. **O modem é um segundo domínio de segurança**, com o próprio armazenamento de
   credenciais, a própria pilha TLS e o próprio boot seguro, fora do alcance do Cortex-M33.

### 3.1 FOTA assinada — o equivalente ao `secure_fota_ble/`

O nRF9151 não tem BLE; a FOTA é pelo rádio LTE. Três camadas, todas com sample para o
9151 [tree]:

| Camada | Sample (todos `nrf9151dk/nrf9151/ns`) | O que verifica a assinatura |
|---|---|---|
| Aplicação (+ TF-M, tratados como uma imagem só) | `cellular/http_update/application_update`; `cellular/nrf_cloud_mqtt_fota`; `cellular/nrf_cloud_coap_fota`; `cellular/lwm2m_client` | **MCUboot**, ECDSA P-256 (padrão para `SOC_SERIES_NRF91` em `nrf/sysbuild/Kconfig.mcuboot`) via `nrf_cc310_bl` [tree, doc]. Downgrade protection por contador monotônico (HW) ou versão semântica (SW) [doc] |
| Bootloader atualizável | idem, com `SB_CONFIG_SECURE_BOOT_APPCORE=y` (tipo `"BOOT"` no nRF Cloud) | **NSIB** verifica o MCUboot em S0/S1, ECDSA P-256, hashes de chave pública em **OTP do UICR**, contador monotônico em OTP, revogação das chaves de índice menor [doc] |
| Firmware do modem | `cellular/http_update/modem_delta_update` (delta, sem memória externa); `modem_full_update` e `fmfu_smp_svr` (imagem completa, precisa de flash externa ≥ 4 MB — a nRF9151 DK tem GD25WB256 de 32 MB no `spi3`, `status = "disabled"` por padrão [tree]; **conferir se a SMA-DK também tem**) | O **próprio modem**: os arquivos vêm assinados e cifrados pela Nordic, o modem verifica e decifra; rollback automático se o boot falhar [doc] |

Peças em comum: `fota_download` + `dfu_target` (identificam o tipo pelo header e
despacham para MCUboot, modem delta ou FMFU) [doc]; o app do nRF Cloud publica
`fota_v2: ["APP","MODEM","MDM_FULL","BOOT"]` no shadow [doc]. Academy: *nRF Connect SDK
Intermediate*, lição 9, exercício 7 (FOTA por LTE-M) [doc].

O que **não** tem no nRF91: chave do MCUboot no KMU (só nRF54L), revogação em runtime de
chave do MCUboot (só nRF54L), imagem cifrada com ECIES (só nRF54L), NSIB no LM20A
(inverso: no nRF91 o NSIB é *Supported*) [doc].

Demo possível (kit do instrutor, LTE em sala): FOTA de aplicação por HTTP com
`application_update`; depois a mesma imagem assinada com outra chave, recusada pelo
MCUboot; depois um delta de modem (arquivo `mfw_nrf91x1_2.0.x_...delta`) aplicado pelo
modem sem passar pelo MCUboot.

### 3.2 TrustZone — o equivalente ao `trustzone_partition/`

- `tfm/tfm_hello_world` e `tfm/tfm_secure_peripheral` listam `nrf9151dk/nrf9151/ns`
  [tree]: as mesmas demos do LM20 rodam no 9151, com o **perfil mínimo *Supported*** [doc].
- No nRF91 a atribuição é feita pelo **SPU**: flash em blocos de 32 KB, RAM em blocos de
  8 KB; `slot0_ns_partition`, `slot1_ns_partition` e `storage_partition` marcam o bloco como
  não seguro; um bloco de 32 KB não pode misturar seguro e não seguro [doc]. O SPU também
  protege pinos e canais DPPI, e bloqueia EasyDMA de periféricos não seguros ("TrustZone
  estendido"); violação vira SecureFault (CPU) ou evento do SPU (DMA), com política
  read-as-zero/write-ignore [datasheet].
- Layouts prontos em `nrf/dts/samples/cellular/` (`nrf91_no_bootloader_partitions.dtsi`,
  `nrf91_bootloader_partitions.dtsi`, `nrf91_immutable_bootloader_partitions.dtsi`,
  `nrf91_crypto_partitions.dtsi`, `nrf91_sram_partitions.dtsi`) [doc]: são o material
  didático do "como se desenha a partição".
- Diferença didática contra o LM20: no nRF91 a SAU fica desligada e o SPU manda no IDAU;
  no nRF54L é MPC + SAU. Um slide de comparação.

### 3.3 Serviço seguro e atestação — o equivalente ao `tfm_secure_service/`

Aqui o nRF9151 tem **mais** que o LM20 no 3.4.0:

| Sample | Alvo 9151 | O que mostra |
|---|---|---|
| `tfm/tfm_secure_peripheral` | `/ns` | partição custom + periférico seguro, igual ao LM20 |
| `tfm/provisioning_image` | secure-only | leva o chip de *Device Assembly and Test* para *PRoT Provisioning*: gera HUKs (MKEK, MEXT) no KMU e uma **identity key secp256r1** no KMU, cifrada com a MKEK, que vira a **Initial Attestation Key** [tree, doc] |
| `tfm/tfm_psa_template` | `/ns` | com `CONFIG_TFM_NRF_PROVISIONING` o TF-M passa o chip para *Secured* no primeiro boot e emite o **token de atestação inicial** (PSA Attestation 1.0, "Received initial attestation token of 360 bytes") [tree, doc]; inclui MCUboot e DFU |
| `keys/hw_unique_key` | ambos | deriva chave da HUK por rótulo e cifra um texto; HUK no KMU, KDR carregado no CryptoCell [tree, doc] |
| `keys/identity_key_usage` | secure-only | lê a identity key do KMU e assina com ela [tree] |
| `crypto/persistent_key_usage`, `crypto/psa_tls`, `crypto/{ecdsa,eddsa,...}` | ambos | PSA Crypto no CC310 (`nrf_cc3xx`, *Supported*) [tree, doc] |

Cuidado de bancada [doc]: depois do `provisioning_image` o chip não volta ao estado
anterior sem `--erase`, e um **ERASEALL apaga a identity key do UICR**. Fazer só em kit do
instrutor.

### 3.4 PQC no nRF9151

ML-DSA, ML-KEM, LMS/HSS e XMSS existem para o nRF91 pelo **nrf_oberon em software**,
*Experimental*; o CC310 não acelera nenhum deles e o sample `ml_dsa` do 3.4.99 não lista
nenhum nRF91 [doc]. A app freestanding da §2.4 compila para o 9151 sem mudança.

### 3.5 O que só o modem oferece (não está na súmula, mas é o material mais concreto)

| Mecanismo | Como funciona | Onde no NCS 3.4.0 |
|---|---|---|
| **Credential store** (`%CMNG`) | Tipos 0 CA, 1 cert de cliente, 2 chave privada, 3 PSK, 4 PSK id, 5 chave pública p/ AT autenticado, 6 identity pública, 8 endorsement, 9 ownership, 10/11 raízes Nordic, 13 asset encryption key. **Chave privada, cert de cliente e PSK são write-only**: escreve, não lê. Escrita só com modem offline (`+CFUN=4`). Cada conjunto tem um `sec_tag` [AT Commands doc] | lib `modem_key_mgmt`; ferramenta `nrfcredstore` (Python, por cima do `at_client`); app Cellular Monitor [doc] |
| **TLS/DTLS 1.2 dentro do modem** | o socket recebe o `sec_tag` via `nrf_setsockopt(NRF_SO_SEC_TAG_LIST)` e `NRF_SO_SEC_PEER_VERIFY`; o handshake e a chave privada ficam no modem; a app nunca vê o segredo [doc]. Cipher suites: ECDHE-ECDSA/RSA com AES-CBC/GCM, PSK; `sec_tag`s 2147483648–2147483667 permitem decifrar o tráfego nas ferramentas Nordic (**só para depuração**) [doc] | `cellular/tls_ciphersuites`, `net/https_client`, `net/mqtt` (todos `nrf9151dk/nrf9151/ns`) [tree] |
| **Par de chaves gerado no modem** (`%KEYGEN`) | gera a chave no modem e devolve CSR ou chave pública em CBOR/COSE; a privada nunca sai [doc] | `nrfcredstore generate`; Azure IoT Hub e nRF Cloud usam esse fluxo [doc] |
| **Identidade Nordic** (`%ATTESTTOKEN`) | identidade injetada em produção; o token traz UUID do chip e UUID do firmware do modem, assinado (COSE) [doc] | lib `modem_attest_token`; é o que o nRF Cloud usa para *claim* do dispositivo [doc] |
| **JWT assinado pelo modem** (`%JWT`) | o modem assina um JWT com a identity key; é a autenticação do dispositivo no serviço de provisionamento [doc] | lib `modem_jwt`; lib `nrf_provisioning` (`CONFIG_NRF_PROVISIONING`) + sample `cellular/nrf_device_provisioning` (`nrf9151dk/nrf9151/ns`) [tree] |
| **Boot seguro do modem** | firmware do modem entregue assinado e cifrado; o modem verifica; delta cifrado e assinado; rollback automático [doc] | `nrf_modem_delta_dfu_*`, `nrf_modem_bootloader` (FMFU) [doc] |
| **AT autenticado** (`%XSUDO`, tipo 5) | comandos sensíveis exigem assinatura com chave cuja pública está no tipo 5 [AT Commands doc] | referência apenas |

Demo natural: gravar CA + cert + chave num `sec_tag` pelo `nrfcredstore`, listar com
`AT%CMNG=1` (a chave aparece como existente mas não se lê), abrir um `https_client` contra
um servidor com verificação estrita, depois trocar a CA e ver o handshake falhar. Segunda
demo: `AT%ATTESTTOKEN` decodificado com `modem_credentials_parser.py` (repositório
`nRFCloud/utils`), mostrando o UUID e o UUID do firmware do modem.

### 3.6 APPROTECT no nRF9151

`nrfutil device protection-set All` (APPROTECT) e `SecureRegions` (SECUREAPPROTECT);
`nrfutil device recover` (ERASEALL) desfaz. No nRF91x1 a proteção vem **ligada de fábrica**
e religa a cada hard reset; o NCS desliga por software com `CONFIG_NRF_APPROTECT_USE_UICR`
(padrão), ou deixa ligada com `CONFIG_NRF_SECURE_APPROTECT_USER_HANDLING`. `ERASEPROTECT`
existe e, ligado junto com APPROTECT, **inutiliza o chip para o desenvolvedor** [doc].
Não há debug autenticado no nRF91 [nwp_057].

## 4. Samples do NCS v3.4.0 que compilam para os kits [tree]

### nRF54LM20-DK (A e B)

```
nrf/samples/dfu/smp_svr                   BLE + MCUboot (overlay-bt.conf)
nrf/samples/dfu/mcuboot_with_encryption   imagem cifrada (Experimental)
nrf/samples/dfu/compressed_update         imagem comprimida
nrf/samples/dfu/single_slot               MCUboot single slot
nrf/samples/tfm/tfm_hello_world           TF-M + PSA + platform service    (/ns)
nrf/samples/tfm/tfm_secure_peripheral     partição custom + periférico S   (/ns)
nrf/samples/crypto/kmu_cracen_usage       chaves no KMU
nrf/samples/crypto/persistent_key_usage   chave persistente
nrf/samples/crypto/{aes_*,ecdsa,eddsa,ecdh,sha256,hmac,rng,...}
nrf/samples/bluetooth/peripheral_lbs      + CONFIG_NCS_SAMPLE_MCUMGR_BT_OTA_DFU
```

Não compilam para o LM20: `bootloader` (NSIB), `tfm/tfm_psa_template`,
`tfm/provisioning_image`, `keys/hw_unique_key`, `keys/identity_key_*`; não existe
`crypto/ml_dsa`.

### nRF9151-DK (`nrf9151dk/nrf9151` e `/ns`)

```
nrf/samples/bootloader                          NSIB (B0), OTP do UICR
nrf/samples/tfm/tfm_hello_world                 (/ns)
nrf/samples/tfm/tfm_secure_peripheral           (/ns)
nrf/samples/tfm/tfm_psa_template                atestação + MCUboot + DFU (/ns)
nrf/samples/tfm/provisioning_image              HUK + identity key no KMU (secure-only)
nrf/samples/keys/hw_unique_key                  ambos
nrf/samples/keys/identity_key_usage             secure-only
nrf/samples/crypto/psa_tls, persistent_key_usage, ecdsa, eddsa, ...   ambos
nrf/samples/cellular/http_update/application_update      FOTA app por HTTP (/ns)
nrf/samples/cellular/http_update/modem_delta_update      delta do modem (/ns)
nrf/samples/cellular/http_update/modem_full_update       FMFU, flash externa (/ns)
nrf/samples/cellular/fmfu_smp_svr                        FMFU por SMP/UART (/ns)
nrf/samples/cellular/nrf_cloud_mqtt_fota, nrf_cloud_coap_fota   (/ns)
nrf/samples/cellular/nrf_device_provisioning             nrf_provisioning + JWT (/ns)
nrf/samples/cellular/tls_ciphersuites                    TLS no modem (/ns)
nrf/samples/cellular/lwm2m_client                        DTLS/PSK, bootstrap (/ns)
nrf/samples/cellular/modem_shell, at_client              AT%CMNG, %KEYGEN, %ATTESTTOKEN
nrf/samples/net/https_client, net/mqtt, net/download     TLS pelo modem (/ns)
```

Não compilam para o 9151: `dfu/smp_svr` (sem BLE), `crypto/kmu_cracen_usage` (sem
CRACEN), `crypto/ml_dsa` (3.4.99, só nRF54L).

## 5. Riscos e decisões que o desenho do módulo precisa tomar

1. **Maturidade.** TF-M e ML-DSA/ML-KEM são *Experimental* no LM20; no nRF9151 o TF-M
   mínimo, o NSIB e o PSA Crypto no CC310 são *Supported*. Se o módulo quiser um slide
   "isto é produção", ele aponta para o nRF9151.
2. **Hardware da súmula.** `security/README.md` lista só o LM20-DK. As demos de
   atestação, boot em dois estágios, credential store e modem FOTA só existem no nRF9151.
   Ou a súmula passa a listar os dois kits, ou esses temas ficam em teoria.
3. **NSIB no LM20.** Doc diz que não; existe overlay no sample. Bancada decide. Se não,
   o primeiro estágio é o MCUboot imutável, que é o que a Nordic recomenda para o nRF54L.
4. **Irreversibilidades na bancada.** KMU (LM20), `provisioning_image` (9151), APPROTECT
   e revogação de chave são operações que só `nrfutil device recover` desfaz — e no 9151
   o ERASEALL apaga a identity key. Fazer nos kits do instrutor, nunca no último slot.
5. **Rede em sala.** As demos de FOTA e provisionamento do 9151 precisam de LTE-M com
   dados (mesma APN privada dos labs de GNSS) e, para o nRF Cloud, de conta e *claim*
   feitos antes.
6. **Flash externa na SMA-DK.** A DK comum tem GD25WB256 no `spi3`; conferir a SMA-DK
   antes de prometer FMFU. O delta não precisa.
7. **RAM do `smp_svr` com BLE no LM20.** MTU 498, reassembly, LittleFS: conferir o tamanho e
   se cabe junto com o que mais a demo precisar.
8. **PQC no 3.4.0 é software** nas duas famílias. Ou o curso fica no 3.4.0 com Oberon e
   diz isso, ou o módulo usa um NCS mais novo só para o CRACEN — o que quebra a regra de
   um SDK só.
9. **Tempo.** 4 h para quatro demos e quatro blocos de teoria, agora com duas
   plataformas. Sugestão de corte: FOTA e serviço seguro no LM20 (BLE, KMU, CRACEN);
   TrustZone como comparação SPU × MPC nos dois; atestação e credential store no 9151;
   PQC como app única nos dois chips, 10 minutos.

## 6. O que este levantamento não conferiu

- Nada foi compilado nem gravado: os alvos vêm dos `sample.yaml`, não de build.
- O comportamento do app nRF Device Manager com `PERM_RW_AUTHEN` (a doc descreve o
  `nrfutil`; o app deve pedir pareamento, mas não foi testado).
- O nível PSA Certified do nRF54LM20 (a tabela do whitepaper só cobre L15/L10/L05; para o
  nRF9151 a tabela diz Level 2).
- A latência de chamada segura no LM20 e no 9151 (o número do sample é do nRF5340).
- A presença da flash externa na **SMA**-DK (o devicetree conferido é o da DK comum).
- Se o `mfw_nrf91x1_2.0.4` dos kits aceita `%KEYGEN`/`%ATTESTTOKEN` (a doc exige 2.0.0+,
  então deve).
