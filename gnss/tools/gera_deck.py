# -*- coding: utf-8 -*-
"""Regera as figuras e os dados do deck de GNSS, todos na mesma janela de 100 s.

Duas regras mandam no numero que sai daqui, e as duas custaram medidas erradas
nesta bancada antes de virarem regra.

**Uma janela so, para tudo.** O CEP cresce com a duracao da captura: o mesmo
arquivo da 1,129 m inteiro (15 min) e 0,338 m em janelas de 5 min. Comparar
condicoes medidas em duracoes diferentes mede a duracao, nao a condicao. A
janela e 100 s porque essa e a MAIOR que as quatro condicoes conseguem
fornecer — o teto vem das epocas em RTK fixo do NTRIP, que so apareceram em
corridas de 113 e 193 epocas.

**Nos degraus de RTK, so epocas de qualidade 4.** Um bloco que mistura fixo com
flutuante nao mede o ruido de nenhum dos dois: mede o DEGRAU entre as duas
solucoes, que chega a ser 7x maior. As duas linhas de RTK recortam qualidade 4;
as epocas fixas do NTRIP sao contiguas, entao o recorte nao costura pedacos
separados no tempo.

O X20P entra sempre com TODAS as constelacoes, GLONASS incluido. As condicoes
sem GLONASS ficam so como registro de bancada: serviram para medir o efeito do
GLONASS, nao para representar o receptor.

Fontes:
  nRF9151            gnss/capturas/matriz/9151_r*_[BD].nmea
  X20P autonomo      gnss/capturas/matriz/r*_B.nmea
  X20P + NTRIP       gnss/capturas/matriz/r*_D.nmea        (so qualidade 4)
  X20P base propria  gnss/capturas/deslocamento/rover.tsv  (so qualidade 4)

A escada e a mediana dos blocos de cada degrau, com a faixa min-max ao lado.
Nunca o CEP de tudo concatenado: entre blocos o ambiente deriva, e a deriva
entraria como dispersao.
"""
import json
import math
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path("C:/work/nrf-manaus-2")
sys.path.insert(0, str(REPO / "gnss" / "tools"))
import nmea  # noqa: E402

IMG = REPO / "doc" / "gnss" / "img"
DATA = REPO / "doc" / "gnss" / "data"
BLOCO = 100

INK, SLATE, NAVY, BLUE = "#0B1B2B", "#566577", "#00224E", "#0093D0"
PANEL, GRADE, VERDE = "#EDF3F8", "#B9C9D6", "#12A36E"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "axes.edgecolor": "#D3E0EB", "axes.labelcolor": SLATE,
    "xtick.color": SLATE, "ytick.color": SLATE,
})


def painel(fx):
    e = nmea.estatisticas(fx)
    return {"n": e["n"], "cep50": e["hpe_m"]["cep50"], "cep95": e["hpe_m"]["cep95"],
            "hpe_m": e["hpe_m"], "qualidades": e["qualidades"],
            "hdop": e["hdop"]["avg"] if e["hdop"] else None}


def sats_gsa(caminho):
    """Satelites usados por epoca, contados nos GSA — o numSV da GGA satura em 12."""
    usados = epocas = 0
    for ln in Path(caminho).read_bytes().split(b"\r\n"):
        if ln[3:6] == b"GSA":
            usados += sum(1 for x in ln.split(b",")[3:15] if x.strip())
        elif ln[3:6] == b"GGA":
            epocas += 1
    return round(usados / epocas, 1) if epocas else None


def fatia(fx, nome, sats=None):
    """Corta em blocos de BLOCO epocas. Cada bloco rende um CEP proprio."""
    saida = []
    for i in range(0, len(fx) - BLOCO + 1, BLOCO):
        p = painel(fx[i:i + BLOCO])
        p["arquivo"] = "%s[%d:%d]" % (nome, i, i + BLOCO)
        p["sats"] = sats
        saida.append(p)
    return saida


def blocos_matriz(padrao, so_fixos=False):
    saida = []
    for arq in sorted((REPO / "gnss/capturas/matriz").glob(padrao)):
        fx = nmea.ler_arquivo(arq)
        sats = sats_gsa(arq)
        if so_fixos:
            # As epocas fixas destes blocos sao contiguas (113 e 193 numa corrida
            # unica), entao recortar nao costura pedacos separados no tempo.
            fx = [f for f in fx if f.qualidade == 4]
        saida += fatia(fx, arq.stem, sats)
    return saida


def blocos_base_propria():
    """P1 e P2 sao de 908 s; fatiadas em blocos de 300 s ficam comparaveis ao
    resto. Cada bloco tem media propria, entao posicoes diferentes nao
    atrapalham — o que se mede aqui e espalhamento, nao coordenada."""
    base = REPO / "gnss/capturas/deslocamento"
    marcas = json.load(open(base / "_marcas.json"))
    saida = []
    for nome in ("P1", "P2"):
        ini, fim = marcas[nome]
        linhas = []
        with open(base / "rover.tsv", encoding="utf-8", errors="replace") as f:
            for ln in f:
                t, _, s = ln.partition("\t")
                try:
                    t = float(t)
                except ValueError:
                    continue
                if ini <= t <= fim:
                    linhas.append(s.strip())
        fx = [f for f in nmea.ler_fluxo("\r\n".join(linhas).encode("ascii", "replace"))
              if f.qualidade == 4]
        for i in range(0, len(fx) - BLOCO + 1, BLOCO):
            p = painel(fx[i:i + BLOCO])
            p["arquivo"] = "%s[%d:%d]" % (nome, i, i + BLOCO)
            saida.append(p)
    return saida


def resume(ps, chave):
    v = [p[chave] for p in ps]
    return statistics.median(v), min(v), max(v)


# ------------------------------------------------------------------ a escada
DEGRAUS = [
    ("nRF9151\nGPS L1", SLATE, lambda: blocos_matriz("9151_r?_[BD].nmea")),
    ("X20P autônomo\ntodas as constelações", BLUE, lambda: blocos_matriz("r?_B.nmea")),
    ("X20P + NTRIP\nVRS, só RTK fixo", VERDE,
     lambda: blocos_matriz("r?_D.nmea", so_fixos=True)),
    ("X20P + base própria\nRTK fixo, 1,5 m", NAVY, blocos_base_propria),
]


def figura(dados, png, titulo):
    fig, eixos = plt.subplots(1, 2, figsize=(12.8, 5.4), sharey=True)
    fig.patch.set_facecolor("white")
    for ax, chave, sub in zip(eixos, ("cep50", "cep95"),
                              ("CEP50 — metade das posições cai dentro",
                               "CEP95 — 19 de cada 20 caem dentro")):
        ax.set_facecolor(PANEL)
        ys, rot = [], []
        for i, (nome, cor, ps) in enumerate(dados):
            y = len(dados) - 1 - i
            ys.append(y)
            rot.append("%s\n%d blocos" % (nome, len(ps)))
            med, lo, hi = resume(ps, chave)
            ax.plot([lo, hi], [y, y], color=cor, lw=2.2, alpha=0.40,
                    solid_capstyle="round", zorder=1)
            ax.plot([p[chave] for p in ps], [y] * len(ps), "o", ms=7,
                    mfc="none", mec=cor, mew=1.4, alpha=0.75, zorder=2)
            ax.plot([med], [y], "o", ms=13, color=cor, mec="white", mew=2, zorder=3)
            ax.annotate("%.2f m" % med if med >= 0.1 else "%.0f cm" % (med * 100),
                        (med, y), textcoords="offset points", xytext=(0, 15),
                        ha="center", fontsize=11, color=INK, fontweight="bold")
            ax.annotate("%.2f–%.2f" % (lo, hi), (med, y),
                        textcoords="offset points", xytext=(0, -22),
                        ha="center", fontsize=8.5, color=SLATE)
        ax.set_yticks(ys)
        ax.set_yticklabels(rot, fontsize=9.5, color=INK)
        ax.set_ylim(-0.62, len(dados) - 0.38)
        ax.set_xlabel("erro horizontal [m]", fontsize=10)
        ax.set_title(sub, fontsize=11.5, color=NAVY, pad=14, loc="left")
        ax.set_xscale("log")
        ax.grid(axis="x", color=GRADE, lw=0.7, alpha=0.6, which="major")
        ax.grid(axis="x", color=GRADE, lw=0.4, alpha=0.3, which="minor")
        ax.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
    fig.suptitle(titulo, fontsize=13, color=INK, x=0.012, ha="left", y=0.985)
    fig.text(0.012, 0.015,
             "Todos os blocos têm 100 s — a maior janela que as quatro condições "
             "fornecem, limitada pelas épocas em RTK fixo do NTRIP.  As duas linhas "
             "de RTK usam só épocas de qualidade 4.\n"
             "Ponto cheio = mediana dos blocos; círculos = cada bloco; linha = "
             "faixa min–max. Faixas que se sobrepõem não sustentam diferença.",
             fontsize=8.5, color=SLATE, linespacing=1.5)
    fig.tight_layout(rect=(0, 0.07, 1, 0.945))
    fig.savefig(png, dpi=170, facecolor="white")
    print("  figura:", png.name)


def main():
    dados = [(nome, cor, fn()) for nome, cor, fn in DEGRAUS]
    for nome, _, ps in dados:
        med50, lo50, hi50 = resume(ps, "cep50")
        med95, _, _ = resume(ps, "cep95")
        print("%-42s %d blocos  CEP50=%.3f (%.3f-%.3f)  CEP95=%.3f"
              % (nome.replace("\n", " · "), len(ps), med50, lo50, hi50, med95))

    figura(dados, IMG / "escada_precisao.png",
           "A escada de precisão — quatro degraus, medidos na mesma bancada")

    # so os dois receptores, que e a comparacao que abre o modulo
    figura(dados[:2], IMG / "comparativo_receptores.png",
           "Dois receptores, o mesmo céu, os mesmos minutos")

    saida = {
        "fonte": "medida propria — campanha da matriz (09/09/2026) e teste de "
                 "base propria, blocos de 300 s",
        "condicoes": "desvio horizontal de cada fix contra a media do proprio "
                     "bloco (precisao, como o Deviation Map do u-center 2). "
                     "Todos os blocos com 100 s, a maior janela que as quatro condicoes "
                     "fornecem. As linhas de RTK usam so epocas de qualidade 4. "
                     "X20P sempre com todas as constelacoes (GPS, GLONASS, "
                     "Galileo, BeiDou); SBAS desligado durante a matriz. "
                     "Cada bloco rende um CEP proprio; o valor de referencia e "
                     "a mediana dos blocos, nunca o CEP de tudo concatenado.",
        "degraus": [],
    }
    for nome, _, ps in dados:
        m50, l50, h50 = resume(ps, "cep50")
        m95, l95, h95 = resume(ps, "cep95")
        saida["degraus"].append({
            "rotulo": nome.replace("\n", " · "),
            "blocos": len(ps),
            "duracao_bloco_s": BLOCO,
            "cep50_m": {"mediana": round(m50, 3), "min": round(l50, 3), "max": round(h50, 3)},
            "cep95_m": {"mediana": round(m95, 3), "min": round(l95, 3), "max": round(h95, 3)},
            "por_bloco": [{"arquivo": p["arquivo"], "n": p["n"],
                           "cep50": round(p["cep50"], 3), "cep95": round(p["cep95"], 3),
                           "sats_usados": p.get("sats"),
                           "qualidades": p["qualidades"]} for p in ps],
        })
    ref = dados[0][2], dados[1][2]
    saida["razao_receptores"] = {
        "cep50": round(resume(ref[0], "cep50")[0] / resume(ref[1], "cep50")[0], 1),
        "cep95": round(resume(ref[0], "cep95")[0] / resume(ref[1], "cep95")[0], 1),
    }
    (DATA / "escada_precisao.json").write_text(
        json.dumps(saida, indent=1, ensure_ascii=False), encoding="utf-8")
    print("  dados:", "escada_precisao.json")
    print("  razao entre receptores:", saida["razao_receptores"])


if __name__ == "__main__":
    main()
