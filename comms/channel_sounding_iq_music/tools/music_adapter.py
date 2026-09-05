#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapta o IQ combinado do firmware ao MUSIC do waves — codigo do curso.

music/cs_music.py (MIT, ver music/ORIGEM.md) quer fase e amplitude por canal. O
nosso IQ e o produto local x remoto: a fase da IDA E DA VOLTA. Por isso a distancia
que o MUSIC devolve para esse dado corresponde ao caminho de ida e volta e e
dividida por ROUND_TRIP_DIVISOR. CONJUGATE espelha o sinal da fase se a convencao
de atraso do waves for a oposta a do cs_de. Os dois valores sao fixados pelo
tests/test_music_adapter.py com IQ sintetico — nao por inspecao.

O arquivo copiado expoe duas funcoes encadeadas (ver music/ORIGEM.md):
compute_music_spectrum(phase, amp) -> (delays_ns, pseudo_spectrum), e
calculate_distance_from_music(delays_ns, pseudo_spectrum) -> float. O adaptador
faz a ponte entre as duas. O MUSIC do waves monta o vetor de direcao pela POSICAO
no vetor ordenado de canais (assume 1 MHz entre vizinhos), nao pelo numero do
canal — por isso os canais reservados zerados (23..25) sao preenchidos por
interpolacao antes de montar fase/amplitude (ver _fill_reserved_channels), em vez
de simplesmente omitidos.
"""
from __future__ import annotations

import math

import numpy as np

from music.cs_music import compute_music_spectrum, calculate_distance_from_music

CH_OFFSET = 2
ROUND_TRIP_DIVISOR = 2.0
CONJUGATE = False
MIN_CHANNELS = 4


def _fill_reserved_channels(comb: np.ndarray):
    """Preenche os canais reservados (23..25, indices 21..23) por interpolacao.

    O MUSIC do waves monta o vetor de direcao pela POSICAO no vetor, assumindo
    1 MHz entre vizinhos, e nao pelo numero do canal. Um buraco de 3 canais
    zerados vira um salto de fase e desloca o pico, tanto mais quanto maior a
    distancia. Aqui os buracos INTERIORES (entre o primeiro e o ultimo canal
    valido) sao preenchidos interpolando fase desenrolada e amplitude entre os
    vizinhos validos. Exato para um caminho unico (fase linear); aproximacao em
    multipath; valido enquanto 4*dphi < pi (~18 m com 1 MHz de espacamento).

    Devolve (comb_preenchido, indices_validos_originais).
    """
    comb = np.asarray(comb, complex).copy()
    valid = np.flatnonzero(comb != 0)
    if valid.size < MIN_CHANNELS:
        return comb, valid
    idx = np.arange(valid.min(), valid.max() + 1)
    missing = idx[comb[idx] == 0]
    if missing.size:
        ph = np.unwrap(np.angle(comb[valid]))
        am = np.abs(comb[valid])
        comb[missing] = np.interp(missing, valid, am) * np.exp(1j * np.interp(missing, valid, ph))
    return comb, valid


def music_m(comb: np.ndarray, ch_offset: int = CH_OFFSET) -> float:
    comb = np.asarray(comb, complex)
    if CONJUGATE:
        comb = np.conj(comb)
    comb, valid = _fill_reserved_channels(comb)
    if valid.size < MIN_CHANNELS:
        return math.nan
    phase, amp = {}, {}
    for idx, z in enumerate(comb):
        if z == 0:
            continue                      # canais reservados (23..25) saem zerados
        phase[idx + ch_offset] = float(np.angle(z))
        amp[idx + ch_offset] = float(20.0 * np.log10(abs(z)))
    if len(phase) < MIN_CHANNELS:
        return math.nan
    delays_ns, pseudo_spectrum = compute_music_spectrum(phase, amp)
    if delays_ns is None:
        return math.nan
    d = calculate_distance_from_music(delays_ns, pseudo_spectrum)
    if d is None or not math.isfinite(d):
        return math.nan
    return float(d) / ROUND_TRIP_DIVISOR
