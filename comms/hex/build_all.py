#!/usr/bin/env python3
"""
build_all.py — gera os .hex de referencia dos labs do modulo de Comunicacao.

Duas classes de variante, e a diferenca importa:

  PUBLICA  — nao carrega credencial nenhuma. O .hex vai para comms/hex/ e e
             versionado. Sao os labs de Channel Sounding (o endereco do TAG nao e
             segredo) e os tres labs de Wi-Fi que nao precisam da rede da sala.
  LOCAL    — precisa da credencial da rede Wi-Fi (minha_rede.conf preenchido).
             O .hex sai em build/hex/_local/ e NUNCA e versionado: um hex com a
             senha da rede embutida e a senha em claro, so que mais dificil de ver.

Uso (de qualquer pasta):
    python comms/hex/build_all.py                # todas as que der para compilar
    python comms/hex/build_all.py 06 08          # so as que comecam com 06 ou 08
    python comms/hex/build_all.py --list
    python comms/hex/build_all.py --publicas     # so as versionaveis

Para as variantes LOCAL, aponte a credencial por variavel de ambiente:
    set COMMS_REDE_CONF=C:\\rede\\minha_rede.conf     (arquivo ja preenchido)
    set COMMS_SERVIDOR_IP=192.168.15.15               (opcional, o IP do PC)
Sem isso elas sao PULADAS, nao falham.

Requisitos: nRF Connect SDK v3.4.0 em C:/ncs/v3.4.0 (o west roda de la) e os
blobs do nRF70 baixados (`west blobs fetch nrf_wifi`) — ver PREREQUISITOS.md.
"""

import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMS = REPO / "comms"
HEX = COMMS / "hex"
BUILD = REPO / "build" / "hex"
LOCAL_OUT = BUILD / "_local"
NCS_WS = Path(r"C:/ncs/v3.4.0")
NCS_VER = "v3.4.0"

TAG = "nrf54l15tag/nrf54l15/cpuapp"
LM20 = "nrf54lm20dk/nrf54lm20b/cpuapp"
EB2 = "nrf7002eb2"

# Endereco do TAG da bancada de referencia — o MESMO do edge_ai/hex. Vem do chip,
# nao do firmware, e nao e segredo: quem tiver outro TAG recompila com o seu.
TAG_ADDR_VALUE = "EC:EF:40:2D:5E:46"
TAG_ADDR_TYPE = "random"

SERVIDOR_IP = os.environ.get("COMMS_SERVIDOR_IP", "192.168.15.15")


# ------------------------------------------------------------- fragmentos .conf
def conf_tag():
    """Endereco do TAG de referencia, gerado fora do repo."""
    p = BUILD / "meu_tag_referencia.conf"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'CONFIG_LAB_TAG_ADDR_VALUE="{TAG_ADDR_VALUE}"\n'
                 f'CONFIG_LAB_TAG_ADDR_TYPE="{TAG_ADDR_TYPE}"\n', encoding="utf-8")
    return str(p).replace("\\", "/")


def conf_rede():
    """A credencial da rede, vinda de fora do repo. None se nao houver."""
    env = os.environ.get("COMMS_REDE_CONF")
    cand = [Path(env)] if env else []
    cand.append(BUILD / "minha_rede_local.conf")
    for p in cand:
        if p.exists() and 'SSID=""' not in p.read_text(encoding="utf-8"):
            return str(p.resolve()).replace("\\", "/")
    return None


# ----------------------------------------------------------------- as variantes
# nome do hex, app (relativo a comms/), board, extras do west, precisa_credencial
def wifi(app, *extras, snippet=True, shield=EB2):
    """Monta os -D<img>_* que o sysbuild exige, com o prefixo do nome da imagem."""
    img = Path(app).name
    args = ["--", f"-D{img}_SHIELD={shield}"]
    if snippet:
        args.append(f"-D{img}_SNIPPET=nrf70-wifi")
    args += [f"-D{img}_{e}" for e in extras]
    return args


VARIANTES = [
    # ---------------------------------------------------------- Channel Sounding
    ("01_cs_reflector_tag", "01_cs_reflector", TAG, [], False),
    ("01_cs_reflector_demo_tag", "01_cs_reflector", TAG,
     ["--", "-DEXTRA_CONF_FILE=android_ranging.conf;demo.conf;s26.conf"], False),
    ("02_cs_initiator_lm20", "02_cs_initiator", LM20,
     ["--", lambda: f"-DEXTRA_CONF_FILE={conf_tag()}"], False),
    ("02_cs_initiator_pbr_lm20", "02_cs_initiator", LM20,
     ["--", lambda: f"-DEXTRA_CONF_FILE={conf_tag()};pbr_only.conf"], False),
    ("03_cs_ipt_reflector_tag", "03_cs_ipt/reflector", TAG, [], False),
    ("03_cs_ipt_initiator_lm20", "03_cs_ipt/initiator", LM20,
     ["--", lambda: f"-DEXTRA_CONF_FILE={conf_tag()}"], False),
    ("05_cs_iq_music_lm20", "05_cs_iq_music", LM20,
     ["--", lambda: f"-DEXTRA_CONF_FILE={conf_tag()}"], False),
    ("05_cs_iq_music_demo_lm20", "05_cs_iq_music", LM20,
     ["--", lambda: f"-DEXTRA_CONF_FILE={conf_tag()};demo.conf"], False),

    # ------------------------------------------- Wi-Fi sem credencial (publicos)
    ("06_wifi_shell_lm20", "06_wifi_shell", LM20, wifi("06_wifi_shell"), False),
    ("08a_wifi_provisioning_lm20", "08a_wifi_provisioning", LM20,
     wifi("08a_wifi_provisioning", "EXTRA_CONF_FILE=meu_softap.conf"), False),
    # o 8b nao leva o snippet: e no-op nesta placa e o sample nao o usa
    ("08b_wifi_provisioning_ble_lm20", "08b_wifi_provisioning_ble", LM20,
     wifi("08b_wifi_provisioning_ble", snippet=False), False),

    # -------------------------------------------- Wi-Fi com credencial (locais)
    ("07_wifi_sta_lm20", "07_wifi_sta", LM20,
     wifi("07_wifi_sta", lambda: f"EXTRA_CONF_FILE={conf_rede()}"), True),
    ("09_wifi_tcp_lm20", "09_wifi_tcp", LM20,
     wifi("09_wifi_tcp", lambda: f"EXTRA_CONF_FILE={conf_rede()}",
          f'CONFIG_LAB_SERVIDOR_IP="{SERVIDOR_IP}"',
          "CONFIG_LAB_TRANSPORTE_TCP=y"), True),
    ("10_wifi_http_lm20", "09_wifi_tcp", LM20,
     wifi("09_wifi_tcp", lambda: f"EXTRA_CONF_FILE={conf_rede()}",
          f'CONFIG_LAB_SERVIDOR_IP="{SERVIDOR_IP}"',
          "CONFIG_LAB_TRANSPORTE_HTTP=y", "CONFIG_LAB_PORTA=8000"), True),
    ("10_wifi_mqtt_lm20", "09_wifi_tcp", LM20,
     wifi("09_wifi_tcp", lambda: f"EXTRA_CONF_FILE={conf_rede()}",
          f'CONFIG_LAB_SERVIDOR_IP="{SERVIDOR_IP}"',
          "CONFIG_LAB_TRANSPORTE_MQTT=y", "CONFIG_LAB_PORTA=1883"), True),
    ("11_wifi_twt_lm20", "11_wifi_twt", LM20,
     wifi("11_wifi_twt", lambda: f"EXTRA_CONF_FILE={conf_rede()}"), True),
    ("12_wifi_coex_on_lm20", "12_wifi_coex", LM20,
     wifi("12_wifi_coex", lambda: f"EXTRA_CONF_FILE={conf_rede()}",
          f'CONFIG_NET_CONFIG_PEER_IPV4_ADDR="{SERVIDOR_IP}"',
          "CONFIG_MPSL_CX=y", "CONFIG_COEX_SEP_ANTENNAS=y",
          shield="nrf7002eb2;nrf7002eb2_coex"), True),
    ("12_wifi_coex_off_lm20", "12_wifi_coex", LM20,
     wifi("12_wifi_coex", lambda: f"EXTRA_CONF_FILE={conf_rede()}",
          f'CONFIG_NET_CONFIG_PEER_IPV4_ADDR="{SERVIDOR_IP}"',
          "CONFIG_MPSL_CX=n", shield="nrf7002eb2;nrf7002eb2_coex"), True),
    ("13_wifi_location_lm20", "13_wifi_location", LM20,
     wifi("13_wifi_location", lambda: f"EXTRA_CONF_FILE={conf_rede()}",
          f'CONFIG_LAB_SERVIDOR_IP="{SERVIDOR_IP}"'), True),
]


def west(args):
    cmd = ["nrfutil", "sdk-manager", "toolchain", "launch", "--ncs-version", NCS_VER, "--",
           "west"] + args
    return subprocess.run(cmd, cwd=str(NCS_WS), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def acha_hex(build_dir, app):
    for cand in (build_dir / "merged.hex",
                 build_dir / Path(app).name / "zephyr" / "zephyr.hex",
                 build_dir / "zephyr" / "zephyr.hex"):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"nenhum hex em {build_dir}")


def tamanho(log):
    m = re.search(r"FLASH:\s+(\d+) B.*?RAM:\s+(\d+) B", log, re.S)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def build(nome, app, board, extra, segredo):
    build_dir = BUILD / nome
    app_dir = COMMS / app
    destino = (LOCAL_OUT if segredo else HEX)
    args = ["build", "-p", "-b", board, "--sysbuild",
            "-d", str(build_dir).replace("\\", "/"),
            str(app_dir).replace("\\", "/")]
    args += [a() if callable(a) else a for a in extra]
    r = west(args)
    log = r.stdout + r.stderr
    if r.returncode != 0:
        (BUILD / f"{nome}.log").write_text(log, encoding="utf-8")
        raise RuntimeError(f"west build falhou (log em build/hex/{nome}.log)")
    src = acha_hex(build_dir, app)
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, destino / f"{nome}.hex")
    return tamanho(log), src.name, destino


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if "--list" in flags:
        for nome, _, _, _, seg in VARIANTES:
            print(f"{nome:34s} {'LOCAL (credencial)' if seg else 'publica'}")
        return
    sel = [v for v in VARIANTES if not argv or any(v[0].startswith(p) for p in argv)]
    if "--publicas" in flags:
        sel = [v for v in sel if not v[4]]
    if not sel:
        sys.exit("nenhuma variante casa com " + " ".join(argv))

    tem_rede = conf_rede()
    if not tem_rede:
        print("sem credencial (COMMS_REDE_CONF ou build/hex/minha_rede_local.conf):"
              " as variantes LOCAL serao puladas")
    print(f"{len(sel)} variante(s) selecionada(s)")

    falhas = puladas = 0
    for nome, app, board, extra, segredo in sel:
        if segredo and not tem_rede:
            puladas += 1
            print(f"\n=== {nome}\n    PULADA (precisa da credencial)")
            continue
        print(f"\n=== {nome}  ({app} · {board})", flush=True)
        try:
            (flash, ram), origem, destino = build(nome, app, board, extra, segredo)
            onde = destino.relative_to(REPO).as_posix()
            print(f"    ok  {origem}  flash {flash:,} B  ram {ram:,} B  -> {onde}"
                  .replace(",", "."))
        except Exception as ex:  # noqa: BLE001
            falhas += 1
            print(f"    FALHOU: {ex}")
    print(f"\n{len(sel) - falhas - puladas} ok, {falhas} falha(s), {puladas} pulada(s)")
    if puladas:
        print("As puladas so saem com a credencial da rede, e o hex delas NAO vai"
              " para comms/hex/ — fica em build/hex/_local/.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
