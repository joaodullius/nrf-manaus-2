#!/usr/bin/env python3
"""Mapa das passadas SatelIoT sobre um ponto numa semana, a partir da tabela do LEO_next_passes.py.

Le passadas_semana_manaus.txt (saida do LEO_next_passes.py) e desenha:
  - esquerda: cada passada como um ponto (hora local x elevacao maxima), uma cor por
    satelite, seta de subida/descida, linha na elevacao minima (50 graus por padrao);
  - direita: carta polar com o azimute e a elevacao do pico de cada passada.

Uso:
    python mapa_semana.py [passadas_semana_manaus.txt] [--min-el 50] [--out plots/mapa_semana_manaus.png]
"""
import argparse
import math
import os
import re
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RE_LINHA = re.compile(
    r"^\s*\d+\s*\|\s*(SATELIOT_\d)\s*\|\s*(\d\d-\d\d-\d\d \d\d:\d\d)\s*\|\s*(\d\d-\d\d-\d\d \d\d:\d\d)\s*\|"
    r"\s*([\d.]+)\S*\s+\S+\s*\|\s*([\d.]+)\S*\s*\|\s*(\S)\s*\|\s*(\d+)m (\d+)s")
CORES = {"SATELIOT_1": "#0093D0", "SATELIOT_2": "#566577", "SATELIOT_3": "#C94F4F", "SATELIOT_4": "#1FA971"}


def ler(path):
    passadas = []
    with open(path, encoding="utf-8") as fh:
        for linha in fh:
            m = RE_LINHA.match(linha)
            if not m:
                continue
            sat, utc, local, az, el, seta, mins, segs = m.groups()
            passadas.append({
                "sat": sat,
                "utc": datetime.strptime(utc, "%y-%m-%d %H:%M"),
                "local": datetime.strptime(local, "%y-%m-%d %H:%M"),
                "az": float(az), "el": float(el),
                "sobe": seta in ("^", "\u2191"),
                "dur_s": int(mins) * 60 + int(segs),
            })
    if not passadas:
        raise SystemExit(f"{path}: nenhuma linha de passada reconhecida")
    return passadas


def cabecalho(path):
    obs = fuso = None
    with open(path, encoding="utf-8") as fh:
        for linha in fh:
            if "Observer" in linha:
                obs = linha.split(":", 1)[1].strip()
            if "Local timezone" in linha:
                fuso = linha.split(":", 1)[1].strip()
    return obs, fuso


def desenhar(passadas, min_el, out, obs, fuso):
    fig = plt.figure(figsize=(16, 7), dpi=110)
    ax = fig.add_subplot(1, 2, 1)
    axp = fig.add_subplot(1, 2, 2, projection="polar")

    for p in passadas:
        cor = CORES.get(p["sat"], "#0B1B2B")
        ax.plot([p["local"]], [p["el"]], marker="^" if p["sobe"] else "v", color=cor, ms=8,
                mec="white", mew=0.5, ls="none")
        if p["el"] >= min_el:
            ax.annotate(f"{p['sat'][-1]} {p['local']:%a %H:%M}\n{p['el']:.0f} graus",
                        (p["local"], p["el"]), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=7, color=cor)
    ax.axhline(min_el, color="#E8A33D", lw=1.2, ls="--")
    ax.text(passadas[0]["local"], min_el + 1, f"{min_el:.0f} graus", color="#E8A33D", fontsize=8)
    ax.set_ylim(0, 90)
    ax.set_ylabel("elevacao maxima da passada (graus)")
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d/%m"))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    ax.grid(which="major", color="#D3E0EB")
    ax.grid(which="minor", color="#EDF3F8")
    ax.set_title(f"Passadas SatelIoT sobre {obs}  (hora local, {fuso})", fontsize=10)
    for sat, cor in CORES.items():
        if any(p["sat"] == sat for p in passadas):
            ax.plot([], [], "o", color=cor, label=sat)
    ax.plot([], [], "^", color="#0B1B2B", label="subindo (sul->norte)")
    ax.plot([], [], "v", color="#0B1B2B", label="descendo (norte->sul)")
    ax.legend(loc="upper left", fontsize=8, ncol=2)

    axp.set_theta_zero_location("N")
    axp.set_theta_direction(-1)
    axp.set_rlim(90, 0)
    axp.set_rticks([30, 50, 70])
    axp.set_yticklabels(["30", "50", "70"], fontsize=7)
    axp.grid(color="#D3E0EB")
    for p in passadas:
        cor = CORES.get(p["sat"], "#0B1B2B")
        alto = p["el"] >= min_el
        axp.plot([math.radians(p["az"])], [p["el"]], marker="^" if p["sobe"] else "v", color=cor,
                 ms=9 if alto else 5, alpha=1.0 if alto else 0.35, mec="white", mew=0.5, ls="none")
    axp.set_title(f"Pico de cada passada (azimute, elevacao); cheios: >= {min_el:.0f} graus", fontsize=10)

    n_alto = sum(1 for p in passadas if p["el"] >= min_el)
    fig.suptitle(f"{len(passadas)} passadas em {passadas[0]['local']:%d/%m} a {passadas[-1]['local']:%d/%m}; "
                 f"{n_alto} com elevacao maxima >= {min_el:.0f} graus  (SGP4, TLE CelesTrak)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return n_alto


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tabela", nargs="?", default=os.path.join(HERE, "passadas_semana_manaus.txt"))
    ap.add_argument("--min-el", type=float, default=50.0)
    ap.add_argument("--out", default=os.path.join(HERE, "plots", "mapa_semana_manaus.png"))
    a = ap.parse_args()
    passadas = ler(a.tabela)
    obs, fuso = cabecalho(a.tabela)
    n = desenhar(passadas, a.min_el, a.out, obs, fuso)
    print(f"{a.out}: {len(passadas)} passadas, {n} com elevacao >= {a.min_el:.0f} graus")
    for p in passadas:
        if p["el"] >= a.min_el:
            print(f"  {p['sat']}  {p['local']:%a %d/%m %H:%M} local  ({p['utc']:%H:%M} UTC)  "
                  f"pico {p['el']:.1f} graus az {p['az']:.0f}  {'sobe' if p['sobe'] else 'desce'}  {p['dur_s']//60} min")


if __name__ == "__main__":
    main()
