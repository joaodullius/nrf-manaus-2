# -*- coding: utf-8 -*-
"""Matriz completa de dispersao: nRF9151 + X20P em 2x2 (GLONASS x NTRIP).

Tres decisoes de desenho, cada uma corrigindo um erro ja cometido nesta bancada:

1. Todos os blocos tem a MESMA duracao. O CEP cresce com a janela: a mesma
   captura de 15 min deu 1,129 m inteira e 0,338 m em janelas de 5 min. Comparar
   condicoes medidas em duracoes diferentes mede a duracao, nao a condicao.

2. SBAS fica desligado o tempo todo. Foi ele, entrando e saindo em proporcoes
   diferentes a cada bloco, que fabricou um "ganho de 2,6x do GLONASS" que nao
   existia.

3. A ordem das condicoes gira a cada rodada. O ambiente deriva o bastante para
   engolir os efeitos, e o CEP de blocos concatenados no tempo mistura deriva com
   dispersao. Cada bloco vira um CEP proprio; o que se compara e a mediana das
   tres rodadas.

O nRF9151 grava continuo, com carimbo de tempo, e depois e fatiado exatamente
nas mesmas 12 janelas. Assim cada bloco do X20P tem sua propria referencia
simultanea, e nao uma medida feita em outra hora.
"""
import base64, json, os, socket, sys, threading, time
sys.path.insert(0, "C:/b")
import serial
import ubxlib as U

SAIDA = "C:/b/matriz"
CRED = ("C:/Users/joaod/AppData/Local/Temp/claude/C--work-nrf-manaus-2/"
        "783f2ea2-e9d0-437f-917b-39f577c2c3ac/scratchpad/nordian_ntrip.txt")
SBAS_ENA, GLO_ENA = 0x10310020, 0x10310025
BLOCO = 300           # segundos de captura, igual para todos
ESPERA_RTK = 240      # teto para convergir ate RTK fixo
ESPERA_SOLTA = 150    # tempo para a correcao envelhecer e voltar a autonomo

os.makedirs(SAIDA, exist_ok=True)
diario = open(SAIDA + "/_diario.txt", "a", buffering=1, encoding="utf-8")


def log(m):
    l = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    print(l, flush=True)
    diario.write(l + "\n")


# ---------------------------------------------------------------- nRF9151
fim_geral = threading.Event()


def grava_9151():
    """Fluxo continuo carimbado. Reabre a porta sozinho se ela cair."""
    f = open(SAIDA + "/ref_9151.tsv", "a", buffering=1, encoding="utf-8")
    s, buf = None, b""
    while not fim_geral.is_set():
        if s is None:
            try:
                s = serial.Serial("COM23", 115200, timeout=1)
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
        linhas = buf.split(b"\n")
        buf = linhas.pop()
        agora = time.time()
        for ln in linhas:
            ln = ln.strip()
            if ln.startswith(b"$"):
                f.write("%.2f\t%s\n" % (agora, ln.decode("ascii", "replace")))
    if s:
        try:
            s.close()
        except Exception:
            pass
    f.close()


# ---------------------------------------------------------------- X20P
ultimo_gga, qual = [None], [0]


def le_x20p(destino, seg):
    """Le COM17 por `seg` segundos. Sempre alimenta ultimo_gga/qual, mesmo
    quando destino e None (aquecimento e decantacao)."""
    f = open(destino, "wb", buffering=0) if destino else None
    s, buf, fim = None, b"", time.time() + seg
    while time.time() < fim:
        if s is None:
            try:
                s = serial.Serial("COM17", 115200, timeout=0.5)
                s.reset_input_buffer()
            except Exception:
                time.sleep(2)
                continue
        try:
            d = s.read(4096)
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            s = None
            continue
        if f and d:
            f.write(d)
        buf += d
        linhas = buf.split(b"\r\n")
        buf = linhas.pop()
        for ln in linhas:
            if ln[3:6] == b"GGA":
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
    if f:
        f.close()


# ---------------------------------------------------------------- NTRIP
parar_ntrip = threading.Event()
ntrip_livre = threading.Event()   # o worker soltou a COM18
ntrip_livre.set()


def ntrip_worker():
    u, p = [x.strip() for x in open(CRED, encoding="utf-8").read().splitlines()[:2]]
    auth = base64.b64encode((u + ":" + p).encode()).decode()
    req = ("GET /NEAR-RTCM-VRS HTTP/1.1\r\n"
           "Host: services.nordian.com:2101\r\n"
           "Ntrip-Version: Ntrip/2.0\r\n"
           "User-Agent: NTRIP curso/1.0\r\n"
           "Authorization: Basic " + auth + "\r\n\r\n")
    try:
        cs = socket.create_connection(("services.nordian.com", 2101), timeout=15)
    except Exception as e:
        log("    caster inacessivel: %s" % e)
        return
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
    try:
        rs = serial.Serial("COM18", 115200, timeout=0.5)
    except Exception as e:
        log("    COM18 ocupada: %s" % e)
        cs.close()
        return
    tg, bytes_rtcm = 0, 0
    while not parar_ntrip.is_set():
        try:
            d = cs.recv(8192)
            if d:
                rs.write(d)
                bytes_rtcm += len(d)
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
    log("    NTRIP encerrado, %d bytes de RTCM injetados" % bytes_rtcm)
    for o in (cs, rs):
        try:
            o.close()
        except Exception:
            pass
    ntrip_livre.set()


def solta_ntrip():
    """Para o worker e SO retorna quando a COM18 estiver de fato liberada.

    A COM18 e exclusiva: o worker de NTRIP a mantem aberta para injetar RTCM, e
    e a mesma porta por onde vai a configuracao. Sem esperar o worker soltar, um
    bloco de NTRIP seguido de outro bloco de NTRIP bate em 'Acesso negado' —
    porque o `parar_ntrip` do ramo sem NTRIP nunca chega a rodar.
    """
    parar_ntrip.set()
    if not ntrip_livre.wait(20):
        log("    AVISO: worker de NTRIP nao soltou a COM18 em 20 s")
    time.sleep(0.5)


def cfg(pares, tentativas=5):
    """Configura pela COM18, insistindo se a porta ainda estiver ocupada."""
    for i in range(tentativas):
        try:
            c = serial.Serial("COM18", 115200, timeout=0.3)
        except serial.SerialException:
            time.sleep(2)
            continue
        try:
            return U.valset(c, pares, 0x01)
        finally:
            c.close()
    log("    ERRO: COM18 nunca liberou para configurar")
    return None


# ---------------------------------------------------------------- campanha
COND = {"A": (0, 0), "B": (1, 0), "C": (0, 1), "D": (1, 1)}   # (GLONASS, NTRIP)
RODADAS = [("A", "B", "C", "D"), ("D", "C", "B", "A"), ("B", "D", "A", "C")]
NOMES = {"A": "sem GLONASS, sem NTRIP", "B": "com GLONASS, sem NTRIP",
         "C": "sem GLONASS, com NTRIP", "D": "com GLONASS, com NTRIP"}

# retoma: blocos ja capturados nao sao refeitos
if os.path.exists(SAIDA + "/_janelas.json"):
    janelas = json.load(open(SAIDA + "/_janelas.json"))
else:
    janelas = []
prontos = {j["bloco"] for j in janelas}

threading.Thread(target=grava_9151, daemon=True).start()
log("=" * 60)
log("MATRIZ: 3 rodadas x 4 condicoes x %d s. nRF9151 gravando em paralelo." % BLOCO)
if prontos:
    log("retomando; ja prontos: %s" % ", ".join(sorted(prontos)))
log("SBAS desligado: %s" % cfg([(SBAS_ENA, 0)]))

try:
    for r, ordem in enumerate(RODADAS, 1):
        for cd in ordem:
            glo, ntrip = COND[cd]
            nome = "r%d_%s" % (r, cd)
            if nome in prontos:
                continue
            log("=== %s: %s" % (nome, NOMES[cd]))
            # a COM18 tem de estar livre antes de configurar, sempre
            solta_ntrip()
            log("    GLONASS -> %s: %s" % (glo, cfg([(GLO_ENA, glo)])))

            if ntrip:
                parar_ntrip.clear()
                ntrip_livre.clear()
                threading.Thread(target=ntrip_worker, daemon=True).start()
                prazo = time.time() + ESPERA_RTK
                while time.time() < prazo:
                    le_x20p(None, 5)
                    if qual[0] == 4:
                        break
                log("    entra no bloco com qualidade %d" % qual[0])
            else:
                le_x20p(None, ESPERA_SOLTA)
                log("    correcao envelhecida, qualidade %d" % qual[0])

            t0 = time.time()
            le_x20p(SAIDA + "/" + nome + ".nmea", BLOCO)
            janelas.append({"bloco": nome, "cond": cd, "rodada": r,
                            "glonass": glo, "ntrip": ntrip,
                            "ini": t0, "fim": time.time()})
            json.dump(janelas, open(SAIDA + "/_janelas.json", "w"), indent=1)
            log("    %s concluido (qualidade final %d)" % (nome, qual[0]))
finally:
    solta_ntrip()
    log("religando SBAS e GLONASS: %s" % cfg([(SBAS_ENA, 1), (GLO_ENA, 1)]))
    time.sleep(3)
    fim_geral.set()
    time.sleep(2)
    log("FIM")
