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

No fim, media, desvio e n por estimador (d_ifft, ifft_fw, ps_fw, rtt_fw, music), so
das procedures com tone quality OK. A media do d_ifft no resumo deve ficar perto de
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
        "rtt_fw", "rtt_np", "music"]
STAT_COLS = ["d_ifft", "ifft_fw", "ps_fw", "rtt_fw", "music"]


def summarize(procs, nfft: int = 512) -> list[dict]:
    rows = []
    for p in procs:
        comb = p.comb()
        e = de.estimates(comb, p.rtt_half_ns, p.rtt_count, nfft)
        rows.append({
            "counter": p.counter,
            "tq": 1 if p.tone_quality_ok else 0,
            "ifft_fw": p.fw["ifft"], "ifft_np": e["ifft"],
            "d_ifft": e["ifft"] - p.fw["ifft"],
            "ps_fw": p.fw["phase_slope"], "ps_np": e["phase_slope"],
            "rtt_fw": p.fw["rtt"], "rtt_np": e["rtt"],
            "music": music_adapter.music_m(comb),
        })
    return rows


def stats(rows) -> dict:
    out = {}
    for c in STAT_COLS:
        v = np.array([r[c] for r in rows if r["tq"] == 1 and math.isfinite(r[c])])
        out[c] = (float(v.mean()), float(v.std()), int(v.size)) if v.size else (math.nan, math.nan, 0)
    return out


def imprimir(rows, st) -> None:
    fmt = "{:>7} {:>2} " + " ".join(["{:>8}"] * 8)
    print(fmt.format(*COLS))
    for r in rows:
        print(fmt.format(r["counter"], r["tq"], *[f"{r[c]:.3f}" for c in COLS[2:]]))
    print()
    print("{:>10} {:>8} {:>8} {:>4}".format("estimador", "media", "desvio", "n"))
    for c in STAT_COLS:
        m, s, n = st[c]
        print(f"{c:>10} {m:8.3f} {s:8.3f} {n:4d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("captura", type=Path)
    ap.add_argument("--nfft", type=int, default=512, choices=[512, 1024, 2048])
    ap.add_argument("--csv", type=Path, help="tambem grava a tabela por procedure neste arquivo")
    args = ap.parse_args()

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
