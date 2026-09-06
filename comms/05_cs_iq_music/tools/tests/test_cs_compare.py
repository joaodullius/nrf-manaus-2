# -*- coding: utf-8 -*-
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
