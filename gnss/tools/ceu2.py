# -*- coding: utf-8 -*-
"""Campanha comparativa em ceu aberto: nRF9151, X20P autonomo, VRS e RTK local.

Tres condicoes no rover X20P, alternadas com a ordem girada, e o nRF9151
gravando continuo em paralelo para ser fatiado nas MESMAS janelas.

    A = autonomo      sem correcao nenhuma
    V = VRS Nordian   estacao virtual sintetizada a dezenas de km
    L = RTK local     a outra unidade a 1,42 m, com survey-in proprio

Cada decisao aqui conserta um erro ja cometido nesta bancada:

* **Blocos de duracao igual.** O CEP cresce com a janela — a mesma captura deu
  1,129 m inteira (15 min) e 0,338 m em janelas de 5 min. Duracoes diferentes
  medem a duracao, nao a condicao.
* **Ordem girada, nao enfileirada.** O ambiente deriva o bastante para engolir
  os efeitos: o nRF9151 variou 2,6x sozinho ao longo de uma campanha.
* **Espera o rover LARGAR o fixo antes de cronometrar a nova fonte.** Sem isso
  o cronometro para em zero: o receptor ainda plana nas ambiguidades da fonte
  anterior. Ja aconteceu, e custou um bloco.
* **`qual` comeca em None, nao em 0.** Zero e uma qualidade valida ("sem fix");
  usa-lo como valor inicial confunde ausencia de leitura com leitura de
  ausencia. Mesma classe de erro do numSV saturado em 12.
* **Encerrar por sentinela, nunca por kill.** Fechar porta do X20P a forca vaza
  o handle no Windows e a COM fica presa sem dono.
"""
import base64
import json
import os
import socket
import sys
import threading
import time

sys.path.insert(0, "C:/b")
import serial

BASE_RTCM = "COM20"        # UART2 da base: por onde sai o RTCM
ROVER_RTCM = "COM18"       # UART2 do rover: por onde entra a correcao
ROVER_NMEA = "COM17"       # UART1 do rover: por onde se le NMEA
REF_9151 = "COM23"
CRED = ("C:/Users/joaod/AppData/Local/Temp/claude/C--work-nrf-manaus-2/"
        "783f2ea2-e9d0-437f-917b-39f577c2c3ac/scratchpad/nordian_ntrip.txt")

SENTINELA = "C:/b/parar_ceu2"
SAIDA = "C:/b/ceu2"
BLOCO = 300
ESPERA_LARGAR = 60
ESPERA_FIXO = 420
ESPERA_SOLTA = 120         # para a correcao envelhecer ao voltar para autonomo
RODADAS = [("A", "V", "L"), ("L", "A", "V"), ("V", "L", "A")]
NOMES = {"A": "autonomo, sem correcao",
         "V": "VRS Nordian",
         "L": "RTK local, base a 1,42 m"}

os.makedirs(SAIDA, exist_ok=True)
if os.path.exists(SENTINELA):
    os.remove(SENTINELA)
diario = open(SAIDA + "/_diario.txt", "a", buffering=1, encoding="utf-8")

parar_tudo = threading.Event()
parar_fonte = threading.Event()
fonte_livre = threading.Event()
fonte_livre.set()
ultimo_gga = [None]
qual = [None]              # None = ainda nao vi GGA nenhuma
janelas = []
prontos = set()
if os.path.exists(SAIDA + "/_janelas.json"):
    janelas = json.load(open(SAIDA + "/_janelas.json"))
    prontos = {j["bloco"] for j in janelas}


def log(m):
    l = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    print(l, flush=True)
    diario.write(l + "\n")


# ------------------------------------------------------------- gravadores
def grava(porta, baud, destino, alimenta_estado):
    """Fluxo carimbado. Reabre a porta sozinho se ela cair."""
    f = open(destino, "a", buffering=1, encoding="utf-8")
    s, buf = None, b""
    while not parar_tudo.is_set():
        if s is None:
            try:
                s = serial.Serial(porta, baud, timeout=1)
                s.reset_input_buffer()
            except Exception:
                time.sleep(3)
                continue
        try:
            d = s.read(2048)
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            s = None
            continue
        if not d:
            continue
        buf += d
        linhas = buf.replace(b"\r\n", b"\n").split(b"\n")
        buf = linhas.pop()
        agora = time.time()
        for ln in linhas:
            ln = ln.strip()
            if not ln.startswith(b"$"):
                continue
            f.write("%.2f\t%s\n" % (agora, ln.decode("ascii", "replace")))
            if alimenta_estado and ln[3:6] == b"GGA":
                ultimo_gga[0] = ln + b"\r\n"
                c = ln.split(b",")
                if len(c) > 6:
                    try:
                        qual[0] = int(c[6] or 0)
                    except ValueError:
                        pass
    if s:
        try:
            s.close()
        except Exception:
            pass
    f.close()


def abre_com18(tentativas=15):
    """A COM18 e exclusiva e a fonte anterior pode nao ter soltado ainda —
    trocar de fonte e justamente quando as duas se cruzam."""
    for _ in range(tentativas):
        try:
            return serial.Serial(ROVER_RTCM, 38400, timeout=0.5)
        except serial.SerialException:
            time.sleep(2)
    raise RuntimeError("COM18 nunca liberou")


# ------------------------------------------------------------------ fontes
def fonte_local():
    b = r = None
    total = 0
    try:
        while not parar_fonte.is_set():
            try:
                if b is None:
                    b = serial.Serial(BASE_RTCM, 38400, timeout=0.5)
                if r is None:
                    r = abre_com18()
                d = b.read(1024)
                if d:
                    r.write(d)
                    total += len(d)
            except Exception as e:
                log("    base local reabrindo: %s" % e)
                for o in (b, r):
                    if o:
                        try:
                            o.close()
                        except Exception:
                            pass
                b = r = None
                time.sleep(2)
    finally:
        log("    fonte local encerrada, %d bytes" % total)
        for o in (b, r):
            if o:
                try:
                    o.close()
                except Exception:
                    pass
        fonte_livre.set()


def fonte_vrs():
    cs = r = None
    total = 0
    try:
        u, p = [x.strip() for x in open(CRED, encoding="utf-8").read().splitlines()[:2]]
        auth = base64.b64encode((u + ":" + p).encode()).decode()
        req = ("GET /NEAR-RTCM-VRS HTTP/1.1\r\n"
               "Host: services.nordian.com:2101\r\n"
               "Ntrip-Version: Ntrip/2.0\r\n"
               "User-Agent: NTRIP curso/1.0\r\n"
               "Authorization: Basic " + auth + "\r\n\r\n")
        cs = socket.create_connection(("services.nordian.com", 2101), timeout=15)
        cs.sendall(req.encode())
        cs.settimeout(1.0)
        cab, prazo = b"", time.time() + 15
        while b"\r\n\r\n" not in cab and time.time() < prazo:
            try:
                d = cs.recv(1024)
                if not d:
                    break
                cab += d
            except socket.timeout:
                continue
        log("    caster: %s" % cab.split(b"\r\n")[0].decode("ascii", "replace"))
        r = abre_com18()
        tg = 0
        while not parar_fonte.is_set():
            try:
                d = cs.recv(8192)
                if d:
                    r.write(d)
                    total += len(d)
            except socket.timeout:
                pass
            except Exception:
                break
            if time.time() - tg > 10 and ultimo_gga[0]:
                try:
                    cs.sendall(ultimo_gga[0])
                except Exception:
                    pass
                tg = time.time()
    except Exception as e:
        log("    VRS falhou: %s" % e)
    finally:
        log("    fonte VRS encerrada, %d bytes" % total)
        for o in (cs, r):
            if o:
                try:
                    o.close()
                except Exception:
                    pass
        fonte_livre.set()


def troca_para(cond):
    """Encerra a fonte anterior e SO entao abre a nova — as duas escrevem na
    mesma COM18, que e exclusiva."""
    parar_fonte.set()
    if not fonte_livre.wait(25):
        log("    AVISO: fonte anterior nao soltou a COM18")
    time.sleep(1)
    if cond == "A":
        return                      # autonomo: nenhuma fonte
    parar_fonte.clear()
    fonte_livre.clear()
    threading.Thread(target=fonte_local if cond == "L" else fonte_vrs,
                     daemon=True).start()


def prepara(cond):
    """Leva o rover ao regime da condicao e devolve quanto tempo levou."""
    t0 = time.time()
    troca_para(cond)

    if cond == "A":
        # sem correcao, a solucao tem de ENVELHECER ate voltar a autonomo
        prazo = t0 + ESPERA_SOLTA
        while time.time() < prazo and qual[0] in (4, 5):
            time.sleep(2)
        log("    correcao envelhecida em %.0f s, qualidade %s"
            % (time.time() - t0, qual[0]))
        return time.time() - t0

    # com correcao: primeiro largar o fixo anterior, depois esperar o novo
    prazo = t0 + ESPERA_LARGAR
    while time.time() < prazo and qual[0] == 4:
        time.sleep(1)
    if qual[0] == 4:
        log("    nao largou o fixo anterior em %d s — a nova fonte concorda "
            "com a antiga dentro do ruido" % ESPERA_LARGAR)
    else:
        log("    largou o fixo anterior apos %.0f s (qualidade %s)"
            % (time.time() - t0, qual[0]))

    prazo = time.time() + ESPERA_FIXO
    while time.time() < prazo and qual[0] != 4:
        time.sleep(2)
    dt = time.time() - t0
    if qual[0] == 4:
        log("    RTK FIXO em %.0f s" % dt)
    else:
        log("    nao fixou em %.0f s; grava assim mesmo, qualidade %s"
            % (dt, qual[0]))
    return dt


# ---------------------------------------------------------------- campanha
def main():
    threading.Thread(target=grava, args=(ROVER_NMEA, 38400,
                                         SAIDA + "/rover.tsv", True),
                     daemon=True).start()
    threading.Thread(target=grava, args=(REF_9151, 115200,
                                         SAIDA + "/ref_9151.tsv", False),
                     daemon=True).start()
    espera = time.time() + 30
    while qual[0] is None and time.time() < espera:
        time.sleep(1)
    log("=" * 64)
    if qual[0] is None:
        log("o rover nao falou em 30 s — COM17 presa? encerrando sem gravar")
        parar_tudo.set()
        return 1
    log("CEU ABERTO: nRF9151 + X20P em 3 condicoes, alternadas")
    log("rover falando, qualidade inicial %s" % qual[0])
    if prontos:
        log("retomando; ja prontos: %s" % ", ".join(sorted(prontos)))

    try:
        for r, ordem in enumerate(RODADAS, 1):
            for cond in ordem:
                if parar_tudo.is_set() or os.path.exists(SENTINELA):
                    raise KeyboardInterrupt
                nome = "r%d_%s" % (r, cond)
                if nome in prontos:
                    continue
                log("=== %s: %s" % (nome, NOMES[cond]))
                dt = prepara(cond)

                t0 = time.time()
                time.sleep(BLOCO)
                janelas.append({"bloco": nome, "cond": cond, "rodada": r,
                                "ini": t0, "fim": time.time(),
                                "s_ate_regime": round(dt, 1)})
                json.dump(janelas, open(SAIDA + "/_janelas.json", "w"), indent=1)
                log("    %s concluido (qualidade final %s)" % (nome, qual[0]))
    except KeyboardInterrupt:
        log("interrompido")
    finally:
        parar_fonte.set()
        fonte_livre.wait(25)
        time.sleep(2)
        parar_tudo.set()
        time.sleep(2)
        log("FIM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
