#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grava o CSV de IQ do firmware do lab 5 direto da serial — codigo do curso.

    python cs_capture.py --seconds 30 --out capturas/1m.csv
    python cs_capture.py --port COM22 --seconds 30 --out capturas/3m.csv

Antes de rodar: o firmware pede o endereco do TAG na serial a cada boot. Abra
a COM num terminal serial, digite o endereco (nao cole), Enter, e FECHE o
terminal — a porta aceita um leitor por vez. So entao rode o script.

Sem --port, procura a porta que esta enviando linhas IQ,/CS, (a DK enumera duas
COM; o CSV sai numa delas — na bancada do curso, a segunda). Guarda so as linhas
que o cs_csv.parse_line() aceita; o banner de boot fica de fora. Enquanto grava,
mostra uma linha de status por segundo (tempo, procedures, ultima estimativa) e
avisa se em 10 s nenhuma procedure chegou. No fim conta procedures completas
(75 IQ + 1 CS) e a taxa. Ctrl+C encerra antes e mantem o arquivo.

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


def waiting_for_tag(lines) -> bool:
    return any(cs_csv.is_tag_prompt(line) for line in lines)


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
    no_prompt = None
    for porta in candidatas:
        try:
            with Serial(porta, BAUD, timeout=0.3, dsrdtr=False) as s:
                # LM20-DK: as linhas do VCOM so falam com DTR ativo.
                s.dtr = True
                # O prompt se repete a cada 5 s: espera pelo menos um ciclo.
                fim = time.time() + max(espera, 6.0)
                vistas = []
                while time.time() < fim:
                    vistas.append(s.readline().decode("utf-8", "replace"))
                    if looks_like_ours(vistas):
                        print(f"porta encontrada: {porta}")
                        return porta
                    if waiting_for_tag(vistas):
                        no_prompt = porta
                        break
        except (SerialException, OSError):
            continue
    if no_prompt:
        morrer(f"a DK em {no_prompt} esta pedindo o endereco do TAG.\n"
               "       abra essa COM num terminal, digite o endereco do SEU TAG, Enter,\n"
               "       feche o terminal e rode de novo.")
    morrer("nenhuma porta esta enviando linhas IQ,/CS,.\n"
           "       confira: a DK esta gravada com o 05_cs_iq_music? o TAG esta\n"
           "       ligado com o reflector do lab 1? o endereco digitado e o dele?\n"
           "       o terminal em que voce digitou o endereco esta fechado?")


def capturar(porta: str, segundos: float, saida: Path) -> None:
    from serial import Serial

    saida.parent.mkdir(parents=True, exist_ok=True)
    n_iq = n_cs = 0
    ultima = ""
    avisou_silencio = False
    avisou_conexao = False
    print(f"capturando {segundos:.0f} s em {porta} -> {saida}  (Ctrl+C encerra antes e mantem o arquivo)")
    inicio = time.time()
    proximo_status = inicio
    with Serial(porta, BAUD, timeout=1, dsrdtr=False) as s, open(saida, "w", encoding="utf-8") as f:
        # LM20-DK: as linhas do VCOM so falam com DTR ativo.
        s.dtr = True
        try:
            while time.time() - inicio < segundos:
                line = s.readline().decode("utf-8", "replace")
                agora = time.time()
                if cs_csv.is_tag_prompt(line):
                    print("\naviso: a DK esta no prompt do endereco. Abra a COM num terminal, "
                          "digite o endereco do TAG, Enter, feche o terminal e rode de novo.",
                          flush=True)
                rec = cs_csv.parse_line(line)
                if rec is not None:
                    if not avisou_conexao:
                        avisou_conexao = True
                        # O firmware so despeja IQ depois de conectar e ativar o CS:
                        # a primeira linha de dados e a prova de que o par fechou.
                        print("\nDK conectada ao TAG: chegando dados de Channel Sounding", flush=True)
                    f.write(line if line.endswith("\n") else line + "\n")
                    if rec[0] == "IQ":
                        n_iq += 1
                    else:
                        n_cs += 1
                        ultima = (f"ultima: ifft={rec[4]:.2f} phase_slope={rec[5]:.2f} "
                                  f"rtt={rec[6]:.2f} m")
                # Linha de status a cada segundo, com ou sem dado chegando: e o
                # sinal de que o script esta vivo e de que a DK esta (ou nao) falando.
                if agora >= proximo_status or (rec is not None and rec[0] == "CS"):
                    dt = max(agora - inicio, 1e-3)
                    print(f"\r[{dt:5.1f} / {segundos:.0f} s]  {n_cs} procedures "
                          f"({n_cs / dt:.1f}/s)  {ultima}   ", end="", flush=True)
                    proximo_status = agora + 1.0
                if not avisou_silencio and n_cs == 0 and agora - inicio > 10:
                    avisou_silencio = True
                    print("\naviso: 10 s sem nenhuma procedure. O TAG esta ligado? O endereco "
                          "digitado e o dele? A DK esta com o 05_cs_iq_music?", flush=True)
        except KeyboardInterrupt:
            print("\ninterrompido pelo usuario; fechando o arquivo.")
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
