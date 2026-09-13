#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assinante MQTT do lab 10 (wifi_http_mqtt) -- codigo do curso (nrf-manaus-2).

Roda no PC, ao lado de um broker MQTT (mosquitto, ver ../README.md). Assina o
topico de telemetria do firmware, imprime cada amostra valida e publica
comandos de LED no topico "<topico>/comando" pelo teclado. Mesmo formato de
payload do lab 9 (payload_ref.py) -- so o transporte muda.

Uso:
    python wifi_mqtt_sub.py --host localhost --porta 1883 --topico nrf-manaus/telemetria

Teclas depois de subir: 'l' liga o LED1 (led1 no firmware), 'd' desliga,
'q' sai.
"""
from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

# payload_ref.py mora no lab 9 (tools/) -- mesmo raciocinio de
# wifi_http_server.py: o lab 10 nao tem firmware proprio nem formato de
# payload proprio.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "09_wifi_tcp" / "tools"))
import payload_ref  # noqa: E402

TOPICO_PADRAO = "nrf-manaus/telemetria"


class AssinanteMQTT:
    """Assinante MQTT do lab 10.

    Publica a telemetria assinando `topico` com QoS 0 -- mesmo QoS que o
    firmware usa para publicar (src/transporte.c), best-effort dos dois
    lados. Comandos saem em "<topico>/comando", tambem QoS 0: e o firmware
    quem assina esse topico e reage (thread_recepcao(), em src/main.c).
    """

    def __init__(self, host: str, porta: int, topico: str, ao_receber=None,
                 client_id: str = ""):
        self._ao_receber = ao_receber if ao_receber is not None else (lambda amostra: None)
        self.topico = topico
        self.topico_comando = f"{topico}/comando"
        self._host = host
        self._porta = porta
        self._conectado = threading.Event()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        del userdata, connect_flags, properties
        if reason_code == 0:
            client.subscribe(self.topico, qos=0)
            self._conectado.set()

    def _on_message(self, client, userdata, message):
        del client, userdata
        linha = message.payload.decode("utf-8", errors="replace").strip()
        amostra = payload_ref.parse(linha)
        if amostra is None:
            # JSON invalido, campo faltando ou com tipo errado: descarta sem
            # derrubar a assinatura -- mesmo criterio do servidor TCP do
            # lab 9 para uma linha que nao passa no parser.
            return
        self._ao_receber(amostra)

    def conectar(self, timeout: float = 5.0) -> bool:
        """Conecta e espera o CONNACK (via on_connect) por ate `timeout`
        segundos. Devolve False sem levantar excecao tanto se o broker
        recusar a conexao na hora (porta fechada, host errado -- o
        connect() do paho-mqtt e sincrono e levanta OSError nesse caso)
        quanto se ele nao responder a tempo -- quem chama decide o que fazer
        (main() aborta com uma mensagem clara em vez de um traceback cru).
        """
        try:
            self._client.connect(self._host, self._porta, keepalive=30)
        except OSError:
            return False
        self._client.loop_start()
        return self._conectado.wait(timeout)

    def publicar_comando(self, texto: str) -> None:
        self._client.publish(self.topico_comando, payload=texto, qos=0)

    def fechar(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()


def _formatar_amostra(amostra: dict) -> str:
    marca = " BOTAO" if amostra["botao"] else ""
    return (
        f"seq={amostra['seq']:>6}  uptime_ms={amostra['uptime_ms']:>8}  "
        f"temp_c={amostra['temp_c']:>6.2f}  rssi_dbm={amostra['rssi_dbm']:>4}{marca}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Assinante MQTT do lab 10 (wifi_http_mqtt)")
    parser.add_argument("--host", default="localhost", help="endereco do broker (padrao localhost)")
    parser.add_argument("--porta", type=int, default=1883, help="porta do broker (padrao 1883)")
    parser.add_argument("--topico", default=TOPICO_PADRAO,
                         help=f"topico de telemetria (padrao {TOPICO_PADRAO})")
    args = parser.parse_args()

    assinante = AssinanteMQTT(
        host=args.host,
        porta=args.porta,
        topico=args.topico,
        ao_receber=lambda amostra: print(_formatar_amostra(amostra)),
    )

    if not assinante.conectar():
        print(f"Falha ao conectar no broker {args.host}:{args.porta} -- "
              "confira se o mosquitto esta rodando (ver ../README.md)",
              file=sys.stderr)
        sys.exit(1)

    print(f"Assinando '{args.topico}' em {args.host}:{args.porta}. "
          f"Comandos em '{assinante.topico_comando}'. Teclas: l liga o LED1, d apaga, q sai.")

    try:
        while True:
            tecla = input().strip().lower()
            if tecla == "l":
                assinante.publicar_comando("LED 1")
            elif tecla == "d":
                assinante.publicar_comando("LED 0")
            elif tecla == "q":
                break
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        assinante.fechar()


if __name__ == "__main__":
    main()
