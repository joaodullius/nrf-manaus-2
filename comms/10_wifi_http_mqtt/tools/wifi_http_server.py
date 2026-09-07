#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor HTTP do lab 10 (wifi_http_mqtt) -- codigo do curso (nrf-manaus-2).

Roda no PC. Recebe cada amostra de telemetria por `POST /telemetria` (corpo:
uma linha do formato de payload_ref.py) e entrega comandos de LED pendentes
por `GET /comando` (204 se nao houver nenhum). E o mesmo formato de payload
do lab 9 -- so o transporte muda; ver ../README.md.

Uso:
    python wifi_http_server.py --porta 8000

Teclas depois de subir: 'l' liga o LED1 (led1 no firmware), 'd' desliga,
'q' sai.
"""
from __future__ import annotations

import argparse
import http.server
import sys
import threading
from pathlib import Path

# payload_ref.py mora no lab 9 (tools/) -- o lab 10 nao tem firmware proprio
# (recompila o do lab 9 com outro transporte) nem reescreve o formato do
# payload, entao tambem nao duplica o modulo que o interpreta.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "09_wifi_tcp" / "tools"))
import payload_ref  # noqa: E402


class ServidorHTTP:
    """Servidor HTTP do lab 10.

    porta=0 deixa o sistema operacional escolher uma porta livre; porta_real
    guarda a porta efetiva depois do bind, o que torna os testes
    deterministicos sem depender de uma porta fixa disponivel na maquina.

    Ao contrario do Servidor TCP do lab 9, aqui nao ha "a conexao mais
    recente": cada requisicao HTTP e independente, entao so existe um unico
    comando pendente por vez (enviar_comando sobrescreve; GET /comando
    consome e limpa). Isso e suficiente para o roteiro deste lab (uma tecla
    por vez no servidor) e evita inventar uma fila que o firmware nunca
    pediria.
    """

    def __init__(self, porta: int, ao_receber=None):
        ao_receber_fn = ao_receber if ao_receber is not None else (lambda amostra: None)

        self._comando_lock = threading.Lock()
        self._comando_pendente: str | None = None
        servidor = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            # HTTP/1.0: fecha a conexao ao final de cada resposta. Casa com
            # o cliente do firmware (transporte.c), que tambem abre um
            # socket novo por requisicao -- nenhum dos dois lados tenta
            # manter uma conexao viva entre chamadas.
            protocol_version = "HTTP/1.0"

            def log_message(self, fmt, *args):  # noqa: A002 (assinatura da base)
                pass  # a impressao de cada amostra (main(), abaixo) ja mostra o que importa

            def do_POST(self):  # noqa: N802 (nome exigido pela classe base)
                if self.path != "/telemetria":
                    self.send_response(404)
                    self.end_headers()
                    return

                tamanho = int(self.headers.get("Content-Length", 0))
                corpo = self.rfile.read(tamanho)
                linha = corpo.decode("utf-8", errors="replace").strip()
                amostra = payload_ref.parse(linha)
                if amostra is None:
                    # JSON invalido, campo faltando ou com tipo errado --
                    # mesma rejeicao silenciosa (do lado do dado) que o
                    # servidor TCP do lab 9 faz, so que aqui reportada ao
                    # remetente via status HTTP em vez de descartada calada.
                    self.send_response(400)
                    self.end_headers()
                    return

                ao_receber_fn(amostra)
                self.send_response(200)
                self.end_headers()

            def do_GET(self):  # noqa: N802
                if self.path != "/comando":
                    self.send_response(404)
                    self.end_headers()
                    return

                with servidor._comando_lock:
                    comando = servidor._comando_pendente
                    servidor._comando_pendente = None

                if comando is None:
                    self.send_response(204)
                    self.end_headers()
                    return

                corpo = comando.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        self._httpd = http.server.ThreadingHTTPServer(("0.0.0.0", porta), _Handler)
        self.porta_real = self._httpd.server_address[1]

    def enviar_comando(self, texto: str) -> None:
        """Deixa `texto` pendente para o proximo `GET /comando` -- sobrescreve
        um comando anterior ainda nao consumido (o roteiro deste lab so
        manda um de cada vez pelo teclado; nunca ha fila a esvaziar).
        """
        with self._comando_lock:
            self._comando_pendente = texto

    def servir_para_sempre(self) -> None:
        self._httpd.serve_forever(poll_interval=0.1)

    def fechar(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _formatar_amostra(amostra: dict) -> str:
    marca = " BOTAO" if amostra["botao"] else ""
    return (
        f"seq={amostra['seq']:>6}  uptime_ms={amostra['uptime_ms']:>8}  "
        f"temp_c={amostra['temp_c']:>6.2f}  rssi_dbm={amostra['rssi_dbm']:>4}{marca}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor HTTP do lab 10 (wifi_http_mqtt)")
    parser.add_argument("--porta", type=int, default=8000, help="porta HTTP a escutar (padrao 8000)")
    args = parser.parse_args()

    srv = ServidorHTTP(porta=args.porta, ao_receber=lambda amostra: print(_formatar_amostra(amostra)))
    print(f"Ouvindo HTTP na porta {srv.porta_real}. Teclas: l liga o LED1, d apaga, q sai.")

    threading.Thread(target=srv.servir_para_sempre, daemon=True).start()

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
