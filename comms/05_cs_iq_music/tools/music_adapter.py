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

from music import cs_music
from music.cs_music import compute_music_spectrum
from music.constants import SPEED_OF_LIGHT, BLE_CS_STEP_1MHZ

CH_OFFSET = 2
ROUND_TRIP_DIVISOR = 2.0
CONJUGATE = False
MIN_CHANNELS = 4

# INTERPOLATE_PEAK: o waves toma o pico do pseudo-espectro pelo argmax cru numa
# grade de 512 atrasos em 500 ns — 0,98 ns, ou 14,7 cm de distancia por bin (ja
# com o /2 de ida e volta). Sem interpolar, a estimativa sai quantizada nesse
# passo: na bancada do curso, 100 procedures a 1 m cairam em 4 valores distintos,
# espacados exatamente 0,1467 m. O cs_de faz interpolacao parabolica no pico da
# IFFT (calculate_ifft_peak_index_to_distance); aqui ela entra do lado do curso,
# sobre o log do pseudo-espectro (o pico do MUSIC e estreito demais para a
# parabola casar na escala linear). Com --music-grid o cs_compare.py desliga a
# interpolacao, para o aluno ver a diferenca.
INTERPOLATE_PEAK = True


def _peak_distance(dist_m: np.ndarray, spec: np.ndarray) -> float:
    """Distancia do pico do pseudo-espectro, com interpolacao parabolica opcional."""
    k = int(np.argmax(spec))
    if not INTERPOLATE_PEAK or k == 0 or k == spec.size - 1:
        return float(dist_m[k])
    y = np.log(np.maximum(spec[k - 1:k + 2], 1e-300))
    den = y[0] - 2.0 * y[1] + y[2]
    if den == 0.0:
        return float(dist_m[k])
    delta = float(np.clip(0.5 * (y[0] - y[2]) / den, -1.0, 1.0))
    return float(dist_m[k] + delta * (dist_m[1] - dist_m[0]))


def _fill_reserved_channels(comb: np.ndarray):
    """Preenche os canais reservados (23..25, indices 21..23) por interpolacao.

    O MUSIC do waves monta o vetor de direcao pela POSICAO no vetor, assumindo
    1 MHz entre vizinhos, e nao pelo numero do canal. Um buraco de 3 canais
    zerados vira um salto de fase e desloca o pico, tanto mais quanto maior a
    distancia. Aqui os buracos INTERIORES (entre o primeiro e o ultimo canal
    valido) sao preenchidos interpolando fase desenrolada e amplitude entre os
    vizinhos validos. Exato para um caminho unico (fase linear); aproximacao em
    multipath; valido enquanto 4*dphi < pi — ate ~18 m de distancia (~37 m de
    caminho de ida-e-volta, com 1 MHz de espacamento entre canais).

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


def music_spectrum(comb: np.ndarray, ch_offset: int = CH_OFFSET):
    """Pseudo-espectro do MUSIC para um caminho de antena.

    Devolve (dist_m, pseudo_spectrum): a grade de atrasos do waves ja convertida
    em metros de distancia (ida e volta / ROUND_TRIP_DIVISOR) e o pseudo-espectro
    correspondente. (None, None) se houver menos de MIN_CHANNELS canais validos.
    """
    comb = np.asarray(comb, complex)
    if CONJUGATE:
        comb = np.conj(comb)
    comb, valid = _fill_reserved_channels(comb)
    if valid.size < MIN_CHANNELS:
        return None, None
    phase, amp = {}, {}
    for idx, z in enumerate(comb):
        if z == 0:
            continue                      # canais reservados (23..25) saem zerados
        phase[idx + ch_offset] = float(np.angle(z))
        amp[idx + ch_offset] = float(20.0 * np.log10(abs(z)))
    if len(phase) < MIN_CHANNELS:
        return None, None
    delays_ns, pseudo_spectrum = compute_music_spectrum(phase, amp)
    if delays_ns is None:
        return None, None
    dist_m = np.asarray(delays_ns, float) * SPEED_OF_LIGHT / 1e9 / ROUND_TRIP_DIVISOR
    return dist_m, np.asarray(pseudo_spectrum, float)


def music_m(comb: np.ndarray, ch_offset: int = CH_OFFSET) -> float:
    """Distancia do pico do pseudo-espectro, ja na convencao de ida e volta.

    Com INTERPOLATE_PEAK=False e o calculate_distance_from_music() do waves (pico
    na grade); com True, o pico interpolado (ver INTERPOLATE_PEAK).
    """
    dist_m, spec = music_spectrum(comb, ch_offset)
    if dist_m is None:
        return math.nan
    d = _peak_distance(dist_m, spec)
    return d if math.isfinite(d) else math.nan


def music_multi_m(combs, ch_offset: int = CH_OFFSET) -> float:
    """MUSIC sobre VARIOS caminhos de antena da mesma procedure.

    Combinacao incoerente: soma dos pseudo-espectros normalizados de cada caminho
    e pico da soma. Cada caminho de antena ve um multipath diferente; o caminho
    direto e o unico que aparece no mesmo atraso em todos, entao e o que se
    reforca na soma. Nao aumenta a resolucao (a banda e a mesma); da diversidade.
    Com um unico caminho equivale a music_m().
    """
    acc = None
    dist_m = None
    for comb in combs:
        d, s = music_spectrum(comb, ch_offset)
        if d is None or not np.isfinite(s).all() or s.max() <= 0:
            continue
        s = s / s.max()
        acc = s if acc is None else acc + s
        dist_m = d
    if acc is None:
        return math.nan
    return _peak_distance(dist_m, acc)


# --------------------------------------------------------------------------
# Combinacao por MEDIA DAS COVARIANCIAS (codigo do curso)
#
# music_multi_m() acima soma os pseudo-espectros ja prontos. O jeito canonico de
# dar diversidade ao MUSIC e outro: montar a covariancia de cada caminho de
# antena e tirar a MEDIA delas ANTES da autodecomposicao. Com mais snapshots, a
# separacao entre subespaco de sinal e de ruido fica melhor condicionada.
#
# Isso nao da para fazer chamando as duas funcoes que o waves expoe (elas vao do
# vetor de canais direto ao espectro, sem devolver a covariancia). Por isso as
# duas funcoes abaixo REPETEM a construcao do music/cs_music.py, com os mesmos
# parametros importados de la — e o teste
# tests/test_music_adapter.py::test_cov_path_matches_waves exige que, para UM
# caminho, o espectro daqui seja identico ao do arquivo vendorizado. Se o
# upstream mudar, o teste quebra.
#
# NORMALIZE_COV: cada caminho e uma antena diferente, com ganho diferente. Sem
# normalizar, o caminho de maior amplitude domina a media. Dividir cada
# covariancia pelo seu traco (= potencia total) faz os dois entrarem com o mesmo
# peso. Fixado por medida na bancada, nao por gosto — ver README.
NORMALIZE_COV = True


def _snapshot(comb: np.ndarray, ch_offset: int = CH_OFFSET):
    """Vetor complexo por canal, com os reservados preenchidos.

    E exatamente o `x` que compute_music_spectrum() monta a partir dos
    dicionarios de fase/amplitude: 10**(dB/20) * exp(j*fase) == o proprio IQ
    combinado, ja que a amplitude entra em dB como 20*log10(|z|).
    """
    comb = np.asarray(comb, complex)
    if CONJUGATE:
        comb = np.conj(comb)
    comb, valid = _fill_reserved_channels(comb)
    if valid.size < MIN_CHANNELS:
        return None
    x = comb[valid.min():valid.max() + 1]
    return x if x.size >= MIN_CHANNELS else None


def _smoothed_covariance(x: np.ndarray) -> np.ndarray:
    """Covariancia por spatial smoothing — mesma construcao do cs_music.py."""
    n = x.size
    L = cs_music._SUBARRAY_LEN if cs_music._SUBARRAY_LEN is not None else n // 2
    L = max(L, cs_music._N_SIGNALS + 1)
    n_sub = n - L + 1
    R = np.zeros((L, L), dtype=complex)
    for i in range(n_sub):
        sub = x[i:i + L]
        R += np.outer(sub, sub.conj())
    return R / n_sub


def _spectrum_from_covariance(R: np.ndarray):
    """Pseudo-espectro a partir da covariancia — mesma conta do cs_music.py."""
    L = R.shape[0]
    _, eigvecs = np.linalg.eigh(R)
    noise_vecs = eigvecs[:, : L - cs_music._N_SIGNALS]
    delays_ns = np.linspace(0.0, cs_music._MAX_DELAY_NS, cs_music._N_DELAY_POINTS)
    A = np.exp(-1j * 2 * np.pi * BLE_CS_STEP_1MHZ * np.outer(np.arange(L), delays_ns * 1e-9))
    proj = noise_vecs.conj().T @ A
    denom = np.maximum(np.sum(np.abs(proj) ** 2, axis=0), 1e-12)
    return delays_ns, 1.0 / denom


def music_cov_m(combs, ch_offset: int = CH_OFFSET) -> float:
    """MUSIC com a media das covariancias dos caminhos de antena.

    Com um caminho so, e identico ao music_m() (mesma covariancia, mesma conta).
    Todos os caminhos precisam ter o mesmo numero de canais validos — se um
    divergir, ele fica de fora.
    """
    mats = []
    for comb in combs:
        x = _snapshot(comb, ch_offset)
        if x is None:
            continue
        R = _smoothed_covariance(x)
        if NORMALIZE_COV:
            tr = float(np.real(np.trace(R)))
            if tr <= 0:
                continue
            R = R / tr
        mats.append(R)
    if not mats:
        return math.nan
    shapes = {m.shape for m in mats}
    if len(shapes) > 1:                      # caminhos com contagem de canais diferente
        L = min(s[0] for s in shapes)
        mats = [m[:L, :L] for m in mats]
    R = sum(mats) / len(mats)
    delays_ns, spec = _spectrum_from_covariance(R)
    dist_m = delays_ns * SPEED_OF_LIGHT / 1e9 / ROUND_TRIP_DIVISOR
    return _peak_distance(dist_m, spec)
