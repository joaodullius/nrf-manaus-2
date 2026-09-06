#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formato do payload do lab 9 — codigo do curso (nrf-manaus-2).

Uma linha JSON por amostra. E a MESMA estrutura que o firmware monta em
src/payload.c; este modulo existe para o servidor do PC e para os testes, e
para o aluno poder ler o formato sem abrir o C.

    {"seq":7,"uptime_ms":1234,"temp_c":25.37,"rssi_dbm":-52,"botao":false}

temp_c vem do firmware em centesimos de grau (int) para nao precisar de float
na serializacao embarcada; aqui vira grau com duas casas.
"""
from __future__ import annotations

import json

CAMPOS = ("seq", "uptime_ms", "temp_c", "rssi_dbm", "botao")


def montar(seq: int, uptime_ms: int, temp_cc: int, rssi_dbm: int, botao: bool) -> str:
    return json.dumps({
        "seq": seq,
        "uptime_ms": uptime_ms,
        "temp_c": round(temp_cc / 100.0, 2),
        "rssi_dbm": rssi_dbm,
        "botao": botao,
    }, separators=(",", ":")) + "\n"


def parse(linha: str):
    """Devolve o dicionario da amostra, ou None se a linha nao for uma."""
    try:
        d = json.loads(linha)
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict) or any(c not in d for c in CAMPOS):
        return None
    return {c: d[c] for c in CAMPOS}
