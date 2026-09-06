# -*- coding: utf-8 -*-
import math

import numpy as np

from conftest import synthetic_comb, write_procedure
import cs_csv


def test_parse_iq_line():
    assert cs_csv.parse_line("IQ,17,0,2,-123.0,456.0,7.0,-8.0\n") == (
        "IQ", 17, 0, 2, -123.0, 456.0, 7.0, -8.0)


def test_parse_cs_line_with_nan():
    got = cs_csv.parse_line("CS,17,0,1,2.310,nan,2.700,12,-345\n")
    assert got[:5] == ("CS", 17, 0, 1, 2.31)
    assert math.isnan(got[5])
    assert got[6:] == (2.7, 12, -345)


def test_parse_ignores_noise():
    assert cs_csv.parse_line("*** Booting nRF Connect SDK ***\n") is None
    assert cs_csv.parse_line("IQ,garbage\n") is None
    assert cs_csv.parse_line("") is None


def test_read_procedures_roundtrip(tmp_path):
    p = tmp_path / "cap.csv"
    with open(p, "w") as f:
        f.write("*** Booting ***\n")
        write_procedure(f, 5, synthetic_comb(3.0))
        f.write("IQ,6,0,2,1.0,1.0,1.0,0.0\n")          # procedure 6 incompleta
        write_procedure(f, 7, synthetic_comb(1.0), tq=0)
    procs = cs_csv.read_procedures(p)
    assert [q.counter for q in procs] == [5, 7]
    assert procs[0].tone_quality_ok and not procs[1].tone_quality_ok
    assert procs[0].fw == {"ifft": 3.0, "phase_slope": 3.0, "rtt": 2.998}
    assert procs[0].rtt_half_ns == 40 and procs[0].rtt_count == 1
    # comb() == local * remoto; remoto = 1+0j no fixture, entao comb == local
    np.testing.assert_allclose(procs[0].comb(), synthetic_comb(3.0), atol=0.1)


def test_format_is_firmware_format():
    assert cs_csv.format_iq(3, 0, 2, 1.26, -2.0, 3.0, 4.0) == "IQ,3,0,2,1.3,-2.0,3.0,4.0\n"
    assert cs_csv.format_cs(3, 0, 1, 1.0, float("nan"), 2.0, 5, -7) == "CS,3,0,1,1.000,nan,2.000,5,-7\n"


def test_group_by_counter_pairs_antenna_paths(tmp_path):
    p = tmp_path / "2ap.csv"
    with open(p, "w") as f:
        write_procedure(f, 5, synthetic_comb(3.0), ap=0)
        write_procedure(f, 5, synthetic_comb(3.0), ap=1)
        write_procedure(f, 6, synthetic_comb(1.0), ap=0)
    grupos = cs_csv.group_by_counter(cs_csv.read_procedures(p))
    assert sorted(grupos) == [5, 6]
    assert [q.ap for q in grupos[5]] == [0, 1]
    assert [q.ap for q in grupos[6]] == [0]
