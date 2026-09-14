#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centraliza gestos discretos numa gravacao do Data Forwarder Host.

Codigo do curso. Entra UM CSV como o Host gravou, sai UM CSV no MESMO formato,
so com as janelas dos gestos, cada uma com o pico no meio. O resultado vai
direto no fwd_to_lab.py merge, como qualquer gravacao.

O algoritmo nao esta aqui: e o script da Nordic em
03_central_uart/tools/segment-center-signal/, e a calibracao automatica de
eixo e limiar e a do center_gestures.py do 03 — este script importa as
funcoes de la e so traduz o formato do Host (ax..gz, micro-unidades, label
texto) para o que elas esperam. Um unico lugar para a centralizacao.

O limiar da Nordic e relativo (coef x media do envelope), entao micro ou mili
da o mesmo recorte — conferido contra o center_gestures.py com a mesma
gravacao nas duas escalas.

Uso:
    python tools/center_host.py swipe_left_ble-xxxx.csv
        -> swipe_left_ble-xxxx_centrado.csv, ao lado da entrada

    python tools/center_host.py swipe_left.csv -w 100 --axis gz --coef 0.9 -o saida.csv

Depois:
    python tools/fwd_to_lab.py merge *_centrado.csv idle_*.csv --classes ... --out dataset.csv

Nao serve para classe continua (idle, vibracao): essas vao inteiras no merge.
"""
from __future__ import annotations

import argparse
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
TOOLS_03 = os.path.abspath(os.path.join(AQUI, "..", "..", "03_central_uart", "tools"))

TIME_COL = "device_time_ms"
LABEL_COL = "label"
IMU_HOST = ["ax", "ay", "az", "gx", "gy", "gz"]
IMU_LAB = ["acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"]
HOST_PARA_LAB = dict(zip(IMU_HOST, IMU_LAB))
EIXOS = ["gx", "gy", "gz"]


def morrer(msg: str):
    print(f"erro: {msg}", file=sys.stderr)
    raise SystemExit(1)


def carrega_03():
    if not os.path.isdir(TOOLS_03):
        morrer(f"nao achei {TOOLS_03}\n       este script depende do 03_central_uart do repo")
    sys.path.insert(0, TOOLS_03)
    import center_gestures as cg                                   # noqa: E402
    return cg


def le_host(caminho, pd):
    df = pd.read_csv(caminho)
    cols = list(df.columns)
    if not cols or cols[0] != TIME_COL or cols[-1] != LABEL_COL:
        morrer(f"{caminho}: header nao e do Data Forwarder Host\n"
               f"       esperado: {TIME_COL},...,{LABEL_COL}\n"
               f"       lido    : {','.join(map(str, cols))}")
    faltam = [c for c in IMU_HOST if c not in cols]
    if faltam:
        morrer(f"{caminho}: faltam canais do IMU no header: {faltam}")
    if df.isnull().sum().sum():
        morrer(f"{caminho}: tem valores vazios — o Lab rejeita")
    labels = df[LABEL_COL].unique()
    if len(labels) != 1:
        morrer(f"{caminho}: {len(labels)} labels no mesmo arquivo ({', '.join(map(str, labels))}); "
               f"esperava 1")
    return df, str(labels[0])


def main():
    p = argparse.ArgumentParser(
        description="Centraliza gestos discretos num CSV do Data Forwarder Host.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Algoritmo: 03_central_uart/tools/center_gestures.py (Nordic + calibracao).")
    p.add_argument("entrada", help="CSV gravado pelo Data Forwarder Host, uma classe")
    p.add_argument("-o", "--out", help="CSV de saida (padrao: <entrada>_centrado.csv)")
    p.add_argument("-w", "--window", type=int, default=100,
                   help="janela em linhas; PAR, e igual ao Window size do Lab (padrao 100)")
    p.add_argument("--axis", default="auto",
                   help=f"eixo de deteccao: auto ou um de {', '.join(EIXOS)}")
    p.add_argument("--coef", default="auto",
                   help="threshold_coef: auto (varredura) ou um valor fixo")
    p.add_argument("--trim", type=int, default=400,
                   help="linhas descartadas de cada ponta (padrao 400, 4 s a 100 Hz)")
    args = p.parse_args()

    if args.window % 2:
        morrer(f"--window {args.window} e impar; o recorte da Nordic produziria "
               f"{2 * (args.window // 2)} linhas por gesto. Use um valor par.")
    if args.axis != "auto" and args.axis not in EIXOS:
        morrer(f"--axis {args.axis!r}: use auto ou um de {', '.join(EIXOS)}")

    try:
        import numpy as np
        import pandas as pd
    except ImportError as e:
        morrer(f"falta dependencia: {e.name}. Rode:\n"
               f"       pip install numpy pandas")

    cg = carrega_03()
    ns = cg.carrega_funcoes_nordic()

    df, label = le_host(args.entrada, pd)
    linhas_brutas = len(df)
    df = ns["remove_nrows"](df, args.trim, first=True)
    df = ns["remove_nrows"](df, args.trim, first=False)
    df.reset_index(drop=True, inplace=True)
    if len(df) < args.window:
        morrer(f"{args.entrada}: {linhas_brutas} linhas; sobram {len(df)} depois de "
               f"aparar {args.trim} de cada ponta. Grave mais, ou --trim menor.")

    # As funcoes do 03 enxergam so o IMU, com os nomes internos da Nordic.
    imu = df[IMU_HOST].copy()
    imu.columns = cg.COLUNAS_NORDIC[:6]

    eixos = [HOST_PARA_LAB[e] for e in (EIXOS if args.axis == "auto" else [args.axis])]
    coefs = cg.GRADE_COEF if args.coef == "auto" else [float(args.coef)]

    print(f"\n  arquivo   {args.entrada}")
    print(f"  label     {label}")
    print(f"  linhas    {linhas_brutas} brutas -> {len(df)} apos aparar {args.trim} de cada ponta")

    resultados = cg.varre(ns, imu, args.window, eixos, coefs, np)
    esc = cg.melhor(resultados)
    if esc is None:
        morrer(f"{args.entrada}: nenhuma combinacao produziu >= {cg.MIN_GESTOS} gestos.\n"
               f"       confira o eixo, ou se este arquivo e mesmo de gesto discreto")
    cg.imprime_varredura(resultados, esc, args.window)

    # Recorte definitivo com a combinacao vencedora, nas LINHAS do df completo:
    # a saida leva todas as colunas do Host, nao so o IMU.
    col = cg.LAB_PARA_NORDIC[esc["eixo"]]
    work = int(args.window * 0.95)
    ns["config"] = {"work_axis": col, "work_wind_size": work,
                    "total_wind_size": args.window, "threshold_coef": esc["coef"],
                    "step": 1}
    vetor = imu[col].values.reshape(len(imu[col]))
    envelope = ns["prepare_data"](vetor - np.mean(vetor), 1, work)
    segmentos = ns["segment_data"](envelope, work, esc["coef"])
    centros, descartados = cg.centros_dos_segmentos(segmentos, len(df), args.window)
    meia = args.window // 2
    idx = [i for c in centros for i in range(c - meia, c + meia)]
    seg = df.iloc[idx]

    saida = args.out or os.path.splitext(args.entrada)[0] + "_centrado.csv"
    seg.to_csv(saida, index=False)

    n = len(seg)
    eixo_host = {v: k for k, v in HOST_PARA_LAB.items()}[esc["eixo"]]
    print(f"\n  escolhido eixo {eixo_host} · coef {esc['coef']:.2f}")
    print(f"  gravado   {n} linhas ({n // args.window} gestos) -> {saida}")
    if descartados:
        print(f"  nota      {descartados} segmento(s) descartado(s) por cair fora dos limites")
    assert n % args.window == 0, "saida nao e multipla da janela"


if __name__ == "__main__":
    main()
