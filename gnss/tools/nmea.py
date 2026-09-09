#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le NMEA e calcula as estatisticas de desvio do u-center — codigo do curso.

Aceita fluxo cru (.nmea, .ubx) e o contendor do u-center 2 (.uc2). De cada
sentenca GGA tira posicao, qualidade do fix, satelites e HDOP; e devolve o mesmo
painel que o u-center mostra no Deviation Map, com CEP50 e CEP95 no centro.

A qualidade do GGA (campo 6) e o que separa os tres degraus da escada:

    1  autonomo          o pe da escada: nRF9151 e X20P sem correcao
    2  DGPS/SBAS
    4  RTK fixo          ambiguidades resolvidas — centimetros
    5  RTK flutuante     correcao chegando, ambiguidades ainda nao resolvidas

Desvio contra a MEDIA mede precisao (o espalhamento da nuvem). Desvio contra uma
coordenada de referencia conhecida mede exatidao (onde a nuvem esta). Sao coisas
diferentes: um receptor pode ser preciso e estar 40 m fora do lugar.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from pathlib import Path

QUALIDADE = {
    0: "sem fix",
    1: "autonomo",
    2: "DGPS",
    4: "RTK fixo",
    5: "RTK flutuante",
    6: "estimado",
}


@dataclass
class Fix:
    hora: str
    lat: float
    lon: float
    alt_m: float | None
    qualidade: int
    sats: int | None
    hdop: float | None


def _grau(campo: str, hemi: str) -> float | None:
    """ddmm.mmmm + hemisferio -> graus decimais."""
    if not campo:
        return None
    ponto = campo.find(".")
    if ponto < 3:
        return None
    g = float(campo[:ponto - 2])
    m = float(campo[ponto - 2:])
    v = g + m / 60.0
    return -v if hemi in ("S", "W") else v


def checksum_ok(sentenca: str) -> bool:
    if "*" not in sentenca:
        return False
    corpo, _, ck = sentenca[1:].partition("*")
    c = 0
    for ch in corpo:
        c ^= ord(ch)
    return f"{c:02X}" == ck.strip().upper()[:2]


def ler_fluxo(dados: bytes, *, exigir_checksum: bool = True) -> list[Fix]:
    """Extrai os fixes das sentencas GGA de um fluxo cru."""
    fixes = []
    for linha in dados.split(b"\n"):
        s = linha.strip().decode("ascii", "ignore")
        if len(s) < 7 or not s.startswith("$") or s[3:6] != "GGA":
            continue
        if exigir_checksum and not checksum_ok(s):
            continue
        c = s.split("*")[0].split(",")
        if len(c) < 10:
            continue
        lat, lon = _grau(c[2], c[3]), _grau(c[4], c[5])
        if lat is None or lon is None:
            continue
        try:
            q = int(c[6] or 0)
        except ValueError:
            continue
        if q == 0:
            continue
        fixes.append(Fix(
            hora=c[1],
            lat=lat, lon=lon,
            alt_m=float(c[9]) if c[9] else None,
            qualidade=q,
            sats=int(c[7]) if c[7] else None,
            hdop=float(c[8]) if c[8] else None,
        ))
    return fixes


def ler_arquivo(caminho: Path, **kw) -> list[Fix]:
    """Le .nmea/.ubx cru ou .uc2 do u-center 2."""
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".uc2":
        import uc2
        return ler_fluxo(uc2.bruto(caminho), **kw)
    return ler_fluxo(caminho.read_bytes(), **kw)


def metros_por_grau(lat_deg: float) -> tuple[float, float]:
    """(metros por grau de latitude, metros por grau de longitude) no WGS84."""
    f = math.radians(lat_deg)
    m_lat = (111132.92 - 559.82 * math.cos(2 * f)
             + 1.175 * math.cos(4 * f) - 0.0023 * math.cos(6 * f))
    m_lon = (111412.84 * math.cos(f) - 93.5 * math.cos(3 * f)
             + 0.118 * math.cos(5 * f))
    return m_lat, m_lon


def _painel(v: list[float]) -> dict:
    return {
        "min": min(v), "max": max(v),
        "avg": statistics.fmean(v),
        "std": statistics.stdev(v) if len(v) > 1 else 0.0,
    }


def _percentil(ordenado: list[float], p: float) -> float:
    """Percentil com interpolacao linear, como o numpy faz por padrao."""
    if len(ordenado) == 1:
        return ordenado[0]
    i = (len(ordenado) - 1) * p
    baixo = math.floor(i)
    alto = math.ceil(i)
    if baixo == alto:
        return ordenado[baixo]
    return ordenado[baixo] * (alto - i) + ordenado[alto] * (i - baixo)


def estatisticas(fixes: list[Fix], referencia: tuple[float, float] | None = None) -> dict:
    """O painel do Deviation Map: HPE com CEP50/68/95, e os desvios N-S e E-W.

    Sem referencia, usa a media das posicoes — e a medida de PRECISAO, que e o
    que o u-center mostra por padrao. Com referencia, vira medida de EXATIDAO.
    """
    if not fixes:
        raise ValueError("nenhum fix no log")
    lats = [f.lat for f in fixes]
    lons = [f.lon for f in fixes]
    if referencia is None:
        ref_lat, ref_lon = statistics.fmean(lats), statistics.fmean(lons)
        tipo = "media"
    else:
        ref_lat, ref_lon = referencia
        tipo = "referencia"

    m_lat, m_lon = metros_por_grau(ref_lat)
    norte = [(la - ref_lat) * m_lat for la in lats]
    leste = [(lo - ref_lon) * m_lon for lo in lons]
    hpe = [math.hypot(n, e) for n, e in zip(norte, leste)]
    ord_hpe = sorted(hpe)

    alts = [f.alt_m for f in fixes if f.alt_m is not None]
    por_qual = {}
    for f in fixes:
        por_qual[f.qualidade] = por_qual.get(f.qualidade, 0) + 1

    return {
        "n": len(fixes),
        "referencia": {"tipo": tipo, "lat": ref_lat, "lon": ref_lon},
        "hpe_m": {**_painel(hpe),
                  "cep50": _percentil(ord_hpe, 0.50),
                  "cep68": _percentil(ord_hpe, 0.68),
                  "cep95": _percentil(ord_hpe, 0.95)},
        "desvio_ns_m": _painel(norte),
        "desvio_ew_m": _painel(leste),
        "altitude_m": _painel(alts) if alts else None,
        "qualidades": {QUALIDADE.get(k, str(k)): v for k, v in sorted(por_qual.items())},
        "hdop": _painel([f.hdop for f in fixes if f.hdop is not None]) or None,
        "sats": _painel([float(f.sats) for f in fixes if f.sats is not None]) or None,
        "_norte_m": norte,
        "_leste_m": leste,
    }


@dataclass
class Visada:
    """Uma linha de visada para um satelite, como a GSV reporta."""
    prn: int
    elev: float | None   # graus acima do horizonte; 90 = no zenite
    azim: float | None   # graus a partir do norte, sentido horario
    cn0: float           # dB-Hz; 0 significa rastreado sem sinal utilizavel


def _campos_gsv(c):
    """Os blocos de 4 campos (prn, elev, azim, cn0) de uma GSV.

    A NMEA 4.10 acrescentou um campo de ID de sinal no fim, que a sentenca do
    nRF9151 traz. Detecta pela sobra ao dividir o corpo por 4.
    """
    corpo = c[4:]
    if len(corpo) % 4 == 1:
        corpo = corpo[:-1]
    return [corpo[i:i + 4] for i in range(0, len(corpo), 4)]


def ler_ceu(dados: bytes, *, exigir_checksum: bool = True) -> dict:
    """Extrai as visadas das GSV e os satelites usados no calculo, das GSA.

    Separa as visadas COM posicao das SEM: o receptor as vezes ouve um satelite
    antes de saber onde ele esta, e as duas situacoes contam coisas diferentes
    sobre o ceu. Um satelite alto e fraco e obstrucao; um satelite ouvido sem
    orbita conhecida e so falta de tempo.
    """
    com_pos, sem_pos, usados = [], [], {}
    for linha in dados.splitlines():
        s = linha.strip().decode("ascii", "ignore")
        if len(s) < 7 or not s.startswith("$"):
            continue
        if exigir_checksum and not checksum_ok(s):
            continue
        tipo, c = s[3:6], s.split("*")[0].split(",")
        if tipo == "GSV" and len(c) > 4:
            for b in _campos_gsv(c):
                if len(b) < 4 or not b[0]:
                    continue
                v = Visada(int(b[0]),
                           float(b[1]) if b[1] else None,
                           float(b[2]) if b[2] else None,
                           float(b[3]) if b[3] else 0.0)
                alvo = com_pos if v.elev is not None and v.azim is not None else sem_pos
                alvo.append(v)
        elif tipo == "GSA" and len(c) > 14:
            for prn in c[3:15]:
                if prn:
                    usados[int(prn)] = usados.get(int(prn), 0) + 1
    return {"com_posicao": com_pos, "sem_posicao": sem_pos, "usados": usados}


def resumo_ceu(ceu: dict) -> dict:
    """Agrega por satelite: onde ficou no ceu, com que forca, e quanto foi usado."""
    por_prn = {}
    for v in ceu["com_posicao"]:
        d = por_prn.setdefault(v.prn, {"elev": [], "azim": [], "cn0": []})
        d["elev"].append(v.elev)
        d["azim"].append(v.azim)
        d["cn0"].append(v.cn0)
    epocas = max(ceu["usados"].values(), default=0)
    saida = {}
    for prn, d in sorted(por_prn.items()):
        usos = ceu["usados"].get(prn, 0)
        saida[prn] = {
            "elev_med": statistics.fmean(d["elev"]),
            "azim_med": statistics.fmean(d["azim"]),
            "cn0_med": statistics.fmean(d["cn0"]),
            "cn0_max": max(d["cn0"]),
            "visadas": len(d["elev"]),
            "usado_em": usos,
            "fracao_usado": usos / epocas if epocas else 0.0,
        }
    return saida
