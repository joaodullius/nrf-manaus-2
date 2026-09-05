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


def write_procedure(f, counter, comb, tq=1, rtt_half_ns=40, rtt_count=1,
                    fw=(3.0, 3.0, 2.998)):
    """Escreve uma procedure completa no formato do firmware: 75 linhas IQ com
    local = comb e remoto = 1+0j (entao comb() == local), e a linha CS."""
    import cs_csv
    for idx in range(NCH):
        f.write(cs_csv.format_iq(counter, 0, idx + 2, comb[idx].real, comb[idx].imag, 1.0, 0.0))
    f.write(cs_csv.format_cs(counter, 0, tq, fw[0], fw[1], fw[2], rtt_count, rtt_half_ns))
