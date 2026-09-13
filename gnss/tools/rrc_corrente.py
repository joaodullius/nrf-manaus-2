# -*- coding: utf-8 -*-
"""Corrente x tempo de um ciclo de A-GNSS, com a janela RRC conectado sombreada.

    python rrc_corrente.py <log da serial> <csv de corrente> <saida.png>

Mostra por que a assistencia de nuvem NAO encurta o TTFF nesta bancada: o modem
fica preso em RRC conectado ate o timer de inatividade da rede expirar, e o GNSS
so trabalha depois disso. O plato liso de ~35 mA e o GNSS rastreando; ele comeca
no instante do +CSCON: 0.

O timer e da rede e o dispositivo nao negocia (5 a 60 s, conforme a Nordic; ~30 s
medido na Claro em LTE-M). Encurta-lo exige AS-RAI ou APN privada — desativar o
LTE na mao mede o efeito, mas nao e pratica recomendavel em produto.

Cruza o CSV de corrente do PPK2 com os eventos do log da serial:
  Deleting GNSS data  -> inicio do ciclo (partida a frio)
  +CSCON: 1 / 0       -> UE entra e sai de RRC conectado
  A-GNSS data processed -> assistencia ja esta no modem
  Time to fix         -> fim do ciclo
"""
import csv, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAVY, BLUE, CYAN, SLATE, LINE, INK, PANEL, WARN, RED = (
    "#00224E", "#0093D0", "#22C3E6", "#566577", "#D3E0EB", "#0B1B2B",
    "#EDF3F8", "#E8A33D", "#C94F4F")
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"]})

def le_log(caminho):
    ev = []
    pat = re.compile(r"^\[\s*([\d.]+)\]\s*(.*)$")
    for ln in open(caminho, encoding="utf-8", errors="replace"):
        m = pat.match(ln.strip())
        if not m:
            continue
        t, txt = float(m.group(1)), m.group(2)
        if "Deleting GNSS data" in txt:      ev.append((t, "inicio", None))
        elif "+CSCON: 1" in txt:             ev.append((t, "rrc_on", None))
        elif "+CSCON: 0" in txt:             ev.append((t, "rrc_off", None))
        elif "A-GNSS data processed" in txt: ev.append((t, "agnss", None))
        else:
            m2 = re.search(r"Time to fix: ([\d.]+) s", txt)
            if m2: ev.append((t, "fix", float(m2.group(1))))
            m3 = re.search(r"blocked by LTE: (\d+) s", txt)
            if m3: ev.append((t, "bloqueio", float(m3.group(1))))
    return ev

def ciclos(ev):
    """Agrupa eventos entre um 'inicio' e o 'fix' seguinte."""
    out, atual = [], None
    for t, tipo, val in ev:
        if tipo == "inicio":
            atual = {"inicio": t}
        elif atual is None:
            continue
        elif tipo == "fix":
            atual["fix"] = t; atual["ttff"] = val
        elif tipo == "bloqueio":
            atual["bloqueio"] = val
            out.append(atual); atual = None
        else:
            atual.setdefault(tipo, t)
    return out

def le_csv(caminho):
    t, med, mn, mx = [], [], [], []
    for r in csv.DictReader(open(caminho)):
        try:
            t.append(float(r["t_s"])); med.append(float(r["media_mA"]))
            mn.append(float(r["min_mA"])); mx.append(float(r["max_mA"]))
        except (ValueError, KeyError, TypeError):
            pass
    return t, med, mn, mx

def painel(ax, c, dados, titulo):
    t, med, mn, mx = dados
    t0 = c["inicio"]
    fim = c.get("fix", t0 + 200) + 12
    idx = [i for i, x in enumerate(t) if t0 - 12 <= x <= fim]
    xs = [t[i] - t0 for i in idx]
    ax.fill_between(xs, [mn[i] for i in idx], [mx[i] for i in idx],
                    color=BLUE, alpha=0.18, lw=0, zorder=2)
    ax.plot(xs, [med[i] for i in idx], color=NAVY, lw=2.0, zorder=3)
    # janela RRC conectado
    if "rrc_on" in c and "rrc_off" in c:
        a, b = c["rrc_on"] - t0, c["rrc_off"] - t0
        ax.axvspan(a, b, color=WARN, alpha=0.22, lw=0, zorder=1)
        ax.annotate(f"RRC conectado: {b-a:.1f} s",
                    xy=((a + b) / 2, ax.get_ylim()[1]), xytext=(0, -14),
                    textcoords="offset points", ha="center", va="top",
                    fontsize=11, color="#8a5a10", fontweight="bold", zorder=5)
    for chave, cor, rot in (('agnss', CYAN, 'A-GNSS no modem'),
                            ('fix', RED, 'fix')):
        if chave in c:
            x = c[chave] - t0
            ax.axvline(x, color=cor, lw=1.6, ls='--', zorder=4)
            ax.annotate(rot, xy=(x, 0), xytext=(3, 4), textcoords='offset points',
                        fontsize=9.5, color=cor, rotation=90, va='bottom', zorder=5)
    # janela em que o GNSS de fato trabalha: da liberacao do RRC ate o fix
    if 'rrc_off' in c and 'fix' in c:
        a, b = c['rrc_off'] - t0, c['fix'] - t0
        y = ax.get_ylim()[1] * 0.62
        ax.annotate('', xy=(a, y), xytext=(b, y),
                    arrowprops=dict(arrowstyle='<->', color=NAVY, lw=1.8))
        ax.text((a + b) / 2, y * 1.06,
                'GNSS trabalhando: %.0f s' % (b - a),
                ha='center', va='bottom', fontsize=11.5, color=NAVY, fontweight='bold')
    ax.set_title(titulo, fontsize=13, color=INK, fontweight="bold", loc="left", pad=8)
    ax.set_xlabel("segundos desde a partida a frio", fontsize=10.5, color=SLATE)
    ax.grid(True, color=LINE, lw=0.8, alpha=0.7)
    ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(LINE)
    ax.tick_params(colors=SLATE, labelsize=9.5)

if __name__ == "__main__":
    log, csvf, png = sys.argv[1], sys.argv[2], sys.argv[3]
    ev = le_log(log); cs = ciclos(ev); dados = le_csv(csvf)
    print(f"{len(cs)} ciclos completos")
    for i, c in enumerate(cs):
        rrc = (c["rrc_off"] - c["rrc_on"]) if "rrc_on" in c and "rrc_off" in c else None
        print(f"  [{i}] inicio={c['inicio']:.0f}s  RRC={rrc if rrc is None else f'{rrc:.1f}s'}"
              f"  bloqueio={c.get('bloqueio')}s  TTFF={c.get('ttff')}s")
    # escolhe: o de maior TTFF, e o de menor janela RRC como controle
    comp = [c for c in cs if "rrc_on" in c and "rrc_off" in c and "ttff" in c]
    alto = max(comp, key=lambda c: c["ttff"])
    curto = min(comp, key=lambda c: c["rrc_off"] - c["rrc_on"])
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6), sharey=True)
    fig.patch.set_facecolor("white")
    painel(axes[0], alto, dados,
           "A rede segurou a UE %.0f s  —  TTFF %.0f s" % (
               alto["rrc_off"] - alto["rrc_on"], alto["ttff"]))
    painel(axes[1], curto, dados,
           "A rede liberou em %.1f s  —  TTFF %.0f s" % (
               curto["rrc_off"] - curto["rrc_on"], curto["ttff"]))
    axes[0].set_ylabel("corrente (mA)", fontsize=10.5, color=SLATE)
    fig.suptitle("O timer de liberacao RRC e o que atrasa o fix",
                 fontsize=17, color=INK, fontweight="bold", x=0.055, ha="left", y=0.98)
    fig.text(0.055, 0.905,
             "nRF9151, assistencia A-GNSS pela nRF Cloud, LTE-M. Linha = media por segundo; "
             "faixa clara = min-max no mesmo segundo.",
             fontsize=11, color=SLATE, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(png, dpi=150, facecolor="white")
    print("png:", png)
