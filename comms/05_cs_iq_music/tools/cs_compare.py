#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quatro estimadores sobre o mesmo IQ — codigo do curso (nrf-manaus-2).

    python cs_compare.py capturas/1m.csv
    python cs_compare.py capturas/3m.csv --nfft 512 --csv saida_3m.csv

Para cada procedure completa do arquivo (cs_capture.py):
  - ifft_fw / ps_fw / rtt_fw : o que o FIRMWARE imprimiu (cs_de da Nordic, float32)
  - ifft_np / ps_np / rtt_np : o mesmo algoritmo reimplementado em NumPy (cs_de_numpy.py)
  - d_ifft                   : ifft_np - ifft_fw  (se nao for ~0, o port nao reproduz o chip)
  - music                    : MUSIC do waves sobre o MESMO IQ (music_adapter.py)

Com dois caminhos de antena (CONFIG_LAB_ANTENNA_PATHS=2), as colunas acima sao do
ap 0 (o mesmo par A1-B1 do lab 2) e entram mais tres, da MESMA procedure:
  - ifft_ap1  : ifft do firmware no segundo caminho (A1-B2)
  - music_ap1 : MUSIC so no segundo caminho
  - music_2ap : MUSIC com os dois caminhos, somando os pseudo-espectros
  - music_cov : MUSIC com os dois caminhos, media das covariancias (o canonico)
Com um caminho elas ficam NaN e fora do resumo.

No fim, media, desvio e n por estimador, so das procedures com tone quality OK em
todos os caminhos. A media do d_ifft no resumo deve ficar perto de
0 — e o mesmo teste do "port reproduz o chip" da tabela, so que agregado.
--nfft deve ser o CONFIG_BT_CS_DE_NFFT_SIZE do firmware (512 no lab).
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

import cs_csv
import cs_de_numpy as de
import music_adapter

COLS = ["counter", "tq", "ifft_fw", "ifft_np", "d_ifft", "ps_fw", "ps_np",
        "rtt_fw", "rtt_np", "music", "ifft_ap1", "music_ap1", "music_2ap",
        "music_cov"]
STAT_COLS = ["d_ifft", "ifft_fw", "ps_fw", "rtt_fw", "music",
             "ifft_ap1", "music_ap1", "music_2ap", "music_cov"]


def summarize(procs, nfft: int = 512) -> list[dict]:
    rows = []
    for counter, aps in cs_csv.group_by_counter(procs).items():
        p = aps[0]                                   # ap 0: o par A1-B1 do lab 2
        comb = p.comb()
        e = de.estimates(comb, p.rtt_half_ns, p.rtt_count, nfft)
        row = {
            "counter": counter,
            "tq": 1 if all(a.tone_quality_ok for a in aps) else 0,
            "ifft_fw": p.fw["ifft"], "ifft_np": e["ifft"],
            "d_ifft": e["ifft"] - p.fw["ifft"],
            "ps_fw": p.fw["phase_slope"], "ps_np": e["phase_slope"],
            "rtt_fw": p.fw["rtt"], "rtt_np": e["rtt"],
            "music": music_adapter.music_m(comb),
            "ifft_ap1": math.nan, "music_ap1": math.nan, "music_2ap": math.nan,
            "music_cov": math.nan,
        }
        if len(aps) >= 2:                            # segundo caminho: A1-B2
            row["ifft_ap1"] = aps[1].fw["ifft"]
            row["music_ap1"] = music_adapter.music_m(aps[1].comb())
            combs = [a.comb() for a in aps]
            row["music_2ap"] = music_adapter.music_multi_m(combs)
            row["music_cov"] = music_adapter.music_cov_m(combs)
        rows.append(row)
    return rows


def stats(rows) -> dict:
    out = {}
    for c in STAT_COLS:
        v = np.array([r[c] for r in rows if r["tq"] == 1 and math.isfinite(r[c])])
        out[c] = (float(v.mean()), float(v.std()), int(v.size)) if v.size else (math.nan, math.nan, 0)
    return out


def imprimir(rows, st) -> None:
    dois_ap = any(math.isfinite(r["music_2ap"]) for r in rows)
    cols = COLS if dois_ap else COLS[:10]
    fmt = "{:>7} {:>2} " + " ".join(["{:>9}"] * (len(cols) - 2))
    print(fmt.format(*cols))
    for r in rows:
        print(fmt.format(r["counter"], r["tq"], *[f"{r[c]:.3f}" for c in cols[2:]]))
    print()
    print("{:>10} {:>8} {:>8} {:>4}".format("estimador", "media", "desvio", "n"))
    for c in STAT_COLS:
        m, s, n = st[c]
        if n == 0 and c in ("ifft_ap1", "music_ap1", "music_2ap", "music_cov"):
            continue                                 # captura com um caminho so
        print(f"{c:>10} {m:8.3f} {s:8.3f} {n:4d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("captura", type=Path)
    ap.add_argument("--nfft", type=int, default=512, choices=[512, 1024, 2048])
    ap.add_argument("--csv", type=Path, help="tambem grava a tabela por procedure neste arquivo")
    ap.add_argument("--music-grid", action="store_true",
                    help="MUSIC sem interpolacao do pico: o argmax cru na grade de 512 "
                         "atrasos do waves (quantiza em 14,7 cm)")
    args = ap.parse_args()
    if args.music_grid:
        music_adapter.INTERPOLATE_PEAK = False

    procs = cs_csv.read_procedures(args.captura)
    if not procs:
        raise SystemExit(f"nenhuma procedure completa em {args.captura}")
    rows = summarize(procs, args.nfft)
    imprimir(rows, stats(rows))
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(rows)
        print(f"tabela gravada em {args.csv}")


if __name__ == "__main__":
    main()
