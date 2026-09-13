#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede TTFF a frio no ZED-X20P, repetidas vezes — codigo do curso.

    python x20p_ttff.py --porta COM18 --amostras 6

O X20P mede o proprio TTFF: o campo `ttff` do UBX-NAV-STATUS traz, em
milissegundos, o tempo desde a partida ate o primeiro fix. Nao e preciso
cronometrar de fora, e o numero nao depende de latencia de serial.

O laco e: UBX-CFG-RST com navBbrMask=0xFFFF (apaga efemerides, almanaque, hora e
posicao) e resetMode=0x02 (reinicio controlado, so do GNSS); espera o fix; le o
ttff; repete.

Conferido na bancada: esse reset **preserva a configuracao em RAM** (baud e
mensagens habilitadas continuam), e zera o fix de verdade — o GGA volta a
qualidade 0 com zero satelites.

A u-blox avisa que firmware novo NAO confirma o CFG-RST; nao esperar ACK.

Use a porta de CONTROLE (a que fala UBX). A porta de captura deve ficar livre
para o NMEA, e nao se deve medir dispersao ao mesmo tempo: cada reset apaga o
fix.
"""
from __future__ import annotations

import argparse
import statistics
import struct
import sys
import time

import serial

CFG_RST = (0x06, 0x04)
NAV_STATUS = (0x01, 0x03)
FIXO = {0: "nenhum", 1: "dead reckoning", 2: "2D", 3: "3D", 4: "GPS+DR", 5: "so tempo"}


def _ubx(cls: int, mid: int, payload: bytes = b"") -> bytes:
    corpo = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for x in corpo:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return bytes([0xB5, 0x62]) + corpo + bytes([a, b])


def _quadros(buf: bytes):
    saida, i = [], 0
    while True:
        i = buf.find(b"\xb5\x62", i)
        if i < 0 or i + 6 > len(buf):
            break
        ln = struct.unpack("<H", buf[i + 4:i + 6])[0]
        fim = i + 6 + ln + 2
        if fim > len(buf):
            break
        q = buf[i:fim]
        a = b = 0
        for x in q[2:-2]:
            a = (a + x) & 0xFF
            b = (b + a) & 0xFF
        if (a, b) == (q[-2], q[-1]):
            saida.append((q[2], q[3], q[6:-2]))
        i = fim
    return saida


def le_status(s: serial.Serial, espera: float = 1.5):
    """Devolve (gpsFix, gpsFixOK, carrSoln, ttff_ms, msss_ms) ou None."""
    s.reset_input_buffer()
    s.write(_ubx(*NAV_STATUS))
    fim, buf = time.time() + espera, b""
    while time.time() < fim:
        buf += s.read(4096)
    for cls, mid, p in _quadros(buf):
        if (cls, mid) == NAV_STATUS and len(p) >= 16:
            # 4 gpsFix, 5 flags, 6 fixStat, 7 flags2, 8 ttff, 12 msss
            ttff, msss = struct.unpack("<II", p[8:16])
            return p[4], bool(p[5] & 0x01), (p[7] >> 6) & 0x03, ttff, msss
    return None


def frio(s: serial.Serial) -> None:
    """Partida a frio: apaga tudo da BBR, reinicia so o GNSS. Nao devolve ACK."""
    s.write(_ubx(*CFG_RST, struct.pack("<HBB", 0xFFFF, 0x02, 0x00)))
    time.sleep(1.5)


def uma_amostra(s: serial.Serial, limite: float) -> tuple[float | None, int]:
    frio(s)
    t0 = time.time()
    while time.time() - t0 < limite:
        st = le_status(s)
        if st and st[1] and st[3] > 0:
            return st[3] / 1000.0, st[0]
        time.sleep(1.0)
    return None, 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--porta", required=True, help="porta de CONTROLE, a que fala UBX")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--amostras", type=int, default=6)
    p.add_argument("--limite", type=float, default=420.0,
                   help="segundos de espera maxima por amostra")
    p.add_argument("--descartar", type=int, default=0,
                   help="quantas primeiras amostras ignorar no resumo")
    a = p.parse_args(argv)

    s = serial.Serial(a.porta, a.baud, timeout=0.3)
    st = le_status(s)
    if not st:
        print(f"erro: {a.porta} nao respondeu ao UBX-NAV-STATUS", file=sys.stderr)
        return 1
    print(f"{a.porta}: fix atual {FIXO.get(st[0], st[0])}, ttff da partida corrente "
          f"{st[3]/1000:.1f} s")

    vals = []
    for i in range(a.amostras):
        t, fix = uma_amostra(s, a.limite)
        if t is None:
            print(f"  [{i+1}/{a.amostras}] sem fix em {a.limite:.0f} s", flush=True)
        else:
            vals.append(t)
            print(f"  [{i+1}/{a.amostras}] TTFF = {t:6.1f} s   (fix {FIXO.get(fix, fix)})",
                  flush=True)
    s.close()

    uteis = vals[a.descartar:]
    if uteis:
        print(f"\namostras: {vals}")
        print(f"regime (descartando {a.descartar}): mediana {statistics.median(uteis):.1f} s, "
              f"faixa {min(uteis):.1f} a {max(uteis):.1f} s, n={len(uteis)}")
    return 0 if vals else 1


if __name__ == "__main__":
    sys.exit(main())
