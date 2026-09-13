# -*- coding: utf-8 -*-
"""Testes do formato do payload, so em Python (payload_ref.py contra ele
mesmo). A travessia contra o payload.c real esta em test_payload_c.py; os
vetores usados aqui vem do mesmo arquivo que aquele teste usa
(vetores_payload.json), para o contrato ficar num lugar so.
"""
import json
from pathlib import Path

import pytest
from payload_ref import montar, parse

VETORES = json.loads((Path(__file__).parent / "vetores_payload.json").read_text(encoding="utf-8"))
CASOS = VETORES["casos"]


def _por_nome(nome):
    for caso in CASOS:
        if caso["nome"] == nome:
            return caso
    raise KeyError(nome)


def test_monta_linha_json_com_todos_os_campos():
    c = _por_nome("todos_os_campos")
    linha = montar(seq=c["seq"], uptime_ms=c["uptime_ms"], temp_cc=c["temp_cc"],
                   rssi_dbm=c["rssi_dbm"], botao=c["botao"])
    assert linha.endswith("\n")
    d = json.loads(linha)
    assert d == c["esperado"]


def test_temperatura_negativa_e_meio_grau():
    c = _por_nome("temperatura_negativa_meio_grau")
    d = json.loads(montar(seq=c["seq"], uptime_ms=c["uptime_ms"], temp_cc=c["temp_cc"],
                          rssi_dbm=c["rssi_dbm"], botao=c["botao"]))
    assert d["temp_c"] == c["esperado"]["temp_c"]
    assert d["botao"] is c["esperado"]["botao"]


def test_parse_e_o_inverso_de_montar():
    c = _por_nome("parse_inverso")
    linha = montar(seq=c["seq"], uptime_ms=c["uptime_ms"], temp_cc=c["temp_cc"],
                   rssi_dbm=c["rssi_dbm"], botao=c["botao"])
    assert parse(linha) == c["esperado"]


def test_parse_rejeita_linha_invalida():
    assert parse("nao e json\n") is None
    assert parse('{"seq": 1}\n') is None          # faltam campos


def test_parse_rejeita_campo_com_tipo_errado():
    # todos os campos presentes, mas "seq" veio como string em vez de int
    linha = '{"seq":"7","uptime_ms":1234,"temp_c":25.37,"rssi_dbm":-52,"botao":false}\n'
    assert parse(linha) is None
    # "botao" como 0/1 em vez de bool
    linha2 = '{"seq":7,"uptime_ms":1234,"temp_c":25.37,"rssi_dbm":-52,"botao":0}\n'
    assert parse(linha2) is None


@pytest.mark.parametrize("caso", CASOS, ids=[c["nome"] for c in CASOS])
def test_vetores_completos_montar_e_parse(caso):
    linha = montar(seq=caso["seq"], uptime_ms=caso["uptime_ms"], temp_cc=caso["temp_cc"],
                   rssi_dbm=caso["rssi_dbm"], botao=caso["botao"])
    assert json.loads(linha) == caso["esperado"]
    assert parse(linha) == caso["esperado"]
