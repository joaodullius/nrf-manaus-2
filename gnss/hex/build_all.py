#!/usr/bin/env python3
"""
build_all.py — gera os .hex de referencia do modulo de GNSS.

Todas as cinco variantes sao PUBLICAS. Nenhuma carrega credencial:

  - a coordenada de referencia (GNSS_SAMPLE_REFERENCE_LATITUDE/LONGITUDE) fica
    vazia no repositorio, por decisao de escopo;
  - a variante de nuvem so liga a biblioteca cliente da nRF Cloud no binario. O
    certificado e o provisionamento do dispositivo sao pre-requisito para RODAR,
    nao para compilar — nada de segredo entra no hex.

Por isso este modulo nao tem a separacao publica/local do comms/hex/build_all.py:
os cinco hex vao para gnss/hex/ e sao versionados.

Uso (de qualquer pasta):
    python gnss/hex/build_all.py                # todas
    python gnss/hex/build_all.py 02             # so as que comecam com 02
    python gnss/hex/build_all.py --list

Um unico codigo fonte (gnss/01_nrf9151_basic) em cinco configuracoes: e o mesmo
desenho dos labs 2 e 3, que sao pastas de receita sem codigo.

O hex publicado e o merged_<board>.hex do sysbuild (SB_CONFIG_MERGED_HEX_FILES=y),
com o mesmo conteudo do tfm_merged.hex — o alvo /ns tem TF-M, e o que o `west flash`
grava e a imagem segura e a nao segura ja fundidas. O zephyr.hex sozinho e so a
aplicacao, e nao roda.

Requisitos: nRF Connect SDK v3.4.0 em C:/ncs/v3.4.0 (o west roda de la).
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GNSS = REPO / "gnss"
HEX = GNSS / "hex"
BUILD = REPO / "build" / "hex_gnss"
NCS_WS = Path(r"C:/ncs/v3.4.0")
NCS_VER = "v3.4.0"

BOARD = "nrf9151dk/nrf9151/ns"
APP = "01_nrf9151_basic"          # a unica pasta com codigo; tambem o nome da imagem


def d(*opts):
    """Os -D do west com o prefixo do nome da imagem, que o sysbuild exige."""
    return ["--"] + [f"-D{APP}_{o}" for o in opts]


TTFF = ("CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=n",
        "CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y",
        "CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST_COLD_START=y")

# nome do hex, extras do west, o que o .config gerado tem que dizer.
# Uma entrada com "!" na frente e o contrario: essa linha NAO pode estar la.
VARIANTES = [
    ("01_nrf9151_basic", [],
     ["CONFIG_GNSS_SAMPLE_MODE_CONTINUOUS=y",
      "CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=y"]),

    ("02_nrf9151_ttff_sem", d(*TTFF),
     ["CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y",
      "CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=y"]),

    ("02_nrf9151_ttff_minima",
     d(*TTFF, "CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=n",
       "CONFIG_GNSS_SAMPLE_ASSISTANCE_MINIMAL=y"),
     ["CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y",
      "CONFIG_GNSS_SAMPLE_ASSISTANCE_MINIMAL=y"]),

    ("02_nrf9151_ttff_nuvem",
     d(*TTFF, "CONFIG_GNSS_SAMPLE_ASSISTANCE_NONE=n",
       "CONFIG_GNSS_SAMPLE_ASSISTANCE_NRF_CLOUD=y"),
     ["CONFIG_GNSS_SAMPLE_MODE_TTFF_TEST=y",
      "CONFIG_GNSS_SAMPLE_ASSISTANCE_NRF_CLOUD=y"]),

    ("03_nrf9151_nmea",
     d("CONFIG_GNSS_SAMPLE_NMEA_ONLY=y", "CONFIG_LOG=n",
       "CONFIG_AT_HOST_LIBRARY=n"),
     ["CONFIG_GNSS_SAMPLE_NMEA_ONLY=y",
      "!CONFIG_LOG=y", "!CONFIG_AT_HOST_LIBRARY=y"]),
]


def west(args):
    cmd = ["nrfutil", "sdk-manager", "toolchain", "launch", "--ncs-version", NCS_VER, "--",
           "west"] + args
    return subprocess.run(cmd, cwd=str(NCS_WS), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def acha_hex(build_dir):
    """Prefere o merged_<board>.hex do sysbuild (SB_CONFIG_MERGED_HEX_FILES=y no
    sysbuild.conf do lab): TF-M + aplicacao num arquivo so, o mesmo conteudo do
    tfm_merged.hex que o west flash grava no alvo /ns. Os dois seguintes sao
    fallback para um build sem essa opcao."""
    for cand in (*sorted(build_dir.glob("merged*.hex")),
                 build_dir / APP / "zephyr" / "tfm_merged.hex",
                 build_dir / APP / "zephyr" / "zephyr.hex"):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"nenhum hex em {build_dir}")


def confere(build_dir, esperado):
    """A mesma ideia dos verifica_*.sh dos labs, aplicada ao .config gerado."""
    cfg = build_dir / APP / "zephyr" / ".config"
    linhas = set(cfg.read_text(encoding="utf-8").splitlines())
    faltando = [e for e in esperado if not e.startswith("!") and e not in linhas]
    sobrando = [e[1:] for e in esperado if e.startswith("!") and e[1:] in linhas]
    if faltando or sobrando:
        raise RuntimeError("config errada -- falta " + str(faltando)
                           + ", sobra " + str(sobrando))


def tamanho(log):
    """O ultimo bloco de memoria do log e o da imagem de aplicacao, nao o do TF-M."""
    achados = re.findall(r"FLASH:\s+(\d+) B.*?RAM:\s+(\d+) B", log, re.S)
    return (int(achados[-1][0]), int(achados[-1][1])) if achados else (None, None)


def build(nome, extra, esperado):
    build_dir = BUILD / nome
    args = ["build", "-p", "-b", BOARD, "--sysbuild",
            "-d", str(build_dir).replace("\\", "/"),
            str(GNSS / APP).replace("\\", "/")] + extra
    r = west(args)
    log = r.stdout + r.stderr
    if r.returncode != 0:
        BUILD.mkdir(parents=True, exist_ok=True)
        (BUILD / f"{nome}.log").write_text(log, encoding="utf-8")
        raise RuntimeError(f"west build falhou (log em build/hex_gnss/{nome}.log)")
    confere(build_dir, esperado)
    src = acha_hex(build_dir)
    HEX.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, HEX / f"{nome}.hex")
    return tamanho(log), src.name


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if "--list" in flags:
        for nome, _, _ in VARIANTES:
            print(f"{nome:28s} publica")
        return
    sel = [v for v in VARIANTES if not argv or any(v[0].startswith(p) for p in argv)]
    if not sel:
        sys.exit("nenhuma variante casa com " + " ".join(argv))
    print(f"{len(sel)} variante(s) selecionada(s)")

    falhas = 0
    for nome, extra, esperado in sel:
        print(f"\n=== {nome}  ({APP} - {BOARD})", flush=True)
        try:
            (flash, ram), origem = build(nome, extra, esperado)
            print(f"    ok  {origem}  flash {flash} B  ram {ram} B  -> gnss/hex/{nome}.hex")
        except Exception as ex:  # noqa: BLE001
            falhas += 1
            print(f"    FALHOU: {ex}")
    print(f"\n{len(sel) - falhas} ok, {falhas} falha(s)")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
