# -*- coding: utf-8 -*-
import math
import numpy as np
import pytest

from conftest import synthetic_comb, write_procedure
import cs_csv
import cs_de_numpy as de
import cs_compare


@pytest.fixture
def captura_3m(tmp_path):
    p = tmp_path / "3m.csv"
    comb = synthetic_comb(3.0)
    fw = (de.ifft_m(comb), de.phase_slope_m(comb), de.rtt_m(40, 1))
    with open(p, "w") as f:
        for k in range(3):
            write_procedure(f, 10 + k, comb, fw=fw)
        write_procedure(f, 13, synthetic_comb(0.7), tq=0, fw=fw)   # tone quality BAD: fora das estatisticas
    return p


def test_summarize_reproduces_firmware(captura_3m):
    rows = cs_compare.summarize(cs_csv.read_procedures(captura_3m))
    assert [r["counter"] for r in rows] == [10, 11, 12, 13]
    for r in rows[:3]:
        assert abs(r["d_ifft"]) < 0.02            # NumPy == firmware (o CSV tem 3 casas)
        assert r["ps_np"] == pytest.approx(3.0, abs=0.01)
        assert r["rtt_np"] == pytest.approx(2.998, abs=0.001)
        assert r["music"] == pytest.approx(3.0, abs=0.2)


def test_stats_skip_bad_tone_quality(captura_3m):
    rows = cs_compare.summarize(cs_csv.read_procedures(captura_3m))
    st = cs_compare.stats(rows)
    assert st["music"][2] == 3                    # n = so as tres com tq == 1
    assert st["music"][0] == pytest.approx(3.0, abs=0.2)
    assert st["ifft_fw"][1] == pytest.approx(0.0, abs=1e-9)


def test_summarize_two_antenna_paths(tmp_path):
    p = tmp_path / "2ap.csv"
    comb = synthetic_comb(3.0)
    fw = (de.ifft_m(comb), de.phase_slope_m(comb), de.rtt_m(40, 1))
    with open(p, "w") as f:
        write_procedure(f, 20, comb, fw=fw, ap=0)
        write_procedure(f, 20, comb * np.exp(1j * 0.8), fw=(2.9, 3.0, 2.998), ap=1)
        write_procedure(f, 21, comb, fw=fw, ap=0)
        write_procedure(f, 21, comb, fw=fw, tq=0, ap=1)   # um caminho ruim derruba a procedure
    rows = cs_compare.summarize(cs_csv.read_procedures(p))
    assert [r["counter"] for r in rows] == [20, 21]      # uma linha por procedure, nao por ap
    assert rows[0]["tq"] == 1 and rows[1]["tq"] == 0
    assert rows[0]["ifft_ap1"] == pytest.approx(2.9)
    assert rows[0]["music_ap1"] == pytest.approx(3.0, abs=0.2)
    assert rows[0]["music_2ap"] == pytest.approx(3.0, abs=0.2)
    st = cs_compare.stats(rows)
    assert st["music_2ap"][2] == 1


def test_summarize_one_path_leaves_extra_columns_nan(captura_3m):
    rows = cs_compare.summarize(cs_csv.read_procedures(captura_3m))
    assert all(np.isnan(r["music_2ap"]) for r in rows)
    assert cs_compare.stats(rows)["music_2ap"][2] == 0


def test_escolhe_ifft_min_pega_o_mais_curto():
    class P:
        def __init__(self, d):
            self.fw = {"ifft": d}
    assert cs_compare.escolhe_ifft_min([P(4.8), P(5.6)]) == pytest.approx(4.8)
    assert cs_compare.escolhe_ifft_min([P(float("nan")), P(5.6)]) == pytest.approx(5.6)
    assert np.isnan(cs_compare.escolhe_ifft_min([P(float("nan"))]))


def test_escolhe_ifft_potencia_pega_o_canal_mais_forte():
    class P:
        def __init__(self, d):
            self.fw = {"ifft": d}
    fraco = synthetic_comb(3.0, amp=100.0)
    forte = synthetic_comb(3.0, amp=1000.0)
    # o caminho forte e o segundo: a regra tem de devolver o ifft DELE
    assert cs_compare.escolhe_ifft_potencia([P(9.9), P(4.2)], [fraco, forte]) == pytest.approx(4.2)
    assert cs_compare.escolhe_ifft_potencia([P(4.2), P(9.9)], [forte, fraco]) == pytest.approx(4.2)


def test_selecao_entra_no_summarize(tmp_path):
    p = tmp_path / "sel.csv"
    comb = synthetic_comb(3.0)
    with open(p, "w") as f:
        write_procedure(f, 30, comb, fw=(5.6, 3.0, 2.998), ap=0)
        write_procedure(f, 30, comb, fw=(4.8, 3.0, 2.998), ap=1)
    r = cs_compare.summarize(cs_csv.read_procedures(p))[0]
    assert r["ifft_min"] == pytest.approx(4.8)
    assert math.isfinite(r["ifft_pot"])
