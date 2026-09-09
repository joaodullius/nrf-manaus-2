#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monta um par base/rover de ZED-X20P e liga o RTK — codigo do curso.

Um receptor vira base: ele fica parado, descobre onde esta (survey-in) e passa a
publicar o que observa em RTCM. O outro vira rover: recebe esse RTCM e resolve a
propria posicao em relacao a base. Este script cuida das duas pontas e da ponte
entre elas.

    python rtk_base.py --base COM20 --rover COM18 --rover-nmea COM17

A distincao que o RTK exige e que quase todo mundo confunde:

    EXATIDAO ABSOLUTA  — onde a base acha que esta no mundo. Sai do survey-in, e
                         com meia hora de ceu urbano fica em metros.
    EXATIDAO RELATIVA  — o vetor da base ate o rover. Sai em centimetros, e nao
                         depende da anterior.

Se a base estiver 10 m fora do lugar, o rover fica 10 m fora do lugar junto com
ela — mas a DISTANCIA entre os dois continua certa no centimetro. Para medir
deslocamento, deformacao, ou a diferenca entre duas posicoes, so a relativa
importa. Para saber a coordenada de verdade, e preciso uma base com coordenada
conhecida (--fixa) ou um servico de correcao.

Tres coisas aprendidas na bancada e embutidas aqui:

* **Fixo e o que vale.** Em RTK flutuante a posicao pode estar decimetros ou
  metros fora, e ao fixar ela SALTA. Comparar uma janela flutuante com uma fixa
  mede o salto, nao o que se queria medir. Por isso `--exigir-fixo`.
* **Entrar no fixo e caro, manter e barato.** Numa janela urbana levou 19 min
  para fixar da primeira vez, e depois o fixo sobreviveu a mover a antena aos
  trancos, sem cair uma epoca.
* **Nunca matar o processo.** Fechar porta do X20P a forca vaza o handle no
  Windows: a COM fica presa, sem dono, e so se solta depois de minutos. Ctrl+C
  aqui encerra em ordem.
"""
from __future__ import annotations

import argparse
import signal
import struct
import sys
import threading
import time
from pathlib import Path

import serial
import serial.tools.list_ports

# --------------------------------------------------------------- protocolo UBX
TAM = {0: 1, 1: 1, 2: 1, 3: 2, 4: 4, 5: 8}


def ubx(cls: int, mid: int, payload: bytes = b"") -> bytes:
    c = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for x in c:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return bytes([0xB5, 0x62]) + c + bytes([a, b])


def quadros(buf: bytes):
    saida, i = [], 0
    while True:
        i = buf.find(b"\xb5\x62", i)
        if i < 0 or i + 6 > len(buf):
            break
        ln = struct.unpack("<H", buf[i + 4:i + 6])[0]
        fim = i + 6 + ln + 2
        if fim > len(buf):
            break
        q = buf[i:fim]
        a = b = 0
        for x in q[2:-2]:
            a = (a + x) & 0xFF
            b = (b + a) & 0xFF
        if (a, b) == (q[-2], q[-1]):
            saida.append((q[2], q[3], q[6:-2]))
        i = fim
    return saida


def fala(s: serial.Serial, msg: bytes, espera: float = 2.0):
    s.reset_input_buffer()
    s.write(msg)
    fim, buf = time.time() + espera, b""
    while time.time() < fim:
        buf += s.read(4096)
    return quadros(buf)


def valset(s: serial.Serial, pares, camadas: int = 0x01) -> bool:
    p = struct.pack("<BBBB", 0x00, camadas, 0x00, 0x00)
    for k, v in pares:
        t = TAM.get((k >> 28) & 0x7, 1)
        p += struct.pack("<I", k) + int(v).to_bytes(t, "little", signed=(v < 0))
    for cls, mid, _ in fala(s, ubx(0x06, 0x8A, p)):
        if cls == 0x05:
            return mid == 1
    return False


def monver(s: serial.Serial):
    for cls, mid, p in fala(s, ubx(0x0A, 0x04)):
        if (cls, mid) == (0x0A, 0x04):
            sw = p[0:30].split(b"\x00")[0].decode("ascii", "replace")
            hw = p[30:40].split(b"\x00")[0].decode("ascii", "replace")
            ext = [p[j:j + 30].split(b"\x00")[0].decode("ascii", "replace")
                   for j in range(40, len(p), 30)]
            return sw, hw, [e for e in ext if e.strip()]
    return None


def nav_svin(s: serial.Serial):
    """Estado do survey-in: (segundos, precisao_m, observacoes, valido, ativo)."""
    for cls, mid, p in fala(s, ubx(0x01, 0x3B), 1.5):
        if (cls, mid) == (0x01, 0x3B) and len(p) >= 40:
            return (struct.unpack("<I", p[8:12])[0],
                    struct.unpack("<I", p[28:32])[0] / 10000.0,
                    struct.unpack("<I", p[32:36])[0],
                    bool(p[36]), bool(p[37]))
    return None


# ------------------------------------------------------------------ chaves CFG
# As chaves de saida dizem por QUAL UART a mensagem sai, entao mudam conforme a
# porta em que a base fala com o rover.
RTCM_POR_UART = {
    1: {"1006": 0x209102C3, "4072.0": 0x20910300, "1074": 0x20910360,
        "1084": 0x20910365, "1094": 0x2091036A, "1124": 0x2091036F,
        "1230": 0x20910304},
    2: {"1006": 0x209102C4, "4072.0": 0x20910301, "1074": 0x20910361,
        "1084": 0x20910366, "1094": 0x2091036B, "1124": 0x20910370,
        "1230": 0x20910305},
}
# 1006 da a coordenada da estacao; 1074/1084/1094/1124 sao as observacoes MSM4 de
# GPS, GLONASS, Galileo e BeiDou; 1230 traz os vieses de fase do GLONASS, sem os
# quais o GLONASS entra nas contas mas nao ajuda a fixar; 4072.0 e proprietaria
# da u-blox e so faz falta em base movel.

TMODE_MODE, TMODE_POS_TYPE = 0x20030001, 0x20030002
SVIN_MIN_DUR, SVIN_ACC_LIMIT = 0x40030010, 0x40030011
FIXED_LAT, FIXED_LON, FIXED_ALT = 0x40030009, 0x4003000A, 0x40030008
FIXED_LAT_HP, FIXED_LON_HP, FIXED_ALT_HP = 0x2003000C, 0x2003000D, 0x2003000B
FIXED_POS_ACC = 0x4003000F
NMEA_HIGHPREC = 0x10930006

QUALIDADE = {0: "sem fix", 1: "autonomo", 2: "DGPS", 4: "RTK fixo",
             5: "RTK flutuante", 6: "estimado"}


# ------------------------------------------------------------------ utilidades
def portas_x20p():
    return [(p.device, p.description)
            for p in serial.tools.list_ports.comports()
            if "X20P" in (p.description or "")]


def uart_da_porta(porta: str, forcado: int | None) -> int:
    """Descobre se a COM e a UART1 ou a UART2 do EVK, pela descricao do driver."""
    if forcado:
        return forcado
    for dev, desc in portas_x20p():
        if dev.upper() == porta.upper():
            if "UART2" in desc:
                return 2
            if "UART1" in desc:
                return 1
    raise SystemExit(
        f"nao consegui saber se {porta} e UART1 ou UART2; passe --uart-base 1 ou 2")


def abre(porta: str, baud: int | None, log) -> tuple[serial.Serial, int]:
    """Abre e confirma que ha um X20P do outro lado, testando os bauds usuais."""
    for b in ([baud] if baud else [115200, 38400, 9600]):
        try:
            s = serial.Serial(porta, b, timeout=0.3)
        except serial.SerialException as e:
            raise SystemExit(f"{porta}: {e}\n"
                             "Se a porta ficou presa sem dono, foi processo morto a "
                             "forca: espere alguns minutos ou reconecte o cabo.")
        r = monver(s)
        if r:
            log(f"{porta} @ {b}: {r[0]}")
            for e in r[2]:
                if e.startswith(("FWVER", "MOD", "PROTVER")):
                    log(f"    {e}")
            return s, b
        s.close()
    raise SystemExit(f"{porta}: nenhum receptor u-blox respondeu")


# ----------------------------------------------------------------------- fluxo
class Rig:
    def __init__(self, arg):
        self.arg = arg
        self.parar = threading.Event()
        self.bytes_rtcm = 0
        self.qualidade = None
        self.desde = time.time()
        self.marcos: dict[int, float] = {}
        self.arquivo = None
        self.diario = None

    def log(self, m: str):
        linha = f"[{time.strftime('%H:%M:%S')}] {m}"
        print(linha, flush=True)
        if self.diario:
            self.diario.write(linha + "\n")

    # ---------------------------------------------------------------- base
    def prepara_base(self):
        s, baud = abre(self.arg.base, self.arg.baud_base, self.log)
        self.baud_base = baud
        uart = uart_da_porta(self.arg.base, self.arg.uart_base)
        chaves = RTCM_POR_UART[uart]
        self.log(f"base em {self.arg.base} (UART{uart}) — publicando "
                 + ", ".join(f"RTCM {k}" for k in chaves))
        if not valset(s, [(v, 1) for v in chaves.values()]):
            raise SystemExit("a base recusou a configuracao de RTCM")

        if self.arg.fixa:
            lat, lon, alt = self.arg.fixa
            # A chave inteira guarda 1e-7 grau; a de alta precisao acrescenta os
            # 1e-9 restantes. Sem a segunda, a coordenada dada perde ~1 cm.
            gi, gf = int(lat * 1e7), round((lat * 1e7 % 1) * 100)
            oi, of = int(lon * 1e7), round((lon * 1e7 % 1) * 100)
            ai, af = int(alt * 100), round((alt * 100 % 1) * 100)
            ok = valset(s, [(TMODE_MODE, 2), (TMODE_POS_TYPE, 1),
                            (FIXED_LAT, gi), (FIXED_LAT_HP, gf),
                            (FIXED_LON, oi), (FIXED_LON_HP, of),
                            (FIXED_ALT, ai), (FIXED_ALT_HP, af),
                            (FIXED_POS_ACC, 100)])
            self.log(f"base em coordenada fixa {lat:.7f}, {lon:.7f}, {alt:.2f} m: {ok}")
            s.close()
            return

        dur, acc = self.arg.survey_dur, self.arg.survey_acc
        ok = valset(s, [(TMODE_MODE, 1), (SVIN_MIN_DUR, dur),
                        (SVIN_ACC_LIMIT, int(acc * 10000))])
        self.log(f"survey-in: minimo {dur} s, aceita ate {acc:.1f} m — {ok}")
        try:
            prazo = time.time() + self.arg.survey_max
            ultimo = 0.0
            while time.time() < prazo and not self.parar.is_set():
                r = nav_svin(s)
                if r:
                    seg, prec, obs, valido, ativo = r
                    if valido:
                        self.log(f"survey-in VALIDO aos {seg} s — "
                                 f"exatidao ABSOLUTA da base {prec:.2f} m")
                        if prec > 1.0:
                            self.log("    a posicao absoluta e grosseira, e isso e "
                                     "esperado sob ceu obstruido. O vetor ate o "
                                     "rover continua centimetrico.")
                        return
                    if seg != ultimo:
                        self.log(f"survey-in: {seg} s, {prec:.2f} m, {obs} observacoes")
                        ultimo = seg
                time.sleep(self.arg.intervalo)
            raise SystemExit(
                f"survey-in nao validou em {self.arg.survey_max} s.\n"
                "Sob ceu obstruido a precisao estagna: afrouxe --survey-acc, "
                "aumente --survey-max, ou use --fixa com uma coordenada conhecida.")
        finally:
            s.close()

    # --------------------------------------------------------------- ponte
    def ponte(self):
        """Tudo que a base emite vai para o rover, sem interpretar. Quem valida
        CRC e decide o que usar e o receptor."""
        b = r = None
        while not self.parar.is_set():
            try:
                if b is None:
                    b = serial.Serial(self.arg.base, self.baud_base, timeout=0.5)
                if r is None:
                    r = serial.Serial(self.arg.rover, self.baud_rover, timeout=0.5)
                d = b.read(1024)
                if d:
                    r.write(d)
                    self.bytes_rtcm += len(d)
            except Exception as e:
                self.log(f"ponte reabrindo: {e}")
                for o in (b, r):
                    if o:
                        try:
                            o.close()
                        except Exception:
                            pass
                b = r = None
                time.sleep(2)
        for o in (b, r):
            if o:
                try:
                    o.close()
                except Exception:
                    pass

    # --------------------------------------------------------- rover / NMEA
    def acompanha_rover(self):
        s, buf = None, b""
        t0 = time.time()
        while not self.parar.is_set():
            if s is None:
                try:
                    s = serial.Serial(self.arg.rover_nmea, self.baud_rover, timeout=1)
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
            if self.arquivo:
                self.arquivo.write(d)
            buf += d
            linhas = buf.split(b"\r\n")
            buf = linhas.pop()
            for ln in linhas:
                if ln[3:6] != b"GGA":
                    continue
                c = ln.split(b",")
                if len(c) <= 6:
                    continue
                try:
                    q = int(c[6] or 0)
                except ValueError:
                    continue
                if q == self.qualidade:
                    continue
                agora = time.time()
                if self.qualidade is None:
                    self.log(f"rover: comeca em {QUALIDADE.get(q, q)}")
                else:
                    self.log(f"rover: {QUALIDADE.get(self.qualidade, self.qualidade)} "
                             f"-> {QUALIDADE.get(q, q)}  "
                             f"(ficou {agora - self.desde:.0f} s no anterior)")
                self.qualidade, self.desde = q, agora
                self.marcos.setdefault(q, agora - t0)
                if q == 4:
                    self.log(f"    RTK FIXO em {agora - t0:.0f} s desde o inicio. "
                             "Daqui em diante a posicao e comparavel entre janelas.")
        if s:
            try:
                s.close()
            except Exception:
                pass

    # ----------------------------------------------------------------- roda
    def roda(self):
        if self.arg.diario:
            self.diario = open(self.arg.diario, "a", buffering=1, encoding="utf-8")
        self.log("=" * 64)
        self.prepara_base()

        s, self.baud_rover = abre(self.arg.rover_nmea or self.arg.rover,
                                  self.arg.baud_rover, self.log)
        if self.arg.highprec:
            self.log(f"NMEA de alta precisao no rover: {valset(s, [(NMEA_HIGHPREC, 1)])}"
                     "  (sem isso a GGA quantiza a posicao em ~1,85 cm)")
        s.close()

        if self.arg.gravar:
            self.arquivo = open(self.arg.gravar, "wb", buffering=0)
            self.log(f"gravando NMEA do rover em {self.arg.gravar}")

        threading.Thread(target=self.ponte, daemon=True).start()
        if self.arg.rover_nmea:
            threading.Thread(target=self.acompanha_rover, daemon=True).start()
        else:
            self.log("sem --rover-nmea: injetando correcao as cegas, "
                     "sem saber se o rover fixou")

        self.log(f"ponte {self.arg.base} -> {self.arg.rover} ligada. Ctrl+C encerra.")
        fim = time.time() + self.arg.duracao if self.arg.duracao else None
        try:
            while not self.parar.is_set():
                if fim and time.time() >= fim:
                    break
                if (self.arg.exigir_fixo and self.qualidade == 4
                        and self.arg.duracao is None):
                    pass
                time.sleep(1)
        except KeyboardInterrupt:
            self.log("Ctrl+C — encerrando em ordem")
        finally:
            self.encerra()

    def encerra(self):
        self.parar.set()
        time.sleep(2)
        self.log(f"{self.bytes_rtcm} bytes de RTCM entregues")
        if self.marcos:
            for q in sorted(self.marcos):
                self.log(f"    {QUALIDADE.get(q, q)}: {self.marcos[q]:.0f} s")
        if self.arg.exigir_fixo and 4 not in self.marcos:
            self.log("ATENCAO: o rover nunca chegou a RTK fixo. Posicoes medidas "
                     "em flutuante NAO sao comparaveis entre si — ao fixar, a "
                     "solucao salta.")
        if self.arquivo:
            self.arquivo.close()
        if self.diario:
            self.diario.close()


def coordenada(txt: str):
    try:
        lat, lon, alt = (float(x) for x in txt.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("esperado LAT,LON,ALT em graus e metros")
    return lat, lon, alt


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="exemplo:\n"
               "  python rtk_base.py --base COM20 --rover COM18 --rover-nmea COM17\n"
               "  python rtk_base.py --listar")
    p.add_argument("--listar", action="store_true",
                   help="mostra as portas de EVK-X20P vistas e sai")
    p.add_argument("--base", help="COM do receptor que vira base (por onde sai o RTCM)")
    p.add_argument("--rover", help="COM do rover que RECEBE a correcao")
    p.add_argument("--rover-nmea", help="COM do rover de onde se le NMEA; "
                                        "sem ela nao da para saber se fixou")
    p.add_argument("--uart-base", type=int, choices=(1, 2),
                   help="forca a UART da base, se a descricao do driver nao disser")
    p.add_argument("--baud-base", type=int, help="padrao: detecta 115200/38400/9600")
    p.add_argument("--baud-rover", type=int, help="padrao: detecta")
    p.add_argument("--survey-dur", type=int, default=120,
                   help="segundos minimos de survey-in (padrao 120)")
    p.add_argument("--survey-acc", type=float, default=5.0,
                   help="exatidao absoluta aceita, em metros (padrao 5,0). "
                        "Sob ceu obstruido ela estagina; afrouxe em vez de esperar")
    p.add_argument("--survey-max", type=int, default=900,
                   help="teto de espera pelo survey-in (padrao 900 s)")
    p.add_argument("--fixa", type=coordenada, metavar="LAT,LON,ALT",
                   help="pula o survey-in e usa uma coordenada conhecida; "
                        "e o unico jeito de ter exatidao absoluta boa")
    p.add_argument("--highprec", action="store_true",
                   help="liga a NMEA de alta precisao no rover (recomendado: "
                        "sem ela a GGA quantiza em ~1,85 cm)")
    p.add_argument("--gravar", type=Path, help="arquivo .nmea do rover")
    p.add_argument("--diario", type=Path, help="arquivo de log das transicoes")
    p.add_argument("--duracao", type=int, help="segundos e encerra (padrao: ate Ctrl+C)")
    p.add_argument("--intervalo", type=float, default=5.0,
                   help="periodo de consulta ao survey-in (padrao 5 s)")
    p.add_argument("--exigir-fixo", action="store_true", default=True,
                   help="avisa no fim se o rover nunca fixou (ligado por padrao)")
    arg = p.parse_args(argv)

    if arg.listar:
        achadas = portas_x20p()
        if not achadas:
            print("nenhum EVK-X20P encontrado")
            return 1
        for dev, desc in sorted(achadas):
            print(f"  {dev:8s} {desc}")
        return 0

    if not arg.base or not arg.rover:
        p.error("--base e --rover sao obrigatorios (ou use --listar)")
    if arg.base.upper() == arg.rover.upper():
        p.error("--base e --rover nao podem ser a mesma porta")

    rig = Rig(arg)
    # SIGTERM tambem: e o sinal que `timeout`, o gerenciador de tarefas e os
    # scripts de bancada mandam. Sem trata-lo, o processo morre sem fechar as
    # COM, e no Windows o handle vaza — a porta fica presa, sem dono, por
    # minutos. Foi assim que se perderam duas portas nesta bancada.
    for sinal in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sinal, lambda *_: rig.parar.set())
        except (ValueError, AttributeError):
            pass
    rig.roda()
    return 0


if __name__ == "__main__":
    sys.exit(main())
