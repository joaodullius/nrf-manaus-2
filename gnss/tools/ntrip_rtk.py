#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cliente NTRIP que injeta correcao no receptor e acompanha a convergencia.

CONFIGURACAO DO CASTER E DO MOUNTPOINT (os dois usados no curso)
----------------------------------------------------------------
  PointPerfect (u-blox) via Nordian -- PPP-RTK entregue como base virtual RTCM
      --caster services.nordian.com --porta-caster 2101 --mountpoint NEAR-RTCM-VRS
      exige GGA de volta (o servico gera a base virtual na posicao do rover);
      credencial de assinatura, teste limitado a 10 h; sem cobertura em Manaus.
  IBGE RBMC-IP -- estacao FISICA de referencia, RTCM legado (1004/1012/1006/1033)
      --caster <caster do IBGE> --porta-caster 2101 --mountpoint AMUA0   (Manaus, UEA)
                                                    --mountpoint POAL0   (Porto Alegre)
      cadastro gratuito no IBGE; nao exige GGA (nmea=0), mas envia-lo nao atrapalha.
  --credenciais aponta para um arquivo de DUAS linhas (usuario, senha) FORA do repo.
  --serial-rtcm e a porta de CONTROLE do X20P (UBX/RTCM); --serial-nmea, a de captura.

    python ntrip_rtk.py --caster services.nordian.com --porta-caster 2101 \
        --mountpoint NEAR-RTCM-VRS --credenciais <arquivo> \
        --serial-nmea COM17 --serial-rtcm COM18 --minutos 15 \
        --out ../capturas/rtk_sessao

Le o NMEA da porta de captura e escreve o RTCM na porta de controle. As duas
podem ser UARTs diferentes do mesmo receptor — no EVK-X20P sao a UART1 e a UART2,
e e isso que permite medir sem o u-center no meio.

Antes de conectar ao caster, o script confere na porta de controle se a UART
aceita RTCM3 (CFG-UARTxINPROT-RTCM3X). O padrao de fabrica e aceitar; se alguem
desligou, ele religa em RAM e avisa. Com --highprec liga tambem a NMEA de alta
precisao no rover, como o rtk_base_rover.py.

Muitos casters de rede exigem que o cliente envie um GGA de volta (campo `nmea=1`
na sourcetable): e assim que o servidor sabe onde gerar a estacao virtual. Este
cliente reenvia o ultimo GGA valido do proprio receptor a cada 10 s.

O arquivo de credenciais tem duas linhas: usuario e senha. Ele fica FORA do
repositorio.

Enquanto roda, imprime cada mudanca de qualidade do fix:
1 autonomo, 2 DGPS, 5 RTK flutuante, 4 RTK fixo.
"""
from __future__ import annotations

import argparse
import base64
import socket
import struct
import sys
import threading
import time
from pathlib import Path

import serial

from rtk_base_rover import ubx, fala, valset, monver, uart_da_porta, NMEA_HIGHPREC, TAM

# entrada de RTCM3 por UART: o padrao de fabrica e 1 (ligada), mas um receptor mexido
# pode estar com 0 e ai a correcao entra pela porta e o receptor a ignora, sem erro
INPROT_RTCM3X = {1: 0x10730004, 2: 0x10750004}

QUAL = {0: "sem fix", 1: "autonomo", 2: "DGPS", 4: "RTK FIXO", 5: "RTK flutuante", 6: "estimado"}


def tipos_rtcm(buf: bytes) -> dict:
    """Conta as mensagens RTCM3 do buffer, por numero de tipo."""
    tipos, i = {}, 0
    while i < len(buf) - 6:
        if buf[i] != 0xD3:
            i += 1
            continue
        tam = ((buf[i + 1] & 0x03) << 8) | buf[i + 2]
        if i + 3 + tam + 3 > len(buf):
            break
        m = buf[i + 3:i + 3 + tam]
        if len(m) >= 2:
            t = (m[0] << 4) | (m[1] >> 4)
            tipos[t] = tipos.get(t, 0) + 1
        i += 3 + tam + 3
    return tipos


def valget1(s: serial.Serial, chave: int, camada: int = 0):
    """Le uma chave numa camada; None se o receptor nao respondeu."""
    pl = struct.pack("<BBH", 0x00, camada, 0) + struct.pack("<I", chave)
    for cls, mid, d in fala(s, ubx(0x06, 0x8B, pl)):
        if (cls, mid) == (0x06, 0x8B) and len(d) >= 8:
            t = TAM.get((chave >> 28) & 0x7, 1)
            return int.from_bytes(d[8:8 + t], "little")
    return None


def prepara_rover(porta: str, baud: int, uart: int | None, highprec: bool) -> None:
    """Garante que a UART por onde o RTCM entra aceita RTCM3 (VALSET em RAM se
    nao aceitar) e, se pedido, liga a NMEA de alta precisao. Fecha a porta ao sair."""
    s = serial.Serial(porta, baud, timeout=0.3)
    try:
        if not monver(s):
            raise SystemExit(f"{porta}: nenhum receptor u-blox respondeu a {baud} bps")
        n = uart_da_porta(porta, uart)
        chave = INPROT_RTCM3X[n]
        v = valget1(s, chave)
        if v == 1:
            print(f"{porta} (UART{n}): entrada RTCM3 ja habilitada", flush=True)
        elif v is None:
            print(f"{porta} (UART{n}): nao consegui ler INPROT-RTCM3X; seguindo assim mesmo", flush=True)
        else:
            ok = valset(s, [(chave, 1)]) and valget1(s, chave) == 1
            print(f"{porta} (UART{n}): entrada RTCM3 estava desligada -> "
                  f"{'habilitada em RAM' if ok else 'FALHOU ao habilitar'}", flush=True)
            if not ok:
                raise SystemExit("sem entrada RTCM3 o rover ignora a correcao; "
                                 "restaure o padrao com x20p_default.py --aplicar")
        if highprec:
            ok = valset(s, [(NMEA_HIGHPREC, 1)])
            print(f"NMEA de alta precisao: {'ligada' if ok else 'FALHOU'}", flush=True)
    finally:
        s.close()


class Sessao:
    def __init__(self, a):
        self.a = a
        self.gga = None
        self.parar = threading.Event()
        self.t0 = time.time()
        self.bytes_rtcm = 0
        self.tipos = {}
        self.qual_atual = None
        self.marcos = {}

    def monitora_nmea(self, f_log):
        """Le a porta de captura: guarda o ultimo GGA e anota mudancas de qualidade."""
        s, buf = None, b""
        while not self.parar.is_set():
            if s is None:
                try:
                    s = serial.Serial(self.a.serial_nmea, self.a.baud, timeout=0.5)
                except Exception:
                    time.sleep(2); continue
            try:
                buf += s.read(4096)
            except Exception:
                s = None; continue
            linhas = buf.split(b"\r\n")
            buf = linhas.pop()
            for ln in linhas:
                if f_log:
                    f_log.write(ln + b"\r\n")
                if ln[3:6] != b"GGA":
                    continue
                self.gga = ln + b"\r\n"
                c = ln.split(b",")
                if len(c) < 7:
                    continue
                try:
                    q = int(c[6] or 0)
                except ValueError:
                    continue
                if q != self.qual_atual:
                    dt = time.time() - self.t0
                    self.qual_atual = q
                    self.marcos.setdefault(q, dt)
                    print(f"[{dt:7.1f}s] qualidade -> {QUAL.get(q, q)}"
                          f"   sats={c[7].decode()} HDOP={c[8].decode()}", flush=True)
        if s:
            try: s.close()
            except Exception: pass

    def roda(self):
        a = self.a
        user, senha = Path(a.credenciais).read_text(encoding="utf-8").split("\n")[:2]
        auth = base64.b64encode(f"{user}:{senha}".encode()).decode()

        prepara_rover(a.serial_rtcm, a.baud, a.uart_rtcm, a.highprec)

        f_log = open(a.out + ".nmea", "wb", buffering=0) if a.out else None
        threading.Thread(target=self.monitora_nmea, args=(f_log,), daemon=True).start()
        time.sleep(2.0)   # deixa aparecer um GGA antes de conectar

        req = (f"GET /{a.mountpoint} HTTP/1.1\r\nHost: {a.caster}:{a.porta_caster}\r\n"
               f"Ntrip-Version: Ntrip/2.0\r\nUser-Agent: NTRIP curso-gnss/1.0\r\n"
               f"Authorization: Basic {auth}\r\n\r\n")
        cs = socket.create_connection((a.caster, a.porta_caster), timeout=15)
        cs.sendall(req.encode())
        cs.settimeout(1.0)
        cab = b""
        # espera por PRAZO, nao por uma tentativa: o caster pode levar segundos para
        # responder, e desistir no primeiro timeout joga fora a conexao
        prazo = time.time() + 15
        while b"\r\n\r\n" not in cab and len(cab) < 8192 and time.time() < prazo:
            try:
                d = cs.recv(1024)
                if not d:
                    break
                cab += d
            except socket.timeout:
                continue
        linha = cab.split(b"\r\n")[0].decode("latin1", "replace")
        print(f"caster: {linha}", flush=True)
        if b"200" not in cab.split(b"\r\n")[0]:
            print(cab.decode("latin1", "replace")[:400], file=sys.stderr)
            self.parar.set(); return 1

        rs = serial.Serial(a.serial_rtcm, a.baud, timeout=0.5)
        sobra = cab.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in cab else b""
        if sobra:
            rs.write(sobra); self.bytes_rtcm += len(sobra)
        if self.gga:
            cs.sendall(self.gga)
            print(f"GGA enviado ao caster: {self.gga.decode('ascii','replace').strip()}", flush=True)

        fim, ultimo_gga = self.t0 + a.minutos * 60, time.time()
        try:
            while time.time() < fim:
                try:
                    d = cs.recv(8192)
                    if not d:
                        print("caster fechou a conexao", flush=True); break
                    rs.write(d)
                    self.bytes_rtcm += len(d)
                    for k, v in tipos_rtcm(d).items():
                        self.tipos[k] = self.tipos.get(k, 0) + v
                except socket.timeout:
                    pass
                if time.time() - ultimo_gga > 10 and self.gga:
                    try: cs.sendall(self.gga)
                    except Exception: pass
                    ultimo_gga = time.time()
        finally:
            self.parar.set()
            time.sleep(0.5)
            cs.close(); rs.close()
            if f_log: f_log.close()

        dur = time.time() - self.t0
        print(f"\nRTCM injetado: {self.bytes_rtcm} bytes em {dur:.0f} s "
              f"({self.bytes_rtcm/dur:.0f} B/s)")
        print("mensagens:", dict(sorted(self.tipos.items())))
        print("primeira vez em cada qualidade:")
        for q, dt in sorted(self.marcos.items(), key=lambda x: x[1]):
            print(f"   {QUAL.get(q, q):16} {dt:7.1f} s")
        return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--caster", required=True)
    p.add_argument("--porta-caster", type=int, default=2101)
    p.add_argument("--mountpoint", required=True)
    p.add_argument("--credenciais", required=True, help="arquivo com usuario e senha, fora do repo")
    p.add_argument("--serial-nmea", required=True, help="porta de onde sai o NMEA")
    p.add_argument("--serial-rtcm", required=True, help="porta por onde entra o RTCM")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--minutos", type=float, default=15.0)
    p.add_argument("--out", help="nome base para gravar o NMEA da sessao")
    p.add_argument("--uart-rtcm", type=int, choices=(1, 2),
                   help="forca qual UART do X20P e a --serial-rtcm, se a descricao do driver nao disser")
    p.add_argument("--highprec", action="store_true",
                   help="liga a NMEA de alta precisao no rover (sem ela a GGA quantiza em ~1,85 cm)")
    return Sessao(p.parse_args(argv)).roda()


if __name__ == "__main__":
    sys.exit(main())
