#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confere se um ZED-X20P esta no padrao de fabrica e, se pedido, devolve-o a ele — codigo do curso.

    python x20p_default.py --porta COM18            # so confere: RAM x padrao de fabrica
    python x20p_default.py --porta COM18 --aplicar  # apaga BBR e flash, recarrega o padrao, confere
    python x20p_default.py --listar                 # portas de EVK-X20P vistas

Serve para desfazer o que rtk_base_rover.py (ou o u-center 2) deixou no receptor:
modo de base (TMODE), saida de RTCM, NMEA de alta precisao, baud trocado. Um X20P
no padrao e o receptor "autonomo" do degrau 2 da escada: sem correcao, sem RTCM,
plano de sinal SP2, 38400 bps nas duas UARTs.

Como confere: UBX-CFG-VALGET das chaves que o curso mexe, na camada 0 (RAM, o que
vale agora) e na camada 7 (Default, o padrao de fabrica). A diferenca entre as
duas e exatamente o que alguem mudou.

Como aplica: UBX-CFG-CFG com clearMask = loadMask = 0xFFFF em BBR e flash, que e
a forma da u-blox de "restaurar padrao": apaga as duas camadas persistentes e
recarrega o padrao na RAM. Depois disso o receptor volta a falar a 38400 bps, e
o script reabre a porta nesse baud para conferir de novo. A configuracao de
navegacao (efemerides, almanaque) nao e apagada por isto; para partida a frio
use o x20p_ttff.py.

Use a porta de CONTROLE (a que fala UBX). O u-center 2 nao pode estar com a
mesma porta aberta.
"""
from __future__ import annotations

import argparse
import struct
import sys
import time

import serial

from rtk_base_rover import (TAM, ubx, fala, monver, abre, portas_x20p,
                            RTCM_POR_UART, TMODE_MODE, NMEA_HIGHPREC)

SIGNAL_PLAN = 0x2031003A
UART1_BAUD, UART2_BAUD = 0x40520001, 0x40530001
BAUD_PADRAO = 38400

# chaves que o curso mexe, com nome legivel
CHAVES = [("CFG-TMODE-MODE (0 = rover)", TMODE_MODE),
          ("CFG-NMEA-HIGHPREC", NMEA_HIGHPREC),
          ("CFG-SIGNAL-PLAN (2 = SP2)", SIGNAL_PLAN),
          ("CFG-UART1-BAUDRATE", UART1_BAUD),
          ("CFG-UART2-BAUDRATE", UART2_BAUD)]
for uart in (1, 2):
    for nome, k in RTCM_POR_UART[uart].items():
        if nome != "4072.0":
            CHAVES.append((f"RTCM {nome} na UART{uart}", k))


def valget(s: serial.Serial, chaves, camada: int) -> dict[int, int]:
    """Le as chaves numa camada (0 RAM, 1 BBR, 2 flash, 7 default)."""
    p = struct.pack("<BBH", 0x00, camada, 0) + b"".join(struct.pack("<I", k) for k in chaves)
    for cls, mid, pl in fala(s, ubx(0x06, 0x8B, p)):
        if (cls, mid) == (0x06, 0x8B) and len(pl) >= 4:
            out, i = {}, 4
            while i + 4 <= len(pl):
                k = struct.unpack("<I", pl[i:i + 4])[0]
                t = TAM.get((k >> 28) & 0x7, 1)
                out[k] = int.from_bytes(pl[i + 4:i + 4 + t], "little")
                i += 4 + t
            return out
    return {}


def tabela(s: serial.Serial) -> int:
    """Imprime RAM x Default e devolve quantas chaves diferem."""
    ks = [k for _, k in CHAVES]
    ram, padrao = valget(s, ks, 0), valget(s, ks, 7)
    if not ram or not padrao:
        print("  (o receptor nao respondeu ao VALGET; versao antiga ou porta errada?)")
        return -1
    dif = 0
    print(f"  {'chave':32s} {'RAM':>8s} {'padrao':>8s}")
    for nome, k in CHAVES:
        a, b = ram.get(k, "?"), padrao.get(k, "?")
        marca = "" if a == b else "  <- difere"
        dif += a != b
        print(f"  {nome:32s} {str(a):>8s} {str(b):>8s}{marca}")
    return dif


def restaura(s: serial.Serial) -> bool:
    """UBX-CFG-CFG: limpa BBR e flash e recarrega o padrao na RAM."""
    payload = struct.pack("<IIIB", 0x0000FFFF, 0x00000000, 0x0000FFFF, 0x03)
    for cls, mid, _ in fala(s, ubx(0x06, 0x09, payload), 3.0):
        if cls == 0x05:
            return mid == 1
    return False   # sem ACK: confere pelo VALGET mesmo assim


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--porta", help="porta de CONTROLE do X20P (a que fala UBX)")
    p.add_argument("--baud", type=int, help="padrao: detecta 115200/38400/9600")
    p.add_argument("--aplicar", action="store_true",
                   help="restaura o padrao de fabrica (apaga BBR e flash); sem isto so confere")
    p.add_argument("--listar", action="store_true", help="mostra as portas de EVK-X20P e sai")
    a = p.parse_args(argv)

    if a.listar:
        portas = portas_x20p()
        if not portas:
            print("nenhum EVK-X20P encontrado")
        for dev, desc in portas:
            print(f"  {dev:8s} {desc}")
        return 0
    if not a.porta:
        p.error("--porta e obrigatorio (ou use --listar)")

    log = lambda m: print(m, flush=True)  # noqa: E731
    s, baud = abre(a.porta, a.baud, log)

    print("\nantes:")
    dif = tabela(s)
    if dif == 0:
        print("\nOK: o receptor ja esta no padrao de fabrica nas chaves conferidas")
    if not a.aplicar:
        s.close()
        return 0 if dif == 0 else 1

    print("\nrestaurando o padrao de fabrica (UBX-CFG-CFG, BBR + flash)...")
    ack = restaura(s)
    print("  ACK" if ack else "  sem ACK (conferindo pelo VALGET)")
    s.close()
    time.sleep(1.5)

    # depois do reset o receptor fala no baud de fabrica
    for b in (BAUD_PADRAO, baud, 115200, 9600):
        try:
            s = serial.Serial(a.porta, b, timeout=0.3)
        except serial.SerialException as e:
            raise SystemExit(f"{a.porta}: {e}")
        if monver(s):
            print(f"\nreaberto a {b} bps")
            break
        s.close()
    else:
        raise SystemExit(f"{a.porta}: o receptor nao respondeu depois do reset")

    print("\ndepois:")
    dif = tabela(s)
    s.close()
    if dif == 0:
        print("\nOK: padrao de fabrica restaurado. O X20P e de novo o receptor autonomo do degrau 2.")
        return 0
    print(f"\nATENCAO: {dif} chave(s) ainda diferem do padrao", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
