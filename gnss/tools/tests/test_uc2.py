# -*- coding: utf-8 -*-
"""O contendor .uc2: layout, ida e volta, e o indice do fim."""
import struct

import pytest

import uc2


def registros():
    return [uc2.Registro(0, b"$GPGGA,um*00\r\n"),
            uc2.Registro(7, b"$GPRMC,dois*00\r\n"),
            uc2.Registro(1013, b"\xb5b\x06\x8b\x00\x00")]


def test_ida_e_volta(tmp_path):
    p = uc2.escrever(tmp_path / "x.uc2", registros(), device_name="COM9")
    meta, lidos = uc2.ler(p)
    assert meta["deviceName"] == "COM9"
    assert meta["deviceId"] == "serial-COM9"
    assert meta["logType"] == "timestamped"
    assert [(r.ts_ms, r.dados) for r in lidos] == [(r.ts_ms, r.dados) for r in registros()]


def test_bruto_concatena(tmp_path):
    p = uc2.escrever(tmp_path / "x.uc2", registros(), device_name="COM9")
    assert uc2.bruto(p) == b"".join(r.dados for r in registros())


def test_layout_do_cabecalho(tmp_path):
    p = uc2.escrever(tmp_path / "x.uc2", registros(), device_name="COM9")
    d = p.read_bytes()
    magia, versao, z1, fim, z2, tam_json = struct.unpack("<6I", d[:24])
    assert magia == 0x3C613A08
    assert (versao, z1, z2) == (1, 0, 0)
    # a secao de dados termina onde o indice comeca
    assert fim == len(d) - 12 * len(registros())
    assert d[24:24 + tam_json].startswith(b'{"startTime"')


def test_indice_aponta_para_os_registros(tmp_path):
    p = uc2.escrever(tmp_path / "x.uc2", registros(), device_name="COM9")
    d = p.read_bytes()
    fim, tam_json = struct.unpack("<I", d[12:16])[0], struct.unpack("<I", d[20:24])[0]
    # offsets reais, varrendo a secao de dados
    off, reais = 24 + tam_json, []
    while off < fim:
        ts, tam = struct.unpack("<II", d[off:off + 8])
        reais.append((ts, off))
        off += 8 + tam
    indice = [struct.unpack("<III", d[fim + i * 12:fim + (i + 1) * 12])
              for i in range(len(reais))]
    assert [(ts, o) for ts, o, _ in indice] == reais
    assert all(z == 0 for _, _, z in indice)


def test_recusa_arquivo_que_nao_e_uc2(tmp_path):
    p = tmp_path / "nao.uc2"
    p.write_bytes(b"$GPGGA,isso e nmea cru*00\r\n" * 4)
    with pytest.raises(ValueError, match="nao e um .uc2"):
        uc2.ler(p)


def test_arquivo_sem_registros(tmp_path):
    p = uc2.escrever(tmp_path / "vazio.uc2", [], device_name="COM1")
    meta, lidos = uc2.ler(p)
    assert lidos == []
    assert meta["version"] == 1
