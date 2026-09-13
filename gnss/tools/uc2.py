#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le e escreve o formato .uc2, o log do u-center 2 — codigo do curso.

O u-center 2 grava dois arquivos por sessao: um .ubx, que e o fluxo cru, e um
.uc2, que e o mesmo fluxo com carimbo de tempo por registro. Para reproduzir um
log dentro do u-center 2 e preciso o .uc2 — o .ubx sozinho nao abre.

Layout, obtido por engenharia reversa de um log real e conferido regenerando o
arquivo byte a byte:

    [0x00] uint32  magia = 0x3C613A08
    [0x04] uint32  versao = 1
    [0x08] uint32  zero
    [0x0C] uint32  offset onde a secao de dados termina
    [0x10] uint32  zero
    [0x14] uint32  tamanho do JSON de metadados
    [0x18] JSON
           dados:   { uint32 ts_ms; uint32 tam; bytes }  repetido
    [fim]  indice:  { uint32 ts_ms; uint32 offset; uint32 zero }  um por registro

O ts_ms conta a partir do startTime do JSON. Os registros guardam as duas
direcoes: o que o receptor mandou e o que o u-center enviou a ele.
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MAGIA = 0x3C613A08
VERSAO = 1
CABECALHO = 24


@dataclass
class Registro:
    ts_ms: int
    dados: bytes


def escrever(destino: Path, registros, *, device_name: str,
             start_time: datetime | None = None,
             connection_type: str = "serial") -> Path:
    """Grava um .uc2 a partir de uma sequencia de Registro."""
    registros = list(registros)
    inicio = start_time or datetime.now(timezone.utc)
    meta = {
        "startTime": inicio.astimezone(timezone.utc)
                     .strftime("%Y-%m-%dT%H:%M:%S.") + f"{inicio.microsecond // 1000:03d}Z",
        "deviceId": f"{connection_type}-{device_name}",
        "connectionType": connection_type,
        "deviceName": device_name,
        "logType": "timestamped",
        "version": VERSAO,
    }
    js = json.dumps(meta, separators=(",", ":")).encode("utf-8")

    dados, indice = bytearray(), bytearray()
    pos = CABECALHO + len(js)
    for r in registros:
        indice += struct.pack("<III", r.ts_ms, pos, 0)
        dados += struct.pack("<II", r.ts_ms, len(r.dados)) + r.dados
        pos += 8 + len(r.dados)

    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "wb") as f:
        f.write(struct.pack("<6I", MAGIA, VERSAO, 0, pos, 0, len(js)))
        f.write(js)
        f.write(dados)
        f.write(indice)
    return destino


def ler(origem: Path) -> tuple[dict, list[Registro]]:
    """Devolve (metadados, registros) de um .uc2."""
    d = Path(origem).read_bytes()
    magia, versao, _, fim, _, tam_json = struct.unpack("<6I", d[:CABECALHO])
    if magia != MAGIA:
        raise ValueError(f"{origem}: nao e um .uc2 (magia {magia:#x})")
    meta = json.loads(d[CABECALHO:CABECALHO + tam_json])
    off, regs = CABECALHO + tam_json, []
    while off < fim:
        ts, tam = struct.unpack("<II", d[off:off + 8])
        regs.append(Registro(ts, d[off + 8:off + 8 + tam]))
        off += 8 + tam
    return meta, regs


def bruto(origem: Path) -> bytes:
    """O fluxo cru de dentro de um .uc2 — o equivalente ao .ubx irmao."""
    return b"".join(r.dados for r in ler(origem)[1])
