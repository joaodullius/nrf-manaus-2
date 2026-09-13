#!/usr/bin/env python3
"""Compoe uma passada LEO completa, do nascer ao por, a partir de trechos de traces reais.

Saida: um trace .txt no formato do nrf_trace (data e hora UTC por linha), que o
plot_snr.py desenha como qualquer trace real. Cada trecho real mantem os seus
intervalos internos; so a posicao de cada trecho na passada e escolhida aqui,
pela elevacao do satelite calculada por SGP4 a partir de um TLE local. O ciclo
de busca de celula entre o modem ligar e a celula aparecer e gerado, e cada
linha gerada leva a marca [sintetico].

Uso:
    python compoe_passada.py
    python ../tools/plot_snr.py passada_sintetica_SIOT1.txt -s SATELIOT_1 \
        --tle-file tle/sateliot_1_20260913.tle --no-open --out-dir plots
"""
import argparse
import os
import re
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
TLE = os.path.join(HERE, "tle", "sateliot_1_20260913.tle")
SAIDA = os.path.join(HERE, "passada_sintetica_SIOT1.txt")

# Observador e passada de referencia: a de 07/09 sobre Porto Alegre (KY).
LAT, LON = -30.028827, -51.213172
CENTRO = datetime(2026, 9, 7, 2, 28, tzinfo=timezone.utc)

RE_NOVO = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}\.\d+) (.*)$")
RE_ANTIGO = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d+) (.*)$")
MARCA = " [sintetico]"


def _dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)


# (arquivo, inicio, fim, linhas a descartar por substring, posicao)
# posicao: ("apos_nascer", s) | ("elevacao", graus, "subindo"|"descendo") | ("apos_anterior", s)
TRECHOS = [
    # modem liga (AT+CFUN=21) e procura a celula durante 8 s reais
    ("20260907_0228_SIOT1_BRA_KY.txt", "2026-09-07 02:28:35.340000", "2026-09-07 02:28:43.080000",
     (), ("apos_nascer", 20.0)),
    # MIB, SIB1, SI, PRACH/RAR, Attach Request/Accept, +CEREG: 5 (o UL 10 ms depois fica de fora)
    ("20260907_0228_SIOT1_BRA_KY.txt", "2026-09-07 02:28:43.080000", "2026-09-07 02:28:54.765000",
     (), ("elevacao", 35.0, "subindo")),
    # envio UL e resposta DL do servidor
    ("20260909_0233_SIOT1_BRA_KY.txt", "2026-09-09 02:33:39.595000", "2026-09-09 02:33:41.100000",
     (), ("apos_anterior", 3.0)),
    # perda da celula ao descer: T310, +CSCON: 0, NO_CELL (trace antigo, sem data)
    ("20260412_1349_SIOT3_BRA.txt", "2026-04-12 14:53:59.100000", "2026-04-12 14:54:01.500000",
     (), ("elevacao", 8.0, "descendo")),
]
GNSS_ORIGEM = ("20260907_0228_SIOT1_BRA_KY.txt", "GNSS_POS_REP_PV")


def ler_linhas(nome, data_padrao):
    """Devolve [(datetime UTC, resto da linha)] de um trace novo (com data) ou antigo (sem data)."""
    out = []
    with open(os.path.join(DATA, nome), encoding="utf-8", errors="replace") as fh:
        for linha in fh:
            linha = linha.rstrip("\n")
            m = RE_NOVO.match(linha)
            if m:
                out.append((_dt(f"{m.group(1)} {m.group(2)}"), m.group(3)))
                continue
            m = RE_ANTIGO.match(linha)
            if m:
                out.append((_dt(f"{data_padrao} {m.group(1)}"), m.group(2)))
    return out


def geometria(tle_path, lat, lon, centro):
    """Nascer, pico, por e elevacao a cada segundo da passada que contem `centro`."""
    from skyfield.api import EarthSatellite, load, wgs84

    with open(tle_path, encoding="ascii") as fh:
        linhas = [l.strip() for l in fh if l.strip()]
    nome, l1, l2 = (linhas[0], linhas[1], linhas[2]) if len(linhas) == 3 else ("SAT", linhas[0], linhas[1])
    ts = load.timescale()
    sat = EarthSatellite(l1, l2, nome, ts)
    obs = wgs84.latlon(lat, lon)
    t0 = ts.from_datetime(centro - timedelta(minutes=30))
    t1 = ts.from_datetime(centro + timedelta(minutes=30))
    tempos, eventos = sat.find_events(obs, t0, t1, altitude_degrees=0.0)
    nascer = pico = por = None
    for ti, ev in zip(tempos, eventos):
        d = ti.utc_datetime()
        if ev == 0 and d <= centro:
            nascer = d
        elif ev == 1 and nascer is not None and pico is None and d >= nascer:
            pico = d
        elif ev == 2 and pico is not None and por is None and d >= pico:
            por = d
    if None in (nascer, pico, por):
        raise SystemExit(f"nenhuma passada completa em torno de {centro}")
    amostras = []
    n = int((por - nascer).total_seconds()) + 1
    for i in range(n):
        d = nascer + timedelta(seconds=i)
        alt, _, _ = (sat - obs).at(ts.from_datetime(d)).altaz()
        amostras.append((d, alt.degrees))
    return nascer, pico, por, amostras


def instante(posicao, nascer, pico, amostras, fim_anterior):
    tipo = posicao[0]
    if tipo == "apos_nascer":
        return nascer + timedelta(seconds=posicao[1])
    if tipo == "apos_anterior":
        return fim_anterior + timedelta(seconds=posicao[1])
    if tipo == "elevacao":
        _, alvo, ramo = posicao
        cand = [(d, el) for d, el in amostras if (d <= pico) == (ramo == "subindo")]
        return min(cand, key=lambda p: abs(p[1] - alvo))[0]
    raise ValueError(posicao)


def compor(tle_path=TLE, lat=LAT, lon=LON, centro=CENTRO):
    nascer, pico, por, amostras = geometria(tle_path, lat, lon, centro)
    saida = []  # (datetime, texto, origem)

    gnss = [r for r in ler_linhas(GNSS_ORIGEM[0], "2026-09-07") if GNSS_ORIGEM[1] in r[1]]
    saida.append((nascer - timedelta(seconds=120), gnss[0][1], GNSS_ORIGEM[0]))

    fim_anterior = None
    fim_busca_real = None
    for nome, ini, fim, descartar, posicao in TRECHOS:
        data_padrao = ini[:10]
        linhas = [(d, t) for d, t in ler_linhas(nome, data_padrao)
                  if _dt(ini) <= d <= _dt(fim) and not any(x in t for x in descartar)]
        if not linhas:
            raise SystemExit(f"{nome}: nenhuma linha entre {ini} e {fim}")
        inicio = instante(posicao, nascer, pico, amostras, fim_anterior)
        base = linhas[0][0]
        for d, t in linhas:
            saida.append((inicio + (d - base), t, nome))
        fim_anterior = inicio + (linhas[-1][0] - base)
        if fim_busca_real is None:
            fim_busca_real = fim_anterior
        elif posicao[0] == "elevacao" and posicao[2] == "subindo":
            # busca de celula gerada: do fim da busca real ate o MIB, um ciclo a cada 2 s
            d = fim_busca_real + timedelta(seconds=2)
            while d < inicio - timedelta(seconds=1):
                saida.append((d, "L23_DEFAULT_INFO_RRCSTATECHANGEEVENT RRC State: 1 (ERRC_CNTRL_RRC_NO_CELL)" + MARCA, "gerado"))
                d += timedelta(seconds=2)

    saida.sort(key=lambda r: r[0])
    origens = sorted({o for _, _, o in saida if o != "gerado"})
    cab = ("# sintetico: passada de " + nascer.strftime("%Y-%m-%d %H:%M:%S") + " a "
           + por.strftime("%H:%M:%S") + " UTC (SGP4, TLE " + os.path.basename(tle_path)
           + "); trechos reais de " + ", ".join(origens) + "; linhas geradas levam" + MARCA)
    return cab, saida, (nascer, pico, por)


def escrever(caminho, cab, saida):
    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(cab + "\n")
        for d, t, _ in saida:
            fh.write(d.strftime("%Y-%m-%d %H:%M:%S.%f") + " " + t + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tle", default=TLE)
    ap.add_argument("--out", default=SAIDA)
    a = ap.parse_args()
    cab, saida, (nascer, pico, por) = compor(a.tle)
    escrever(a.out, cab, saida)
    gerados = sum(1 for _, _, o in saida if o == "gerado")
    print(f"{a.out}: {len(saida)} linhas ({gerados} geradas); nascer {nascer:%H:%M:%S}, "
          f"pico {pico:%H:%M:%S}, por {por:%H:%M:%S} UTC")


if __name__ == "__main__":
    main()
