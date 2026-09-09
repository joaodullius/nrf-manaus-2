# -*- coding: utf-8 -*-
"""Exercita a maquina de estados do ceu2.py com portas e caster falsos.

Existe porque os tres bugs da campanha anterior — o cronometro parando em zero,
o `qual` inicial ambiguo e o `%d` recebendo None — eram todos detectaveis sem
receptor nenhum, e cada ciclo de conserto na bancada custou um par de portas
seriais presas. Rodar isto leva segundos; descobrir na bancada levou uma hora.
"""
import sys
import threading
import time
import types

# --- dubles instalados ANTES de importar o modulo sob teste ------------------
relogio = [0.0]
REAL_SLEEP = time.sleep


class SerialFalsa:
    aberta = set()

    def __init__(self, porta, baud, timeout=0.5):
        if porta in SerialFalsa.aberta:
            raise SerialFake_Excecao("porta ocupada: %s" % porta)
        SerialFalsa.aberta.add(porta)
        self.porta = porta

    def read(self, n=1):
        REAL_SLEEP(0.001)
        return b"\xd3\x00\x10" + b"\x00" * 16

    def write(self, d):
        return len(d)

    def reset_input_buffer(self):
        pass

    def close(self):
        SerialFalsa.aberta.discard(self.porta)


class SerialFake_Excecao(Exception):
    pass


serial_falso = types.ModuleType("serial")
serial_falso.Serial = SerialFalsa
serial_falso.SerialException = SerialFake_Excecao
sys.modules["serial"] = serial_falso

socket_falso = types.ModuleType("socket")


class SockFalso:
    def sendall(self, d):
        pass

    def settimeout(self, t):
        pass

    def recv(self, n):
        REAL_SLEEP(0.001)
        return b"ICY 200 OK\r\n\r\n"

    def close(self):
        pass


socket_falso.create_connection = lambda *a, **k: SockFalso()
socket_falso.timeout = TimeoutError
sys.modules["socket"] = socket_falso

sys.path.insert(0, "C:/b")
import ceu2  # noqa: E402

# encurta tudo: o que se testa e a LOGICA, nao a espera
ceu2.BLOCO = 0.05
ceu2.ESPERA_LARGAR = 0.3
ceu2.ESPERA_FIXO = 0.6
ceu2.ESPERA_SOLTA = 0.3
ceu2.SAIDA = "C:/b/teste_ceu2"
import os  # noqa: E402
os.makedirs(ceu2.SAIDA, exist_ok=True)
for f in ("_janelas.json", "_diario.txt"):
    if os.path.exists(ceu2.SAIDA + "/" + f):
        os.remove(ceu2.SAIDA + "/" + f)
ceu2.janelas, ceu2.prontos = [], set()
ceu2.diario = open(ceu2.SAIDA + "/_diario.txt", "w", buffering=1, encoding="utf-8")

# --- o receptor simulado ------------------------------------------------------
# Fica em fixo enquanto ha fonte; larga o fixo pouco depois de a fonte sair, e
# demora um pouco para voltar. E o comportamento que quebrou a versao anterior.
estado = {"fonte": None}
falhas = []


def receptor():
    while not ceu2.parar_tudo.is_set():
        REAL_SLEEP(0.05)
        tem_fonte = not ceu2.parar_fonte.is_set() and estado["fonte"] is not None
        if tem_fonte:
            ceu2.qual[0] = 4
        elif ceu2.qual[0] == 4:
            ceu2.qual[0] = 5      # largou o fixo
        else:
            ceu2.qual[0] = 1


troca_real = ceu2.troca_para


def troca_espiao(cond):
    estado["fonte"] = None
    ceu2.qual[0] = 4              # ainda planando na fonte anterior
    troca_real(cond)
    if cond != "A":
        REAL_SLEEP(0.15)
        estado["fonte"] = cond


ceu2.troca_para = troca_espiao
ceu2.qual[0] = 1
threading.Thread(target=receptor, daemon=True).start()

ret = ceu2.main()

# --- o que precisa ser verdade ------------------------------------------------
import json  # noqa: E402
j = json.load(open(ceu2.SAIDA + "/_janelas.json"))
esperados = [f"r{r}_{c}" for r, ordem in enumerate(ceu2.RODADAS, 1) for c in ordem]

if ret != 0:
    falhas.append("main() devolveu %s" % ret)
if [x["bloco"] for x in j] != esperados:
    falhas.append("blocos gravados %s != esperados %s"
                  % ([x["bloco"] for x in j], esperados))
for x in j:
    if x["fim"] <= x["ini"]:
        falhas.append("%s: janela invertida" % x["bloco"])
    # o bug que custou um bloco: cronometro parando antes de a fonte existir
    if x["cond"] != "A" and x["s_ate_regime"] < 0.1:
        falhas.append("%s: s_ate_regime=%.2f — cronometro parou cedo demais, "
                      "o rover ainda planava no fixo anterior"
                      % (x["bloco"], x["s_ate_regime"]))
if SerialFalsa.aberta:
    falhas.append("portas deixadas abertas: %s" % SerialFalsa.aberta)

print()
if falhas:
    print("FALHOU:")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("OK — %d blocos na ordem certa, nenhum cronometro zerado, "
      "nenhuma porta vazada" % len(j))
