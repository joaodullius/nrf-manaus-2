# -*- coding: utf-8 -*-
"""Figura da matriz: CEP50 e CEP95 por condicao, com a faixa das tres rodadas.

A barra e a MEDIANA dos blocos daquela condicao; o traco fino atras dela e o
intervalo min-max entre as rodadas. E esse traco que diz se a diferenca entre
duas barras significa alguma coisa: quando as faixas se sobrepoem, a diferenca
cabe dentro da variacao do proprio ambiente.

Todos os blocos tem 5 min. Nao ha CEP concatenado aqui — cada bloco rendeu o seu.
"""
import json
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, "C:/work/nrf-manaus-2/gnss/tools")
sys.path.insert(0, "C:/b")
import nmea  # noqa: E402
from analisa_matriz import fatia_9151, painel, sats_usados  # noqa: E402

INK, SLATE, NAVY, BLUE = "#0B1B2B", "#566577", "#00224E", "#0093D0"
PANEL, LINE, GRADE = "#EDF3F8", "#D3E0EB", "#B9C9D6"
VERDE = "#12A36E"
SAIDA = "C:/b/matriz"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "axes.edgecolor": LINE, "axes.labelcolor": SLATE,
    "xtick.color": SLATE, "ytick.color": SLATE,
})

# o degrau, do pe para o topo. Todas as constelacoes ligadas em todas as linhas.
#
# A ultima linha e o recorte do NTRIP nas epocas em RTK fixo, e ela precisa
# existir separada: um bloco que mistura fixo e flutuante nao mede o ruido de
# nenhum dos dois, mede o DEGRAU entre as duas solucoes. Em r2_D o bloco inteiro
# da 0,479 m e a parte fixa da 0,069 m — 7x de diferenca produzida pela
# transicao. Somar os dois num numero so esconde justamente o que o RTK entrega.
LINHAS = [
    ("9151", "nRF9151\nGPS L1", SLATE),
    ("B", "X20P\nautônomo", BLUE),
    ("D", "X20P + NTRIP\nbloco inteiro", VERDE),
    ("Dfixo", "X20P + NTRIP\nsó RTK fixo", NAVY),
]
CONDS = {"B", "D"}


def coleta():
    """So os blocos das condicoes mostradas — e o nRF9151 so das MESMAS janelas.

    Fatiar o nRF9151 nas janelas exibidas, e nao em todas as 12, mantem a
    referencia simultanea: o que ele mostra e o ceu daqueles mesmos minutos.
    """
    janelas = json.load(open(SAIDA + "/_janelas.json"))
    dados = {k: [] for k, _, _ in LINHAS}
    for j in janelas:
        if j["cond"] not in CONDS:
            continue
        arq = SAIDA + "/" + j["bloco"] + ".nmea"
        px = painel(nmea.ler_arquivo(arq))
        if px:
            px["sats"] = sats_usados(arq)
            dados[j["cond"]].append(px)
            if px["cep50_fixo"] is not None:
                dados["Dfixo"].append({"cep50": px["cep50_fixo"],
                                       "cep95": px["cep95_fixo"],
                                       "sats": px["sats"]})
        p9 = painel(fatia_9151(j["ini"], j["fim"]))
        if p9:
            dados["9151"].append(p9)
    return dados


def resume(ps, chave):
    v = [p[chave] for p in ps]
    return statistics.median(v), min(v), max(v)


def figura(dados, png):
    """Ponto-e-faixa, nao barra.

    O eixo e logaritmico porque as tres condicoes moram em decadas diferentes.
    Barra em eixo log mente: o comprimento dela deveria contar a partir do zero,
    e em log o zero nao existe — a barra passa a comecar onde o eixo comeca, e o
    tamanho vira um artefato do limite escolhido. O ponto marca a mediana, a
    linha cobre min-max, e cada bloco aparece como um circulo vazado atras.
    """
    fig, eixos = plt.subplots(1, 2, figsize=(12.6, 5.2), sharey=True)
    fig.patch.set_facecolor("white")

    for ax, chave, titulo in zip(eixos, ("cep50", "cep95"),
                                 ("CEP50 — metade das posições cai dentro",
                                  "CEP95 — 19 de cada 20 caem dentro")):
        ax.set_facecolor(PANEL)
        ys, rotulos = [], []
        for i, (k, rot, cor) in enumerate(LINHAS):
            ps = dados.get(k)
            y = len(LINHAS) - 1 - i
            ys.append(y)
            rotulos.append("%s\n%d blocos" % (rot, len(ps)) if ps else rot)
            if not ps:
                continue
            med, lo, hi = resume(ps, chave)
            ax.plot([lo, hi], [y, y], color=cor, lw=2.2, alpha=0.40,
                    solid_capstyle="round", zorder=1)
            # cada bloco, para nao esconder quantas medidas sustentam a mediana
            ax.plot([p[chave] for p in ps], [y] * len(ps), "o", ms=7,
                    mfc="none", mec=cor, mew=1.4, alpha=0.75, zorder=2)
            ax.plot([med], [y], "o", ms=13, color=cor, mec="white", mew=2,
                    zorder=3)
            ax.annotate("%.2f m" % med, (med, y), textcoords="offset points",
                        xytext=(0, 15), ha="center", fontsize=11, color=INK,
                        fontweight="bold")
            ax.annotate("%.2f–%.2f" % (lo, hi), (med, y),
                        textcoords="offset points", xytext=(0, -22),
                        ha="center", fontsize=8.5, color=SLATE)

        ax.set_yticks(ys)
        ax.set_yticklabels(rotulos, fontsize=10, color=INK)
        ax.set_ylim(-0.62, len(LINHAS) - 0.38)
        ax.set_xlabel("erro horizontal [m]", fontsize=10)
        ax.set_title(titulo, fontsize=11.5, color=NAVY, pad=14, loc="left")
        ax.set_xscale("log")
        ax.grid(axis="x", color=GRADE, lw=0.7, alpha=0.6, which="major")
        ax.grid(axis="x", color=GRADE, lw=0.4, alpha=0.3, which="minor")
        ax.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)

    fig.suptitle("Dispersão horizontal — blocos de 5 min, 3 rodadas alternadas, medidos ao mesmo tempo",
                 fontsize=13, color=INK, x=0.012, ha="left", y=0.985)
    fig.text(0.012, 0.015,
             "Ponto cheio = mediana dos blocos.  Círculos vazados = cada bloco.  Linha = faixa min–max: "
             "faixas que se sobrepõem não sustentam diferença.\n"
             "Todas as constelações ligadas (GPS, GLONASS, Galileo, BeiDou); SBAS desligado. "
             "O RTK só fixou com GLONASS ligado: 306 épocas fixas em 901 com, 0 em 600 sem.",
             fontsize=8.5, color=SLATE, linespacing=1.5)
    fig.tight_layout(rect=(0, 0.075, 1, 0.945))
    fig.savefig(png, dpi=170, facecolor="white")
    print("figura em", png)


if __name__ == "__main__":
    figura(coleta(), sys.argv[1] if len(sys.argv) > 1 else SAIDA + "/matriz.png")
