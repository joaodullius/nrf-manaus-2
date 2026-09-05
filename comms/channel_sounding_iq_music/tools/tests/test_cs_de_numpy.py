# -*- coding: utf-8 -*-
import math

import numpy as np
import pytest

from conftest import synthetic_comb
import cs_de_numpy as de


def test_combine_is_complex_product():
    i_l, q_l, i_r, q_r = (np.array([1.0]), np.array([2.0]), np.array([3.0]), np.array([4.0]))
    comb = de.combine(i_l, q_l, i_r, q_r)
    # (1 + 2j) * (3 + 4j) = (3 - 8) + (4 + 6)j  — a mesma conta do cs_de_combined_iq_calculate()
    assert comb[0] == pytest.approx(-5 + 10j)


def test_rtt_formula_matches_cs_de_rtt():
    # 40 meias-ns acumuladas em 1 medida = 20 ns de ida e volta = 10 ns de voo = 2.998 m
    assert de.rtt_m(40, 1) == pytest.approx(2.99792458, abs=1e-6)
    assert de.rtt_m(-40, 1) == 0.0            # fmaxf(..., 0)
    assert math.isnan(de.rtt_m(0, 0))         # rtt_count == 0


def test_phase_slope_recovers_distance():
    assert de.phase_slope_m(synthetic_comb(3.0)) == pytest.approx(3.0, abs=0.01)
    assert de.phase_slope_m(synthetic_comb(0.5)) == pytest.approx(0.5, abs=0.01)


def test_phase_slope_negative_is_nan():
    comb = np.conj(synthetic_comb(3.0))       # inclinacao invertida => distancia negativa
    assert math.isnan(de.phase_slope_m(comb))


def test_ifft_recovers_distance_512():
    assert de.ifft_m(synthetic_comb(3.0), nfft=512) == pytest.approx(3.0, abs=0.15)
    assert de.ifft_m(synthetic_comb(8.0), nfft=512) == pytest.approx(8.0, abs=0.15)


def test_ifft_1024_is_finer():
    err512 = abs(de.ifft_m(synthetic_comb(5.0), nfft=512) - 5.0)
    err1024 = abs(de.ifft_m(synthetic_comb(5.0), nfft=1024) - 5.0)
    assert err1024 <= err512 + 0.01


def test_estimates_dict(comb_3m):
    e = de.estimates(comb_3m, rtt_half_ns=40, rtt_count=1)
    assert set(e) == {"ifft", "phase_slope", "rtt"}
    assert e["phase_slope"] == pytest.approx(3.0, abs=0.01)
