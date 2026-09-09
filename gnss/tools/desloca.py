# -*- coding: utf-8 -*-
"""O teste do deslocamento: duas nuvens do mesmo rover, antes e depois de mover.

Uso:  python desloca.py A_ini A_fim B_ini B_fim [saida.png]
      (tempos unix; ou 'A' e 'B' lidos de C:/b/base_rover/_marcas.json)

O que este teste prova, e que nenhum numero de CEP prova sozinho: se a nuvem
inteira se desloca pela distancia que a antena andou, e a dispersao de cada
nuvem e muito menor que esse deslocamento, entao o receptor esta medindo
POSICAO, nao apenas repetindo um numero estavel. Um receptor pode ser
belissimamente preciso e estar medindo a coisa errada; mover a antena e o unico
jeito barato de separar os dois casos.

A referencia comum e o centroide da nuvem A. As duas nuvens sao projetadas no
mesmo plano local norte/leste, entao o vetor entre os centroides sai direto em
centimetros — e nao depende da posicao absoluta da base, que aqui tem ~10 m de
incerteza. Base deslocada move as duas nuvens juntas; a distancia entre elas nao
muda.
"""
import json
import math
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, "C:/work/nrf-manaus-2/gnss/tools")
import nmea  # noqa: E402

INK, SLATE, NAVY, BLUE = "#0B1B2B", "#566577", "#00224E", "#0093D0"
PANEL, GRADE, VERDE = "#EDF3F8", "#B9C9D6", "#12A36E"
FONTE = "C:/b/base_rover/rover.tsv"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "axes.edgecolor": "#D3E0EB", "axes.labelcolor": SLATE,
    "xtick.color": SLATE, "ytick.color": SLATE,
})


def fatia(ini, fim):
    linhas = []
    with open(FONTE, encoding="utf-8", errors="replace") as f:
        for ln in f:
            t, _, sent = ln.partition("\t")
            try:
                t = float(t)
            except ValueError:
                continue
            if ini <= t <= fim:
                linhas.append(sent.strip())
    return nmea.ler_fluxo("\r\n".join(linhas).encode("ascii", "replace"))


def so_fixos(fx):
    """Preferir epocas em RTK fixo. Se nao houver, cai para o que existir e
    avisa — misturar fixo com flutuante desloca o centroide e falseia o vetor."""
    f4 = [f for f in fx if f.qualidade == 4]
    return (f4, True) if len(f4) >= 30 else (fx, False)


def painel(fx, ref_lat, ref_lon, sub=60):
    m_lat, m_lon = nmea.metros_por_grau(ref_lat)
    n = [(f.lat - ref_lat) * m_lat for f in fx]
    e = [(f.lon - ref_lon) * m_lon for f in fx]
    cn, ce = statistics.fmean(n), statistics.fmean(e)
    hpe = sorted(math.hypot(a - cn, b - ce) for a, b in zip(n, e))

    # Incerteza do centroide, medida e nao assumida.
    #
    # sigma/raiz(n) so vale para ruido independente, e erro de GNSS nao e: epocas
    # consecutivas compartilham a mesma ionosfera, o mesmo multipath e as mesmas
    # ambiguidades, entao o n efetivo em 5 min e da ordem de dezenas, nao de
    # centenas. Aqui o centroide de cada sub-janela de 1 min e uma amostra
    # independente o bastante; o espalhamento entre elas e a incerteza de
    # verdade. Se ele nao for bem menor que o deslocamento, o teste nao conclui.
    subs = []
    for i in range(0, len(n) - sub + 1, sub):
        subs.append((statistics.fmean(n[i:i + sub]), statistics.fmean(e[i:i + sub])))
    if len(subs) >= 2:
        dn = statistics.stdev([s[0] for s in subs])
        de = statistics.stdev([s[1] for s in subs])
        inc = math.hypot(dn, de) / math.sqrt(len(subs))   # erro padrao da media
    else:
        inc = float("nan")

    return {"n": n, "e": e, "cn": cn, "ce": ce, "qtd": len(fx),
            "cep50": nmea._percentil(hpe, 0.50),
            "cep95": nmea._percentil(hpe, 0.95),
            "inc_centroide": inc, "subs": subs}


def main(a_ini, a_fim, b_ini, b_fim, png):
    fa, ok_a = so_fixos(fatia(a_ini, a_fim))
    fb, ok_b = so_fixos(fatia(b_ini, b_fim))
    if not fa or not fb:
        print("faltam epocas numa das janelas"); return 1
    ref_lat, ref_lon = fa[0].lat, fa[0].lon
    A = painel(fa, ref_lat, ref_lon)
    B = painel(fb, ref_lat, ref_lon)

    dn, de = B["cn"] - A["cn"], B["ce"] - A["ce"]
    dist = math.hypot(dn, de)
    rumo = (math.degrees(math.atan2(de, dn)) + 360) % 360
    print("A: %d epocas%s  CEP50=%.3f m  CEP95=%.3f m"
          % (A["qtd"], "" if ok_a else " (SEM RTK fixo)", A["cep50"], A["cep95"]))
    print("B: %d epocas%s  CEP50=%.3f m  CEP95=%.3f m"
          % (B["qtd"], "" if ok_b else " (SEM RTK fixo)", B["cep50"], B["cep95"]))
    print("deslocamento medido: %.1f cm  (norte %+.1f, leste %+.1f)  rumo %.0f graus"
          % (dist * 100, dn * 100, de * 100, rumo))
    inc = math.hypot(A["inc_centroide"], B["inc_centroide"])
    print("incerteza do deslocamento: +-%.1f cm  (medida no espalhamento dos "
          "centroides de 1 min, nao suposta)" % (inc * 100))
    if inc == inc and inc > 0:
        print("veredito: deslocamento e %.1fx a sua propria incerteza — %s"
              % (dist / inc,
                 "conclusivo" if dist > 3 * inc else "INCONCLUSIVO, precisa de janela maior"))

    fig, ax = plt.subplots(figsize=(7.4, 7.0))
    fig.patch.set_facecolor("white")
    ax.set_facecolor(PANEL)
    for p, cor, rot in ((A, BLUE, "P1 — antes de mover"), (B, VERDE, "P2 — depois de mover")):
        ax.plot([x * 100 for x in p["e"]], [y * 100 for y in p["n"]], "o",
                ms=4, mfc=cor, mec="none", alpha=0.35, zorder=2, label=None)
        ax.plot([p["ce"] * 100], [p["cn"] * 100], "o", ms=13, color=cor,
                mec="white", mew=2, zorder=4, label="%s — %d épocas" % (rot, p["qtd"]))
    ax.annotate("", xy=(B["ce"] * 100, B["cn"] * 100),
                xytext=(A["ce"] * 100, A["cn"] * 100),
                arrowprops=dict(arrowstyle="->", color=INK, lw=2, shrinkA=8, shrinkB=8),
                zorder=5)
    meio_e = (A["ce"] + B["ce"]) / 2 * 100
    meio_n = (A["cn"] + B["cn"]) / 2 * 100
    ax.annotate("%.1f cm" % (dist * 100), (meio_e, meio_n),
                textcoords="offset points", xytext=(10, 10),
                fontsize=13, fontweight="bold", color=INK, zorder=6)
    ax.set_xlabel("leste [cm]", fontsize=10)
    ax.set_ylabel("norte [cm]", fontsize=10)
    ax.set_aspect("equal")
    ax.grid(color=GRADE, lw=0.7, alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.set_title("A antena se moveu — e o receptor viu, com direção",
                 fontsize=13, color=INK, loc="left", pad=12)
    fig.text(0.02, 0.015,
             "RTK com base própria a 1,5 m.  Pontos = épocas em RTK fixo; "
             "ponto grande = centroide.\nA base tem ~10 m de incerteza absoluta, "
             "e isso não afeta o vetor: as duas nuvens erram juntas.",
             fontsize=8.5, color=SLATE, linespacing=1.5)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(png, dpi=170, facecolor="white")
    print("figura em", png)
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["marcas"]:
        m = json.load(open("C:/b/base_rover/_marcas.json"))
        sys.exit(main(m["P1"][0], m["P1"][1], m["P2"][0], m["P2"][1],
                      sys.argv[2] if len(sys.argv) > 2 else "C:/b/base_rover/desloca.png"))
    a = [float(x) for x in sys.argv[1:5]]
    sys.exit(main(a[0], a[1], a[2], a[3],
                  sys.argv[5] if len(sys.argv) > 5 else "C:/b/base_rover/desloca.png"))
