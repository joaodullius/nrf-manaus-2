# -*- coding: utf-8 -*-
import math

import numpy as np
import pytest

from conftest import synthetic_comb
import music_adapter


@pytest.mark.parametrize("d", [1.0, 3.0, 7.5])
def test_music_recovers_distance(d):
    assert music_adapter.music_m(synthetic_comb(d)) == pytest.approx(d, abs=0.2)


def test_music_needs_four_channels():
    comb = np.zeros(75, complex)
    comb[:3] = 1.0
    assert math.isnan(music_adapter.music_m(comb))


def test_music_multi_single_path_equals_music_m():
    comb = synthetic_comb(3.0)
    assert music_adapter.music_multi_m([comb]) == music_adapter.music_m(comb)


def test_music_multi_two_paths_recovers_distance():
    # dois caminhos de antena da mesma procedure: mesma distancia, fase absoluta
    # diferente (outra antena) e um eco diferente em cada um
    rng = np.random.default_rng(7)
    d = 3.0
    ap0 = synthetic_comb(d) + 0.5 * synthetic_comb(d + 2.5)
    ap1 = synthetic_comb(d) * np.exp(1j * 1.1) + 0.5 * synthetic_comb(d + 4.0)
    for a in (ap0, ap1):
        a += 20.0 * (rng.standard_normal(75) + 1j * rng.standard_normal(75)) * (a != 0)
    assert music_adapter.music_multi_m([ap0, ap1]) == pytest.approx(d, abs=0.3)


def test_music_multi_skips_bad_path():
    ruim = np.zeros(75, complex)
    ruim[:3] = 1.0
    assert music_adapter.music_multi_m([ruim, synthetic_comb(3.0)]) == pytest.approx(3.0, abs=0.2)
    assert math.isnan(music_adapter.music_multi_m([ruim]))


def test_cov_path_matches_waves():
    """Para UM caminho, a via da covariancia tem de reproduzir o waves."""
    comb = synthetic_comb(3.0)
    assert music_adapter.music_cov_m([comb]) == pytest.approx(music_adapter.music_m(comb),
                                                             abs=1e-9)
    x = music_adapter._snapshot(comb)
    R = music_adapter._smoothed_covariance(x)
    _, spec_curso = music_adapter._spectrum_from_covariance(R)
    dist_waves, spec_waves = music_adapter.music_spectrum(comb)
    # mesmo espectro a menos de escala (a normalizacao do traco nao entra aqui)
    a = spec_curso / spec_curso.max()
    b = spec_waves / spec_waves.max()
    assert np.allclose(a, b, atol=1e-9)


def test_cov_two_paths_recovers_distance():
    rng = np.random.default_rng(11)
    d = 3.0
    ap0 = synthetic_comb(d) + 0.5 * synthetic_comb(d + 2.5)
    ap1 = synthetic_comb(d) * np.exp(1j * 1.1) + 0.5 * synthetic_comb(d + 4.0)
    for a in (ap0, ap1):
        a += 20.0 * (rng.standard_normal(75) + 1j * rng.standard_normal(75)) * (a != 0)
    assert music_adapter.music_cov_m([ap0, ap1]) == pytest.approx(d, abs=0.3)


def test_cov_ignores_useless_path():
    ruim = np.zeros(75, complex)
    ruim[:3] = 1.0
    assert music_adapter.music_cov_m([ruim, synthetic_comb(3.0)]) == pytest.approx(3.0, abs=0.2)
    assert math.isnan(music_adapter.music_cov_m([ruim]))


def test_interpolacao_bate_com_a_grade_quando_desligada(monkeypatch):
    comb = synthetic_comb(3.0)
    monkeypatch.setattr(music_adapter, "INTERPOLATE_PEAK", False)
    dist_m, spec = music_adapter.music_spectrum(comb)
    assert music_adapter.music_m(comb) == pytest.approx(float(dist_m[int(np.argmax(spec))]))


def test_interpolacao_reduz_a_quantizacao():
    """Sem interpolar, a estimativa so cai em multiplos do passo da grade."""
    passo = None
    fora_da_grade = 0
    for d in np.linspace(1.0, 8.0, 25):
        comb = synthetic_comb(float(d))
        dist_m, _ = music_adapter.music_spectrum(comb)
        passo = float(dist_m[1] - dist_m[0])
        if abs(music_adapter.music_m(comb) / passo - round(music_adapter.music_m(comb) / passo)) > 0.02:
            fora_da_grade += 1
    assert passo == pytest.approx(0.1467, abs=1e-3)
    assert fora_da_grade >= 20        # com interpolacao, quase nada cai na grade


@pytest.mark.parametrize("d", [1.0, 3.0, 7.5])
def test_interpolacao_melhora_a_exatidao(d):
    """Com o pico interpolado, o erro no sintetico cai bem abaixo de um bin."""
    assert music_adapter.music_m(synthetic_comb(d)) == pytest.approx(d, abs=0.05)
