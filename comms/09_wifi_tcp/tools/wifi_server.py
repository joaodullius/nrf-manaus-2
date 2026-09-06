#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor do lab 9 (wifi_tcp) -- codigo do curso (nrf-manaus-2).

Roda no PC do instrutor/aluno. Aceita conexoes TCP da DK, le uma linha JSON
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

# Com um firmware que reconecta sozinho depois de uma queda de Wi-Fi, uma
# conexao pendente na fila de aceite e situacao normal, nao excepcional: a
# conexao antiga (morta, sem fechamento limpo) pode ainda nao ter sido limpa
# quando a reconexao chega. Backlog folgado para essa fila nunca ser o
# gargalo.
BACKLOG = 8

# Tempo sem nenhum byte de uma conexao antes de considera-la morta e fechar.
# O valor existe para o caso de uma queda de associacao Wi-Fi que nunca manda
# FIN nem RST -- sem um limite de tempo, recv() ficaria bloqueado nessa
# conexao para sempre. Tem que ficar acima do maior CONFIG_LAB_INTERVALO_MS
# que o Kconfig do firmware permite (range 200..60000, ou seja ate 60 s de
# intervalo entre amostras) -- 90 s da folga confortavel sobre esse pior
# caso legitimo. Quem mudar um dos dois numeros tem que olhar o outro.
TEMPO_LIMITE_LEITURA_S = 90.0


class Servidor:
    """Servidor TCP do lab 9.

    porta=0 deixa o sistema operacional escolher uma porta livre; porta_real
    guarda a porta efetiva depois do bind, o que torna os testes
    deterministicos sem depender de uma porta fixa disponivel na maquina.

    Aceita mais de uma conexao ao mesmo tempo por design, nao por acidente:
    o firmware reconecta sozinho depois de uma queda de Wi-Fi, e a conexao
    antiga (morta, sem fechamento limpo) pode continuar existindo por um
    tempo depois que a nova ja chegou. O servidor precisa aceitar essa
    conexao nova imediatamente -- nunca esperar a antiga terminar primeiro,
    porque ela pode nunca terminar sozinha. enviar_comando() sempre manda
    para a conexao aceita mais recentemente.
    """

    def __init__(self, porta: int, ao_receber=None, tempo_limite_leitura_s: float = TEMPO_LIMITE_LEITURA_S):
        self._ao_receber = ao_receber if ao_receber is not None else (lambda amostra: None)
        self._tempo_limite_leitura_s = tempo_limite_leitura_s
        self._cliente_lock = threading.Lock()
        self._cliente: socket.socket | None = None

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", porta))
        self._sock.listen(BACKLOG)
        self.porta_real = self._sock.getsockname()[1]

    def servir_uma_conexao(self) -> None:
        """Aceita um cliente e serve ate ele desconectar, dar erro de
        leitura (por exemplo um RST abrupto) ou o socket do servidor ser
        fechado, o que derruba o accept() com OSError para quem chamou.

        Trata uma unica conexao por chamada. Quem quiser aceitar
        continuamente (main() e aceitar_para_sempre(), abaixo) chama isso
        (ou o equivalente) repetidas vezes, uma conexao por thread -- assim
        uma conexao lenta ou morta nunca bloqueia o aceite da proxima.
        """
        conexao, _endereco = self._sock.accept()
        self._servir_conexao_aceita(conexao)

    def aceitar_para_sempre(self) -> None:
        """Aceita conexoes continuamente, uma thread por conexao aceita, ate
        o socket do servidor ser fechado (fechar()).

        O laco aqui NUNCA serve uma conexao -- so aceita e delega para uma
        thread nova, e volta a aceitar imediatamente. E essa separacao que
        garante que uma conexao antiga travada (sem FIN nem RST, o caso real
        de uma queda de associacao Wi-Fi) nao impede o servidor de aceitar a
        reconexao do firmware: antes dessa separacao, servir uma conexao ate
        o fim e so depois aceitar a proxima deixava o servidor preso na
        antiga, com a nova parada na fila do listen() sem ser atendida. Um
        erro de leitura numa conexao (por exemplo um RST abrupto) e tratado
        dentro de _servir_conexao_aceita e nunca chega a este laco -- erro
        de leitura de uma conexao e problema so dela, nunca do aceite.
        """
        while True:
            try:
                conexao, _endereco = self._sock.accept()
            except OSError:
                # self._sock foi fechado (fechar()): encerra o laco.
                return
            threading.Thread(
                target=self._servir_conexao_aceita, args=(conexao,), daemon=True
            ).start()

    def _servir_conexao_aceita(self, conexao: socket.socket) -> None:
        with self._cliente_lock:
            self._cliente = conexao
        try:
            conexao.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except OSError:
            pass
        conexao.settimeout(self._tempo_limite_leitura_s)

        buffer = b""
        try:
            while True:
                try:
                    dados = conexao.recv(TAMANHO_LEITURA)
                except OSError:
                    # Erro so desta conexao: RST abrupto (ConnectionResetError)
                    # ou tempo limite de leitura (TimeoutError) -- as duas sao
                    # subclasses de OSError. Nunca deve encostar em quem
                    # aceita conexoes novas (aceitar_para_sempre ou o
                    # chamador de servir_uma_conexao).
                    return
                if not dados:
                    # O outro lado fechou a conexao de forma limpa (FIN).
                    return
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
        """Manda `texto + '\\n'` para a conexao aceita mais recentemente.
        Sem cliente conectado no momento, e um no-op silencioso -- teclar
        'l' entre uma queda e a reconexao do kit nao deve derrubar o
        servidor.
        """
        with self._cliente_lock:
            cliente = self._cliente
        if cliente is None:
            return
        try:
            cliente.sendall((texto + "\n").encode("utf-8"))
        except OSError:
            # Cliente caiu entre o momento em que lemos self._cliente e o
            # envio; a proxima leitura dessa conexao ja vai detectar a queda
            # e limpar self._cliente.
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
    parser.add_argument(
        "--tempo-limite-leitura",
        type=float,
        default=TEMPO_LIMITE_LEITURA_S,
        help=(
            "segundos sem dados de uma conexao antes de considera-la morta "
            f"(padrao {TEMPO_LIMITE_LEITURA_S:g}). Tem que ficar acima do "
            "CONFIG_LAB_INTERVALO_MS configurado no firmware -- se aumentar o "
            "intervalo de telemetria alem do padrao do lab, aumente este valor "
            "junto"
        ),
    )
    args = parser.parse_args()

    srv = Servidor(
        porta=args.porta,
        ao_receber=lambda amostra: print(_formatar_amostra(amostra)),
        tempo_limite_leitura_s=args.tempo_limite_leitura,
    )
    print(f"Ouvindo na porta {srv.porta_real}. Teclas: l liga o LED 2, d apaga, q sai.")

    threading.Thread(target=srv.aceitar_para_sempre, daemon=True).start()

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
