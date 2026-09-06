#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor do lab 9 (wifi_tcp) -- codigo do curso (nrf-manaus-2).

Roda no PC do instrutor/aluno. Aceita uma conexao TCP da DK, le uma linha JSON
por amostra (formato em payload_ref.py), imprime cada uma e manda comandos de
LED de volta pelo teclado.

Uso:
    python wifi_server.py --porta 9000

Teclas depois de subir: 'l' liga o LED 2 (led1 no firmware), 'd' desliga,
'q' sai.
"""
from __future__ import annotations

import argparse
import socket
import threading

import payload_ref

TAMANHO_LEITURA = 4096


class Servidor:
    """Um servidor TCP de uma conexao por vez.

    porta=0 deixa o sistema operacional escolher uma porta livre; porta_real
    guarda a porta efetiva depois do bind, o que torna os testes
    deterministicos sem depender de uma porta fixa disponivel na maquina.
    """

    def __init__(self, porta: int, ao_receber=None):
        self._ao_receber = ao_receber if ao_receber is not None else (lambda amostra: None)
        self._cliente_lock = threading.Lock()
        self._cliente: socket.socket | None = None

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", porta))
        self._sock.listen(1)
        self.porta_real = self._sock.getsockname()[1]

    def servir_uma_conexao(self) -> None:
        """Aceita um cliente e serve ate ele desconectar (ou o socket do
        servidor ser fechado, o que derruba o accept() com OSError).

        Linhas incompletas ficam no buffer ate chegar o '\\n'; um pacote com
        mais de uma linha processa todas antes de voltar a esperar dados
        novos. Linhas que payload_ref.parse() rejeita (JSON invalido, campo
        faltando ou com tipo errado) sao descartadas sem derrubar a conexao
        -- o resto do fluxo de amostras continua valendo.
        """
        conexao, _endereco = self._sock.accept()
        with self._cliente_lock:
            self._cliente = conexao

        buffer = b""
        try:
            while True:
                dados = conexao.recv(TAMANHO_LEITURA)
                if not dados:
                    # O outro lado fechou a conexao (recv devolveu vazio).
                    break
                buffer += dados
                while b"\n" in buffer:
                    linha, buffer = buffer.split(b"\n", 1)
                    amostra = payload_ref.parse(linha.decode("utf-8", errors="replace"))
                    if amostra is not None:
                        self._ao_receber(amostra)
        finally:
            with self._cliente_lock:
                if self._cliente is conexao:
                    self._cliente = None
            conexao.close()

    def enviar_comando(self, texto: str) -> None:
        """Manda `texto + '\\n'` para o cliente conectado. Sem cliente
        conectado no momento, e um no-op silencioso -- teclar 'l' entre uma
        queda e a reconexao do kit nao deve derrubar o servidor.
        """
        with self._cliente_lock:
            cliente = self._cliente
        if cliente is None:
            return
        try:
            cliente.sendall((texto + "\n").encode("utf-8"))
        except OSError:
            # Cliente caiu entre o momento em que lemos self._cliente e o
            # envio; a proxima leitura de servir_uma_conexao ja vai detectar
            # a queda e limpar self._cliente.
            pass

    def fechar(self) -> None:
        self._sock.close()


def _formatar_amostra(amostra: dict) -> str:
    marca = " BOTAO" if amostra["botao"] else ""
    return (
        f"seq={amostra['seq']:>6}  uptime_ms={amostra['uptime_ms']:>8}  "
        f"temp_c={amostra['temp_c']:>6.2f}  rssi_dbm={amostra['rssi_dbm']:>4}{marca}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor do lab 9 (wifi_tcp)")
    parser.add_argument("--porta", type=int, default=9000, help="porta TCP a escutar (padrao 9000)")
    args = parser.parse_args()

    srv = Servidor(porta=args.porta, ao_receber=lambda amostra: print(_formatar_amostra(amostra)))
    print(f"Ouvindo na porta {srv.porta_real}. Teclas: l = LED 1, d = LED 0, q = sair.")

    def aceitar_conexoes():
        while True:
            try:
                srv.servir_uma_conexao()
            except OSError:
                # self._sock foi fechado (saida por 'q'): encerra a thread.
                return
            print("Conexao encerrada; aguardando nova conexao...")

    thread_aceitacao = threading.Thread(target=aceitar_conexoes, daemon=True)
    thread_aceitacao.start()

    try:
        while True:
            tecla = input().strip().lower()
            if tecla == "l":
                srv.enviar_comando("LED 1")
            elif tecla == "d":
                srv.enviar_comando("LED 0")
            elif tecla == "q":
                break
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        srv.fechar()


if __name__ == "__main__":
    main()
