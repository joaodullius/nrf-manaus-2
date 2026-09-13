import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import nrf_trace

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "02_leo_replay", "data"))
BIN = os.path.join(DATA, "20260906_0226_SIOT1_BRA_YG.bin")
BIN2 = os.path.join(DATA, "20260902_0216_SIOT1_BRA.bin")
DB = os.path.join(DATA, "trace_db_external_eae22c84-2506-423a-883e-91bd9b2ad229.tar.gz")

EPOCH_US = 1788660933791348          # 2026-09-06 02:15:33.791348 UTC
EPOCH = datetime(2026, 9, 6, 2, 15, 33, 791348, tzinfo=timezone.utc)
CCLK_UTC = datetime(2026, 9, 6, 2, 22, 0, tzinfo=timezone.utc)

GNSS = "GNSS_POS_REP_PV Lat -30.029084 Lon -51.212456"
CCLK = 'L23_AT_STRING => AT+CCLK="26/09/06,02:22:00+99"'


@unittest.skipUnless(os.path.exists(BIN) and os.path.exists(DB),
                     "traces .bin e trace-db nao estao no repositorio")
class ReadEpochTests(unittest.TestCase):
    def test_reads_epoch_microseconds_from_bin_header(self):
        self.assertEqual(nrf_trace.read_epoch_us(BIN), EPOCH_US)

    def test_raises_when_header_missing(self):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"nao ha epoca aqui" * 8)
            path = f.name
        try:
            with self.assertRaises(nrf_trace.TraceError):
                nrf_trace.read_epoch_us(path)
        finally:
            os.unlink(path)


class ParseTextTests(unittest.TestCase):
    def test_first_record_lands_on_the_header_epoch_without_cclk(self):
        (rec,) = nrf_trace.parse_text("13:35:33.399380 A x\n", EPOCH_US)
        self.assertEqual(rec.timestamp, EPOCH)

    def test_later_records_follow_the_deltas_printed_by_nrfutil(self):
        first, second = nrf_trace.parse_text(
            "13:35:33.399380 A x\n13:35:34.899380 B y\n", EPOCH_US)
        self.assertEqual(second.timestamp - first.timestamp,
                         timedelta(milliseconds=1500))

    def test_splits_label_from_message_text(self):
        (rec,) = nrf_trace.parse_text(
            "13:35:33.399380 L23_AT_STRING => AT+CFUN?\n", EPOCH_US)
        self.assertEqual(rec.label, "L23_AT_STRING")
        self.assertEqual(rec.text, "=> AT+CFUN?")

    def test_rolls_over_to_next_day_when_time_of_day_decreases(self):
        first, second = nrf_trace.parse_text(
            "23:59:59.000000 A x\n00:00:01.000000 B y\n", EPOCH_US)
        self.assertEqual(second.timestamp - first.timestamp, timedelta(seconds=2))

    def test_line_without_timestamp_continues_previous_record(self):
        (rec,) = nrf_trace.parse_text(
            "13:35:33.399380 L23_AT_STRING <= +CFUN: 4\n    OK\n", EPOCH_US)
        self.assertEqual(rec.text, "<= +CFUN: 4\n    OK")

    def test_raises_when_first_line_has_no_timestamp(self):
        with self.assertRaises(nrf_trace.TraceError):
            nrf_trace.parse_text("lixo sem hora\n", EPOCH_US)


class CclkAnchorTests(unittest.TestCase):
    """O +CCLK emitido logo apos um fix de GNSS traz hora real e tem precedencia."""

    def test_cclk_after_a_gnss_fix_becomes_the_anchor(self):
        text = "10:00:00.000000 " + GNSS + "\n10:00:30.000000 " + CCLK + "\n"
        _, cclk_rec = nrf_trace.parse_text(text, EPOCH_US)
        self.assertEqual(cclk_rec.timestamp, CCLK_UTC)

    def test_anchoring_on_cclk_preserves_the_relative_deltas(self):
        text = "10:00:00.000000 " + GNSS + "\n10:00:30.000000 " + CCLK + "\n"
        first, second = nrf_trace.parse_text(text, EPOCH_US)
        self.assertEqual(second.timestamp - first.timestamp, timedelta(seconds=30))

    def test_a_cclk_without_a_preceding_gnss_fix_is_ignored(self):
        text = "10:00:30.000000 " + CCLK + "\n"
        (rec,) = nrf_trace.parse_text(text, EPOCH_US)
        self.assertEqual(rec.timestamp, EPOCH)

    def test_a_cclk_long_after_the_gnss_fix_is_ignored(self):
        text = "10:00:00.000000 " + GNSS + "\n10:05:00.000000 " + CCLK + "\n"
        first, _ = nrf_trace.parse_text(text, EPOCH_US)
        self.assertEqual(first.timestamp, EPOCH)


@unittest.skipUnless(os.path.exists(BIN) and os.path.exists(DB),
                     "traces .bin e trace-db nao estao no repositorio")
class ConvertTests(unittest.TestCase):
    def test_raises_helpful_error_when_nrfutil_is_missing(self):
        with self.assertRaises(nrf_trace.TraceError) as ctx:
            nrf_trace.convert(BIN, DB, nrfutil="nrfutil-inexistente-xyz")
        self.assertIn("nrfutil", str(ctx.exception))

    def test_decodes_the_real_trace(self):
        recs = nrf_trace.convert(BIN, DB)
        self.assertEqual(len(recs), 848)
        self.assertEqual(recs[0].label, "L23_AT_STRING")

    def test_timestamps_are_non_decreasing(self):
        recs = nrf_trace.convert(BIN, DB)
        self.assertEqual(list(recs), sorted(recs, key=lambda r: r.timestamp))


@unittest.skipUnless(os.path.exists(BIN) and os.path.exists(DB),
                     "traces .bin e trace-db nao estao no repositorio")
class RealTraceAnchorTests(unittest.TestCase):
    """Nos traces reais o TOW do GPS vence -- e o +CCLK confirma o resultado.

    Sao duas leituras independentes do mesmo relogio: o TOW sai do subframe de
    navegacao, o +CCLK sai do que a aplicacao escreveu no modem depois do fix.
    Concordarem e o que da confianca nas duas.
    """

    def test_the_reference_trace_anchors_on_gnss(self):
        self.assertEqual(nrf_trace.convert(BIN, DB).anchor.kind, "gnss")

    def test_gnss_and_cclk_agree_to_well_under_a_second(self):
        log = nrf_trace.convert(BIN, DB)
        cclk = next(r for r in log.records if "CCLK=" in r.text)
        self.assertLess(abs(cclk.timestamp - CCLK_UTC), timedelta(seconds=0.5))

    def test_a_trace_without_cclk_still_anchors_on_gnss(self):
        # 20260902 nao tem +CCLK; antes caia na epoca do cabecalho e errava minutos
        self.assertEqual(nrf_trace.convert(BIN2, DB).anchor.kind, "gnss")

    def test_the_gnss_anchor_lands_inside_the_capture_window(self):
        log = nrf_trace.convert(BIN2, DB)
        epoch = nrf_trace._UNIX_EPOCH + timedelta(
            microseconds=nrf_trace.read_epoch_us(BIN2))
        mtime = datetime.fromtimestamp(os.path.getmtime(BIN2), timezone.utc)
        self.assertGreater(log.records[0].timestamp, epoch)
        self.assertLess(log.records[-1].timestamp, mtime + timedelta(minutes=1))


class WriteTxtTests(unittest.TestCase):
    def test_writes_date_time_label_and_text_per_record(self):
        rec = nrf_trace.TraceRecord(timestamp=EPOCH, label="L23_AT_STRING",
                                    text="=> AT+CFUN?")
        path = os.path.join(tempfile.mkdtemp(), "saida.txt")
        nrf_trace.write_txt([rec], path)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertEqual(
            content, "2026-09-06 02:15:33.791348 L23_AT_STRING => AT+CFUN?\n")



MT = datetime(2026, 9, 6, 2, 30, 0, tzinfo=timezone.utc)   # mtime remoto plausivel


class GnssTowAnchorTests(unittest.TestCase):
    """O receptor GNSS loga o TOW do GPS: hora absoluta dentro do proprio trace.

    Cada canal reporta o TOW do ultimo subframe que decodificou, e um subframe
    GPS dura 6 s, entao os valores ficam espalhados ate 6 s para tras. O menos
    atrasado -- o maximo de (TOW - hora do registro) -- e a referencia.
    """

    # 2026-09-06 e domingo, inicio da semana GPS. 02:16:00 UTC -> TOW 8178.
    TOW = 8178
    REAL = datetime(2026, 9, 6, 2, 16, 0, tzinfo=timezone.utc)

    def mlog(self, tow):
        campos = ["559245569280", "1300", "3", "1", "1", "185598395", "412",
                  str(tow), "21", "430", "31763", "0", "0", "92774"]
        return "GNSS_GPS_MLOG_T " + " ".join(campos)

    def texto(self, tows):
        """Um registro por segundo; o TOW acompanha, menos o atraso de cada canal."""
        return "".join(f"02:00:{i:02d}.000000 {self.mlog(t)}\n"
                       for i, t in enumerate(tows))

    def frescos(self, n=nrf_trace.GNSS_MIN_SAMPLES):
        return [self.TOW + i for i in range(n)]

    def test_the_gnss_tow_anchors_the_trace(self):
        log = nrf_trace.parse_text(self.texto(self.frescos()), EPOCH_US)
        self.assertEqual(log.anchor.kind, "gnss")
        self.assertTrue(log.anchor.trustworthy)
        self.assertEqual(log.records[0].timestamp, self.REAL)

    def test_stale_channels_do_not_drag_the_anchor(self):
        tows = [t - 5 for t in self.frescos()] + [self.TOW + nrf_trace.GNSS_MIN_SAMPLES]
        log = nrf_trace.parse_text(self.texto(tows), EPOCH_US)
        self.assertEqual(log.anchor.kind, "gnss")
        self.assertEqual(log.records[0].timestamp, self.REAL)

    def test_channels_without_a_decoded_tow_are_ignored(self):
        log = nrf_trace.parse_text(self.texto([0] * 50), EPOCH_US, mtime_utc=MT)
        self.assertEqual(log.anchor.kind, "mtime")

    def test_too_few_samples_fall_back_instead_of_guessing(self):
        tows = self.frescos(nrf_trace.GNSS_MIN_SAMPLES - 1)
        log = nrf_trace.parse_text(self.texto(tows), EPOCH_US, mtime_utc=MT)
        self.assertEqual(log.anchor.kind, "mtime")

    def test_gnss_wins_over_cclk(self):
        texto = self.texto(self.frescos()) + f"02:00:30.000000 {GNSS}\n02:00:31.000000 {CCLK}\n"
        log = nrf_trace.parse_text(texto, EPOCH_US)
        self.assertEqual(log.anchor.kind, "gnss")

    def test_a_tow_that_lands_days_away_is_rejected(self):
        log = nrf_trace.parse_text(self.texto([500000] * 30), EPOCH_US, mtime_utc=MT)
        self.assertEqual(log.anchor.kind, "mtime")


class AnchorChainTests(unittest.TestCase):
    """CCLK > mtime do arquivo > epoca do cabecalho, nessa ordem, e sempre declarada.

    A epoca do cabecalho marca o inicio da captura, nao o primeiro registro: o
    modem pode ficar minutos dormindo antes de emitir a primeira linha. Ancorar
    nela deixou o trace da Kyocera de 08/09 adiantado em 333 s.
    """

    def txt(self, *linhas):
        return "".join(f"1{i}:00:00.000000 {l}\n" for i, l in enumerate(linhas))

    def txt_cclk(self):
        # o CCLK so vale como ancora dentro de _CCLK_WINDOW apos o fix de GNSS
        return f"10:00:00.000000 {GNSS}\n10:00:01.000000 {CCLK}\n"

    def test_cclk_wins_and_is_declared_as_such(self):
        log = nrf_trace.parse_text(self.txt_cclk(), EPOCH_US, mtime_utc=MT)
        self.assertEqual(log.anchor.kind, "cclk")
        self.assertEqual(log.records[1].timestamp, CCLK_UTC)

    def test_mtime_anchors_the_last_record_when_there_is_no_cclk(self):
        log = nrf_trace.parse_text(self.txt("A x", "B y"), EPOCH_US, mtime_utc=MT)
        self.assertEqual(log.anchor.kind, "mtime")
        self.assertEqual(log.records[-1].timestamp, MT + nrf_trace.CAPTURE_TAIL_LAG)

    def test_mtime_keeps_the_relative_deltas(self):
        log = nrf_trace.parse_text(self.txt("A x", "B y"), EPOCH_US, mtime_utc=MT)
        first, last = log.records[0], log.records[-1]
        self.assertEqual(last.timestamp - first.timestamp, timedelta(hours=1))

    def test_a_mtime_long_after_the_capture_is_rejected(self):
        # arquivo tocado localmente: o mtime nao e mais o fim da captura
        tarde = EPOCH + timedelta(hours=7)
        log = nrf_trace.parse_text(self.txt("A x"), EPOCH_US, mtime_utc=tarde)
        self.assertEqual(log.anchor.kind, "header")

    def test_a_mtime_before_the_capture_start_is_rejected(self):
        log = nrf_trace.parse_text(self.txt("A x"), EPOCH_US,
                                   mtime_utc=EPOCH - timedelta(minutes=1))
        self.assertEqual(log.anchor.kind, "header")

    def test_without_cclk_or_mtime_the_header_is_used_and_flagged(self):
        log = nrf_trace.parse_text(self.txt("A x"), EPOCH_US)
        self.assertEqual(log.anchor.kind, "header")
        self.assertFalse(log.anchor.trustworthy)
        self.assertEqual(log.records[0].timestamp, EPOCH)

    def test_cclk_and_mtime_are_trustworthy(self):
        for kind in ("cclk", "mtime"):
            with self.subTest(kind=kind):
                text = self.txt_cclk() if kind == "cclk" else self.txt("A x")
                log = nrf_trace.parse_text(text, EPOCH_US, mtime_utc=MT)
                self.assertTrue(log.anchor.trustworthy)


class ProvenanceHeaderTests(unittest.TestCase):
    def write(self, log):
        path = os.path.join(tempfile.mkdtemp(), "t.txt")
        nrf_trace.write_txt(log, path)
        return open(path, encoding="utf-8").read()

    def test_the_txt_declares_which_anchor_was_used(self):
        log = nrf_trace.parse_text("10:00:00.000000 A x\n", EPOCH_US, mtime_utc=MT)
        self.assertTrue(self.write(log).startswith("# anchor: mtime"))

    def test_an_untrustworthy_anchor_is_marked_in_the_txt(self):
        log = nrf_trace.parse_text("10:00:00.000000 A x\n", EPOCH_US)
        first = self.write(log).splitlines()[0]
        self.assertIn("header", first)
        self.assertIn(nrf_trace.UNTRUSTWORTHY, first)

    def test_records_still_follow_the_header_line(self):
        log = nrf_trace.parse_text("10:00:00.000000 A x\n", EPOCH_US, mtime_utc=MT)
        linhas = self.write(log).splitlines()
        self.assertEqual(len(linhas), 2)
        self.assertTrue(linhas[1].endswith("A x"))

    def test_a_bare_record_list_is_still_accepted(self):
        recs = [nrf_trace.TraceRecord(timestamp=EPOCH, label="A", text="x")]
        self.assertEqual(self.write(recs).splitlines(), ["2026-09-06 02:15:33.791348 A x"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
