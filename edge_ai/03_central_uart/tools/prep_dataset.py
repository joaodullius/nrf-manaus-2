#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepara o dataset de gestos para o Nordic Edge AI Lab.

Cola entre o que a serial cospe (via 03_central_uart) e o que o Lab aceita.

Fluxo:

    1. record   grava um gesto por vez, direto da serial, ja no formato do Lab
    2. merge    junta os arquivos por classe num dataset.csv e valida

    (convert)   alternativa ao record, para quem gravou com o Serial Terminal
                do nRF Connect for Desktop

O que a serial entrega (03_central_uart, 100 Hz):

    87799 67,9602,535,1,-3,0
    ^^^^^ ^^ ^^^^ ^^^ ^ ^^ ^
    id    ax ay   az  gx gy gz      int16 em mili-unidades

O que o Edge AI Lab exige:

    acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z,class
    67,9602,535,1,-3,0,2

O id e descartado: serve so para detectar amostra perdida, o que este script
faz durante a gravacao.

Unidades: mantidas como vem, int16 em mili-unidades. NAO converter para fisico.
O Lab aceita INT16, e a app alimenta nrf_edgeai_feed_inputs() com imu_data.raw,
que e a mesma escala — treinar em mili e auto-consistente com a inferencia.

Requisitos: Python 3.8+ e pyserial (ja presente no toolchain do nRF Connect).
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime

# Classes do 01_gesture_recognition (src/inference_postprocessing.h).
# A ordem do enum coincide com a numeracao usada na doc do Edge AI Lab.
CLASSES = {
    "idle": 0,
    "unknown": 1,
    "swipe_right": 2,
    "swipe_left": 3,
    "double_shake": 4,
    "double_thumb": 5,
    "rotation_right": 6,
    "rotation_left": 7,
}

COLUNAS = ["acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"]
COLUNA_ALVO = "class"

# "<id> ax,ay,az,gx,gy,gz"
LINHA = re.compile(r"^\s*(\d+)\s+(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+)\s*$")

# Regras do Lab (docs.nordicsemi.com/r/bundle/edge-ai-lab, dataset_requirements)
MIN_AMOSTRAS_POR_CLASSE = 20
MIN_CLASSES = 2


def morrer(msg: str) -> "NoReturn":  # noqa: F821
    print(f"erro: {msg}", file=sys.stderr)
    raise SystemExit(1)


def classe_para_numero(nome: str) -> int:
    chave = nome.strip().lower().replace("-", "_").replace(" ", "_")
    if chave not in CLASSES:
        morrer(
            f"classe desconhecida: {nome!r}\n"
            f"       use uma de: {', '.join(CLASSES)}"
        )
    return CLASSES[chave]


def escreve_csv(caminho: str, linhas, numero_classe: int) -> int:
    """Grava o CSV no formato do Lab. Devolve quantas linhas de dados sairam."""
    os.makedirs(os.path.dirname(os.path.abspath(caminho)) or ".", exist_ok=True)
    n = 0
    # newline="" + lineterminator="\n": LF consistente, como o Lab pede.
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUNAS + [COLUNA_ALVO])
        for valores in linhas:
            w.writerow(list(valores) + [numero_classe])
            n += 1
    return n


# --------------------------------------------------------------------------
# record
# --------------------------------------------------------------------------

def acha_porta(baud: int, espera: float = 3.0) -> str:
    """Devolve a primeira porta que estiver cuspindo linhas no formato esperado."""
    from serial import Serial, SerialException
    from serial.tools import list_ports

    candidatas = [p.device for p in list_ports.comports()]
    if not candidatas:
        morrer("nenhuma porta serial encontrada")

    print(f"procurando a porta com dados ({', '.join(candidatas)}) ...")
    for porta in candidatas:
        try:
            with Serial(porta, baud, timeout=0.3) as s:
                fim = time.time() + espera
                while time.time() < fim:
                    linha = s.readline().decode("utf-8", "replace")
                    if LINHA.match(linha):
                        print(f"porta encontrada: {porta}")
                        return porta
        except (SerialException, OSError):
            continue
    morrer(
        "nenhuma porta esta enviando dados no formato esperado.\n"
        "       confira: a DK esta gravada com o 03_central_uart? o tag esta ligado\n"
        "       e com o data_collection.conf? o endereco digitado no central esta certo?"
    )


def cmd_record(args) -> None:
    try:
        from serial import Serial
    except ImportError:
        morrer("pyserial nao encontrado. Rode dentro do toolchain do nRF Connect,\n"
               "       ou instale com: pip install pyserial")

    numero = classe_para_numero(args.classe)
    porta = args.port or acha_porta(args.baud)

    carimbo = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    saida = args.out or os.path.join("dataset", f"{args.classe.lower()}_{carimbo}.csv")

    print()
    print(f"  classe   {args.classe} (= {numero})")
    print(f"  porta    {porta} @ {args.baud}")
    print(f"  saida    {saida}")
    print(f"  duracao  {args.seconds} s" if args.seconds else "  duracao  ate Ctrl-C")
    print()
    print("  Faca SO este gesto, repetidamente. Sugestao da Nordic:")
    print("    3-5 s parado no comeco · gesto de 1-2 s · ~1 s de pausa entre eles")
    print("    varie velocidade, orientacao e intensidade")
    print()
    input("  ENTER para comecar a gravar... ")

    amostras = []
    perdidas = 0
    lixo = 0
    ultimo_id = None
    t0 = time.time()

    try:
        with Serial(porta, args.baud, timeout=0.5) as s:
            s.reset_input_buffer()
            while True:
                if args.seconds and (time.time() - t0) >= args.seconds:
                    break
                bruto = s.readline().decode("utf-8", "replace")
                if not bruto:
                    continue
                m = LINHA.match(bruto)
                if not m:
                    lixo += 1
                    continue
                ident = int(m.group(1))
                if ultimo_id is not None:
                    salto = ident - ultimo_id
                    if salto > 1:
                        perdidas += salto - 1
                ultimo_id = ident
                amostras.append(m.groups()[1:])

                if len(amostras) % 100 == 0:
                    dt = time.time() - t0
                    taxa = len(amostras) / dt if dt else 0
                    print(f"\r  {len(amostras):6d} amostras · {dt:5.1f} s · "
                          f"{taxa:5.1f} Hz · {perdidas} perdidas", end="", flush=True)
    except KeyboardInterrupt:
        print("\n  interrompido.")

    dt = time.time() - t0
    print()

    if not amostras:
        morrer("nenhuma amostra capturada — a serial nao entregou nada no formato esperado")

    n = escreve_csv(saida, amostras, numero)
    taxa = n / dt if dt else 0
    print()
    print(f"  gravado  {n} amostras em {dt:.1f} s ({taxa:.1f} Hz) -> {saida}")
    if perdidas:
        pct = 100.0 * perdidas / (n + perdidas)
        print(f"  ATENCAO  {perdidas} amostras perdidas ({pct:.2f}%) — buracos na sequencia de id")
    if lixo:
        print(f"  nota     {lixo} linhas ignoradas (banner de boot, linha partida)")
    if dt < 60:
        print("  nota     a doc do Lab sugere 3-5 min por gesto para um PoC")
    print()
    print("  Proximo: grave as outras classes e depois rode 'merge'.")


# --------------------------------------------------------------------------
# convert
# --------------------------------------------------------------------------

def cmd_convert(args) -> None:
    numero = classe_para_numero(args.classe)
    if not os.path.isfile(args.entrada):
        morrer(f"arquivo nao encontrado: {args.entrada}")

    amostras, lixo, perdidas = [], 0, 0
    ultimo_id = None
    with open(args.entrada, "r", encoding="utf-8", errors="replace") as f:
        for bruto in f:
            m = LINHA.match(bruto)
            if not m:
                lixo += 1
                continue
            ident = int(m.group(1))
            if ultimo_id is not None and ident - ultimo_id > 1:
                perdidas += ident - ultimo_id - 1
            ultimo_id = ident
            amostras.append(m.groups()[1:])

    if not amostras:
        morrer(f"nenhuma linha no formato '<id> ax,ay,az,gx,gy,gz' em {args.entrada}")

    saida = args.out or os.path.splitext(args.entrada)[0] + "_lab.csv"
    n = escreve_csv(saida, amostras, numero)
    print(f"{n} amostras · classe {args.classe} (= {numero}) -> {saida}")
    if perdidas:
        print(f"ATENCAO: {perdidas} amostras perdidas (buracos no id)")
    if lixo:
        print(f"nota: {lixo} linhas ignoradas")


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------

def cmd_merge(args) -> None:
    entradas = []
    for padrao in args.entradas:
        achados = sorted(glob.glob(padrao))
        if not achados:
            morrer(f"nada casou com {padrao!r}")
        entradas.extend(achados)
    entradas = [e for e in entradas if os.path.abspath(e) != os.path.abspath(args.out)]
    if not entradas:
        morrer("nenhum arquivo de entrada")

    cabecalho_esperado = COLUNAS + [COLUNA_ALVO]
    todas, por_classe = [], Counter()

    for caminho in entradas:
        with open(caminho, "r", encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            try:
                cab = next(r)
            except StopIteration:
                morrer(f"{caminho}: arquivo vazio")
            if cab != cabecalho_esperado:
                morrer(f"{caminho}: header inesperado\n"
                       f"       esperado: {','.join(cabecalho_esperado)}\n"
                       f"       lido    : {','.join(cab)}")
            for i, linha in enumerate(r, start=2):
                if len(linha) != len(cabecalho_esperado):
                    morrer(f"{caminho}:{i}: {len(linha)} colunas, esperava {len(cabecalho_esperado)}")
                for v in linha:
                    if v.strip() == "":
                        morrer(f"{caminho}:{i}: valor vazio — o Lab rejeita")
                    try:
                        int(v)
                    except ValueError:
                        morrer(f"{caminho}:{i}: valor nao inteiro: {v!r}")
                todas.append(linha)
                por_classe[int(linha[-1])] += 1
        print(f"  lido {caminho}")

    # Regras do Lab
    problemas = []
    if len(por_classe) < MIN_CLASSES:
        problemas.append(f"so {len(por_classe)} classe(s); o Lab exige >= {MIN_CLASSES}")
    for c, n in sorted(por_classe.items()):
        if n < MIN_AMOSTRAS_POR_CLASSE:
            problemas.append(f"classe {c}: {n} amostras, minimo {MIN_AMOSTRAS_POR_CLASSE}")
    if 0 not in por_classe:
        problemas.append("nenhuma amostra da classe 0 — o Lab exige que o alvo comece em 0")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cabecalho_esperado)
        w.writerows(todas)

    invertido = {v: k for k, v in CLASSES.items()}
    print()
    print(f"  {args.out}: {len(todas)} amostras, {len(por_classe)} classes")
    for c, n in sorted(por_classe.items()):
        print(f"    {c}  {invertido.get(c, '?'):<16} {n:7d} amostras  ({n/100.0:6.1f} s a 100 Hz)")
    print()

    if problemas:
        print("  NAO subir ainda:")
        for p in problemas:
            print(f"    - {p}")
        raise SystemExit(1)

    print("  Validado contra as regras do Edge AI Lab.")
    print()

    # A janela do Lab tem que ser a mesma usada na centralizacao, senao as
    # janelas do Lab comecam desalinhadas dos segmentos e a centralizacao e
    # desfeita. Detectamos pelo tamanho das classes: o center_gestures.py
    # deixa toda classe multipla da janela.
    centralizado = all(n % 100 == 0 for n in por_classe.values())

    if centralizado:
        print("  Todas as classes sao multiplas de 100 — dataset ja centralizado.")
        print("  ai.lab.nordicsemi.com -> classification -> target = 'class'")
        print("  signal processing: window 100, training shift 100, inference shift 33")
        print()
        print("  A window do Lab TEM que ser a mesma da centralizacao. Diferente,")
        print("  as janelas do Lab comecam desalinhadas dos segmentos.")
    else:
        print("  Gestos discretos (swipe, knock, tap) ainda NAO estao centralizados.")
        print("  Sem isso a janela corta gestos ao meio. Para centralizar:")
        print("    python tools/center_gestures.py \"dataset/swipe_*.csv\"")
        print("    python tools/center_gestures.py \"dataset/idle_*.csv\" \"dataset/unknown_*.csv\" --continuo")
        print()
        print("  Para subir assim mesmo (sem centralizar):")
        print("  ai.lab.nordicsemi.com -> classification -> target = 'class'")
        print("  signal processing: window 99, training shift 33, inference shift 33")


# --------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="Prepara o dataset de gestos para o Nordic Edge AI Lab.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="classes: " + ", ".join(f"{k}={v}" for k, v in CLASSES.items()),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="grava um gesto direto da serial")
    r.add_argument("classe", help="nome da classe (ex.: swipe_right)")
    r.add_argument("--port", help="porta serial (auto-detecta se omitido)")
    r.add_argument("--baud", type=int, default=115200)
    r.add_argument("--seconds", type=float, default=None,
                   help="duracao; sem isto, grava ate Ctrl-C")
    r.add_argument("--out", help="arquivo de saida")
    r.set_defaults(func=cmd_record)

    c = sub.add_parser("convert", help="converte um log salvo pelo Serial Terminal")
    c.add_argument("classe")
    c.add_argument("entrada")
    c.add_argument("--out")
    c.set_defaults(func=cmd_convert)

    m = sub.add_parser("merge", help="junta os CSVs por classe e valida")
    m.add_argument("entradas", nargs="+", help="arquivos ou padroes (ex.: dataset/*.csv)")
    m.add_argument("--out", default="dataset.csv")
    m.set_defaults(func=cmd_merge)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
