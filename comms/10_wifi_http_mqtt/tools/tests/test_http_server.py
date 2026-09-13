"""Testes de wifi_http_server.py -- sobem um ServidorHTTP de verdade (sem
hardware) e conversam com ele por HTTP, cobrindo o caminho feliz e os casos
ruins: JSON invalido, campo faltando, rota desconhecida, e o consumo
(uma vez so) do comando pendente.
"""
import http.client
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wifi_http_server import ServidorHTTP  # noqa: E402

LINHA_VALIDA = '{"seq":7,"uptime_ms":1234,"temp_c":25.37,"rssi_dbm":-52,"botao":false}'


@pytest.fixture
def servidor():
    recebidas = []
    srv = ServidorHTTP(porta=0, ao_receber=recebidas.append)
    thread = threading.Thread(target=srv.servir_para_sempre, daemon=True)
    thread.start()
    try:
        yield srv, recebidas
    finally:
        srv.fechar()


def _conexao(srv):
    return http.client.HTTPConnection("127.0.0.1", srv.porta_real, timeout=5)


def test_post_telemetria_valida_chama_ao_receber(servidor):
    srv, recebidas = servidor
    conexao = _conexao(srv)

    conexao.request("POST", "/telemetria", body=LINHA_VALIDA)
    resposta = conexao.getresponse()
    resposta.read()

    assert resposta.status == 200
    assert recebidas == [
        {"seq": 7, "uptime_ms": 1234, "temp_c": 25.37, "rssi_dbm": -52, "botao": False}
    ]


def test_post_telemetria_json_invalido_nao_chama_ao_receber(servidor):
    srv, recebidas = servidor
    conexao = _conexao(srv)

    conexao.request("POST", "/telemetria", body="isto nao e json")
    resposta = conexao.getresponse()
    resposta.read()

    assert resposta.status == 400
    assert recebidas == []


def test_post_telemetria_campo_faltando_nao_chama_ao_receber(servidor):
    srv, recebidas = servidor
    conexao = _conexao(srv)

    # Falta "botao" -- mesmo criterio de rejeicao de payload_ref.parse() que
    # o servidor TCP do lab 9 usa.
    conexao.request(
        "POST", "/telemetria",
        body='{"seq":1,"uptime_ms":1,"temp_c":1.0,"rssi_dbm":-1}',
    )
    resposta = conexao.getresponse()
    resposta.read()

    assert resposta.status == 400
    assert recebidas == []


def test_get_comando_sem_nada_pendente_devolve_204(servidor):
    srv, _recebidas = servidor
    conexao = _conexao(srv)

    conexao.request("GET", "/comando")
    resposta = conexao.getresponse()
    corpo = resposta.read()

    assert resposta.status == 204
    assert corpo == b""


def test_get_comando_consome_uma_vez_so(servidor):
    srv, _recebidas = servidor
    srv.enviar_comando("LED 1")

    primeira = _conexao(srv)
    primeira.request("GET", "/comando")
    resposta1 = primeira.getresponse()
    corpo1 = resposta1.read()

    segunda = _conexao(srv)
    segunda.request("GET", "/comando")
    resposta2 = segunda.getresponse()
    corpo2 = resposta2.read()

    assert (resposta1.status, corpo1) == (200, b"LED 1")
    # O mesmo comando nao aparece de novo: enviar_comando() so vale para o
    # proximo GET, nao para todos os seguintes.
    assert (resposta2.status, corpo2) == (204, b"")


def test_rota_desconhecida_devolve_404(servidor):
    srv, _recebidas = servidor

    conexao_get = _conexao(srv)
    conexao_get.request("GET", "/rota-que-nao-existe")
    resposta_get = conexao_get.getresponse()
    resposta_get.read()

    conexao_post = _conexao(srv)
    conexao_post.request("POST", "/rota-que-nao-existe", body=LINHA_VALIDA)
    resposta_post = conexao_post.getresponse()
    resposta_post.read()

    assert resposta_get.status == 404
    assert resposta_post.status == 404
