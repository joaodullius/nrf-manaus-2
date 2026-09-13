#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Port em NumPy da biblioteca cs_de da Nordic — codigo do curso (nrf-manaus-2).

Reproduz, funcao a funcao, o que o firmware do initiator faz com o IQ:

    cs_de_combined_iq_calculate()  -> combine()
    cs_de_rtt()                    -> rtt_m()
    cs_de_phase_slope()            -> phase_slope_m()
    cs_de_ifft()                   -> ifft_m()   (calculate_ifft_mag + find_ifft_peak_index
                                                  + calculate_ifft_peak_index_to_distance)

Fonte portada: nRF Connect SDK v3.4.0, nrf/subsys/bluetooth/cs_de/cs_de.c
(licenca LicenseRef-Nordic-5-Clause; este arquivo e uma reimplementacao, nao
uma copia — os nomes das funcoes originais estao nos comentarios para o aluno
ler os dois lado a lado). Constantes de cs_de.c: SPEED_OF_LIGHT_M_PER_S,
CHANNEL_SPACING_HZ = 1e6, NORMAL_PEAK_TO_NULL = (NFFT + 75 - 1) // 75.

O firmware calcula em float32 (CMSIS-DSP); aqui e float64. Diferencas na 2a-3a
casa decimal sao esperadas — o cs_compare.py mede quanto.

Requisitos: numpy.
"""
from __future__ import annotations

import math

import numpy as np

C = 299792458.0        # SPEED_OF_LIGHT_M_PER_S
DF = 1e6               # CHANNEL_SPACING_HZ
NCH = 75               # CS_DE_NUM_CHANNELS


def combine(i_local, q_local, i_remote, q_remote) -> np.ndarray:
    """cs_de_combined_iq_calculate(): produto complexo local x remoto, por canal."""
    return (np.asarray(i_local, float) + 1j * np.asarray(q_local, float)) * (
        np.asarray(i_remote, float) + 1j * np.asarray(q_remote, float))


def rtt_m(rtt_accumulated_half_ns: int, rtt_count: int) -> float:
    """cs_de_rtt(): media das meias-ns acumuladas, metade e o tempo de voo."""
    if rtt_count <= 0:
        return math.nan
    rtt_avg_ns = (rtt_accumulated_half_ns * 0.5) / rtt_count
    tof_ns = rtt_avg_ns / 2.0
    return max(tof_ns * (C / 1e9), 0.0)


def phase_slope_m(comb: np.ndarray) -> float:
    """cs_de_phase_slope(): soma de comb[n] * conj(comb[n-1]); atan2 da soma."""
    comb = np.asarray(comb, complex)
    s = np.sum(comb[1:] * np.conj(comb[:-1]))
    dist = -(C * math.atan2(s.imag, s.real)) / (4.0 * math.pi * DF)
    return dist if dist >= 0 else math.nan


def ifft_mag(comb: np.ndarray, nfft: int = 512) -> np.ndarray:
    """calculate_ifft_mag(): conj -> FFT -> |.| / nfft (a IFFT via FFT do conjugado)."""
    buf = np.zeros(nfft, complex)
    buf[:NCH] = np.conj(np.asarray(comb, complex)[:NCH])
    return np.abs(np.fft.fft(buf)) / nfft


def _find_left_null(peak: int, mag: np.ndarray, nfft: int) -> int:
    """calculate_ifft_find_left_null(): heuristica de nulo a esquerda do pico."""
    ln = peak
    while True:
        nxt = nfft - 1 if ln == 0 else ln - 1
        if ((mag[ln] * 2 > mag[peak] or mag[ln] > 1.10 * mag[nxt])
                and mag[ln] * 10 > mag[peak] and nxt != peak):
            ln = nxt
        else:
            return ln


def _dist_to_left_null(peak: int, ln: int, nfft: int) -> int:
    """calculate_distance_to_left_null()."""
    return (nfft + peak - ln) if ln > peak else (peak - ln)


def _left_null_compensation(peak: int, mag: np.ndarray, nfft: int) -> int:
    """calculate_left_null_compensation_of_peak()."""
    normal_peak_to_null = (nfft + NCH - 1) // NCH
    ln = _find_left_null(peak, mag, nfft)
    if _dist_to_left_null(peak, ln, nfft) > normal_peak_to_null:
        if ln > peak:
            v = ln + normal_peak_to_null - nfft
            return v if v > 0 else peak
        return ln + normal_peak_to_null
    return peak


def _find_peak_index(mag: np.ndarray, nfft: int) -> int:
    """find_ifft_peak_index(): maximo, busca por pico mais curto, compensacao."""
    max_idx = int(np.argmax(mag))
    max_val = mag[max_idx]

    nw, nw_next = nfft - 2, nfft - 1
    shortest = max_idx
    short_found = False
    first_rise = False
    while nw != max_idx and not short_found:
        if mag[nw_next] < mag[nw]:
            if 2.5 * mag[nw] > max_val and first_rise:
                shortest = nw
                short_found = True
        else:
            first_rise = True
        nw = nw_next
        nw_next = (nw_next + 1) % nfft

    comp = shortest
    if comp < nfft - 2:
        comp = _left_null_compensation(shortest, mag, nfft)
    return comp


def _peak_to_distance(k: int, mag: np.ndarray, nfft: int) -> float:
    """calculate_ifft_peak_index_to_distance(): interpolacao parabolica do pico."""
    prompt = mag[k]
    early = mag[k - 1] if k != 0 else mag[nfft - 1]
    late = mag[k + 1] if k != nfft - 1 else mag[0]
    if prompt >= early and prompt >= late:
        t_hat = (late - early) / (4 * prompt - 2 * (early + late))
    else:
        t_hat = 0.0
    dist = ((k + t_hat) * C) / (2.0 * nfft * DF)
    if k >= nfft - 2 or dist < 0.0:
        return math.nan
    return dist


def ifft_m(comb: np.ndarray, nfft: int = 512) -> float:
    """cs_de_ifft(): magnitude da IFFT -> indice do pico -> distancia."""
    mag = ifft_mag(comb, nfft)
    return _peak_to_distance(_find_peak_index(mag, nfft), mag, nfft)


def estimates(comb: np.ndarray, rtt_half_ns: int, rtt_count: int, nfft: int = 512) -> dict:
    """O que cs_de_calc() preenche em distance_estimates (sem o 'best')."""
    return {
        "ifft": ifft_m(comb, nfft),
        "phase_slope": phase_slope_m(comb),
        "rtt": rtt_m(rtt_half_ns, rtt_count),
    }
