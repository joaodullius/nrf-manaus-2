#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Traduz as gravacoes do loop 1 (03_central_uart) para o formato do Data
Forwarder Host, para entrarem no pipeline do 05 (center_host.py, fwd_to_lab.py).

Codigo do curso. So stdlib.

Entra: os CSVs por classe do 03 (acc_x..gyro_z,class; int16 em mili-unidades,
sem tempo). Sai: um CSV + um .txt por gravacao, como o Host grava:

    device_time_ms,ax,ay,az,gx,gy,gz,label
    0,7285000.0,-3270000.0,5552000.0,5000.0,5000.0,20000.0,swipe_right

Ajustes:
  - mili -> micro (x1000), escritos como float, igual ao Host
  - class numerico -> label texto (tabela CLASSES do prep_dataset.py do 03)
  - device_time_ms sintetico, 10 ms por linha (100 Hz nominal; o 03 nao
    gravou tempo, so id sequencial contiguo)
  - sem temp/hum/pres: o loop 1 nao tem, e o merge do 05 as descarta

O fundo de escala e o mesmo dos dois firmwares (+-4 g / +-1000 dps), entao
so a escala muda. Os labels ficam os do loop 1.

Uso:
    python tools/loop1_para_host.py
        -> dataset_gestos/<label>_loop1-uart_<carimbo original>_000Z.csv + .txt

    python tools/loop1_para_host.py --src ../03_central_uart/dataset --out outra_pasta
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import platform
import re
import sys
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(AQUI, ".."))
TOOLS_03 = os.path.abspath(os.path.join(BASE, "..", "03_central_uart", "tools"))
SRC_PADRAO = os.path.join(BASE, "..", "03_central_uart", "dataset_referencia", "bruto")
OUT_PADRAO = os.path.join(BASE, "dataset_gestos")

COLUNAS_03 = ["acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z", "class"]
COLUNAS_HOST = ["device_time_ms", "ax", "ay", "az", "gx", "gy", "gz", "label"]
SESSION_TAG = "loop1-uart"
PERIODO_MS = 10          # 100 Hz
MILI_PARA_MICRO = 1000

CARIMBO = re.compile(r"_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.csv$")


def morrer(msg: str):
    print(f"erro: {msg}", file=sys.stderr)
    raise SystemExit(1)


def carrega_classes():
    if not os.path.isdir(TOOLS_03):
        morrer(f"nao achei {TOOLS_03}\n       este script depende do 03_central_uart do repo")
    sys.path.insert(0, TOOLS_03)
    from prep_dataset import CLASSES                               # noqa: E402
    return {v: k for k, v in CLASSES.items()}


def converte(entrada, saida_csv, saida_txt, nome_por_rotulo):
    with open(entrada, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        header = next(rd, None)
        if header != COLUNAS_03:
            morrer(f"{entrada}: header nao e do 03\n"
                   f"       esperado: {','.join(COLUNAS_03)}\n"
                   f"       lido    : {','.join(map(str, header or []))}")
        linhas = []
        rotulos = set()
        for n, r in enumerate(rd, start=2):
            if len(r) != len(COLUNAS_03):
                morrer(f"{entrada}:{n}: {len(r)} colunas, esperava {len(COLUNAS_03)}")
            try:
                vals = [int(v) for v in r]
            except ValueError:
                morrer(f"{entrada}:{n}: valor nao inteiro: {r}")
            rotulos.add(vals[6])
            linhas.append(vals[:6])
    if not linhas:
        morrer(f"{entrada}: sem linhas de dados")
    if len(rotulos) != 1:
        morrer(f"{entrada}: {len(rotulos)} classes no mesmo arquivo ({sorted(rotulos)})")
    rotulo = rotulos.pop()
    if rotulo not in nome_por_rotulo:
        morrer(f"{entrada}: classe {rotulo} nao esta na tabela CLASSES do 03")
    label = nome_por_rotulo[rotulo]

    with open(saida_csv, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(COLUNAS_HOST)
        for i, v in enumerate(linhas):
            wr.writerow([i * PERIODO_MS]
                        + [f"{x * MILI_PARA_MICRO:.1f}" for x in v]
                        + [label])

    agora = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    dur_s = (len(linhas) - 1) * PERIODO_MS / 1000.0
    with open(saida_txt, "w", encoding="utf-8") as f:
        f.write(
            "[Recording]\n"
            f"label       : {label}\n"
            f"session_tag : {SESSION_TAG}\n"
            f"data_rows   : {len(linhas)}\n"
            "\n[Host]\n"
            f"written_utc : {agora}\n"
            f"os          : {platform.platform()}\n"
            f"hostname    : {platform.node()}\n"
            f"python      : {platform.python_version()}\n"
            f"tool        : tools/loop1_para_host.py\n"
            "\n[Transport]\n"
            "transport   : UART / serial (03_central_uart na nRF54L15-DK, ponte BLE NUS -> serial)\n"
            "protocol    : texto '<id> ax,ay,az,gx,gy,gz'\n"
            "\n[Origem]\n"
            f"arquivo        : {os.path.relpath(entrada, BASE).replace(os.sep, '/')}\n"
            "firmware       : 01_gesture_recognition + data_collection.conf (CONFIG_DATA_COLLECTION_MODE)\n"
            "unidades       : int16 mili -> float micro (x1000)\n"
            "fundo_escala   : +-4 g / +-1000 dps (igual ao 05)\n"
            f"device_time_ms : sintetico, {PERIODO_MS} ms por linha (nao gravado no 03)\n"
            "\n[Device session_info]\n"
            "device_reported_name : nRF54L15 TAG (01_gesture_recognition)\n"
            "sampling_rate_hz     : 100\n"
            "channel_count        : 6\n"
            "channels             : ax, ay, az, gx, gy, gz\n"
            "\n[Channels]\n"
            "count : 6\n"
            "names : ax, ay, az, gx, gy, gz\n"
            "\n[Timing]\n"
            f"duration_s : {dur_s:.2f}\n"
        )
    return label, len(linhas)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", default=SRC_PADRAO, help="pasta com os CSVs do 03")
    p.add_argument("--out", default=OUT_PADRAO, help="pasta de saida")
    args = p.parse_args()

    entradas = sorted(glob.glob(os.path.join(args.src, "*.csv")))
    if not entradas:
        morrer(f"nenhum CSV em {args.src}")
    nome_por_rotulo = carrega_classes()
    os.makedirs(args.out, exist_ok=True)

    print(f"\n  origem  {os.path.relpath(args.src, BASE)}")
    print(f"  saida   {os.path.relpath(args.out, BASE)}\n")
    total = 0
    for entrada in entradas:
        m = CARIMBO.search(os.path.basename(entrada))
        if not m:
            morrer(f"{entrada}: nome sem carimbo <classe>_AAAA-MM-DD_hh-mm-ss.csv")
        # Nome no padrao do Host: <label>_<session>_<carimbo>_<ms>Z. O carimbo e
        # o original do 03 (hora local da bancada), sem milissegundos.
        base = None
        with open(entrada, newline="", encoding="utf-8") as f:
            next(f)
            primeira = next(f, "")
        try:
            rotulo = int(primeira.strip().split(",")[-1])
        except ValueError:
            morrer(f"{entrada}: primeira linha ilegivel")
        label = nome_por_rotulo.get(rotulo)
        if label is None:
            morrer(f"{entrada}: classe {rotulo} nao esta na tabela CLASSES do 03")
        base = f"{label}_{SESSION_TAG}_{m.group(1)}_000Z"
        saida_csv = os.path.join(args.out, base + ".csv")
        saida_txt = os.path.join(args.out, base + ".txt")
        label, n = converte(entrada, saida_csv, saida_txt, nome_por_rotulo)
        total += n
        print(f"  {os.path.basename(entrada):45s} -> {base}.csv  ({n} linhas, {label})")
    print(f"\n  total {total} linhas em {len(entradas)} gravacoes")


if __name__ == "__main__":
    main()
