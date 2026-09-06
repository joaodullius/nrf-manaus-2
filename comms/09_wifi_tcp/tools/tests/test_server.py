# -*- coding: utf-8 -*-
"""Testes de wifi_server.py -- servidor testavel sem hardware: porta=0 deixa
o SO escolher uma porta livre, porta_real devolve a porta efetiva, e um
socket local no proprio processo faz o papel do kit.

Cobre o caminho feliz e os casos ruins que importam para esse servidor:
linha partida em dois pedacos, duas linhas no mesmo pacote, linha malformada,
e cliente que desconecta no meio (a queda de Wi-Fi que o firmware trata com
reconexao do lado dele).
"""
import socket
import threading
import time

from wifi_server import Servidor


def _subir_servidor(ao_receber):
    srv = Servidor(porta=0, ao_receber=ao_receber)
    t = threading.Thread(target=srv.servir_uma_conexao, daemon=True)
    t.start()
    time.sleep(0.1)  # da tempo do accept() estar pronto antes do connect
    return srv, t


def test_recebe_amostras_e_devolve_comando_de_led():
    recebidas = []
    srv, t = _subir_servidor(recebidas.append)

    with socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2) as s:
        s.sendall(b'{"seq":1,"uptime_ms":10,"temp_c":25.0,"rssi_dbm":-40,"botao":false}\n')
        s.sendall(b'{"seq":2,"uptime_ms":20,"temp_c":25.1,"rssi_dbm":-41,"botao":true}\n')
        time.sleep(0.2)
        srv.enviar_comando("LED 1")
        assert s.recv(16) == b"LED 1\n"

    t.join(timeout=2)
    assert [a["seq"] for a in recebidas] == [1, 2]
    assert recebidas[1]["botao"] is True


def test_ignora_linha_malformada_sem_derrubar_a_conexao():
    recebidas = []
    srv, t = _subir_servidor(recebidas.append)

    with socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2) as s:
        s.sendall(b"lixo\n")
        s.sendall(b'{"seq": "nove"}\n')  # JSON valido, mas campos errados/faltando
        s.sendall(b'{"seq":9,"uptime_ms":1,"temp_c":1.0,"rssi_dbm":-1,"botao":false}\n')
        time.sleep(0.2)

    t.join(timeout=2)
    assert [a["seq"] for a in recebidas] == [9]


def test_reconstroi_linha_que_chega_partida_em_dois_pedacos():
    recebidas = []
    srv, t = _subir_servidor(recebidas.append)

    linha = b'{"seq":5,"uptime_ms":50,"temp_c":20.0,"rssi_dbm":-30,"botao":false}\n'
    metade = len(linha) // 2
    with socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2) as s:
        s.sendall(linha[:metade])
        time.sleep(0.1)  # garante que os dois sendall virem recv() separados
        s.sendall(linha[metade:])
        time.sleep(0.2)

    t.join(timeout=2)
    assert [a["seq"] for a in recebidas] == [5]


def test_duas_amostras_no_mesmo_pacote():
    recebidas = []
    srv, t = _subir_servidor(recebidas.append)

    pacote = (
        b'{"seq":1,"uptime_ms":1,"temp_c":1.0,"rssi_dbm":-1,"botao":false}\n'
        b'{"seq":2,"uptime_ms":2,"temp_c":2.0,"rssi_dbm":-2,"botao":true}\n'
    )
    with socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2) as s:
        s.sendall(pacote)
        time.sleep(0.2)

    t.join(timeout=2)
    assert [a["seq"] for a in recebidas] == [1, 2]


def test_cliente_desconecta_no_meio_nao_derruba_o_servidor():
    recebidas = []
    srv, t = _subir_servidor(recebidas.append)

    s = socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2)
    s.sendall(b'{"seq":1,"uptime_ms":1,"temp_c":1.0,"rssi_dbm":-1,"botao":false}\n')
    time.sleep(0.1)
    s.close()  # fecha sem avisar, como uma queda de Wi-Fi do kit

    t.join(timeout=2)
    assert not t.is_alive()
    assert [a["seq"] for a in recebidas] == [1]

    # depois da queda nao ha cliente conectado; enviar comando tem que ser
    # um no-op, nunca levantar excecao (o instrutor pode teclar 'l' nesse
    # meio-tempo, antes do kit reconectar).
    srv.enviar_comando("LED 0")
