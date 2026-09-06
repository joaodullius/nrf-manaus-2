#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formato do payload do lab 9 — codigo do curso (nrf-manaus-2).

Uma linha JSON por amostra. E a MESMA estrutura que o firmware monta em
src/payload.c -- e de proposito que existem duas implementacoes do mesmo
formato, uma em C e outra aqui: o firmware roda no kit e so pode ser C; o
servidor do PC (wifi_server.py) e os testes rodam em Python. Manter as duas
manualmente sincronizadas seria facil de deixar divergir sem ninguem notar;
por isso tests/test_payload_c.py compila payload.c de verdade num binario de
host e compara, byte a byte, com o que montar() produz aqui -- e essa
comparacao, nao os testes so em Python contra eles mesmos, que prova que as
duas implementacoes concordam.

    {"seq":7,"uptime_ms":1234,"temp_c":25.37,"rssi_dbm":-52,"botao":false}

temp_c chega do firmware como centesimos de grau, um inteiro (temp_cc), nao
como ponto flutuante: o firmware desliga o suporte a float no cbprintf
(CONFIG_CBPRINTF_FP_SUPPORT=n, em prj.conf) para nao pagar o custo de flash
desse suporte so para formatar uma temperatura, e monta a linha com divisao e
resto inteiros em vez de "%f" (ver src/payload.c). montar() aqui faz o
caminho inverso, de volta para grau com duas casas -- o lado do PC nao tem
essa restricao de espaco.
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
