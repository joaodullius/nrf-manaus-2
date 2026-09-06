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
