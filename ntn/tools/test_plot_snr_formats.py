"""O parser de TXT deve aceitar o padrao novo, com data, e o antigo, sem data."""

import ast
import os
import tempfile
import unittest
from datetime import datetime, timedelta

import plot_snr

MEAS = "L1_DEFAULT_INFO_SERVING_CELL_MEASUREMENTS rsrp: -95 rsrq: -12 SNR: 3"

FIELDS = (
    "utc_fix dev_fix_td all_time_anchors fallback_utc fallback_dev_td records events "
    "gnss_lat gnss_lon udp_packets dl_packets sib32_entries cfun_ntn_on no_cell_tds "
    "rrc_idle_tds rrc_release_tds t310_tds cereg_events"
).split()


def load(content):
    path = os.path.join(tempfile.mkdtemp(), "log.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return dict(zip(FIELDS, plot_snr.load_log(path)))


class OldFormatTests(unittest.TestCase):
    def test_time_only_line_still_yields_a_measurement(self):
        out = load(f"16:35:33.399380 {MEAS}\n")
        self.assertEqual(len(out["records"]), 1)
        self.assertEqual(
            out["records"][0][0],
            timedelta(hours=16, minutes=35, seconds=33, microseconds=399380),
        )

    def test_time_only_line_has_no_exact_anchor(self):
        out = load(f"16:35:33.399380 {MEAS}\n")
        self.assertIsNone(out["utc_fix"])


class NewFormatTests(unittest.TestCase):
    def test_dated_line_yields_the_same_device_timedelta(self):
        out = load(f"2026-09-06 16:35:33.399380 {MEAS}\n")
        self.assertEqual(
            out["records"][0][0],
            timedelta(hours=16, minutes=35, seconds=33, microseconds=399380),
        )

    def test_dated_line_provides_an_exact_utc_anchor(self):
        out = load(f"2026-09-06 16:35:33.399380 {MEAS}\n")
        self.assertEqual(
            out["utc_fix"], datetime(2026, 9, 6, 16, 35, 33, 399380)
        )
        self.assertEqual(
            plot_snr.dev_to_utc(out["records"][0][0], out["utc_fix"], out["dev_fix_td"]),
            datetime(2026, 9, 6, 16, 35, 33, 399380),
        )

    def test_device_timedelta_keeps_growing_across_midnight(self):
        out = load(
            f"2026-09-06 23:59:59.000000 {MEAS}\n"
            f"2026-09-07 00:00:01.000000 {MEAS}\n"
        )
        first, second = out["records"][0][0], out["records"][1][0]
        self.assertEqual(second - first, timedelta(seconds=2))

    def test_anchor_still_converts_correctly_after_midnight(self):
        out = load(
            f"2026-09-06 23:59:59.000000 {MEAS}\n"
            f"2026-09-07 00:00:01.000000 {MEAS}\n"
        )
        self.assertEqual(
            plot_snr.dev_to_utc(out["records"][1][0], out["utc_fix"], out["dev_fix_td"]),
            datetime(2026, 9, 7, 0, 0, 1),
        )


class CallerContractTests(unittest.TestCase):
    def test_analyze_elevation_signal_unpacks_every_value_load_log_returns(self):
        src = open("analyze_elevation_signal.py", encoding="utf-8").read()
        targets = [
            n
            for node in ast.walk(ast.parse(src))
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", "") == "load_log"
            for t in node.targets
            for n in getattr(t, "elts", [])
        ]
        self.assertEqual(len(targets), len(FIELDS))


class ElevationYlimTests(unittest.TestCase):
    """O eixo da elevacao deve enquadrar a curva, e nao afogar 0.7 grau em 10."""

    def test_short_window_gets_a_tight_frame(self):
        lo, hi = plot_snr.elevation_ylim([60.0, 60.7, 60.4])
        self.assertAlmostEqual(lo, 59.9)
        self.assertAlmostEqual(hi, 60.8)

    def test_full_pass_keeps_a_proportional_margin(self):
        lo, hi = plot_snr.elevation_ylim([0.0, 30.0, 60.0, 30.0, 0.0])
        self.assertAlmostEqual(lo, -6.0)
        self.assertAlmostEqual(hi, 66.0)

    def test_flat_series_still_has_a_visible_span(self):
        lo, hi = plot_snr.elevation_ylim([45.0, 45.0])
        self.assertLess(lo, 45.0)
        self.assertGreater(hi, 45.0)


class NetAckTests(unittest.TestCase):
    """O ack de rede e um bloco DL pequeno, confirmado no NPUCCH, sem PDU L3.

    A DB externa nao expoe o RLC STATUS; o que sobra no trace e um grant N1
    depois do envio, seguido do HARQ-ACK do UE e de nenhum ERRC/NAS decodificado.
    """

    def s(self, sec):
        return timedelta(seconds=sec)

    def burst(self, start, n=8, step=0.001):
        return [self.s(start + i * step) for i in range(n)]

    def test_picks_the_first_small_dl_block_acked_on_pucch_with_no_l3_pdu(self):
        acks = plot_snr.find_net_acks(
            send_tds=[self.s(54.734)],
            dl_grant_tds=self.burst(54.685) + self.burst(54.797) + self.burst(58.525),
            rar_tds=[],
            pucch_tds=[self.s(54.741), self.s(54.916), self.s(58.581)],
            dl_pdu_tds=[self.s(54.897)],
        )
        self.assertEqual(acks, [(self.s(54.734), self.s(58.525))])

    def test_skips_a_rar_burst(self):
        acks = plot_snr.find_net_acks(
            send_tds=[self.s(54.734)],
            dl_grant_tds=self.burst(55.997) + self.burst(58.525),
            rar_tds=[self.s(56.059)],
            pucch_tds=[self.s(58.581)],
            dl_pdu_tds=[],
        )
        self.assertEqual(acks, [(self.s(54.734), self.s(58.525))])

    def test_skips_a_block_that_carried_an_l3_pdu(self):
        acks = plot_snr.find_net_acks(
            send_tds=[self.s(10.0)],
            dl_grant_tds=self.burst(11.0) + self.burst(13.0),
            rar_tds=[],
            pucch_tds=[self.s(11.05), self.s(13.05)],
            dl_pdu_tds=[self.s(11.1)],
        )
        self.assertEqual(acks, [(self.s(10.0), self.s(13.0))])

    def test_requires_the_pucch_confirmation(self):
        acks = plot_snr.find_net_acks(
            send_tds=[self.s(10.0)],
            dl_grant_tds=self.burst(11.0),
            rar_tds=[],
            pucch_tds=[],
            dl_pdu_tds=[],
        )
        self.assertEqual(acks, [])

    def test_no_send_means_no_ack(self):
        acks = plot_snr.find_net_acks([], self.burst(11.0), [], [self.s(11.05)], [])
        self.assertEqual(acks, [])

    def test_load_log_exposes_the_ack_as_an_event(self):
        out = load(
            "2026-09-07 02:28:54.734222 EPDCP_UP_PACKET_UL_MULTI [4500]\n"
            "2026-09-07 02:28:55.997467 L1_DCI_DEC_N1_CONTENT_PHY_ALLOC modem: tbs:15\n"
            "2026-09-07 02:28:56.059662 L1_DCI_DEC_NBIOT_RAR_UL_GRANT_CONTENT_NPUSCH modem: x\n"
            "2026-09-07 02:28:58.525513 L1_DCI_DEC_N1_CONTENT_PHY_ALLOC modem: tbs:15\n"
            "2026-09-07 02:28:58.581146 L1_DEFAULT_INFO_PUCCH_POWER_CONTROL pucch_tx_power_value: 23\n"
            f"2026-09-07 02:28:59.000000 {MEAS}\n"
        )
        self.assertEqual(
            out["events"]["Net ACK"],
            [timedelta(hours=2, minutes=28, seconds=58, microseconds=525513)],
        )


class ReadAnchorTests(unittest.TestCase):
    """O .txt declara de onde veio a hora; um trace mal ancorado nao pode
    desenhar elevacao em silencio, foi assim que a Kyocera de 08/09 saiu
    333 s adiantada e passou por boa."""

    def write(self, primeira_linha):
        path = os.path.join(tempfile.mkdtemp(), "log.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(primeira_linha + f"2026-09-07 02:28:45.000000 {MEAS}\n")
        return path

    def test_reads_a_trustworthy_anchor(self):
        a = plot_snr.read_anchor(self.write("# anchor: cclk (sub-segundo)\n"))
        self.assertEqual(a.kind, "cclk")
        self.assertTrue(a.trustworthy)

    def test_reads_the_approximate_mtime_anchor(self):
        a = plot_snr.read_anchor(self.write("# anchor: mtime (+-10 s)\n"))
        self.assertEqual(a.kind, "mtime")
        self.assertTrue(a.trustworthy)
        self.assertIn("10 s", a.note)

    def test_flags_the_header_epoch_as_untrustworthy(self):
        a = plot_snr.read_anchor(
            self.write("# anchor: header (inicio da captura)  NAO CONFIAVEL\n"))
        self.assertEqual(a.kind, "header")
        self.assertFalse(a.trustworthy)

    def test_a_txt_without_the_marker_is_unknown_not_trusted(self):
        a = plot_snr.read_anchor(self.write(""))
        self.assertIsNone(a)


class OpenFileTests(unittest.TestCase):
    """Handlers AppX do Windows falham em silencio; precisa de plano B."""

    def setUp(self):
        self.png = os.path.join(tempfile.mkdtemp(), "grafico.png")
        with open(self.png, "wb") as fh:
            fh.write(b"\x89PNG\r\n")
        self.opened = []

    def test_uses_the_shell_when_the_registered_handler_is_runnable(self):
        how = plot_snr.open_file(
            self.png,
            handler_runnable=lambda: True,
            shell_open=self.opened.append,
            browser_open=self.opened.append,
        )
        self.assertEqual(how, "shell")
        self.assertEqual(self.opened, [os.path.abspath(self.png)])

    def test_falls_back_to_the_browser_when_no_runnable_handler(self):
        how = plot_snr.open_file(
            self.png,
            handler_runnable=lambda: False,
            shell_open=self.opened.append,
            browser_open=self.opened.append,
        )
        self.assertEqual(how, "browser")
        self.assertTrue(self.opened[0].startswith("file:///"))

    def test_falls_back_to_the_browser_when_the_shell_raises(self):
        def boom(_):
            raise OSError("nenhum aplicativo associado")

        how = plot_snr.open_file(
            self.png,
            handler_runnable=lambda: True,
            shell_open=boom,
            browser_open=self.opened.append,
        )
        self.assertEqual(how, "browser")
        self.assertTrue(self.opened[0].endswith("grafico.png"))


class HandlerDetectionTests(unittest.TestCase):
    """Handler AppX registra a chave sem comando, so com DelegateExecute."""

    def test_a_classic_handler_with_a_command_line_is_runnable(self):
        self.assertTrue(plot_snr._default_handler_is_runnable(
            ".png", read_command=lambda ext: r'C:\Windows\system32\mspaint.exe "%1"'))

    def test_an_appx_handler_without_a_command_is_not_runnable(self):
        self.assertFalse(plot_snr._default_handler_is_runnable(
            ".png", read_command=lambda ext: ""))

    def test_a_missing_handler_is_not_runnable(self):
        self.assertFalse(plot_snr._default_handler_is_runnable(
            ".png", read_command=lambda ext: None))
