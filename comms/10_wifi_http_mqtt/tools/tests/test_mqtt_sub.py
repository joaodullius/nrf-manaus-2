"""Testes de wifi_mqtt_sub.py -- sobem um mosquitto de verdade num processo a
parte (sem hardware, sem mock de MQTT) e conversam com o AssinanteMQTT por
ele, cobrindo o caminho feliz, uma mensagem invalida no meio de validas (nao
pode derrubar a assinatura) e uma falha de conexao franca.

Pulados (com mensagem clara) se o binario do mosquitto nao for encontrado --
mesmo criterio de tools/tests/test_payload_c.py do lab 9 para um compilador
de host ausente.
"""
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wifi_mqtt_sub import AssinanteMQTT  # noqa: E402

LINHA_VALIDA_1 = '{"seq":1,"uptime_ms":100,"temp_c":21.5,"rssi_dbm":-40,"botao":false}'
LINHA_VALIDA_2 = '{"seq":2,"uptime_ms":200,"temp_c":21.7,"rssi_dbm":-41,"botao":true}'
LINHA_INVALIDA = "isto nao e json"

TEMPO_ESPERA_S = 5.0


def _localizar_mosquitto() -> str | None:
    encontrado = shutil.which("mosquitto")
    if encontrado:
        return encontrado
    candidato = Path(r"C:\Program Files\mosquitto\mosquitto.exe")
    if candidato.is_file():
        return str(candidato)
    return None


def _porta_livre() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def _esperar_porta_aberta(host: str, porta: int, tempo_limite_s: float) -> bool:
    prazo = time.monotonic() + tempo_limite_s
    while time.monotonic() < prazo:
        try:
            with socket.create_connection((host, porta), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


@pytest.fixture(scope="module")
def broker():
    executavel = _localizar_mosquitto()
    if executavel is None:
        pytest.skip(
            "mosquitto nao encontrado no PATH nem em 'C:\\Program Files\\mosquitto' -- "
            "instale o mosquitto para rodar os testes de wifi_mqtt_sub.py "
            "(ver ../README.md)"
        )

    porta = _porta_livre()
    # Sem -c/config: o mosquitto sobe com o padrao de fabrica, que aceita
    # conexao anonima em localhost -- suficiente e mais simples que gerar um
    # arquivo de configuracao so para o teste.
    processo = subprocess.Popen(
        [executavel, "-p", str(porta)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if not _esperar_porta_aberta("127.0.0.1", porta, TEMPO_ESPERA_S):
            saida = processo.communicate(timeout=2)[0] if processo.poll() is not None else ""
            pytest.fail(f"mosquitto nao abriu a porta {porta} a tempo. Saida:\n{saida}")
        yield "127.0.0.1", porta
    finally:
        processo.terminate()
        try:
            processo.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.communicate(timeout=5)


def _topico_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


def _publicador(host: str, porta: int) -> mqtt.Client:
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    cliente.connect(host, porta, keepalive=10)
    cliente.loop_start()
    return cliente


def _esperar(condicao, tempo_limite_s: float = TEMPO_ESPERA_S) -> bool:
    prazo = time.monotonic() + tempo_limite_s
    while time.monotonic() < prazo:
        if condicao():
            return True
        time.sleep(0.05)
    return condicao()


def test_mensagem_valida_chega_ao_assinante(broker):
    host, porta = broker
    topico = _topico_unico("lab10-valida")
    recebidas = []

    assinante = AssinanteMQTT(host, porta, topico, ao_receber=recebidas.append)
    try:
        assert assinante.conectar(timeout=TEMPO_ESPERA_S)
        time.sleep(0.3)  # tempo para o broker processar o SUBSCRIBE antes de publicar

        publicador = _publicador(host, porta)
        try:
            publicador.publish(topico, payload=LINHA_VALIDA_1, qos=0)
            assert _esperar(lambda: len(recebidas) == 1)
        finally:
            publicador.loop_stop()
            publicador.disconnect()
    finally:
        assinante.fechar()

    assert recebidas == [
        {"seq": 1, "uptime_ms": 100, "temp_c": 21.5, "rssi_dbm": -40, "botao": False}
    ]


def test_mensagem_invalida_nao_derruba_a_assinatura(broker):
    host, porta = broker
    topico = _topico_unico("lab10-invalida")
    recebidas = []

    assinante = AssinanteMQTT(host, porta, topico, ao_receber=recebidas.append)
    try:
        assert assinante.conectar(timeout=TEMPO_ESPERA_S)
        time.sleep(0.3)

        publicador = _publicador(host, porta)
        try:
            publicador.publish(topico, payload=LINHA_VALIDA_1, qos=0)
            assert _esperar(lambda: len(recebidas) == 1)

            publicador.publish(topico, payload=LINHA_INVALIDA, qos=0)
            # Sem campo para uma mensagem invalida chegar em recebidas --
            # confere que ela realmente nao chega, e que a proxima mensagem
            # valida ainda assim e processada (a assinatura continua viva).
            time.sleep(0.5)

            publicador.publish(topico, payload=LINHA_VALIDA_2, qos=0)
            assert _esperar(lambda: len(recebidas) == 2)
        finally:
            publicador.loop_stop()
            publicador.disconnect()
    finally:
        assinante.fechar()

    assert recebidas == [
        {"seq": 1, "uptime_ms": 100, "temp_c": 21.5, "rssi_dbm": -40, "botao": False},
        {"seq": 2, "uptime_ms": 200, "temp_c": 21.7, "rssi_dbm": -41, "botao": True},
    ]


def test_publicar_comando_vai_para_topico_comando(broker):
    host, porta = broker
    topico = _topico_unico("lab10-comando")
    recebidos_no_topico_comando = []

    assinante_de_teste = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def _on_message(client, userdata, message):
        del client, userdata
        recebidos_no_topico_comando.append(message.payload.decode("utf-8"))

    assinante_de_teste.on_message = _on_message
    assinante_de_teste.connect(host, porta, keepalive=10)
    assinante_de_teste.subscribe(f"{topico}/comando", qos=0)
    assinante_de_teste.loop_start()
    time.sleep(0.3)

    assinante = AssinanteMQTT(host, porta, topico)
    try:
        assert assinante.conectar(timeout=TEMPO_ESPERA_S)
        assinante.publicar_comando("LED 1")
        assert _esperar(lambda: len(recebidos_no_topico_comando) == 1)
    finally:
        assinante.fechar()
        assinante_de_teste.loop_stop()
        assinante_de_teste.disconnect()

    assert recebidos_no_topico_comando == ["LED 1"]
    assert assinante.topico_comando == f"{topico}/comando"


def test_conectar_com_porta_fechada_devolve_false_sem_excecao(broker):
    host, _porta_do_broker = broker
    porta_fechada = _porta_livre()  # ninguem esta escutando nela

    assinante = AssinanteMQTT(host, porta_fechada, _topico_unico("lab10-erro"))
    try:
        assert assinante.conectar(timeout=1.5) is False
    finally:
        # fechar() nao deve levantar mesmo sem conexao estabelecida.
        assinante.fechar()
