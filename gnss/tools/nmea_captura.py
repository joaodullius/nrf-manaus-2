#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grava o fluxo de uma porta NMEA em .nmea e em .uc2 — codigo do curso.

    python nmea_captura.py --port COM23 --seconds 900 --out capturas/nrf9151_aberto

Saem dois arquivos com o mesmo nome base:

    <out>.nmea   o fluxo cru, byte a byte, para o desvio.py (repo de docs) e para qualquer
                 ferramenta que leia NMEA
    <out>.uc2    o mesmo fluxo com carimbo de tempo, que abre no u-center 2 e
                 reproduz a sessao — inclusive o mapa de desvio com CEP50/CEP95

So funciona com uma porta que entregue NMEA limpo. No nRF9151 isso quer dizer o
build do lab 3 (NMEA_ONLY, sem CONFIG_LOG e sem AT host): a porta do lab 1
mistura log do Zephyr e codigo ANSI no meio das sentencas, e o u-center descarta
o que nao fecha checksum.

A porta serial e exclusiva: com o u-center 2 conectado na mesma COM, esta captura
falha com 'Acesso negado'. Feche um antes de abrir o outro.

Requisitos: pyserial (ja vem no toolchain do nRF Connect).
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import serial

import uc2

BAUD = 115200


def captura(port: str, baud: int, segundos: float, base: Path) -> dict:
    """Copia a serial para <base>.nmea e <base>.uc2, e conta o que passou."""
    base.parent.mkdir(parents=True, exist_ok=True)
    bruto = base.with_suffix(".nmea")
    st = {"bytes": 0, "sentencas": 0, "gga_com_fix": 0, "qualidades": {}}
    registros, resto = [], b""
    inicio = datetime.now(timezone.utc)
    t0 = time.time()
    fim = t0 + segundos
    with serial.Serial(port, baud, timeout=0.5) as s, open(bruto, "wb") as f:
        s.reset_input_buffer()
        while time.time() < fim:
            bloco = s.read(4096)
            if not bloco:
                continue
            agora = int((time.time() - t0) * 1000)
            f.write(bloco)
            f.flush()
            st["bytes"] += len(bloco)
            resto += bloco
            # um registro por sentenca completa, como o u-center faz
            while b"\n" in resto:
                linha, resto = resto.split(b"\n", 1)
                linha += b"\n"
                registros.append(uc2.Registro(agora, linha))
                nua = linha.strip()
                if not nua.startswith(b"$"):
                    continue
                st["sentencas"] += 1
                campos = nua.split(b",")
                if campos[0][3:6] == b"GGA" and len(campos) > 6:
                    q = campos[6].decode("ascii", "replace") or "-"
                    st["qualidades"][q] = st["qualidades"].get(q, 0) + 1
                    if q not in ("", "0", "-"):
                        st["gga_com_fix"] += 1
        if resto:
            registros.append(uc2.Registro(int((time.time() - t0) * 1000), resto))
    uc2.escrever(base.with_suffix(".uc2"), registros,
                 device_name=port, start_time=inicio)
    st["registros"] = len(registros)
    return st


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", required=True)
    p.add_argument("--baud", type=int, default=BAUD)
    p.add_argument("--seconds", type=float, required=True)
    p.add_argument("--out", required=True, type=Path,
                   help="nome base, sem extensao")
    a = p.parse_args(argv)

    base = a.out.with_suffix("")
    t0 = time.time()
    st = captura(a.port, a.baud, a.seconds, base)
    print(f"{base}.nmea + {base}.uc2: {st['bytes']} bytes em {time.time()-t0:.0f}s")
    print(f"  registros no .uc2: {st['registros']}")
    print(f"  sentencas NMEA: {st['sentencas']}")
    print(f"  GGA com fix: {st['gga_com_fix']}")
    print(f"  qualidades vistas (campo 6 do GGA): {st['qualidades']}")
    if st["gga_com_fix"] == 0:
        print("  ATENCAO: nenhum fix no periodo — o log nao serve para o mapa de desvio")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
