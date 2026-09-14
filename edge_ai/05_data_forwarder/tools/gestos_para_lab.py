#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deixa o dataset_gestos/ pronto para subir no Edge AI Lab.

Codigo do curso. So stdlib; o trabalho e dos outros dois scripts desta pasta:

    1. center_host.py em cada gravacao de gesto discreto (swipe_*)
       -> dataset_gestos/centrado/<nome>_centrado.csv
       idle e unknown sao classes continuas: vao inteiras, sem centralizar
       (o center_host.py nao acha gesto nelas e para)
    2. fwd_to_lab.py merge com os centrados + as continuas
       -> dataset_gestos/dataset_gestos.csv, classes na ordem do enum do 01:
          0 idle, 1 unknown, 2 swipe_right, 3 swipe_left

Uso (o padrao roda direto no dataset_gestos/ do repo):
    python tools/gestos_para_lab.py

    python tools/gestos_para_lab.py --src outra_pasta --window 100 \
        --continuas idle,unknown --classes idle,unknown,swipe_right,swipe_left \
        --out outra_pasta/dataset.csv

Para em qualquer etapa que falhar (codigo 1).
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(AQUI, ".."))
CENTER = os.path.join(AQUI, "center_host.py")
FWD = os.path.join(AQUI, "fwd_to_lab.py")

SRC_PADRAO = os.path.join(BASE, "dataset_gestos")
CONTINUAS_PADRAO = "idle,unknown"
CLASSES_PADRAO = "idle,unknown,swipe_right,swipe_left"


def morrer(msg: str):
    print(f"erro: {msg}", file=sys.stderr)
    raise SystemExit(1)


def roda(cmd):
    print(f"\n$ {' '.join(os.path.relpath(c, BASE) if os.path.isabs(c) else c for c in cmd)}", flush=True)
    r = subprocess.run([sys.executable] + cmd, cwd=BASE)
    if r.returncode:
        morrer(f"etapa falhou (codigo {r.returncode}); nada gerado depois dela")


def label_do(caminho):
    """Label pelo nome do arquivo do Host: <label>_<session>_<carimbo>Z.csv."""
    nome = os.path.basename(caminho)
    for sep in ("_ble-", "_uart-", "_loop1-"):
        if sep in nome:
            return nome.split(sep)[0]
    morrer(f"{nome}: nao consegui tirar o label do nome (esperava <label>_<session>_...)")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", default=SRC_PADRAO, help="pasta com os CSVs no formato do Host")
    p.add_argument("--out", help="CSV final (padrao: <src>/dataset_gestos.csv)")
    p.add_argument("--window", type=int, default=100, help="janela do center_host (padrao 100)")
    p.add_argument("--continuas", default=CONTINUAS_PADRAO,
                   help=f"labels que vao inteiros, sem centralizar (padrao {CONTINUAS_PADRAO})")
    p.add_argument("--classes", default=CLASSES_PADRAO,
                   help=f"ordem das classes 0..N-1 (padrao {CLASSES_PADRAO})")
    args = p.parse_args()

    src = os.path.abspath(args.src)
    out = os.path.abspath(args.out) if args.out else os.path.join(src, "dataset_gestos.csv")
    continuas = {c.strip() for c in args.continuas.split(",") if c.strip()}
    pasta_centrado = os.path.join(src, "centrado")

    entradas = sorted(glob.glob(os.path.join(src, "*.csv")))
    entradas = [e for e in entradas if os.path.abspath(e) != out]
    if not entradas:
        morrer(f"nenhum CSV em {src}")

    print(f"  origem  {os.path.relpath(src, BASE)}")
    print(f"  saida   {os.path.relpath(out, BASE)}")

    os.makedirs(pasta_centrado, exist_ok=True)
    para_merge = []
    for e in entradas:
        label = label_do(e)
        if label in continuas:
            print(f"\n  {os.path.basename(e)}: classe continua ({label}), vai inteira", flush=True)
            para_merge.append(e)
            continue
        saida = os.path.join(pasta_centrado,
                             os.path.splitext(os.path.basename(e))[0] + "_centrado.csv")
        roda([CENTER, e, "-w", str(args.window), "-o", saida])
        para_merge.append(saida)

    roda([FWD, "merge"] + para_merge + ["--classes", args.classes, "--out", out])
    print(f"\n  pronto: {os.path.relpath(out, BASE)} -> subir no Edge AI Lab")


if __name__ == "__main__":
    main()
