#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desenha o ceu que a antena enxerga: o skyplot de uma captura NMEA — codigo do curso.

    python ceu.py --log capturas/nrf9151_aberto.nmea --png doc/gnss/img/ceu_bancada.png

Grafico polar, olhando para cima: o azimute e o angulo (Norte no topo, Leste a
direita) e a elevacao e o raio invertido — 90 graus, o zenite, fica no CENTRO;
0 grau, o horizonte, fica na BORDA. Cada satelite aparece na posicao media da
captura, pintado pela forca do sinal (C/N0) e com a forma dizendo se entrou na
solucao de posicao. Em 15 min um satelite GPS anda uns 4 graus no ceu, menos
que o diametro do proprio marcador: a media basta.

E o diagnostico por tras de um CEP ruim. Em ceu aberto, C/N0 cresce com a
elevacao: um satelite a 60 graus entrega 40 dB-Hz ou mais. Se ele esta alto e
entrega 20, tem alguma coisa entre a antena e o ceu — e a figura mostra de que
lado. Um setor de 45 graus fica hachurado quando ha prova: um satelite acima de
15 graus que nao passa de 30 dB-Hz. Setor vazio nao e prova de nada.

As visadas sem orbita conhecida (ouvidas sem elevacao/azimute) nao cabem no ceu
e viram um numero: e o "ouco, mas nao sei onde esta".

O C/N0 tem uma categoria a parte: 0 dB-Hz nao e "o minimo da escala", e um
satelite rastreado sem sinal utilizavel. Ele sai em cinza, com um x.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

import nmea  # noqa: E402

# identidade visual do curso
INK, SLATE, NAVY = "#0B1B2B", "#566577", "#00224E"
BLUE, CYAN = "#0093D0", "#22C3E6"
PANEL, LINE = "#EDF3F8", "#D3E0EB"
GRADE = "#B9C9D6"
CINZA = "#9AA7B4"   # rastreado sem sinal (0 dB-Hz)

# escala sequencial de C/N0: um matiz so, do claro (fraco) ao escuro (forte)
CN0_MIN, CN0_MAX = 10.0, 50.0
CMAP = LinearSegmentedColormap.from_list("cn0", ["#CFE6F5", "#6DBDE6", BLUE, NAVY])
NORMA = Normalize(vmin=CN0_MIN, vmax=CN0_MAX)

# entra na solucao se esteve nas GSA em pelo menos metade das epocas
FRACAO_USADO = 0.5
# alto e fraco: acima desta elevacao, ceu aberto daria bem mais que este C/N0
ELEV_ALTO, CN0_FRACO = 45.0, 30.0
# um satelite so testemunha obstrucao do seu setor se estiver acima disto
ELEV_TESTEMUNHA = 15.0
SETORES = ["N", "NE", "L", "SE", "S", "SO", "O", "NO"]

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "axes.edgecolor": LINE, "axes.labelcolor": SLATE,
    "xtick.color": SLATE, "ytick.color": SLATE,
    "hatch.linewidth": 0.8,
})


# ----------------------------------------------------------------- utilidades

def fmt_pt(v: float, casas: int = 1) -> str:
    """Numero com virgula decimal, como vai para o slide."""
    return f"{v:.{casas}f}".replace(".", ",")


def ler_bytes(caminho: Path) -> bytes:
    """O fluxo cru de .nmea/.ubx, ou o conteudo desempacotado de um .uc2."""
    if caminho.suffix.lower() == ".uc2":
        import uc2
        return uc2.bruto(caminho)
    return caminho.read_bytes()


def duracao_s(dados: bytes) -> float | None:
    """Segundos entre o primeiro e o ultimo GGA com fix; None se nao houver dois."""
    fixes = nmea.ler_fluxo(dados)
    if len(fixes) < 2:
        return None

    def seg(h):
        try:
            return int(h[0:2]) * 3600 + int(h[2:4]) * 60 + float(h[4:])
        except (ValueError, IndexError):
            return None
    a, b = seg(fixes[0].hora), seg(fixes[-1].hora)
    if a is None or b is None:
        return None
    d = b - a
    return d + 86400 if d < 0 else d


def cor_cn0(cn0: float):
    return CINZA if cn0 <= 0 else CMAP(NORMA(cn0))


def classifica(res: dict) -> str:
    """'solucao', 'fora' (tem sinal, nao entra) ou 'mudo' (0 dB-Hz)."""
    if res["cn0_med"] <= 0:
        return "mudo"
    return "solucao" if res["fracao_usado"] >= FRACAO_USADO else "fora"


def alto_e_fraco(res: dict) -> bool:
    return res["elev_med"] >= ELEV_ALTO and 0 < res["cn0_med"] < CN0_FRACO


def setor(azim: float) -> int:
    """Indice do setor de 45 graus centrado nos pontos cardeais e colaterais."""
    return int(((azim + 22.5) % 360) // 45)


def setores(resumo: dict) -> list[dict]:
    """Por setor: o melhor C/N0 visto e se ha prova de obstrucao.

    Prova exige um satelite acima de ELEV_TESTEMUNHA: perto do horizonte todo
    sinal e fraco, com ou sem obstaculo, e nao serve de testemunha.
    """
    saida = []
    for i, nome in enumerate(SETORES):
        no_setor = [r for r in resumo.values() if setor(r["azim_med"]) == i]
        testemunhas = [r for r in no_setor if r["elev_med"] >= ELEV_TESTEMUNHA]
        saida.append({
            "setor": nome,
            "satelites": len(no_setor),
            "cn0_max": max((r["cn0_med"] for r in no_setor), default=None),
            "obstruido": bool(testemunhas) and all(r["cn0_med"] < CN0_FRACO for r in testemunhas),
        })
    return saida


def agregados(ceu: dict, resumo: dict) -> dict:
    """Os numeros que resumem o ceu inteiro, para o rodape e para o JSON."""
    na_sol = [r for r in resumo.values() if classifica(r) == "solucao"]
    mudos = [r for r in resumo.values() if classifica(r) == "mudo"]
    return {
        "epocas": max(ceu["usados"].values(), default=0),
        "satelites_com_posicao": len(resumo),
        "satelites_na_solucao": len(na_sol),
        "satelites_sem_sinal": len(mudos),
        "cn0_med_na_solucao": statistics.fmean([r["cn0_med"] for r in na_sol]) if na_sol else None,
        "visadas_com_posicao": len(ceu["com_posicao"]),
        "visadas_sem_orbita": len(ceu["sem_posicao"]),
        "alto_e_fraco": [prn for prn, r in resumo.items() if alto_e_fraco(r)],
        "setores": setores(resumo),
    }


# -------------------------------------------------------------------- texto

def tabela_texto(resumo: dict, ag: dict) -> str:
    # sem simbolo de grau: o console do Windows nem sempre esta em UTF-8
    linhas = [f"{'PRN':>4} {'elev':>6} {'azim':>6} {'C/N0':>6} {'uso':>6}  situacao"]
    nomes = {"solucao": "na solucao", "fora": "fora da solucao", "mudo": "sem sinal (0 dB-Hz)"}
    for prn, r in resumo.items():
        marca = "  <- alto e fraco: obstrucao" if alto_e_fraco(r) else ""
        linhas.append(f"{prn:>4} {r['elev_med']:>6.1f} {r['azim_med']:>6.1f} "
                      f"{r['cn0_med']:>6.1f} {100 * r['fracao_usado']:>5.1f}%  "
                      f"{nomes[classifica(r)]}{marca}")
    linhas.append("")
    linhas.append(f"epocas (GSA): {ag['epocas']}   satelites com posicao: "
                  f"{ag['satelites_com_posicao']}   na solucao: {ag['satelites_na_solucao']}")
    linhas.append(f"visadas sem orbita conhecida (GSV sem elev/azim): {ag['visadas_sem_orbita']}")
    linhas.append("melhor C/N0 por setor: " + "  ".join(
        f"{x['setor']} {x['cn0_max']:.0f}" if x["cn0_max"] is not None else f"{x['setor']} -"
        for x in ag["setores"]))
    obst = [x["setor"] for x in ag["setores"] if x["obstruido"]]
    if obst:
        linhas.append(f"setores com prova de obstrucao (satelite >= {ELEV_TESTEMUNHA:.0f} graus "
                      f"e < {CN0_FRACO:.0f} dB-Hz): {', '.join(obst)}")
    return "\n".join(linhas)


def _arredonda(d: dict) -> dict:
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def para_json(arquivo: Path, titulo: str | None, dur: float | None,
              resumo: dict, ag: dict) -> dict:
    cond = "medida propria desta bancada, antena do kit, sem correcao"
    if titulo:
        cond = f"{titulo}; " + cond
    if dur:
        cond += f"; captura de {dur / 60:.0f} min"
    return {
        "fonte": f"medida propria: GSV/GSA do log {arquivo.name}, lidas por ceu.py",
        "condicoes": cond + "; elevacao/azimute em graus, C/N0 em dB-Hz, medias das "
                            "visadas com posicao; 0 dB-Hz e rastreado sem sinal utilizavel; "
                            f"'na solucao' = presente nas GSA em >= {FRACAO_USADO:.0%} das epocas; "
                            f"setor obstruido = satelite acima de {ELEV_TESTEMUNHA:.0f} graus "
                            f"com menos de {CN0_FRACO:.0f} dB-Hz",
        "arquivo": arquivo.as_posix(),
        "duracao_s": round(dur, 1) if dur else None,
        "satelites": [
            {"prn": prn, **_arredonda(r), "situacao": classifica(r), "alto_e_fraco": alto_e_fraco(r)}
            for prn, r in resumo.items()
        ],
        "agregados": _arredonda({k: v for k, v in ag.items() if k != "setores"}),
        "setores": [_arredonda(x) for x in ag["setores"]],
    }


# -------------------------------------------------------------------- figura

def _caixa(ax, x, y, w, h):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                fc=PANEL, ec=LINE, lw=1.0, zorder=1))


def _ancora(th: float, afastamento: float) -> tuple[float, float, str, str]:
    """Deslocamento (pt) e alinhamento de um rotulo, empurrado para fora do ceu."""
    dx, dy = afastamento * math.sin(th), afastamento * math.cos(th)
    ha = "left" if dx > 3 else "right" if dx < -3 else "center"
    va = "bottom" if dy > 3 else "top" if dy < -3 else "center"
    return dx, dy, ha, va


def figura(ceu: dict, resumo: dict, ag: dict, titulo: str | None, dur: float | None):
    # medidas em polegadas; o eixo de fundo usa as mesmas unidades para os paineis
    W, H = 12.0, 7.6
    marg = 0.4
    fig = plt.figure(figsize=(W, H), dpi=200, facecolor="white")
    fundo = fig.add_axes([0, 0, 1, 1], zorder=0)
    fundo.set_xlim(0, W)
    fundo.set_ylim(0, H)
    fundo.axis("off")

    # cabecalho
    cab = "O céu que a antena enxerga"
    if titulo:
        cab += f": {titulo}"
    fundo.text(marg, H - 0.42, cab, fontsize=17, fontweight="bold", color=NAVY, va="center")
    sub = "Olhando para cima: zênite no centro, horizonte na borda. Cor = força do sinal; forma = entra ou não na solução"
    if dur:
        sub += f". Captura de {dur / 60:.0f} min"
    fundo.text(marg, H - 0.78, sub, fontsize=10.5, color=SLATE, va="center")

    # o ceu: polar, norte no topo, horario, elevacao invertida no raio
    lado = 5.7
    ax = fig.add_axes([(marg + 0.25) / W, (H - 1.45 - lado) / H, lado / W, lado / H],
                      projection="polar", zorder=2)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 90)
    ax.set_facecolor("white")
    ax.set_rgrids([30, 60], labels=["", ""])
    ax.set_thetagrids(range(0, 360, 30),
                      labels=["N", "30°", "60°", "L", "120°", "150°",
                              "S", "210°", "240°", "O", "300°", "330°"])
    ax.grid(color=GRADE, lw=0.8, ls=(0, (4, 3)))
    ax.spines["polar"].set_color(INK)
    ax.spines["polar"].set_linewidth(1.6)
    ax.tick_params(axis="x", labelsize=10.5, colors=SLATE, pad=5)
    for lab, ang in zip(ax.get_xticklabels(), range(0, 360, 30)):
        if ang % 90 == 0:
            lab.set_color(INK)
            lab.set_fontsize(15)
            lab.set_fontweight("bold")

    # setores com prova de obstrucao: hachura, atras de tudo
    for i, x in enumerate(ag["setores"]):
        if x["obstruido"]:
            ax.bar(math.radians(45 * i), 90, width=math.radians(45), bottom=0,
                   fc="#F4F7FA", ec=GRADE, hatch="///", lw=0, zorder=0.5)

    # rotulos das elevacoes, num raio livre para nao brigar com os satelites
    ang_rot = math.radians(95)
    for elev in (60, 30):
        ax.text(ang_rot, 90 - elev, f"elev. {elev}°", fontsize=9, color=SLATE,
                ha="center", va="center", zorder=3,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.text(ang_rot, 84, "horizonte", fontsize=9, color=SLATE, ha="center", va="center",
            zorder=3, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.text(0, 4, "zênite", fontsize=9, color=SLATE, ha="center", va="bottom", zorder=3)
    ax.plot([0], [0], marker="+", ms=8, color=SLATE, mew=1.0, zorder=3)

    # a posicao media de cada satelite, pintada pelo C/N0 e com a forma da situacao
    R = 15.0
    for prn, r in resumo.items():
        th, rr = math.radians(r["azim_med"]), 90 - r["elev_med"]
        cor = cor_cn0(r["cn0_med"])
        sit = classifica(r)
        # anel de tinta em volta de todos, para o fraco nao sumir no branco
        ax.plot(th, rr, "o", ms=R + 3, mfc="white", mec=INK, mew=1.0, zorder=5)
        if sit == "solucao":
            ax.plot(th, rr, "o", ms=R, mfc=cor, mec="white", mew=1.5, zorder=6)
        elif sit == "fora":
            ax.plot(th, rr, "o", ms=R, mfc="white", mec=cor, mew=3.2, zorder=6)
        else:
            ax.plot(th, rr, "o", ms=R, mfc="white", mec=CINZA, mew=2.0, zorder=6)
            ax.plot(th, rr, "x", ms=R * 0.55, mec=CINZA, mew=2.4, zorder=7)
        # Rotulo so em quem entra na solucao e em quem prova obstrucao.
        #
        # Com multiconstelacao o ceu passa de 50 satelites, e rotular todos
        # produz uma parede de texto sobreposto que esconde justamente o mapa.
        # Quem nao e rotulado continua desenhado: a forma diz se entrou na
        # solucao e a cor diz a forca do sinal, que e o que o mapa precisa
        # mostrar. O nome do satelite so importa para os que sustentam a
        # posicao ou para os que denunciam um setor bloqueado.
        if sit != "solucao" and prn not in ag["alto_e_fraco"]:
            continue
        dx, dy, ha, va = _ancora(th if r["elev_med"] >= 8 else th + math.pi, R * 0.75)
        cn0 = "sem sinal" if r["cn0_med"] <= 0 else f"{fmt_pt(r['cn0_med'])} dB-Hz"
        ax.annotate(f"PRN {prn}\n{cn0}", (th, rr), xytext=(dx, dy), textcoords="offset points",
                    fontsize=9.5, color=INK, ha=ha, va=va, zorder=8, linespacing=1.15,
                    fontweight="bold" if sit == "solucao" else "normal",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))

    # o alto e fraco: a prova da obstrucao, com o balao no setor mais vazio
    for prn in ag["alto_e_fraco"]:
        r = resumo[prn]
        th, rr = math.radians(r["azim_med"]), 90 - r["elev_med"]
        ax.plot(th, rr, "o", ms=R + 18, mfc="none", mec=INK, mew=1.6, ls="", zorder=5)
        # o setor com menos satelites longe do horizonte; empate, o mais perto do PRN
        interior = [sum(1 for q in resumo.values()
                        if setor(q["azim_med"]) == i and q["elev_med"] >= 10) for i in range(8)]
        livre = min(range(8), key=lambda i: (interior[i],
                                              abs(((45 * i - r["azim_med"]) + 180) % 360 - 180)))
        ax.annotate(f"PRN {prn}: {r['elev_med']:.0f}° de elevação\n"
                    f"e só {fmt_pt(r['cn0_med'])} dB-Hz.\nCéu aberto daria 40+.",
                    (th, rr), xytext=(math.radians(45 * livre), 63), textcoords="data",
                    fontsize=10, color=INK, ha="center", va="center", zorder=9,
                    bbox=dict(boxstyle="round,pad=0.45", fc="white", ec=INK, lw=1.2),
                    arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2,
                                    shrinkA=4, shrinkB=R * 0.9 + 6,
                                    connectionstyle="arc3,rad=-0.2"))

    # coluna da direita: escala, legenda de formas, agregados
    x0 = marg + lado + 1.05
    wc = W - x0 - marg

    # escala de C/N0
    y_esc = H - 1.35
    fundo.text(x0, y_esc + 0.02, "C/N0 médio (dB-Hz)", fontsize=11, fontweight="bold",
               color=INK, va="bottom")
    cax = fig.add_axes([x0 / W, (y_esc - 0.34) / H, (wc - 0.2) / W, 0.24 / H], zorder=3)
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=NORMA, cmap=CMAP), cax=cax,
                      orientation="horizontal")
    cb.set_ticks([10, 20, 30, 40, 50])
    cb.ax.tick_params(labelsize=9.5, colors=SLATE, length=3)
    cb.outline.set_edgecolor(LINE)
    fundo.text(x0, y_esc - 0.66, "fraco", fontsize=9.5, color=SLATE, va="center")
    fundo.text(x0 + wc - 0.2, y_esc - 0.66, "forte", fontsize=9.5, color=SLATE,
               va="center", ha="right")

    # legenda das formas
    y_leg = y_esc - 1.1
    fundo.text(x0, y_leg, "Situação na solução de posição", fontsize=11, fontweight="bold",
               color=INK, va="center")
    itens = [
        (dict(marker="o", ms=11, mfc=BLUE, mec=INK, mew=1.0),
         f"entra na solução (usado em ≥ {FRACAO_USADO:.0%} das épocas)"),
        (dict(marker="o", ms=11, mfc="white", mec=BLUE, mew=2.5),
         "rastreado, mas fora da solução"),
        (dict(marker="x", ms=8, mfc="none", mec=CINZA, mew=2.2),
         "rastreado sem sinal (0 dB-Hz)"),
    ]
    y = y_leg
    for est, txt in itens:
        y -= 0.34
        fundo.add_line(Line2D([x0 + 0.12], [y], ls="", zorder=3, **est))
        fundo.text(x0 + 0.4, y, txt, fontsize=10, color=INK, va="center")
    if any(x["obstruido"] for x in ag["setores"]):
        y -= 0.36
        fundo.add_patch(Rectangle((x0, y - 0.1), 0.24, 0.2, fc="#F4F7FA", ec=GRADE,
                                  hatch="///", lw=0.6, zorder=3))
        fundo.text(x0 + 0.4, y, f"setor com prova de obstrução: satélite acima de\n"
                   f"{ELEV_TESTEMUNHA:.0f}° que não passa de {CN0_FRACO:.0f} dB-Hz",
                   fontsize=10, color=INK, va="center", linespacing=1.2)
        y -= 0.1

    # agregados: o painel do "ouco, mas nao sei onde esta"
    y_ag = y - 0.35
    h_ag = y_ag - marg
    _caixa(fundo, x0, marg, wc, h_ag)
    yy = y_ag - 0.32
    fundo.text(x0 + 0.2, yy, "Nesta captura", fontsize=11, fontweight="bold", color=INK, va="center")
    linhas = [
        (f"{ag['satelites_com_posicao']}", "satélites com órbita conhecida, no céu acima"),
        (f"{ag['satelites_na_solucao']}", "entram na solução de posição"),
        (f"{ag['visadas_sem_orbita']}", "visadas ouvidas SEM órbita conhecida —\n"
                                        "não cabem no céu: ouço, mas não sei onde está"),
    ]
    yy -= 0.5
    for num, txt in linhas:
        fundo.text(x0 + 0.2, yy, num, fontsize=20, fontweight="bold", color=NAVY,
                   va="center", ha="left")
        fundo.text(x0 + 1.3, yy, txt, fontsize=10, color=INK, va="center", linespacing=1.25)
        yy -= 0.7 if "\n" in txt else 0.5
    fundo.text(x0 + 0.2, marg + 0.28,
               "melhor C/N0 por setor:  " + "  ".join(
                   f"{x['setor']} {x['cn0_max']:.0f}" if x["cn0_max"] is not None else f"{x['setor']} –"
                   for x in ag["setores"]),
               fontsize=9.5, color=SLATE, va="center")
    return fig


# ---------------------------------------------------------------------- cli

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--log", required=True, type=Path, help="captura .nmea, .ubx ou .uc2")
    p.add_argument("--titulo", help="rotulo da bancada, vai para o cabecalho e para o JSON")
    p.add_argument("--png", type=Path, help="figura de saida")
    p.add_argument("--json", type=Path, help="dados de saida, no formato de doc/*/data")
    a = p.parse_args(argv)

    if not a.log.is_file():
        print(f"erro: log nao encontrado: {a.log}", file=sys.stderr)
        return 1
    dados = ler_bytes(a.log)
    ceu = nmea.ler_ceu(dados)
    if not ceu["com_posicao"]:
        print(f"erro: nenhuma GSV com elevacao/azimute em {a.log} — "
              f"o receptor nao chegou a saber onde os satelites estavam", file=sys.stderr)
        return 1
    resumo = nmea.resumo_ceu(ceu)
    ag = agregados(ceu, resumo)
    dur = duracao_s(dados)

    print(tabela_texto(resumo, ag))
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(para_json(a.log, a.titulo, dur, resumo, ag),
                                     ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"json: {a.json}")
    if a.png:
        a.png.parent.mkdir(parents=True, exist_ok=True)
        fig = figura(ceu, resumo, ag, a.titulo, dur)
        fig.savefig(a.png, dpi=200, facecolor="white")
        print(f"png: {a.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
