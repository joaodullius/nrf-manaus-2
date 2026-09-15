#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Painel ao vivo com todos os estimadores lado a lado — codigo do curso.

    python cs_dash.py --trena 3.0
    python cs_dash.py --port COM22 --trena 5 --janela 12
    python cs_dash.py --tag EC:EF:40:2D:5E:46 --trena 3.0
    python cs_dash.py --texto              (sem janela grafica, so terminal)

O firmware pede o endereco do TAG na serial a cada boot: --tag responde ao abrir
a porta (ignorado se a DK ja passou do prompt); sem --tag, responda num terminal
e feche-o antes.

Le a serial do 05_cs_iq_music, monta cada procedure, roda TODOS os estimadores
sobre o mesmo IQ e mostra o resultado atualizando. Feito para a demonstracao em
aula: com o firmware de 2 caminhos de antena (o default), da para andar com o
TAG e ver ao vivo qual caminho ganha mudando de um lado para o outro — e girar o
TAG no lugar para inverter os dois.

O que aparece:
  ifft ap0 / ap1  o algoritmo do chip em cada caminho de antena
  ifft_min        o menor dos dois (multipath so acrescenta percurso)
  ifft_pot        o do caminho com mais potencia no IQ
  phase_slope     inclinacao da fase, do chip
  rtt             tempo de voo, do chip
  MUSIC ap0/ap1   super-resolucao no PC, por caminho
  MUSIC comb      os dois caminhos somados

Cada barra e a MEDIANA das ultimas --janela procedures (default 8), que e o que
o olho consegue acompanhar; o numero entre parenteses e a MAD dessa janela. Com
1 caminho de antena so, as linhas de ap1 e as combinadas somem sozinhas.

Teclas na janela:  + / -  movem a trena de referencia (10 cm)
                   z      zera o historico
                   q      sai

Requisitos: pyserial e matplotlib (numpy ja e requisito do lab).
"""
from __future__ import annotations

import argparse
import math
import queue
import sys
import threading
import time
from collections import deque

import numpy as np

import cs_csv
import cs_compare
import cs_de_numpy as de
import music_adapter

BAUD = 115200
HIST = 60          # quantas procedures o grafico da direita guarda

# (chave, rotulo, cor, entra no grafico de historico?)
SERIES = [
    ("ifft_ap0", "ifft · ap 0", "#0093D0", True),
    ("ifft_ap1", "ifft · ap 1", "#22C3E6", True),
    ("ifft_min", "ifft_min", "#00224E", True),
    ("ifft_pot", "ifft_pot", "#566577", False),
    ("ps", "phase_slope", "#8FA3B8", False),
    ("rtt", "rtt", "#E8A33D", False),
    ("music_ap0", "MUSIC · ap 0", "#7BC96F", False),
    ("music_ap1", "MUSIC · ap 1", "#4F9E45", False),
    ("music_comb", "MUSIC comb", "#2E6B28", True),
]


def mad(v) -> float:
    v = np.asarray(v, float)
    return float(np.median(np.abs(v - np.median(v))) * 1.4826) if v.size else math.nan


# ----------------------------------------------------------------- serial ---
def autodetect(tag: str | None = None, espera: float = 3.0) -> str:
    """Mesma busca do cs_capture.py: a porta que esta mandando IQ,/CS,."""
    from serial import Serial, SerialException
    from serial.tools import list_ports

    candidatas = [p.device for p in list_ports.comports()]
    if not candidatas:
        sys.exit("erro: nenhuma porta serial encontrada")
    print("procurando a porta com dados (%s) ..." % ", ".join(candidatas))
    no_prompt = None
    for porta in candidatas:
        try:
            with Serial(porta, BAUD, timeout=0.3, dsrdtr=False) as s:
                s.dtr = True                      # o VCOM da LM20-DK exige DTR
                cs_csv.responder_tag(s, tag)
                fim = time.time() + max(espera, 6.0 if tag is None else espera)
                vistas = 0
                while time.time() < fim:
                    line = s.readline().decode("utf-8", "replace")
                    if cs_csv.parse_line(line):
                        vistas += 1
                        if vistas >= 2:
                            print("porta encontrada:", porta)
                            return porta
                    elif cs_csv.is_tag_prompt(line):
                        no_prompt = porta
                        if tag is None:
                            break
        except (SerialException, OSError):
            continue
    if no_prompt:
        sys.exit(f"erro: a DK em {no_prompt} esta pedindo o endereco do TAG.\n"
                 "       passe --tag EC:EF:40:2D:5E:46 (o do SEU TAG), ou responda num\n"
                 "       terminal e feche-o antes de rodar de novo.")
    sys.exit("erro: nenhuma porta esta enviando linhas IQ,/CS,.\n"
             "       a DK esta com o 05_cs_iq_music? o TAG esta ligado?")


def leitor(porta: str, saida: "queue.Queue", parar: threading.Event, rapido: bool,
           tag: str | None = None):
    """Thread: le a serial, monta procedures e poe um dicionario de metricas na fila."""
    from serial import Serial

    pend: dict[tuple[int, int], cs_csv.Procedure] = {}
    prontas: dict[int, list[cs_csv.Procedure]] = {}
    ultimo = None
    with Serial(porta, BAUD, timeout=1, dsrdtr=False) as s:
        s.dtr = True
        cs_csv.responder_tag(s, tag)
        while not parar.is_set():
            rec = cs_csv.parse_line(s.readline().decode("utf-8", "replace"))
            if rec is None:
                continue
            chave = (rec[1], rec[2])
            proc = pend.setdefault(chave, cs_csv.Procedure(counter=rec[1], ap=rec[2]))
            if rec[0] == "IQ":
                idx = rec[3] - cs_csv.CH_OFFSET
                if 0 <= idx < cs_csv.NCH:
                    proc.i_local[idx], proc.q_local[idx] = rec[4], rec[5]
                    proc.i_remote[idx], proc.q_remote[idx] = rec[6], rec[7]
                    proc.seen.add(idx)
                continue
            # linha CS: fecha este caminho de antena
            proc.tone_quality_ok = rec[3] == 1
            proc.fw = {"ifft": rec[4], "phase_slope": rec[5], "rtt": rec[6]}
            proc.rtt_count, proc.rtt_half_ns = rec[7], rec[8]
            del pend[chave]
            if len(proc.seen) != cs_csv.NCH:
                continue
            prontas.setdefault(proc.counter, []).append(proc)
            # o counter anterior nao recebe mais nada: pode ser publicado
            if ultimo is not None and ultimo != proc.counter and ultimo in prontas:
                saida.put(metricas(sorted(prontas.pop(ultimo), key=lambda p: p.ap), rapido))
            ultimo = proc.counter
            for velho in [c for c in prontas if c < proc.counter - 1]:
                prontas.pop(velho, None)


def metricas(aps, rapido: bool) -> dict:
    """Roda os estimadores sobre uma procedure (1 ou 2 caminhos de antena)."""
    p0 = aps[0]
    combs = [a.comb() for a in aps]
    m = {k: math.nan for k, _, _, _ in SERIES}
    m["tq"] = all(a.tone_quality_ok for a in aps)
    m["n_ap"] = len(aps)
    m["ifft_ap0"] = p0.fw["ifft"]
    m["ps"] = p0.fw["phase_slope"]
    m["rtt"] = p0.fw["rtt"]
    if not rapido:
        m["music_ap0"] = music_adapter.music_m(combs[0])
    if len(aps) >= 2:
        m["ifft_ap1"] = aps[1].fw["ifft"]
        m["ifft_min"] = cs_compare.escolhe_ifft_min(aps)
        m["ifft_pot"] = cs_compare.escolhe_ifft_potencia(aps, combs)
        if not rapido:
            m["music_ap1"] = music_adapter.music_m(combs[1])
            m["music_comb"] = music_adapter.music_multi_m(combs)
    return m


# ------------------------------------------------------------------ painel ---
class Painel:
    def __init__(self, trena: float, janela: int):
        self.trena = trena
        self.janela = janela
        self.hist = {k: deque(maxlen=HIST) for k, _, _, _ in SERIES}
        self.n = 0
        self.t0 = time.time()

    def add(self, m: dict) -> None:
        if not m.get("tq", True):
            return
        self.n += 1
        for k, _, _, _ in SERIES:
            self.hist[k].append(m.get(k, math.nan))

    def resumo(self, k: str):
        v = np.array([x for x in list(self.hist[k])[-self.janela:] if math.isfinite(x)])
        return (float(np.median(v)), mad(v), v.size) if v.size else (math.nan, math.nan, 0)

    def zera(self) -> None:
        for d in self.hist.values():
            d.clear()
        self.n = 0


def roda_texto(painel: Painel, fila: "queue.Queue", parar: threading.Event) -> None:
    while not parar.is_set():
        try:
            painel.add(fila.get(timeout=1.0))
        except queue.Empty:
            continue
        if fila.qsize():                      # so desenha quando esvaziou a fila
            continue
        print("\033[H\033[J", end="")          # limpa a tela
        print("trena %.2f m   janela %d   procedures %d\n" % (painel.trena, painel.janela, painel.n))
        print("%-14s %9s %8s %9s" % ("estimador", "mediana", "MAD", "erro"))
        for k, rot, _, _ in SERIES:
            med, dp, n = painel.resumo(k)
            if n == 0:
                continue
            print("%-14s %9.2f %8.3f %+9.2f" % (rot, med, dp, med - painel.trena))
        sys.stdout.flush()


def roda_grafico(painel: Painel, fila: "queue.Queue", parar: threading.Event) -> None:
    import matplotlib
    import matplotlib.pyplot as plt

    NAVY, SLATE, LINE, INK, PANEL, WARN = ("#00224E", "#566577", "#D3E0EB",
                                           "#0B1B2B", "#EDF3F8", "#E8A33D")
    matplotlib.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"],
                                "axes.edgecolor": LINE, "axes.labelcolor": SLATE,
                                "xtick.color": SLATE, "ytick.color": SLATE})
    plt.ion()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 7.5), facecolor="white",
                                 gridspec_kw={"width_ratios": [1.25, 1]})
    fig.subplots_adjust(left=0.13, right=0.98, top=0.90, bottom=0.09, wspace=0.16)
    fig.canvas.manager.set_window_title("Channel Sounding — painel ao vivo")

    def tecla(ev):
        if ev.key in ("+", "="):
            painel.trena += 0.1
        elif ev.key == "-":
            painel.trena = max(0.0, painel.trena - 0.1)
        elif ev.key == "z":
            painel.zera()
        elif ev.key in ("q", "escape"):
            parar.set()
    fig.canvas.mpl_connect("key_press_event", tecla)

    ys = np.arange(len(SERIES))
    while not parar.is_set():
        try:
            while True:
                painel.add(fila.get_nowait())
        except queue.Empty:
            pass

        a1.clear(); a2.clear()
        meds, mads, rots, cores = [], [], [], []
        for k, rot, cor, _ in SERIES:
            med, dp, n = painel.resumo(k)
            meds.append(0.0 if math.isnan(med) else med)
            mads.append(0.0 if math.isnan(dp) else dp)
            rots.append(rot if n else rot + " (—)")
            cores.append(cor)
        a1.barh(ys, meds, xerr=mads, color=cores, height=0.62, zorder=3,
                error_kw=dict(ecolor=SLATE, elinewidth=1.2, capsize=3))
        for y, m, dp in zip(ys, meds, mads):
            if m:
                a1.text(m + dp + 0.06, y, "%.2f" % m, va="center", fontsize=11,
                        color=INK, fontweight="bold")
        a1.axvline(painel.trena, color=WARN, lw=2.0, ls="--", zorder=1)
        a1.text(painel.trena, len(SERIES) - 0.35, " trena %.2f m" % painel.trena,
                color=WARN, fontsize=11, va="bottom")
        a1.set_yticks(ys); a1.set_yticklabels(rots, fontsize=11)
        a1.set_xlim(0, max(6.0, (max(meds) if meds else 1) * 1.25))
        a1.set_ylim(-0.6, len(SERIES) - 0.3)
        a1.set_xlabel("distância (m) — mediana das últimas %d procedures ± MAD" % painel.janela,
                      fontsize=10)
        a1.grid(color=LINE, lw=0.6, alpha=0.7, axis="x")

        for k, rot, cor, no_grafico in SERIES:
            if not no_grafico:
                continue
            v = np.array(painel.hist[k], float)
            if v.size:
                a2.plot(np.arange(-v.size + 1, 1), v, color=cor, lw=1.8, label=rot)
        a2.axhline(painel.trena, color=WARN, lw=2.0, ls="--")
        a2.set_xlabel("procedures atrás", fontsize=10)
        a2.set_ylabel("distância (m)", fontsize=10)
        a2.set_xlim(-HIST, 1)
        a2.grid(color=LINE, lw=0.6, alpha=0.7)
        if a2.get_legend_handles_labels()[0]:
            a2.legend(loc="upper left", fontsize=9, frameon=True, edgecolor=LINE, ncol=2)
        for a in (a1, a2):
            for sp in ("top", "right"):
                a.spines[sp].set_visible(False)

        fig.suptitle("Channel Sounding ao vivo — %d procedures   ·   + / −  movem a trena, "
                     "z zera, q sai" % painel.n, fontsize=12.5, color=INK, x=0.13, ha="left")
        try:
            plt.pause(0.35)
        except Exception:                      # janela fechada no X
            parar.set()
        if not plt.fignum_exists(fig.number):
            parar.set()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="COMx (default: procura sozinho)")
    ap.add_argument("--tag", help="endereco BLE do SEU TAG, respondido ao prompt do firmware")
    ap.add_argument("--trena", type=float, default=3.0, help="distancia de referencia (m)")
    ap.add_argument("--janela", type=int, default=8,
                    help="quantas procedures entram na mediana (default 8)")
    ap.add_argument("--texto", action="store_true", help="sem janela grafica")
    ap.add_argument("--rapido", action="store_true",
                    help="pula o MUSIC (so as contas do firmware), se o PC nao acompanhar")
    args = ap.parse_args()

    porta = args.port or autodetect(args.tag)
    fila: "queue.Queue" = queue.Queue()
    parar = threading.Event()
    t = threading.Thread(target=leitor, args=(porta, fila, parar, args.rapido, args.tag),
                         daemon=True)
    t.start()
    painel = Painel(args.trena, args.janela)
    try:
        (roda_texto if args.texto else roda_grafico)(painel, fila, parar)
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()


if __name__ == "__main__":
    main()
