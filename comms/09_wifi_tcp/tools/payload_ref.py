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


def _tipo_valido(campo: str, valor) -> bool:
    """Confere se o valor de um campo tem o tipo esperado. bool e subclasse
    de int em Python, entao precisa ser tratado antes dos campos numericos
    para nao aceitar 0/1 no lugar de true/false, nem True/False no lugar
    de um numero.
    """
    if campo == "botao":
        return isinstance(valor, bool)
    if campo == "temp_c":
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)
    # seq, uptime_ms, rssi_dbm
    return isinstance(valor, int) and not isinstance(valor, bool)


def parse(linha: str):
    """Devolve o dicionario da amostra, ou None se a linha nao for uma
    (JSON invalido, campo faltando, ou campo com o tipo errado)."""
    try:
        d = json.loads(linha)
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict) or any(c not in d for c in CAMPOS):
        return None
    if any(not _tipo_valido(c, d[c]) for c in CAMPOS):
        return None
    return {c: d[c] for c in CAMPOS}
