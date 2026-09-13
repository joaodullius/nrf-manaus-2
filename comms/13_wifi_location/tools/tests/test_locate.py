# -*- coding: utf-8 -*-
"""Testes de wifi_locate.py -- sem hardware, sem chamar a API de verdade
(localizacao e servico cobrado: os testes automaticos usam resposta gravada).

Os BSSIDs de exemplo (00:00:5e:00:53:xx) vem do bloco reservado pela RFC 7042
para documentacao e exemplos -- nunca corresponde a um ponto de acesso real,
o que importa aqui porque BSSID e exatamente o dado que este lab usa para
localizar um ponto fisico.
"""
import socket

import pytest

import wifi_locate
from wifi_locate import montar_requisicao, parse_scan, resolver


# --- parse_scan -------------------------------------------------------------

def test_parse_scan_le_a_linha_do_firmware():
    linha = 'AP,00:00:5e:00:53:01,-49,5180,rede-exemplo\n'
    assert parse_scan(linha) == {"macAddress": "00:00:5e:00:53:01",
                                 "signalStrength": -49,
                                 "frequency": 5180,
                                 "ssid": "rede-exemplo"}


def test_parse_scan_rejeita_outras_linhas():
    assert parse_scan("qualquer coisa\n") is None
    assert parse_scan("AP,so,dois\n") is None


def test_parse_scan_rejeita_mac_localmente_administrado():
    # Bit 0x02 do primeiro octeto ligado: endereco aleatorio (privacidade do
    # cliente), nao um BSSID de AP real -- o nRF Cloud rejeita esse caso, e
    # nao ha por que gastar a chamada paga so para descobrir isso.
    linha = 'AP,02:00:00:00:00:01,-40,2412,rede-qualquer\n'
    assert parse_scan(linha) is None


# --- montar_requisicao -------------------------------------------------------

def test_requisicao_tem_o_formato_do_nrf_cloud():
    aps = [{"macAddress": "00:00:5e:00:53:01", "signalStrength": -49,
            "frequency": 5180, "ssid": "a"},
           {"macAddress": "00:00:5e:00:53:02", "signalStrength": -60,
            "frequency": 2412, "ssid": "b"}]
    corpo = montar_requisicao(aps)
    assert list(corpo.keys()) == ["accessPoints"]
    assert corpo["accessPoints"][0]["macAddress"] == "00:00:5e:00:53:01"
    assert corpo["accessPoints"][0]["signalStrength"] == -49
    # So macAddress/signalStrength vao no corpo -- e o que a API aceita;
    # frequency/ssid sao so para a lista impressa no PC.
    assert set(corpo["accessPoints"][0].keys()) == {"macAddress", "signalStrength"}


def test_requisicao_exige_pelo_menos_dois_aps():
    with pytest.raises(ValueError, match="dois"):
        montar_requisicao([{"macAddress": "00:00:5e:00:53:01", "signalStrength": -49}])


def test_requisicao_rejeita_lista_vazia():
    with pytest.raises(ValueError, match="dois"):
        montar_requisicao([])


# --- resolver (requests.post monkeypatchado -- nunca chama a API de verdade) -

class _RespostaFalsa:
    def __init__(self, status_code, corpo_json=None, texto=""):
        self.status_code = status_code
        self._corpo_json = corpo_json
        self.text = texto if texto else str(corpo_json)

    def json(self):
        if self._corpo_json is None:
            raise ValueError("corpo nao e JSON")
        return self._corpo_json


def _aps_validos():
    return [{"macAddress": "00:00:5e:00:53:01", "signalStrength": -49},
            {"macAddress": "00:00:5e:00:53:02", "signalStrength": -60}]


def test_resolver_devolve_lat_lon_incerteza(monkeypatch):
    capturado = {}

    def post_falso(url, headers=None, json=None, timeout=None):
        capturado["url"] = url
        capturado["headers"] = headers
        capturado["json"] = json
        return _RespostaFalsa(200, {"lat": -30.0290706, "lon": -51.2124998,
                                     "uncertainty": 14.113})

    monkeypatch.setattr(wifi_locate.requests, "post", post_falso)

    lat, lon, incerteza = resolver(_aps_validos(), "org-x", "proj-y", "oat_teste")

    assert (lat, lon, incerteza) == (-30.0290706, -51.2124998, 14.113)
    assert "org-x" in capturado["url"] and "proj-y" in capturado["url"]
    assert capturado["headers"]["Authorization"] == "Bearer oat_teste"
    assert "x-nrfcloud-tenantid" in capturado["headers"]


def test_resolver_levanta_erro_em_http_nao_200(monkeypatch):
    def post_falso(url, headers=None, json=None, timeout=None):
        return _RespostaFalsa(401, texto='{"message":"Auth token is malformed"}')

    monkeypatch.setattr(wifi_locate.requests, "post", post_falso)

    with pytest.raises(RuntimeError, match="401"):
        resolver(_aps_validos(), "org-x", "proj-y", "token-invalido")


def test_resolver_levanta_erro_em_resposta_malformada(monkeypatch):
    def post_falso(url, headers=None, json=None, timeout=None):
        # 200, mas sem lat/lon -- formato inesperado.
        return _RespostaFalsa(200, {"algo": "diferente"})

    monkeypatch.setattr(wifi_locate.requests, "post", post_falso)

    with pytest.raises(RuntimeError, match="lat"):
        resolver(_aps_validos(), "org-x", "proj-y", "token-qualquer")


def test_resolver_exige_pelo_menos_dois_aps_antes_de_chamar_a_api(monkeypatch):
    chamou = {"post": False}

    def post_falso(*args, **kwargs):
        chamou["post"] = True
        return _RespostaFalsa(200, {"lat": 0, "lon": 0})

    monkeypatch.setattr(wifi_locate.requests, "post", post_falso)

    with pytest.raises(ValueError, match="dois"):
        resolver([{"macAddress": "00:00:5e:00:53:01", "signalStrength": -49}],
                 "org-x", "proj-y", "token-qualquer")

    assert chamou["post"] is False, "nao pode chamar a API (cobrada) sem dois APs"


# --- protocolo TCP do scan (kit -> PC) ---------------------------------------

def test_receber_scan_junta_linhas_e_para_no_fim():
    servidor, cliente = socket.socketpair()
    try:
        cliente.sendall(
            b"AP,00:00:5e:00:53:01,-49,5180,rede-exemplo\n"
            b"AP,00:00:5e:00:53:02,-60,2412,outra-rede\n"
            b"linha invalida sem o prefixo AP\n"
            b"AP,02:00:00:00:00:01,-40,2412,mac-local\n"
            b"FIM\n"
        )
        cliente.close()
        aps = wifi_locate._receber_scan(servidor)
    finally:
        servidor.close()

    # A linha invalida e o MAC localmente administrado sao descartados;
    # sobram so os dois APs validos.
    assert [ap["macAddress"] for ap in aps] == ["00:00:5e:00:53:01", "00:00:5e:00:53:02"]
