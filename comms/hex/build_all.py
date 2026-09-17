#!/usr/bin/env python3
"""
build_all.py — gera os .hex de referencia dos labs do modulo de Comunicacao.

Nenhuma variante carrega credencial: nos labs de Wi-Fi que precisam da rede da
sala (07, 09/10, 11, 12, 13), SSID, senha e, quando ha servidor no PC, IP e
porta sao digitados no terminal serial no primeiro boot e gravados em settings
(src/lab_rede.c de cada lab). Por isso todos os .hex vao para comms/hex/ e sao
versionados.

Uso (de qualquer pasta):
    python comms/hex/build_all.py                # todas
    python comms/hex/build_all.py 06 08          # so as que comecam com 06 ou 08
    python comms/hex/build_all.py --list

Requisitos: nRF Connect SDK v3.4.0 em C:/ncs/v3.4.0 (o west roda de la) e os
blobs do nRF70 baixados (`west blobs fetch nrf_wifi`) — ver PREREQUISITOS.md.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMS = REPO / "comms"
HEX = COMMS / "hex"
BUILD = REPO / "build" / "hex"
NCS_WS = Path(r"C:/ncs/v3.4.0")
NCS_VER = "v3.4.0"

TAG = "nrf54l15tag/nrf54l15/cpuapp"
LM20 = "nrf54lm20dk/nrf54lm20b/cpuapp"
EB2 = "nrf7002eb2"


# ----------------------------------------------------------------- as variantes
# nome do hex, app (relativo a comms/), board, extras do west
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
    ("01_cs_reflector_tag", "01_cs_reflector", TAG, []),
    ("01_cs_reflector_demo_tag", "01_cs_reflector", TAG,
     ["--", "-DEXTRA_CONF_FILE=android_ranging.conf;demo.conf;s26.conf"]),
    ("02_cs_initiator_lm20", "02_cs_initiator", LM20, []),
    ("02_cs_initiator_pbr_lm20", "02_cs_initiator", LM20,
     ["--", "-DEXTRA_CONF_FILE=pbr_only.conf"]),
    ("03_cs_ipt_reflector_tag", "03_cs_ipt/reflector", TAG, []),
    ("03_cs_ipt_initiator_lm20", "03_cs_ipt/initiator", LM20, []),
    ("05_cs_iq_music_lm20", "05_cs_iq_music", LM20, []),
    ("05_cs_iq_music_demo_lm20", "05_cs_iq_music", LM20,
     ["--", "-DEXTRA_CONF_FILE=demo.conf"]),

    # -------------------------------------------------------------------- Wi-Fi
    ("06_wifi_shell_lm20", "06_wifi_shell", LM20, wifi("06_wifi_shell")),
    ("07_wifi_sta_lm20", "07_wifi_sta", LM20, wifi("07_wifi_sta")),
    ("08a_wifi_provisioning_lm20", "08a_wifi_provisioning", LM20,
     wifi("08a_wifi_provisioning", "EXTRA_CONF_FILE=meu_softap.conf")),
    # o 8b nao leva o snippet: e no-op nesta placa e o sample nao o usa
    ("08b_wifi_provisioning_ble_lm20", "08b_wifi_provisioning_ble", LM20,
     wifi("08b_wifi_provisioning_ble", snippet=False)),
    ("09_wifi_tcp_lm20", "09_wifi_tcp", LM20,
     wifi("09_wifi_tcp", "CONFIG_LAB_TRANSPORTE_TCP=y")),
    # o lab 10 recompila o firmware do 9 com outro transporte; a porta e so o
    # padrao que o prompt do boot propoe
    ("10_wifi_http_lm20", "09_wifi_tcp", LM20,
     wifi("09_wifi_tcp", "CONFIG_LAB_TRANSPORTE_HTTP=y", "CONFIG_LAB_PORTA=8000")),
    ("10_wifi_mqtt_lm20", "09_wifi_tcp", LM20,
     wifi("09_wifi_tcp", "CONFIG_LAB_TRANSPORTE_MQTT=y", "CONFIG_LAB_PORTA=1883")),
    ("11_wifi_twt_lm20", "11_wifi_twt", LM20, wifi("11_wifi_twt")),
    ("12_wifi_coex_on_lm20", "12_wifi_coex", LM20,
     wifi("12_wifi_coex", "CONFIG_MPSL_CX=y", "CONFIG_COEX_SEP_ANTENNAS=y",
          shield="nrf7002eb2;nrf7002eb2_coex")),
    ("12_wifi_coex_off_lm20", "12_wifi_coex", LM20,
     wifi("12_wifi_coex", "CONFIG_MPSL_CX=n", shield="nrf7002eb2;nrf7002eb2_coex")),
    ("13_wifi_location_lm20", "13_wifi_location", LM20, wifi("13_wifi_location")),
]


def west(args):
    cmd = ["nrfutil", "sdk-manager", "toolchain", "launch", "--ncs-version", NCS_VER, "--",
           "west"] + args
    return subprocess.run(cmd, cwd=str(NCS_WS), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def acha_hex(build_dir, app):
    # sysbuild: merged.hex (NCS <= 3.1) ou merged_<board>.hex (NCS 3.4)
    merged = sorted(build_dir.glob("merged*.hex"))
    if merged:
        return merged[0]
    for cand in (build_dir / Path(app).name / "zephyr" / "zephyr.hex",
                 build_dir / "zephyr" / "zephyr.hex"):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"nenhum hex em {build_dir}")


def tamanho(log):
    m = re.search(r"FLASH:\s+(\d+) B.*?RAM:\s+(\d+) B", log, re.S)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def build(nome, app, board, extra):
    build_dir = BUILD / nome
    app_dir = COMMS / app
    args = ["build", "-p", "-b", board, "--sysbuild",
            "-d", str(build_dir).replace("\\", "/"),
            str(app_dir).replace("\\", "/")] + extra
    r = west(args)
    log = r.stdout + r.stderr
    if r.returncode != 0:
        (BUILD / f"{nome}.log").write_text(log, encoding="utf-8")
        raise RuntimeError(f"west build falhou (log em build/hex/{nome}.log)")
    src = acha_hex(build_dir, app)
    HEX.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, HEX / f"{nome}.hex")
    return tamanho(log), src.name


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if "--list" in flags:
        for nome, app, board, _ in VARIANTES:
            print(f"{nome:34s} {app:28s} {board}")
        return
    sel = [v for v in VARIANTES if not argv or any(v[0].startswith(p) for p in argv)]
    if not sel:
        sys.exit("nenhuma variante casa com " + " ".join(argv))
    print(f"{len(sel)} variante(s) selecionada(s)")

    falhas = 0
    for nome, app, board, extra in sel:
        print(f"\n=== {nome}  ({app} · {board})", flush=True)
        try:
            (flash, ram), origem = build(nome, app, board, extra)
            print(f"    ok  {origem}  flash {flash:,} B  ram {ram:,} B  -> comms/hex"
                  .replace(",", "."))
        except Exception as ex:  # noqa: BLE001
            falhas += 1
            print(f"    FALHOU: {ex}")
    print(f"\n{len(sel) - falhas} ok, {falhas} falha(s)")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
