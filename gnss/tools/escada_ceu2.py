# -*- coding: utf-8 -*-
"""A escada de precisao em ceu aberto, em janelas iguais de 100 s.

Por que 100 s: os blocos renderam entre 34 e 297 epocas no seu regime, porque
nem todos ficaram no regime o tempo todo. Comparar um CEP de 34 s com um de
297 s mede a duracao, nao a condicao — o CEP cresce com a janela (a mesma
captura deu 1,129 m inteira e 0,338 m em janelas de 5 min). Fatiar tudo em 100 s
iguala, e e a mesma janela da figura da posicao anterior, o que torna as duas
posicoes comparaveis entre si.

Os degraus saem da qualidade do fix, nao da intencao do teste. O SBAS entrou
sozinho e cresceu ao longo da campanha (7 epocas no primeiro bloco autonomo, 266
no ultimo); em vez de descartar, vira um degrau proprio — que e o que ele e.

    q1  autonomo, sem correcao alguma
    q2  SBAS, correcao de area ampla por satelite
    q4  RTK fixo, com a origem da correcao dizendo qual degrau
"""
import json
import math
import statistics
import sys
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, "C:/work/nrf-manaus-2/gnss/tools")
import nmea  # noqa: E402

SAIDA = "C:/b/ceu2"
JANELA = 100
INK, SLATE, NAVY, BLUE = "#0B1B2B", "#566577", "#00224E", "#0093D0"
PANEL, GRADE, VERDE = "#EDF3F8", "#B9C9D6", "#12A36E"
AMBAR = "#C77800"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "axes.edgecolor": "#D3E0EB", "axes.labelcolor": SLATE,
    "xtick.color": SLATE, "ytick.color": SLATE,
})


def carrega(caminho):
    saida = []
    with open(caminho, encoding="utf-8", errors="replace") as f:
        for ln in f:
            t, _, s = ln.partition("\t")
            try:
                saida.append((float(t), s.strip()))
            except ValueError:
                pass
    return saida


def fatia(dados, ini, fim):
    txt = "\r\n".join(s for t, s in dados if ini <= t <= fim)
    return nmea.ler_fluxo(txt.encode("ascii", "replace"))


def janelas_de(fx):
    """Corta em janelas de JANELA epocas; cada uma rende o seu proprio CEP."""
    saida = []
    for i in range(0, len(fx) - JANELA + 1, JANELA):
        e = nmea.estatisticas(fx[i:i + JANELA])
        saida.append({"cep50": e["hpe_m"]["cep50"], "cep95": e["hpe_m"]["cep95"]})
    return saida


def resume(ps, chave):
    v = [p[chave] for p in ps]
    return statistics.median(v), min(v), max(v)


def main():
    J = json.load(open(SAIDA + "/_janelas.json"))
    rover = carrega(SAIDA + "/rover.tsv")
    ref = carrega(SAIDA + "/ref_9151.tsv")

    dados = {"9151": [], "q1": [], "q2": [], "rede": [], "local": []}
    for j in J:
        fx = fatia(rover, j["ini"], j["fim"])
        dados["9151"] += janelas_de(fatia(ref, j["ini"], j["fim"]))
        dados["q1"] += janelas_de([f for f in fx if f.qualidade == 1])
        dados["q2"] += janelas_de([f for f in fx if f.qualidade == 2])
        fixos = [f for f in fx if f.qualidade == 4]
        if j["cond"] == "V":
            dados["rede"] += janelas_de(fixos)
        elif j["cond"] == "L":
            dados["local"] += janelas_de(fixos)

    LINHAS = [
        ("9151", "nRF9151\nGPS L1", SLATE),
        ("q1", "X20P autônomo\nsem correção", BLUE),
        ("q2", "X20P + SBAS\ncorreção por satélite", AMBAR),
        ("rede", "X20P + rede\nestação a 16,4 km", VERDE),
        ("local", "X20P + base local\na 1,42 m", NAVY),
    ]
    LINHAS = [(k, r, c) for k, r, c in LINHAS if dados[k]]

    print("=" * 78)
    for k, rot, _ in LINHAS:
        m50, l50, h50 = resume(dados[k], "cep50")
        m95, _, _ = resume(dados[k], "cep95")
        print("%-32s %2d janelas de %d s  CEP50=%.3f (%.3f-%.3f)  CEP95=%.3f"
              % (rot.replace("\n", " · "), len(dados[k]), JANELA, m50, l50, h50, m95))
    ref50 = resume(dados["9151"], "cep50")[0]
    print()
    for k, rot, _ in LINHAS[1:]:
        print("  nRF9151 -> %-30s %5.1fx" % (rot.replace("\n", " · "),
                                             ref50 / resume(dados[k], "cep50")[0]))

    fig, eixos = plt.subplots(1, 2, figsize=(13.0, 5.8), sharey=True)
    fig.patch.set_facecolor("white")
    for ax, chave, sub in zip(eixos, ("cep50", "cep95"),
                              ("CEP50 — metade das posições cai dentro",
                               "CEP95 — 19 de cada 20 caem dentro")):
        ax.set_facecolor(PANEL)
        ys, rot = [], []
        for i, (k, nome, cor) in enumerate(LINHAS):
            ps = dados[k]
            y = len(LINHAS) - 1 - i
            ys.append(y)
            rot.append("%s\n%d janelas" % (nome, len(ps)))
            med, lo, hi = resume(ps, chave)
            ax.plot([lo, hi], [y, y], color=cor, lw=2.2, alpha=0.40,
                    solid_capstyle="round", zorder=1)
            ax.plot([p[chave] for p in ps], [y] * len(ps), "o", ms=6.5,
                    mfc="none", mec=cor, mew=1.3, alpha=0.7, zorder=2)
            ax.plot([med], [y], "o", ms=13, color=cor, mec="white", mew=2, zorder=3)
            ax.annotate("%.2f m" % med if med >= 0.1 else "%.0f cm" % (med * 100),
                        (med, y), textcoords="offset points", xytext=(0, 15),
                        ha="center", fontsize=11, color=INK, fontweight="bold")
            ax.annotate("%.3f–%.3f" % (lo, hi), (med, y),
                        textcoords="offset points", xytext=(0, -22),
                        ha="center", fontsize=8, color=SLATE)
        ax.set_yticks(ys)
        ax.set_yticklabels(rot, fontsize=9.5, color=INK)
        ax.set_ylim(-0.62, len(LINHAS) - 0.38)
        ax.set_xlabel("erro horizontal [m]", fontsize=10)
        ax.set_title(sub, fontsize=11.5, color=NAVY, pad=14, loc="left")
        ax.set_xscale("log")
        ax.grid(axis="x", color=GRADE, lw=0.7, alpha=0.6, which="major")
        ax.grid(axis="x", color=GRADE, lw=0.4, alpha=0.3, which="minor")
        ax.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)

    fig.suptitle("A escada de precisão — céu aberto, três antenas na mesma altura, "
                 "medidas ao mesmo tempo",
                 fontsize=13, color=INK, x=0.012, ha="left", y=0.985)
    fig.text(0.012, 0.012,
             "Janelas de 100 s em todas as linhas: o CEP cresce com a duração, "
             "e os blocos renderam de 34 a 297 épocas no seu regime.\n"
             "Cada degrau é recortado pela qualidade do fix — misturar regimes "
             "mede o degrau entre soluções, não o ruído de nenhuma delas.  "
             "Ponto cheio = mediana; círculos = cada janela; linha = min–max.",
             fontsize=8.5, color=SLATE, linespacing=1.5)
    fig.tight_layout(rect=(0, 0.075, 1, 0.945))
    png = sys.argv[1] if len(sys.argv) > 1 else SAIDA + "/escada.png"
    fig.savefig(png, dpi=170, facecolor="white")
    print("\nfigura em", png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
