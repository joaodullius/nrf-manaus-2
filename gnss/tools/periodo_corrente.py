#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede o periodo do modo periodico pelo padrao de corrente — codigo do curso.

    python periodo_corrente.py <csv de corrente> <saida.png> [segundos a pular]

O modo periodico do sample acorda, tenta o fix e dorme. Isso deixa uma assinatura
na corrente que se repete, e da para medir o intervalo sem depender do log: e a
autocorrelacao do sinal que diz o periodo.

Serve de conferencia cruzada do CONFIG_GNSS_SAMPLE_PERIODIC_INTERVAL: se o numero
medido nao bater com o configurado, alguma coisa esta segurando o ciclo — o
timeout de busca, o radio ocupado, ou a rede.
"""
from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NAVY, BLUE, CYAN, SLATE, LINE, INK, WARN = (
    "#00224E", "#0093D0", "#22C3E6", "#566577", "#D3E0EB", "#0B1B2B", "#E8A33D")
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"]})


def le(caminho: Path):
    t, med = [], []
    for r in csv.DictReader(open(caminho)):
        try:
            t.append(float(r["t_s"])); med.append(float(r["media_mA"]))
        except (ValueError, KeyError, TypeError):
            pass
    return np.array(t), np.array(med)


def uniformiza(t, y, dt=0.1):
    """Reamostra num passo fixo — a autocorrelacao exige grade uniforme."""
    grade = np.arange(t[0], t[-1], dt)
    return grade, np.interp(grade, t, y)


def periodo(y, dt, minimo_s=30.0):
    """Autocorrelacao do sinal sem media; devolve (periodo_s, forca, curva).

    Busca o maximo entre o lag minimo e metade do registro. Sem esse teto a
    autocorrelacao trava na LARGURA DA RAJADA (a janela de busca do GNSS), que e
    dezenas de segundos, e nao no intervalo entre rajadas.
    """
    x = y - y.mean()
    ac = np.correlate(x, x, mode="full")[len(x) - 1:]
    ac /= ac[0]
    i0, i1 = int(minimo_s / dt), len(ac) // 2
    if i1 <= i0 + 2:
        return None, 0.0, ac
    i = int(np.argmax(ac[i0:i1])) + i0
    return i * dt, float(ac[i]), ac


def ciclos(t, y, limiar):
    """Instantes de subida e a duracao de cada rajada acima do limiar."""
    acima = y > limiar
    sobe = np.where((~acima[:-1]) & (acima[1:]))[0] + 1
    desce = np.where((acima[:-1]) & (~acima[1:]))[0] + 1
    duracoes = []
    for i in sobe:
        j = desce[desce > i]
        if len(j):
            duracoes.append(t[j[0]] - t[i])
    return t[sobe], np.array(duracoes)


def main(argv=None):
    a = argv or sys.argv[1:]
    if len(a) < 2:
        print(__doc__.splitlines()[2]); return 2
    csvf, png = Path(a[0]), Path(a[1])
    t, med = le(csvf)
    if len(t) < 50:
        print("dados de menos"); return 1
    pular = float(a[2]) if len(a) > 2 else 0.0
    if pular:
        sel = t >= pular
        t, med = t[sel], med[sel]
    g, y = uniformiza(t, med)
    dt = g[1] - g[0]

    # ATENCAO: nao usar percentil alto como teto. Em ciclo de trabalho baixo — que e
    # o caso do modo periodico — ate o percentil 90 cai DENTRO do sono, e o limiar
    # desce para o nivel do ruido. O teto tem de vir do topo da distribuicao.
    piso, teto = float(np.percentile(y, 10)), float(np.percentile(y, 99.5))
    limiar = piso + 0.3 * (teto - piso)
    inicios, duracoes = ciclos(g, y, limiar)
    intervalos = np.diff(inicios)
    # a autocorrelacao de um sinal em rajadas tem pico na LARGURA da rajada;
    # so vale procurar o periodo bem depois disso
    largura = float(np.median(duracoes)) if len(duracoes) else 10.0
    per, forca, ac = periodo(y, dt, minimo_s=max(30.0, 1.5 * largura))

    print(f"amostras: {len(g)} em {g[-1]-g[0]:.0f} s (passo {dt*1000:.0f} ms)")
    print(f"corrente: piso {piso:.3f} mA, teto {teto:.2f} mA, limiar {limiar:.2f} mA")
    if len(duracoes):
        print(f"rajadas: {len(duracoes)}, duracao mediana {np.median(duracoes):.1f} s")
    print(f"autocorrelacao: periodo {per:.1f} s (forca {forca:.2f})" if per else "sem periodo")
    if len(intervalos):
        print(f"intervalos entre acordares: {[f'{x:.0f}' for x in intervalos]}")
        estaveis = [x for x in intervalos if x > 10]
        if estaveis:
            print(f"  descartando os < 10 s (ruido de limiar): {[f'{x:.0f}' for x in estaveis]}")
            print(f"  mediana {statistics.median(estaveis):.1f} s")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7.5),
                                   gridspec_kw={"height_ratios": [2, 1]})
    fig.patch.set_facecolor("white")
    ax1.plot(g, y, color=NAVY, lw=1.2)
    ax1.axhline(limiar, color=WARN, lw=1.4, ls="--")
    for x in inicios:
        ax1.axvline(x, color=CYAN, lw=1.2, alpha=0.8)
    ax1.set_ylabel("corrente (mA)", fontsize=10.5, color=SLATE)
    ax1.set_xlabel("segundos", fontsize=10.5, color=SLATE)
    ax1.set_title("Assinatura de corrente do modo periodico", fontsize=13,
                  color=INK, fontweight="bold", loc="left", pad=8)
    ax2.plot(np.arange(len(ac)) * dt, ac, color=BLUE, lw=1.4)
    if per:
        ax2.axvline(per, color=WARN, lw=2.0)
        ax2.annotate(f"periodo {per:.0f} s", xy=(per, ac[int(per/dt)]),
                     xytext=(8, 6), textcoords="offset points",
                     fontsize=12, color="#8a5a10", fontweight="bold")
    ax2.set_xlim(0, min(len(ac) * dt, (per or 120) * 3))
    ax2.set_ylabel("autocorrelacao", fontsize=10.5, color=SLATE)
    ax2.set_xlabel("defasagem (s)", fontsize=10.5, color=SLATE)
    for ax in (ax1, ax2):
        ax.grid(True, color=LINE, lw=0.8, alpha=0.7); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        for s in ("left", "bottom"): ax.spines[s].set_color(LINE)
        ax.tick_params(colors=SLATE, labelsize=9.5)
    fig.tight_layout()
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=150, facecolor="white")
    print("png:", png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
