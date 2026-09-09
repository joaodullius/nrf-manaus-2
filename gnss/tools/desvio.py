#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desenha a escada de precisao: o mapa de desvio de cada log, lado a lado — codigo do curso.

    python desvio.py --log "nRF9151 autonomo=capturas/nrf9151_aberto.nmea" \\
                     --log "X20P aberto=capturas/x20p_aberto.uc2" \\
                     --log "X20P RTK=capturas/x20p_rtk.uc2" \\
                     --png doc/gnss/img/escada_precisao.png \\
                     --json doc/gnss/data/escada_precisao.json

Cada --log e um cenario: "ROTULO=caminho", de 1 a 4. Com um log so, sai o mapa
de desvio daquele receptor, no espirito do Deviation Map do u-center 2, com o
painel de estatisticas ao lado. Com dois ou mais, os mapas ficam lado a lado e
a figura vira o argumento central do modulo: CEP50 e CEP95 sao os numeros.

O problema da figura e a escala. O RTK espalha centimetros; o nRF9151, metros.
No mesmo eixo, o RTK vira um ponto; com um eixo para cada um, o leitor perde a
razao entre eles — que e justamente a mensagem. A solucao aqui e ter os dois:

    - cada mapa tem a sua escala, com os aneis rotulados em metros, para que a
      forma da nuvem apareca em todos;
    - embaixo, uma regua unica em escala logaritmica, onde o CEP50 -> CEP95 de
      cada cenario e uma barra no MESMO eixo. Um degrau de 10x na regua e o mesmo
      tamanho em qualquer ponto dela, entao a distancia entre as barras e a
      distancia real entre os receptores.

Sem --referencia, o desvio e contra a media dos proprios fixes: PRECISAO, o
espalhamento da nuvem. Com --referencia LAT,LON, e contra aquela coordenada:
EXATIDAO, onde a nuvem esta. A figura diz qual dos dois esta mostrando.

Nao acessa rede nem inventa dados: log que nao existe e erro.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import transforms  # noqa: E402
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch  # noqa: E402

import nmea  # noqa: E402

# identidade visual do curso
INK, SLATE, NAVY, BLUE = "#0B1B2B", "#566577", "#00224E", "#0093D0"
PANEL, LINE = "#EDF3F8", "#D3E0EB"
GRADE = "#B9C9D6"
# uma cor por cenario, em ordem fixa: autonomo, aberto multibanda, RTK, extra
CORES = [SLATE, BLUE, "#12A36E", NAVY]
MAX_LOGS = 4

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "axes.edgecolor": LINE, "axes.labelcolor": SLATE,
    "xtick.color": SLATE, "ytick.color": SLATE,
})


# ----------------------------------------------------------------- utilidades

def fmt_m(v: float, anel: bool = False) -> str:
    """Metros em texto de slide: 4,5 m / 38 cm / 1,2 cm, com virgula decimal.

    Com anel=True, um raio redondo sai sem decimal (8 m, e nao 8,0 m).
    """
    if v >= 10 or (anel and v >= 1 and abs(v - round(v)) < 1e-6):
        s = f"{v:.0f} m"
    elif v >= 1:
        s = f"{v:.1f} m"
    elif v >= 0.1:
        s = f"{v * 100:.0f} cm"
    else:
        s = f"{v * 100:.1f} cm"
    return s.replace(".", ",")


def fmt_pt(v: float, casas: int = 2) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def duracao_s(fixes: list[nmea.Fix]) -> float | None:
    """Do hhmmss.ss do primeiro ao ultimo fix, tolerando a virada da meia-noite."""
    def seg(h: str) -> float | None:
        try:
            return int(h[0:2]) * 3600 + int(h[2:4]) * 60 + float(h[4:])
        except (ValueError, IndexError):
            return None
    a, b = seg(fixes[0].hora), seg(fixes[-1].hora)
    if a is None or b is None:
        return None
    return (b - a) % 86400


def fmt_duracao(s: float | None) -> str:
    if s is None:
        return "?"
    m, seg = divmod(int(round(s)), 60)
    return f"{m} min {seg:02d} s" if m else f"{seg} s"


PASSOS = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]


def escala_mapa(maximo: float) -> tuple[float, float]:
    """(passo entre aneis, raio do mapa): 3 a 5 aneis, o ultimo cobrindo o pior fix."""
    alvo = max(maximo, 1e-3) * 1.05
    for passo in PASSOS:
        if alvo / passo <= 5:
            return passo, math.ceil(alvo / passo) * passo
    passo = PASSOS[-1]
    return passo, math.ceil(alvo / passo) * passo


def elipse_sigma(leste: list[float], norte: list[float]) -> tuple[float, float, float]:
    """(semi-eixo maior, semi-eixo menor, angulo em graus) da elipse de 1 sigma."""
    if len(leste) < 3:
        return 0.0, 0.0, 0.0
    cov = np.cov(np.array(leste), np.array(norte))
    val, vet = np.linalg.eigh(cov)
    ordem = np.argsort(val)[::-1]
    val, vet = val[ordem], vet[:, ordem]
    ang = math.degrees(math.atan2(vet[1, 0], vet[0, 0]))
    return math.sqrt(max(val[0], 0)), math.sqrt(max(val[1], 0)), ang


# --------------------------------------------------------------------- mapa

def desenhar_mapa(ax, st: dict, cor: str) -> None:
    """O Deviation Map de um cenario: aneis, nuvem, CEP50, CEP95 e elipse 1 sigma."""
    leste, norte = st["_leste_m"], st["_norte_m"]
    hpe = st["hpe_m"]
    passo, raio = escala_mapa(hpe["max"])

    ax.set_aspect("equal")
    ax.set_xlim(-raio * 1.18, raio * 1.18)
    ax.set_ylim(-raio * 1.18, raio * 1.18)
    ax.axis("off")

    # disco branco com a grade polar tracejada, como no u-center
    ax.add_patch(Circle((0, 0), raio, facecolor="white", edgecolor=GRADE, lw=0.9, zorder=1))
    n_aneis = int(round(raio / passo))
    for k in range(1, n_aneis + 1):
        r = k * passo
        ax.add_patch(Circle((0, 0), r, fill=False, edgecolor=GRADE, lw=0.7,
                            ls=(0, (3, 3)), zorder=2))
        if k in (1, n_aneis):
            ax.text(r * math.cos(math.radians(60)), r * math.sin(math.radians(60)),
                    fmt_m(r, anel=True), fontsize=7.5, color=SLATE,
                    ha="left", va="bottom", zorder=6)
    ax.plot([-raio, raio], [0, 0], color=GRADE, lw=0.7, ls=(0, (3, 3)), zorder=2)
    ax.plot([0, 0], [-raio, raio], color=GRADE, lw=0.7, ls=(0, (3, 3)), zorder=2)
    for txt, x, y in (("N", 0, raio * 1.08), ("S", 0, -raio * 1.08),
                      ("L", raio * 1.08, 0), ("O", -raio * 1.08, 0)):
        ax.text(x, y, txt, fontsize=8.5, color=SLATE, ha="center", va="center", zorder=6)

    # a nuvem
    n = len(leste)
    tam = 14 if n < 200 else (8 if n < 2000 else 4)
    ax.scatter(leste, norte, s=tam, color=cor, alpha=0.55, lw=0, zorder=4)

    # elipse de 1 sigma, CEP50 e CEP95
    a, b, ang = elipse_sigma(leste, norte)
    if a > 0:
        ax.add_patch(Ellipse((0, 0), 2 * a, 2 * b, angle=ang, fill=False,
                             edgecolor=NAVY, lw=1.0, ls=(0, (1, 2)), zorder=5))
    ax.add_patch(Circle((0, 0), hpe["cep50"], fill=False, edgecolor=INK, lw=1.5, zorder=5))
    ax.add_patch(Circle((0, 0), hpe["cep95"], fill=False, edgecolor=INK, lw=1.2,
                        ls=(0, (5, 3)), zorder=5))
    _rotulo_anel(ax, "CEP50", hpe["cep50"], -35, raio)
    _rotulo_anel(ax, "CEP95", hpe["cep95"], -145, raio)

    # o centro: a media ou a referencia
    ax.plot(0, 0, marker="+", color=INK, ms=9, mew=1.4, zorder=6)


def _rotulo_anel(ax, txt: str, r: float, graus: float, raio: float) -> None:
    ang = math.radians(graus)
    x, y = r * math.cos(ang), r * math.sin(ang)
    ax.annotate(txt, (x, y), xytext=(x + 0.04 * raio * math.copysign(1, x),
                                     y - 0.04 * raio),
                fontsize=8, color=INK, fontweight="bold", zorder=7,
                ha="left" if x >= 0 else "right", va="top",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


# ------------------------------------------------------------ estatisticas

def desenhar_stats(ax, rotulo: str, st: dict, cor: str, dur: float | None,
                    lateral: bool) -> None:
    """CEP50 e CEP95 grandes; o resto do painel do u-center em letra pequena."""
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    hpe = st["hpe_m"]
    ns, ew = st["desvio_ns_m"], st["desvio_ew_m"]
    quals = ", ".join(f"{q} {v}" for q, v in st["qualidades"].items())

    if lateral:
        # painel em coluna ao lado do mapa (um log so)
        y = 0.97
        ax.plot(0.03, y - 0.015, "o", color=cor, ms=9, transform=ax.transAxes, clip_on=False)
        ax.text(0.09, y, rotulo, fontsize=15, color=INK, fontweight="bold", va="top")
        y -= 0.13
        for nome, v in (("CEP50", hpe["cep50"]), ("CEP95", hpe["cep95"])):
            ax.text(0.03, y, nome, fontsize=10, color=SLATE, va="top")
            ax.text(0.03, y - 0.05, fmt_m(v), fontsize=30, color=INK, fontweight="bold", va="top")
            y -= 0.22
        y -= 0.02
        linhas = [
            f"{st['n']} fixes em {fmt_duracao(dur)}",
            f"qualidade: {quals}",
            f"HPE  avg {fmt_m(hpe['avg'])}   std {fmt_m(hpe['std'])}   max {fmt_m(hpe['max'])}",
            f"CEP68 {fmt_m(hpe['cep68'])}",
            f"N-S  std {fmt_m(ns['std'])}   L-O  std {fmt_m(ew['std'])}",
        ]
        if st["hdop"]:
            linhas.append(f"HDOP avg {fmt_pt(st['hdop']['avg'], 1)}   "
                          f"satelites avg {fmt_pt(st['sats']['avg'], 1)}")
        for ln in linhas:
            ax.text(0.03, y, ln, fontsize=9.5, color=SLATE, va="top")
            y -= 0.062
        return

    # bloco embaixo do mapa (varios logs)
    ax.plot(0.06, 0.93, "o", color=cor, ms=8, transform=ax.transAxes, clip_on=False)
    ax.text(0.13, 0.955, rotulo, fontsize=13, color=INK, fontweight="bold", va="top")
    for x0, nome, v in ((0.06, "CEP50", hpe["cep50"]), (0.54, "CEP95", hpe["cep95"])):
        ax.text(x0, 0.76, nome, fontsize=9.5, color=SLATE, va="top")
        ax.text(x0, 0.65, fmt_m(v), fontsize=24, color=INK, fontweight="bold", va="top")
    linhas = [
        f"{st['n']} fixes em {fmt_duracao(dur)}  ·  {quals}",
        f"HPE avg {fmt_m(hpe['avg'])}  std {fmt_m(hpe['std'])}  max {fmt_m(hpe['max'])}",
        f"std N-S {fmt_m(ns['std'])}  ·  L-O {fmt_m(ew['std'])}"
        + (f"  ·  HDOP {fmt_pt(st['hdop']['avg'], 1)}" if st["hdop"] else ""),
    ]
    y = 0.33
    for ln in linhas:
        ax.text(0.06, y, ln, fontsize=8.3, color=SLATE, va="top")
        y -= 0.105


# --------------------------------------------------------------------- regua

REGUA_TICKS = [(0.001, "1 mm"), (0.002, "2"), (0.005, "5"), (0.01, "1 cm"), (0.02, "2"),
               (0.05, "5"), (0.1, "10 cm"), (0.2, "20"), (0.5, "50"), (1, "1 m"),
               (2, "2"), (5, "5"), (10, "10 m"), (20, "20"), (50, "50"), (100, "100 m")]


def desenhar_regua(ax, cenarios: list[dict]) -> None:
    """A mesma regua para todos, em log: a barra vai do CEP50 ao CEP95 de cada um."""
    menor = min(c["st"]["hpe_m"]["cep50"] for c in cenarios)
    maior = max(c["st"]["hpe_m"]["cep95"] for c in cenarios)
    x0 = 10 ** math.floor(math.log10(max(menor, 1e-3) / 1.5))
    x1 = 10 ** math.ceil(math.log10(maior * 1.5))
    if x1 / x0 < 100:            # um log so: pelo menos duas decadas, para dar contexto
        x1 = x0 * 100
    ax.set_xscale("log")
    ax.set_xlim(x0, x1)
    n = len(cenarios)
    ax.set_ylim(-0.6, n - 0.4)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRADE)
    ax.set_yticks([])
    ticks = [(v, t) for v, t in REGUA_TICKS if x0 <= v <= x1]
    ax.set_xticks([v for v, _ in ticks])
    ax.set_xticklabels([t for _, t in ticks], fontsize=8.5)
    ax.set_xticks([], minor=True)
    ax.tick_params(axis="x", length=3, color=GRADE)
    for v, _ in ticks:
        ax.axvline(v, color=LINE, lw=0.7, zorder=1)

    for i, c in enumerate(cenarios):
        y = n - 1 - i
        h = c["st"]["hpe_m"]
        ax.plot([h["cep50"], h["cep95"]], [y, y], color=c["cor"], lw=7,
                solid_capstyle="round", zorder=3)
        ax.plot(h["cep50"], y, "o", color=c["cor"], ms=9, zorder=4)
        ax.plot(h["cep95"], y, "o", color=c["cor"], mfc="white", ms=9, mew=2, zorder=4)
        ax.text(h["cep50"] / 1.12, y, fmt_m(h["cep50"]), fontsize=9.5, color=INK,
                fontweight="bold", ha="right", va="center", zorder=5)
        ax.text(h["cep95"] * 1.12, y, fmt_m(h["cep95"]), fontsize=9.5, color=INK,
                fontweight="bold", ha="left", va="center", zorder=5)
        # o rotulo da linha fica na margem a esquerda do eixo, fora da regua
        ax.text(-0.012, y, c["rotulo"], fontsize=8.5, color=SLATE, ha="right", va="center",
                transform=transforms.blended_transform_factory(ax.transAxes, ax.transData))
        # o degrau: quantas vezes o CEP50 encolheu (ou cresceu) em relacao ao de cima
        if i > 0:
            acima = cenarios[i - 1]["st"]["hpe_m"]["cep50"]
            razao = acima / h["cep50"]
            if razao >= 1.15 or razao <= 1 / 1.15:
                r = razao if razao >= 1 else 1 / razao
                txt = ((f"{r:.0f}" if r >= 10 else fmt_pt(r, 1)) + "× "
                       + ("menor" if razao >= 1 else "maior"))
                ax.text(math.sqrt(acima * h["cep50"]), y + 0.5, "CEP50 " + txt,
                        fontsize=8, color=INK, ha="center", va="center", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=LINE, lw=0.6))


# -------------------------------------------------------------------- figura

def figura(cenarios: list[dict], referencia: tuple[float, float] | None):
    n = len(cenarios)
    lateral = n == 1

    # medidas em polegadas; o eixo de fundo usa as mesmas unidades para os paineis
    col_w = 4.3
    marg, gap = 0.45, 0.35
    h_cab, h_mapa, h_stats, h_regua, h_pe = 1.35, col_w, (0.0 if lateral else 1.9), 1.55, 0.45
    if lateral:
        W = marg * 2 + col_w + gap + 4.6
    else:
        W = marg * 2 + col_w * n + gap * (n - 1)
    H = h_cab + h_mapa + h_stats + gap + h_regua + h_pe
    fig = plt.figure(figsize=(W, H), dpi=200, facecolor="white")
    fundo = fig.add_axes([0, 0, 1, 1], zorder=0)
    fundo.set_xlim(0, W)
    fundo.set_ylim(0, H)
    fundo.axis("off")

    def eixo(x, y, w, h, z=2):
        return fig.add_axes([x / W, y / H, w / W, h / H], zorder=z)

    # cabecalho
    if lateral:
        titulo = f"Mapa de desvio: {cenarios[0]['rotulo']}"
    else:
        titulo = f"Escada de precisão: {n} cenários, o mesmo ponto, a mesma régua"
    if referencia is None:
        sub = ("Desvio horizontal de cada fix contra a MÉDIA dos próprios fixes "
               "— mede precisão: o espalhamento da nuvem")
    else:
        sub = ("Desvio horizontal de cada fix contra a REFERÊNCIA "
               f"{fmt_pt(referencia[0], 6)}, {fmt_pt(referencia[1], 6)} "
               "— mede exatidão: onde a nuvem está")
    fig.text(marg / W, (H - 0.32) / H, titulo, fontsize=16, color=INK, fontweight="bold",
             va="top")
    fig.text(marg / W, (H - 0.68) / H, sub, fontsize=9.5, color=SLATE, va="top")
    # legenda dos tracos, numa linha propria abaixo do subtitulo
    lg = eixo(marg, H - 1.22, W - 2 * marg, 0.4, z=3)
    lg.axis("off")
    lg.set_xlim(0, W - 2 * marg)
    lg.set_ylim(0, 0.4)
    itens = [("CEP50", INK, "-", 1.5), ("CEP95", INK, (0, (5, 3)), 1.2),
             ("elipse 1σ", NAVY, (0, (1, 2)), 1.0)]
    x = 0.0
    for txt, cor, ls, lw in itens:
        lg.plot([x, x + 0.38], [0.2, 0.2], color=cor, ls=ls, lw=lw)
        lg.text(x + 0.46, 0.2, txt, fontsize=8.5, color=SLATE, va="center")
        x += 1.15
    lg.plot(x + 0.19, 0.2, marker="+", color=INK, ms=8, mew=1.4)
    lg.text(x + 0.46, 0.2, "centro = " + ("média dos fixes" if referencia is None
                                          else "referência informada"),
            fontsize=8.5, color=SLATE, va="center")

    # paineis: um por cenario
    y_painel = h_pe + h_regua + gap
    for i, c in enumerate(cenarios):
        x = marg + i * (col_w + gap)
        w_painel = col_w + gap + 4.6 if lateral else col_w
        fundo.add_patch(FancyBboxPatch((x, y_painel), w_painel, h_mapa + h_stats,
                                       boxstyle="round,pad=0,rounding_size=0.18",
                                       facecolor=PANEL, edgecolor=LINE, lw=1.0))
        ax_m = eixo(x + 0.12, y_painel + h_stats + 0.12, col_w - 0.24, h_mapa - 0.24)
        desenhar_mapa(ax_m, c["st"], c["cor"])
        if lateral:
            ax_s = eixo(x + col_w + gap * 0.5, y_painel + 0.15, 4.6, h_mapa - 0.3)
        else:
            ax_s = eixo(x, y_painel, col_w, h_stats)
        desenhar_stats(ax_s, c["rotulo"], c["st"], c["cor"], c["dur"], lateral)

    # a regua comum
    ax_r = eixo(marg + 1.2, h_pe, W - marg * 2 - 1.2 - 0.3, h_regua - 0.35)
    desenhar_regua(ax_r, cenarios)
    fig.text(marg / W, (h_pe + h_regua - 0.02) / H,
             "Na mesma régua, em escala logarítmica: ● CEP50  até  ○ CEP95",
             fontsize=10, color=INK, fontweight="bold", va="top")
    fig.text(marg / W, 0.12 / H,
             "Cada mapa tem a própria escala (aneis rotulados); a régua abaixo põe "
             "todos no mesmo eixo. Um degrau de 10× tem o mesmo tamanho em qualquer "
             "ponto da régua.",
             fontsize=8, color=SLATE, va="bottom")
    return fig


# -------------------------------------------------------------- texto e json

def painel_texto(c: dict) -> str:
    st, h = c["st"], c["st"]["hpe_m"]
    ns, ew = st["desvio_ns_m"], st["desvio_ew_m"]
    ref = st["referencia"]
    ln = [
        f"== {c['rotulo']}  ({c['arquivo']})",
        f"   fixes: {st['n']}   duracao: {fmt_duracao(c['dur'])}   "
        f"qualidade: {st['qualidades']}",
        f"   centro ({ref['tipo']}): {ref['lat']:.7f}, {ref['lon']:.7f}",
        f"   HPE    min {h['min']:.3f}  max {h['max']:.3f}  avg {h['avg']:.3f}  "
        f"std {h['std']:.3f}  m",
        f"   CEP50 {h['cep50']:.3f} m   CEP68 {h['cep68']:.3f} m   CEP95 {h['cep95']:.3f} m",
        f"   N-S    min {ns['min']:+.3f}  max {ns['max']:+.3f}  avg {ns['avg']:+.3f}  "
        f"std {ns['std']:.3f}  m",
        f"   L-O    min {ew['min']:+.3f}  max {ew['max']:+.3f}  avg {ew['avg']:+.3f}  "
        f"std {ew['std']:.3f}  m",
    ]
    if st["altitude_m"]:
        a = st["altitude_m"]
        ln.append(f"   alt    min {a['min']:.1f}  max {a['max']:.1f}  avg {a['avg']:.1f}  "
                  f"std {a['std']:.2f}  m")
    if st["hdop"]:
        ln.append(f"   HDOP   avg {st['hdop']['avg']:.2f}   sats avg {st['sats']['avg']:.1f}")
    return "\n".join(ln)


def _arredonda(v, casas: int):
    """Arredonda recursivamente os floats de um dict, para o JSON nao sair com 15 digitos."""
    if isinstance(v, float):
        return round(v, casas)
    if isinstance(v, dict):
        return {k: _arredonda(x, 7 if k in ("lat", "lon") else casas) for k, x in v.items()}
    return v


def para_json(cenarios: list[dict], referencia: tuple[float, float] | None) -> dict:
    if referencia is None:
        cond = ("desvio horizontal de cada fix contra a media dos proprios fixes "
                "(precisao, como o Deviation Map do u-center 2 faz por padrao)")
    else:
        cond = (f"desvio horizontal de cada fix contra a referencia "
                f"{referencia[0]:.7f}, {referencia[1]:.7f} (exatidao)")
    saida = {
        "fonte": "medida propria — desvio.py sobre as sentencas GGA dos logs capturados "
                 "na bancada do curso",
        "condicoes": cond + "; CEP50/68/95 sao percentis do erro horizontal (HPE), "
                            "metros no WGS84, mesma antena/ponto em todos os cenarios",
        "cenarios": [],
    }
    for c in cenarios:
        st = {k: _arredonda(v, 3) for k, v in c["st"].items() if not k.startswith("_")}
        saida["cenarios"].append({"rotulo": c["rotulo"], "arquivo": c["arquivo"],
                                  "duracao_s": c["dur"], **st})
    return saida


# ---------------------------------------------------------------------- cli

def _log(arg: str) -> tuple[str, Path]:
    rotulo, sep, caminho = arg.partition("=")
    if not sep or not rotulo.strip() or not caminho.strip():
        raise argparse.ArgumentTypeError(f"esperado ROTULO=caminho, veio '{arg}'")
    return rotulo.strip(), Path(caminho.strip())


def _referencia(arg: str) -> tuple[float, float]:
    try:
        lat, lon = (float(x) for x in arg.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"esperado LAT,LON em graus decimais, veio '{arg}'")
    return lat, lon


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--log", action="append", required=True, type=_log, metavar="ROTULO=CAMINHO",
                   help="um cenario; repita de 1 a 4 vezes, na ordem da escada")
    p.add_argument("--referencia", type=_referencia, metavar="LAT,LON",
                   help="desvio contra esta coordenada (exatidao) em vez da media (precisao)")
    p.add_argument("--png", type=Path, help="figura de saida")
    p.add_argument("--json", type=Path, help="estatisticas de saida, no formato de doc/*/data")
    a = p.parse_args(argv)
    if len(a.log) > MAX_LOGS:
        p.error(f"no maximo {MAX_LOGS} logs")

    cenarios = []
    for i, (rotulo, caminho) in enumerate(a.log):
        if not caminho.is_file():
            print(f"erro: log '{rotulo}' nao encontrado: {caminho}", file=sys.stderr)
            return 1
        fixes = nmea.ler_arquivo(caminho)
        if not fixes:
            print(f"erro: log '{rotulo}' sem nenhum GGA com fix: {caminho}", file=sys.stderr)
            return 1
        cenarios.append({
            "rotulo": rotulo, "arquivo": caminho.as_posix(), "cor": CORES[i],
            "st": nmea.estatisticas(fixes, a.referencia), "dur": duracao_s(fixes),
        })

    for c in cenarios:
        print(painel_texto(c))
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(para_json(cenarios, a.referencia),
                                     ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"json: {a.json}")
    if a.png:
        a.png.parent.mkdir(parents=True, exist_ok=True)
        fig = figura(cenarios, a.referencia)
        fig.savefig(a.png, dpi=200, facecolor="white")
        print(f"png: {a.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
