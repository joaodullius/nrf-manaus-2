# -*- coding: utf-8 -*-
"""Fixtures dos testes do lab 5.

synthetic_comb(d): IQ combinado (local x remoto) de um unico caminho a d metros,
sem ruido. Fase por canal: -4*pi*DF*d/c * n, que e o que o cs_de_phase_slope()
do cs_de.c inverte (dist = -c*atan2(...)/(4*pi*DF)). Os canais 23..25 (indices
21..23) sao reservados para advertising e saem zerados, como no firmware.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

C = 299792458.0
DF = 1e6
NCH = 75
GAPS = (21, 22, 23)


def synthetic_comb(d_m: float, amp: float = 1000.0) -> np.ndarray:
    n = np.arange(NCH)
    comb = amp * np.exp(-1j * 4 * np.pi * DF * d_m / C * n)
    comb[list(GAPS)] = 0
    return comb


@pytest.fixture
def comb_3m():
    return synthetic_comb(3.0)
