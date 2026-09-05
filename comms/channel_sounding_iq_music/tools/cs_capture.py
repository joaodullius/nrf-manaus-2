#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grava o CSV de IQ do firmware do lab 5 direto da serial — codigo do curso.

    python cs_capture.py --seconds 30 --out capturas/1m.csv
    python cs_capture.py --port COM22 --seconds 30 --out capturas/3m.csv

Sem --port, procura a porta que esta enviando linhas IQ,/CS, (a DK enumera duas
COM; o CSV sai numa delas — na bancada do curso, a segunda). Guarda so as linhas
que o cs_csv.parse_line() aceita; o banner de boot fica de fora. Conta
procedures completas (75 IQ + 1 CS) e mostra a taxa.

Requisitos: pyserial (ja vem no toolchain do nRF Connect).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cs_csv

BAUD = 115200


def filter_lines(lines):
    for line in lines:
        if cs_csv.parse_line(line) is not None:
            yield line if line.endswith("\n") else line + "\n"


def looks_like_ours(lines) -> bool:
    return sum(1 for _ in filter_lines(lines)) >= 2


def morrer(msg: str) -> None:
    print(f"erro: {msg}", file=sys.stderr)
    sys.exit(1)


def autodetect(espera: float = 3.0) -> str:
    from serial import Serial, SerialException
    from serial.tools import list_ports

    candidatas = [p.device for p in list_ports.comports()]
    if not candidatas:
        morrer("nenhuma porta serial encontrada")
    print(f"procurando a porta com dados ({', '.join(candidatas)}) ...")
    for porta in candidatas:
        try:
            with Serial(porta, BAUD, timeout=0.3, dsrdtr=False) as s:
                # LM20-DK: as linhas do VCOM so falam com DTR ativo.
                s.dtr = True
                fim = time.time() + espera
                vistas = []
                while time.time() < fim:
                    vistas.append(s.readline().decode("utf-8", "replace"))
                    if looks_like_ours(vistas):
                        print(f"porta encontrada: {porta}")
                        return porta
        except (SerialException, OSError):
            continue
    morrer("nenhuma porta esta enviando linhas IQ,/CS,.\n"
           "       confira: a DK esta gravada com o channel_sounding_iq_music? o TAG esta\n"
           "       ligado com o reflector do lab 1? o endereco em meu_tag.conf esta certo?")


def capturar(porta: str, segundos: float, saida: Path) -> None:
    from serial import Serial

    saida.parent.mkdir(parents=True, exist_ok=True)
    n_iq = n_cs = 0
    inicio = time.time()
    with Serial(porta, BAUD, timeout=1, dsrdtr=False) as s, open(saida, "w", encoding="utf-8") as f:
        # LM20-DK: as linhas do VCOM so falam com DTR ativo.
        s.dtr = True
        while time.time() - inicio < segundos:
            line = s.readline().decode("utf-8", "replace")
            rec = cs_csv.parse_line(line)
            if rec is None:
                continue
            f.write(line if line.endswith("\n") else line + "\n")
            if rec[0] == "IQ":
                n_iq += 1
            else:
                n_cs += 1
                dt = time.time() - inicio
                print(f"\r{n_cs} procedures, {n_cs / dt:.1f}/s, ultima: ifft={rec[4]:.2f} "
                      f"phase_slope={rec[5]:.2f} rtt={rec[6]:.2f} m", end="")
    print()
    procs = cs_csv.read_procedures(saida)
    print(f"gravado em {saida}: {n_cs} linhas CS, {n_iq} linhas IQ, "
          f"{len(procs)} procedures completas")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="COMx (default: procura sozinho)")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    porta = args.port or autodetect()
    capturar(porta, args.seconds, args.out)


if __name__ == "__main__":
    main()
