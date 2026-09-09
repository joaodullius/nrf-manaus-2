# -*- coding: utf-8 -*-
"""Regera as figuras e os dados do deck de GNSS, todos na mesma janela de 5 min.

Por que refazer: as figuras anteriores foram medidas em janelas de 15 min e as
novas em 5 min. Os dois conjuntos estao certos para a sua propria janela, mas o
CEP cresce com a duracao (1,129 m em 15 min contra 0,338 m em 5 min, do MESMO
arquivo) — entao 5,57 m e 2,49 m para o mesmo receptor no mesmo lugar, lado a
lado num deck, seria indefensavel. Uma janela so, para tudo.

O X20P entra sempre com TODAS as constelacoes, GLONASS incluido. As condicoes
sem GLONASS ficam so como registro de bancada: elas serviram para medir o efeito
do GLONASS, nao para representar o receptor.

Fontes, todas de blocos de 300 s:
  nRF9151            gnss/capturas/matriz/9151_r*_[BD].nmea   (6 blocos)
  X20P autonomo      gnss/capturas/matriz/r*_B.nmea           (3 blocos)
  X20P + NTRIP VRS   gnss/capturas/matriz/r*_D.nmea           (3 blocos)
  X20P base propria  gnss/capturas/deslocamento/rover.tsv     (6 sub-blocos)

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
BLOCO = 300

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


def blocos_matriz(padrao, so_fixos=False):
    saida = []
    for arq in sorted((REPO / "gnss/capturas/matriz").glob(padrao)):
        fx = nmea.ler_arquivo(arq)
        if so_fixos:
            fx = [f for f in fx if f.qualidade == 4]
            if len(fx) < 60:
                continue
        p = painel(fx)
        p["arquivo"] = arq.name
        p["sats"] = sats_gsa(arq)
        saida.append(p)
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
    ("X20P + NTRIP\nVRS a dezenas de km", VERDE, lambda: blocos_matriz("r?_D.nmea")),
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
             "Todos os blocos têm 300 s — o CEP cresce com a janela, então "
             "durações diferentes mediriam a duração, não a condição.\n"
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
                     "Todos os blocos com 300 s: o CEP cresce com a janela. "
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
