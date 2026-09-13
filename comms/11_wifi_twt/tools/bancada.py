"""Peças comuns dos scripts de captura do lab 11.

Tudo o que os cinco scripts deste diretório repetiam: abrir o PPK2 na ordem que
funciona, falar com o shell do lab 6 pela serial, e segmentar os pulsos de
despertar numa captura de corrente.

Nenhuma credencial e nenhuma porta ficam aqui — quem chama passa tudo por
argumento de linha de comando (ver `argumentos()`).
"""

import argparse
import re
import subprocess
import time

import serial

# O shell do Zephyr ecoa com sequencias ANSI; sem tirar, todo regex falha.
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\r")

TAXA_PPK2 = 100000.0      # amostras por segundo do PPK2
DECIMACAO = 10            # o que guardamos no JSON: 1 de cada 10 (10 kSa/s)


def argumentos(descricao, *extras):
    """Os argumentos comuns a todos os scripts, mais os que o script pedir."""
    p = argparse.ArgumentParser(description=descricao)
    p.add_argument("--shell", required=True,
                   help="porta serial do console do kit (a PRIMEIRA VCOM, com o shield)")
    p.add_argument("--ppk2", required=True, help="porta serial do PPK2")
    p.add_argument("--jlink", required=True,
                   help="serial do J-Link da DK (nrfutil device list)")
    p.add_argument("--ssid", required=True, help="SSID da rede")
    p.add_argument("--senha", required=True, help="senha da rede (WPA2-PSK)")
    p.add_argument("--saida", required=True, help="arquivo .json de saida")
    for args, kwargs in extras:
        p.add_argument(*args, **kwargs)
    return p.parse_args()


# --------------------------------------------------------------------- PPK2
def abre_ppk2(porta, tentativas=8):
    """Abre o PPK2 em amperimetro e FECHA a chave de medicao.

    Tres coisas que parecem desnecessarias e nao sao:

    - `set_source_voltage()` e obrigatorio mesmo em amperimetro: ali ele so
      informa a escala, nao vira fonte.
    - `toggle_DUT_power("ON")` em amperimetro apenas FECHA a chave. Sem ele o
      PPK2 le zero e parece defeito.
    - o laco de drenagem: depois do app grafico sobra lixo binario no buffer e o
      `get_modifiers()` quebra ao decodificar como UTF-8.

    O objeto devolvido tem de ficar VIVO ate o fim do script: quando a serial do
    PPK2 fecha, ele volta ao estado seguro e ABRE a chave — o companion perde o
    VBAT e o proximo boot falha com "RPU is unresponsive for 10 sec".
    """
    from ppk2_api.ppk2_api import PPK2_API

    ppk = PPK2_API(porta)
    for tentativa in range(tentativas):
        try:
            ppk.stop_measuring()
        except Exception:
            pass
        time.sleep(0.4)
        try:
            ppk.ser.reset_input_buffer()
            ppk.ser.reset_output_buffer()
        except Exception:
            pass
        time.sleep(0.3)
        try:
            ppk.get_modifiers()
            break
        except Exception:
            print(f"   drenando o buffer do PPK2 (tentativa {tentativa + 1})")
    else:
        raise RuntimeError("nao consegui ler os metadados do PPK2")

    ppk.set_source_voltage(3600)
    ppk.use_ampere_meter()
    ppk.toggle_DUT_power("ON")
    time.sleep(1.0)
    print("PPK2: amperimetro, chave fechada")
    return ppk


def mede(ppk, segundos):
    """Corrente em uA, amostra a amostra, por `segundos`."""
    ppk.start_measuring()
    time.sleep(0.3)
    ppk.get_data()                      # descarta a fila acumulada
    amostras, t0 = [], time.time()
    while time.time() - t0 < segundos:
        d = ppk.get_data()
        if d != b"":
            s, _ = ppk.get_samples(d)
            amostras += s
        time.sleep(0.01)
    ppk.stop_measuring()
    return amostras


def resumo(amostras):
    b = sorted(amostras)
    n = len(b)
    return {"n": n, "media_uA": round(sum(b) / n, 1), "min_uA": round(b[0], 1),
            "p50_uA": round(b[n // 2], 1), "p99_uA": round(b[int(n * 0.99)], 1),
            "max_uA": round(b[-1], 1)}


def pulsos(decimadas, limiar_uA=2000.0, taxa=TAXA_PPK2 / DECIMACAO):
    """Segmenta os despertares: trechos acima do limiar, com pelo menos 3 amostras.

    Devolve (duracao_ms, carga_uC) de cada pulso. É a base da conta que explica o
    lab: media = carga por despertar x frequencia de despertar.
    """
    eventos, dentro, ini = [], False, 0
    for i, v in enumerate(decimadas):
        if v > limiar_uA and not dentro:
            dentro, ini = True, i
        elif v <= limiar_uA and dentro:
            dentro = False
            if i - ini >= 3:
                eventos.append(((i - ini) / taxa * 1000, sum(decimadas[ini:i]) / taxa))
    return eventos


# -------------------------------------------------------------------- serial
def reseta(jlink, espera=10):
    """Reset da DK. So depois de o PPK2 ja estar com a chave FECHADA."""
    subprocess.run(["nrfutil", "device", "reset", "--serial-number", jlink],
                   capture_output=True)
    time.sleep(espera)


def abre_shell(porta):
    return serial.Serial(porta, 115200, timeout=0.2)


def comando(sh, linha, espera=1.5):
    sh.reset_input_buffer()
    sh.write((linha + "\r\n").encode())
    t0, buf = time.time(), ""
    while time.time() - t0 < espera:
        d = sh.read(4096)
        if d:
            buf += d.decode("utf-8", "replace")
    return ANSI.sub("", buf)


def conecta(sh, ssid, senha, banda="2", listen_interval=None, espera=11):
    """Associa. O listen interval viaja no quadro de associacao: tem de ser
    ajustado ANTES do connect, e mudar de valor exige reconectar."""
    if listen_interval is not None:
        comando(sh, f"wifi ps_listen_interval {listen_interval}", 1.5)
    comando(sh, f'wifi connect -s "{ssid}" -k 1 -p "{senha}" -b {banda}', 2.0)
    time.sleep(espera)
    return "COMPLETED" in comando(sh, "wifi status", 2.0)


def estado_do_link(sh):
    """Os quatro numeros que interpretam qualquer medida deste lab."""
    st = comando(sh, "wifi status", 2.0)

    def campo(chave):
        m = re.search(chave + r":\s*(-?\d+)", st)
        return m.group(1) if m else "?"

    return {"canal": campo("Channel"), "rssi": campo("RSSI"),
            "dtim": campo("DTIM"), "beacon_ms": campo("Beacon Interval")}


def ip_do_kit(sh):
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)/[\d.]+\s+DHCP", comando(sh, "net iface", 2.5))
    return m.group(1) if m else None


def um_ping(ip, timeout_ms=4000):
    """Um unico ping. Devolve o RTT em ms, ou None se nao voltou.

    Pings ISOLADOS sao o ponto: o nRF70 tem dynamic power save com timer de
    inatividade de 100 ms, entao uma rajada mede ~8 ms em qualquer regime.
    """
    r = subprocess.run(["ping", "-n", "1", "-w", str(timeout_ms), ip],
                       capture_output=True, text=True, errors="replace")
    m = re.search(r"tempo[=<](\d+)ms|time[=<](\d+)ms", r.stdout)
    return int(m.group(1) or m.group(2)) if m else None
