"""O A/B empilha elevacao, RSRP e SNR num eixo de tempo comum, para N capturas."""

import os
import unittest
from datetime import datetime, timedelta

import numpy as np

import plot_ab_antennas as ab


def make_dataset(label, start_sec, n=5):
    t0 = datetime(2026, 9, 7, 2, 28, 45)
    return {
        "path": f"traces-txt/20260907_0228_SIOT1_BRA_{label}.txt",
        "label": label,
        "sat": "SATELIOT_1",
        "t": [t0 + timedelta(seconds=start_sec + i) for i in range(n)],
        "rsrp": np.linspace(-135.0, -130.0, n),
        "rsrq": np.linspace(-17.0, -14.0, n),
        "snr": np.linspace(-6.0, -1.0, n),
        "el": np.linspace(58.0, 60.5, n),
    }


class SeriesColorsTests(unittest.TestCase):
    """Dois e o caso usual, mas o grafico nao pode perder uma serie se vierem seis."""

    def test_returns_one_color_per_dataset(self):
        self.assertEqual(len(ab.series_colors(2)), 2)

    def test_cycles_once_the_palette_runs_out(self):
        colors = ab.series_colors(6)
        self.assertEqual(len(colors), 6)
        self.assertEqual(colors[4], colors[0])
        self.assertEqual(colors[5], colors[1])

    def test_first_colors_match_the_validated_palette(self):
        self.assertEqual(ab.series_colors(4), ab.SERIES_COLORS)

    def test_zero_datasets_is_not_an_error(self):
        self.assertEqual(ab.series_colors(0), [])


class AntennaLabelTests(unittest.TestCase):
    def test_known_suffix_becomes_the_product_name(self):
        self.assertEqual(
            ab.antenna_from_filename("traces-txt/20260907_0228_SIOT1_BRA_YG.txt"),
            "Yageo W5095",
        )

    def test_unknown_suffix_is_kept_as_is(self):
        self.assertEqual(
            ab.antenna_from_filename("traces-txt/20260907_0228_SIOT1_BRA_ZZ.txt"), "ZZ"
        )

    def test_without_a_suffix_the_filename_identifies_the_series(self):
        self.assertEqual(
            ab.antenna_from_filename("traces-txt/20260907_0228_SIOT1_BRA.txt"),
            "20260907_0228_SIOT1_BRA.txt",
        )


class AnchorGateTests(unittest.TestCase):
    """Um trace mal ancorado nao pode entrar num A/B: o eixo do A/B e a
    geometria da passagem, e a hora errada desloca a serie inteira."""

    def ds(self, label, kind, trustworthy=True, note="+-10 s"):
        d = make_dataset(label, 0)
        d["anchor"] = None if kind is None else ab.plot_snr.TraceAnchor(
            kind, note, trustworthy)
        return d

    def test_an_untrustworthy_dataset_is_dropped(self):
        bons = [self.ds("A", "cclk", note="sub-segundo")]
        ruim = self.ds("B", "header", trustworthy=False)
        kept, dropped = ab.drop_untrusted(bons + [ruim])
        self.assertEqual([d["label"] for d in kept], ["A"])
        self.assertEqual([d["label"] for d in dropped], ["B"])

    def test_force_keeps_everything(self):
        ruim = self.ds("B", "header", trustworthy=False)
        kept, dropped = ab.drop_untrusted([ruim], force=True)
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, [])

    def test_an_unmarked_dataset_is_kept(self):
        # .txt de conversao antiga: nao da para afirmar que a hora e ruim
        kept, dropped = ab.drop_untrusted([self.ds("A", None)])
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, [])

    def test_a_mtime_anchor_is_kept_but_carries_its_accuracy_in_the_label(self):
        d = self.ds("A", "mtime")
        kept, _ = ab.drop_untrusted([d])
        self.assertEqual(len(kept), 1)
        self.assertEqual(ab.series_label(d), "A (+-10 s)")

    def test_a_sub_second_anchor_needs_no_annotation(self):
        self.assertEqual(ab.series_label(self.ds("A", "cclk", note="sub-segundo")), "A")

    def test_an_unmarked_dataset_is_not_annotated(self):
        self.assertEqual(ab.series_label(self.ds("A", None)), "A")


class FigureLayoutTests(unittest.TestCase):
    def setUp(self):
        self.datasets = [make_dataset("A", 0), make_dataset("B", 20)]
        t0 = datetime(2026, 9, 7, 2, 28, 0)
        self.el_times = [t0 + timedelta(seconds=10 * i) for i in range(12)]
        self.el_degs = np.linspace(40.0, 60.7, 12)
        self.kwargs = dict(
            peak_t=datetime(2026, 9, 7, 2, 28, 53),
            peak_el=60.7,
            sat_name="SATELIOT_1",
            lat=-30.0287,
            lon=-51.2133,
            t_start=t0,
            t_end=t0 + timedelta(seconds=120),
        )

    def build(self, datasets=None):
        return ab.build_figure(datasets or self.datasets, self.el_times,
                               self.el_degs, **self.kwargs)

    def test_only_the_three_stacked_panels_are_drawn(self):
        fig = self.build()
        self.assertEqual(len(fig.axes), 3)

    def test_panels_are_elevation_rsrp_and_snr_top_to_bottom(self):
        fig = self.build()
        self.assertEqual(
            [ax.get_ylabel() for ax in fig.axes],
            ["Elevation (deg)", "RSRP (dBm)", "SNR (dB)"],
        )

    def test_every_dataset_reaches_the_signal_panels(self):
        datasets = [make_dataset(c, 10 * i) for i, c in enumerate("ABCDEF")]
        fig = self.build(datasets)
        ax_rsrp, ax_snr = fig.axes[1], fig.axes[2]
        labelled = [ln.get_label() for ln in ax_rsrp.get_lines()
                    if not ln.get_label().startswith("_")]
        self.assertEqual(labelled, list("ABCDEF"))
        self.assertEqual(
            len([ln for ln in ax_snr.get_lines()
                 if not ln.get_label().startswith("_")]), 6)

    def test_only_the_bottom_panel_carries_the_time_axis_label(self):
        fig = self.build()
        self.assertEqual(
            [ax.get_xlabel() for ax in fig.axes], ["", "", "UTC"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
