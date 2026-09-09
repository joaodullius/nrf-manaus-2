# -*- coding: utf-8 -*-
"""Parsing de NMEA e as estatisticas do Deviation Map."""
import math

import pytest

import nmea

# sentenca real da bancada, com o \r\r\n que o sample do nRF9151 emite
GGA = "$GPGGA,013030.09,3001.73774,S,05112.74184,W,1,04,3.86,36.89,M,,M,,*43"


def test_checksum():
    assert nmea.checksum_ok(GGA)
    assert not nmea.checksum_ok(GGA[:-2] + "00")
    assert not nmea.checksum_ok("$GPGGA,sem asterisco")


def test_grau_ddmm_para_decimal():
    assert nmea._grau("3001.73774", "S") == pytest.approx(-30.0289623, abs=1e-7)
    assert nmea._grau("05112.74184", "W") == pytest.approx(-51.2123640, abs=1e-7)
    assert nmea._grau("3001.73774", "N") == pytest.approx(30.0289623, abs=1e-7)
    assert nmea._grau("", "N") is None


def test_le_fixo_com_cr_duplo():
    fx = nmea.ler_fluxo((GGA + "\r\r\n").encode())
    assert len(fx) == 1
    assert fx[0].qualidade == 1 and fx[0].sats == 4
    assert fx[0].alt_m == pytest.approx(36.89)
    assert fx[0].hdop == pytest.approx(3.86)


def test_descarta_sem_fix_e_checksum_ruim():
    sem_fix = "$GPGGA,000016.17,,,,,0,,99.99,,M,,M,,*67"
    ruim = GGA[:-2] + "FF"
    fluxo = "\r\n".join([sem_fix, ruim, GGA]).encode()
    assert len(nmea.ler_fluxo(fluxo)) == 1
    # sem exigir checksum, a sentenca corrompida entra
    assert len(nmea.ler_fluxo(fluxo, exigir_checksum=False)) == 2


def test_metros_por_grau():
    m_lat, m_lon = nmea.metros_por_grau(0.0)
    assert m_lat == pytest.approx(110574, abs=60)
    assert m_lon == pytest.approx(111320, abs=60)
    # no equador o grau de longitude e maior; a 60 graus, cai pela metade
    assert nmea.metros_por_grau(60.0)[1] == pytest.approx(m_lon / 2, rel=0.01)


def test_percentil_bate_com_numpy():
    np = pytest.importorskip("numpy")
    v = sorted([0.1, 4.0, 1.5, 2.25, 9.0, 3.5, 0.75])
    for p in (0.5, 0.68, 0.95, 0.0, 1.0):
        assert nmea._percentil(v, p) == pytest.approx(np.percentile(v, p * 100))


def _fluxo(pontos, qualidade=1):
    """Monta GGA validos a partir de (lat, lon) em graus decimais."""
    linhas = []
    for i, (la, lo) in enumerate(pontos):
        g_la, g_lo = abs(la), abs(lo)
        s = (f"GPGGA,{i:06d}.00,"
             f"{int(g_la):02d}{(g_la % 1) * 60:08.5f},{'N' if la >= 0 else 'S'},"
             f"{int(g_lo):03d}{(g_lo % 1) * 60:08.5f},{'E' if lo >= 0 else 'W'},"
             f"{qualidade},07,1.20,10.0,M,,M,,")
        c = 0
        for ch in s:
            c ^= ord(ch)
        linhas.append(f"${s}*{c:02X}")
    return "\r\n".join(linhas).encode()


def test_estatisticas_contra_a_media():
    # quatro pontos simetricos em torno de um centro
    d = 0.00001
    centro = (-30.0, -51.0)
    pts = [(centro[0] + d, centro[1]), (centro[0] - d, centro[1]),
           (centro[0], centro[1] + d), (centro[0], centro[1] - d)]
    st = nmea.estatisticas(nmea.ler_fluxo(_fluxo(pts)))
    assert st["n"] == 4
    assert st["referencia"]["tipo"] == "media"
    assert st["referencia"]["lat"] == pytest.approx(centro[0], abs=1e-9)
    # simetrico: os desvios medios zeram
    assert st["desvio_ns_m"]["avg"] == pytest.approx(0.0, abs=1e-6)
    assert st["desvio_ew_m"]["avg"] == pytest.approx(0.0, abs=1e-6)
    h = st["hpe_m"]
    assert h["cep50"] <= h["cep68"] <= h["cep95"] <= h["max"]
    assert st["qualidades"] == {"autonomo": 4}


def test_referencia_explicita_mede_exatidao():
    pts = [(-30.0, -51.0)] * 3
    # 1e-4 grau de latitude ~ 11 m ao norte da referencia
    st = nmea.estatisticas(nmea.ler_fluxo(_fluxo(pts)),
                           referencia=(-30.0001, -51.0))
    assert st["referencia"]["tipo"] == "referencia"
    assert st["desvio_ns_m"]["avg"] == pytest.approx(11.06, abs=0.2)
    assert st["hpe_m"]["cep50"] == pytest.approx(11.06, abs=0.2)


def test_qualidades_nomeadas():
    st = nmea.estatisticas(nmea.ler_fluxo(_fluxo([(-30.0, -51.0)] * 2, qualidade=4)))
    assert st["qualidades"] == {"RTK fixo": 2}


def test_log_sem_fix_e_erro():
    with pytest.raises(ValueError, match="nenhum fix"):
        nmea.estatisticas([])
