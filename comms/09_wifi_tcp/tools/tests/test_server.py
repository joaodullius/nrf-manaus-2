# -*- coding: utf-8 -*-
"""Testes de wifi_server.py -- servidor testavel sem hardware: porta=0 deixa
o SO escolher uma porta livre, porta_real devolve a porta efetiva, e um
socket local no proprio processo faz o papel do kit.

Cobre o caminho feliz e os casos ruins que importam para esse servidor:
linha partida em dois pedacos, duas linhas no mesmo pacote, linha malformada,
cliente que desconecta de forma limpa no meio, e -- o caso realista de uma
queda de associacao Wi-Fi -- cliente derrubado com RST abrupto, sem FIN.
"""
import socket
import struct
import threading
import time

from wifi_server import Servidor


def _subir_servidor(ao_receber):
    srv = Servidor(porta=0, ao_receber=ao_receber)
    t = threading.Thread(target=srv.servir_uma_conexao, daemon=True)
    t.start()
    time.sleep(0.1)  # da tempo do accept() estar pronto antes do connect
    return srv, t


def _subir_servidor_aceitando_continuamente(ao_receber):
    srv = Servidor(porta=0, ao_receber=ao_receber)
    t = threading.Thread(target=srv.aceitar_para_sempre, daemon=True)
    t.start()
    time.sleep(0.1)  # da tempo do accept() estar pronto antes do connect
    return srv, t


def _derrubar_com_rst(sock: socket.socket) -> None:
    """Fecha o socket mandando RST em vez de FIN (SO_LINGER com tempo zero).
    Reproduz sem hardware o caso real de uma queda de associacao Wi-Fi: a
    conexao morre sem o fechamento limpo que socket.close() normal manda."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    sock.close()


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


def test_continua_aceitando_conexoes_depois_de_um_rst_abrupto():
    """Uma queda de associacao Wi-Fi nao manda FIN -- se chegar algum aviso
    de rede, e RST. Antes da correcao, o laco que aceita conexoes chamava
    servir_uma_conexao() de forma sequencial, e o erro de leitura do RST
    (nao capturado) subia e derrubava esse laco: nenhuma conexao nova era
    aceita depois disso. Este teste prova que uma conexao aceita depois do
    RST ainda e atendida normalmente."""
    recebidas = []
    srv, t = _subir_servidor_aceitando_continuamente(recebidas.append)

    s1 = socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2)
    s1.sendall(b'{"seq":1,"uptime_ms":1,"temp_c":1.0,"rssi_dbm":-1,"botao":false}\n')
    time.sleep(0.1)
    _derrubar_com_rst(s1)
    time.sleep(0.2)

    with socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2) as s2:
        s2.sendall(b'{"seq":2,"uptime_ms":2,"temp_c":2.0,"rssi_dbm":-2,"botao":false}\n')
        time.sleep(0.2)

    srv.fechar()
    t.join(timeout=2)
    assert [a["seq"] for a in recebidas] == [1, 2]


def test_segunda_conexao_e_atendida_com_a_primeira_ainda_nao_coletada():
    """A conexao derrubada com RST pode ainda nao ter sido limpa (o finally
    de _servir_conexao_aceita ainda nao rodou) quando a proxima ja chega --
    e exatamente essa janela que o firmware pode encontrar numa reconexao
    rapida depois de uma queda. O aceite (aceitar_para_sempre) nao pode
    depender de a conexao anterior ja ter sido coletada."""
    recebidas = []
    srv, t = _subir_servidor_aceitando_continuamente(recebidas.append)

    s1 = socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2)
    _derrubar_com_rst(s1)
    # Sem espera aqui de proposito: a segunda conexao entra logo em seguida,
    # antes de qualquer garantia de que o servidor ja processou a queda da
    # primeira.
    with socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2) as s2:
        s2.sendall(b'{"seq":9,"uptime_ms":9,"temp_c":9.0,"rssi_dbm":-9,"botao":false}\n')
        time.sleep(0.2)

    srv.fechar()
    t.join(timeout=2)
    assert [a["seq"] for a in recebidas] == [9]


def test_conexao_silenciosa_e_derrubada_apos_o_tempo_limite_de_leitura():
    """Uma conexao que nunca manda nada -- nem FIN, nem RST -- tem que ser
    dada como morta depois de tempo_limite_leitura_s, e nao ficar presa para
    sempre. O padrao de producao (TEMPO_LIMITE_LEITURA_S, acima do maior
    CONFIG_LAB_INTERVALO_MS do Kconfig) e grande demais para testar de
    verdade num teste rapido -- por isso o limite entra como parametro, e o
    teste usa um valor pequeno em vez do padrao."""
    recebidas = []
    srv = Servidor(porta=0, ao_receber=recebidas.append, tempo_limite_leitura_s=0.2)
    t = threading.Thread(target=srv.servir_uma_conexao, daemon=True)
    t.start()
    time.sleep(0.1)

    with socket.create_connection(("127.0.0.1", srv.porta_real), timeout=2) as s:
        # nao manda nada -- fica em silencio ate estourar o tempo limite
        t.join(timeout=1)
        assert not t.is_alive()

    assert recebidas == []
