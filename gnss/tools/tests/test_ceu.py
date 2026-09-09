# -*- coding: utf-8 -*-
"""Leitura das GSV/GSA: onde cada satelite esta e qual entrou no calculo."""
import pytest

import nmea

# sentencas reais da bancada, com o campo de ID de sinal da NMEA 4.10 no fim
GSV_A = "$GPGSV,3,3,11,27,,,25,28,17,139,27,31,43,123,43,1*66"
GSA = "$GPGSA,A,3,01,02,03,28,31,,,,,,,,4.26,2.78,3.23,1*18"


def test_sentencas_de_referencia_tem_checksum_valido():
    assert nmea.checksum_ok(GSV_A)
    assert nmea.checksum_ok(GSA)


def test_gsv_separa_quem_tem_posicao():
    ceu = nmea.ler_ceu(GSV_A.encode())
    com = {v.prn: v for v in ceu["com_posicao"]}
    sem = {v.prn: v for v in ceu["sem_posicao"]}
    # 27 e ouvido (C/N0 25) mas sem orbita conhecida
    assert set(sem) == {27}
    assert sem[27].cn0 == 25 and sem[27].elev is None
    assert set(com) == {28, 31}
    assert (com[28].elev, com[28].azim, com[28].cn0) == (17, 139, 27)
    assert (com[31].elev, com[31].azim, com[31].cn0) == (43, 123, 43)


def test_id_de_sinal_nao_vira_satelite():
    """O '1' final e ID de sinal, nao um PRN — se entrasse, viraria um satelite fantasma."""
    ceu = nmea.ler_ceu(GSV_A.encode())
    todos = {v.prn for v in ceu["com_posicao"] + ceu["sem_posicao"]}
    assert todos == {27, 28, 31}


def test_gsv_sem_id_de_sinal():
    """Formato antigo, sem o campo extra: os blocos fecham em 4 exatos."""
    s = "$GPGSV,1,1,1,17,12,264,10"
    c = 0
    for ch in s[1:]:
        c ^= ord(ch)
    ceu = nmea.ler_ceu(f"{s}*{c:02X}".encode())
    assert len(ceu["com_posicao"]) == 1
    assert ceu["com_posicao"][0].prn == 17


def test_gsa_coleta_os_usados():
    ceu = nmea.ler_ceu(GSA.encode())
    assert ceu["usados"] == {'GP01': 1, 'GP02': 1, 'GP03': 1, 'GP28': 1, 'GP31': 1}


def test_cn0_zero_e_rastreado_sem_sinal():
    s = "$GPGSV,1,1,1,16,06,051,"
    c = 0
    for ch in s[1:]:
        c ^= ord(ch)
    v = nmea.ler_ceu(f"{s}*{c:02X}".encode())["com_posicao"][0]
    assert v.prn == 16 and v.elev == 6 and v.cn0 == 0.0


def test_resumo_agrega_e_calcula_fracao_de_uso():
    fluxo = "\r\n".join([GSV_A, GSA, GSV_A, GSA]).encode()
    r = nmea.resumo_ceu(nmea.ler_ceu(fluxo))
    assert set(r) == {'GP28', 'GP31'}   # so os que tem posicao entram no resumo
    assert r["GP31"]["visadas"] == 2
    assert r["GP31"]["elev_med"] == pytest.approx(43)
    assert r["GP31"]["cn0_med"] == pytest.approx(43)
    assert r["GP31"]["usado_em"] == 2
    assert r["GP31"]["fracao_usado"] == pytest.approx(1.0)


def test_resumo_marca_quem_nunca_entra_na_solucao():
    """PRN 17 aparece no ceu mas nunca na GSA — o caso do satelite obstruido."""
    gsv = "$GPGSV,1,1,1,17,12,264,10"
    c = 0
    for ch in gsv[1:]:
        c ^= ord(ch)
    fluxo = "\r\n".join([f"{gsv}*{c:02X}", GSA]).encode()
    r = nmea.resumo_ceu(nmea.ler_ceu(fluxo))
    assert r["GP17"]["usado_em"] == 0
    assert r["GP17"]["fracao_usado"] == 0.0


def test_ceu_vazio():
    ceu = nmea.ler_ceu(b"$GPGGA,013030.09,3001.73774,S,05112.74184,W,1,04,3.86,36.89,M,,M,,*43")
    assert ceu == {"com_posicao": [], "sem_posicao": [],
                   "abaixo_horizonte": [], "usados": {}}
    assert nmea.resumo_ceu(ceu) == {}


def _ck(s):
    c = 0
    for ch in s[1:]:
        c ^= ord(ch)
    return "%s*%02X" % (s, c)


def test_constelacoes_diferentes_nao_se_misturam():
    """GPS 7 e Galileo 7 sao satelites distintos — o X20P e multiconstelacao."""
    fluxo = (_ck("$GPGSV,1,1,1,7,45,120,44,1") + chr(13) + chr(10) +
             _ck("$GAGSV,1,1,1,7,20,300,38,7")).encode()
    r = nmea.resumo_ceu(nmea.ler_ceu(fluxo))
    assert set(r) == {"GP07", "GA07"}
    assert r["GP07"]["elev_med"] == pytest.approx(45)
    assert r["GA07"]["elev_med"] == pytest.approx(20)


def test_gsa_com_talker_gn_usa_o_systemid():
    """Com talker GN a GSA mistura constelacoes; o systemId do fim desempata."""
    ceu = nmea.ler_ceu(_ck("$GNGSA,A,3,07,,,,,,,,,,,,1.5,0.9,1.2,3").encode())
    assert ceu["usados"] == {"GA07": 1}      # systemId 3 = Galileo
    ceu = nmea.ler_ceu(_ck("$GNGSA,A,3,07,,,,,,,,,,,,1.5,0.9,1.2,1").encode())
    assert ceu["usados"] == {"GP07": 1}      # systemId 1 = GPS


def test_gga_de_talker_gn_e_qualidade_rtk():
    """O X20P emite $GNGGA e qualidade 4 (RTK fixo) / 5 (flutuante)."""
    fx = nmea.ler_fluxo(_ck("$GNGGA,120000.00,3001.73774,S,05112.74184,W,4,12,0.60,36.89,M,,M,,").encode())
    assert len(fx) == 1 and fx[0].qualidade == 4
    assert nmea.QUALIDADE[4] == "RTK fixo"


def test_satelite_abaixo_do_horizonte_sai_do_ceu():
    """O modem preve pelo almanaque e reporta elevacao negativa; isso nao e ceu."""
    ceu = nmea.ler_ceu(_ck("$GPGSV,1,1,1,29,-39,224,11,1").encode())
    assert ceu["com_posicao"] == []
    assert len(ceu["abaixo_horizonte"]) == 1
    assert ceu["abaixo_horizonte"][0].elev == -39
    assert nmea.resumo_ceu(ceu) == {}
