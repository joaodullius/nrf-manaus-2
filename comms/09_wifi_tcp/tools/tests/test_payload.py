# -*- coding: utf-8 -*-
import json
import pytest
from payload_ref import montar, parse


def test_monta_linha_json_com_todos_os_campos():
    linha = montar(seq=7, uptime_ms=1234, temp_cc=2537, rssi_dbm=-52, botao=False)
    assert linha.endswith("\n")
    d = json.loads(linha)
    assert d == {"seq": 7, "uptime_ms": 1234, "temp_c": 25.37,
                 "rssi_dbm": -52, "botao": False}


def test_temperatura_negativa_e_meio_grau():
    d = json.loads(montar(seq=1, uptime_ms=0, temp_cc=-450, rssi_dbm=-70, botao=True))
    assert d["temp_c"] == -4.5
    assert d["botao"] is True


def test_parse_e_o_inverso_de_montar():
    linha = montar(seq=99, uptime_ms=5, temp_cc=100, rssi_dbm=-1, botao=True)
    assert parse(linha) == {"seq": 99, "uptime_ms": 5, "temp_c": 1.0,
                            "rssi_dbm": -1, "botao": True}


def test_parse_rejeita_linha_invalida():
    assert parse("nao e json\n") is None
    assert parse('{"seq": 1}\n') is None          # faltam campos
